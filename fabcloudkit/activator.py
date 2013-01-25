from __future__ import absolute_import

# standard
import posixpath as path

# pypi
from fabric.api import env
from fabric.context_managers import prefix

# package
from fabcloudkit import ctx
from tool import nginx, supervisord, virtualenv
from .build import BuildInfo
from .internal import *
from .util import *


def unused_port():
    """
    Finds an unused port on the remote host. Note that the returned port could be taken by another
    process before it's used.

    :return: an unused port number.
    """
    _UNUSED_PORT_CMD = """
cat <<-EOF | python -
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('localhost', 0))
addr, port = s.getsockname()
s.close()
print(port)
EOF
""".lstrip()

    result = run(_UNUSED_PORT_CMD, quiet=True)
    if result.failed:
        raise HaltError('Failed to find unused port.')

    port = int(result)
    white_msg('Found unused port={0}'.format(port), bold=True)
    return port

def cpu_count():
    # note: requires python 2.6+.
    _CPU_CMD = """
cat <<-EOF | python -
import multiprocessing as mp
print(mp.cpu_count())
EOF
""".lstrip()

    result = run(_CPU_CMD, quiet=True)
    if result.failed:
        raise HaltError('Failed to retrieve CPU count.')

    count = int(result)
    white_msg('Found CPU count={0}'.format(count), bold=True)
    return count

def site_packages_dir(virtualenv_dir):
    _DIR_CMD = """
cat <<-EOF | python -
import os, sys
v=sys.version_info
print(os.path.join(sys.prefix, 'lib', 'python{0}.{1}'.format(v.major, v.minor), 'site-packages'))
EOF
""".lstrip()

    with prefix(virtualenv.activate_prefix(virtualenv_dir)):
        result = run(_DIR_CMD, quiet=True)
        if result.failed:
            raise HaltError('Failed to retrieve Python "site-packages" location.')
        white_msg('Python site-packages dir: "{0}"'.format(result))
        return result


class Activator(object):
    def __init__(self, role):
        self._role = role

    def execute(self, force=False):
        spec = self._role.get('activate', None)
        if not spec:
            return None, None

        start_msg('Begin activation for instance in role: "{0}":'.format(self._role.name))
        info = BuildInfo().load()
        if not force and info.last == info.active and info.active is not None:
            succeed_msg('The last know good build is already active.')
            return None, None

        # the old build is what's currently active; last good build is being activated.
        old_build_name = info.active
        new_build_name = info.last
        message('Last build: {0}; New build: {1}'.format(old_build_name, new_build_name))

        # start gunicorn and Nginx for the new build.
        port = self._start_gunicorn(spec, new_build_name)
        try:
            self._nginx_switch(spec.get('nginx', {}), old_build_name, new_build_name, port)
        except:
            supervisord.stop_and_remove(new_build_name)
            failed_msg('Activation failed for instance in role: "{0}"'.format(self._role.name))
            raise

        # delete the supervisor config for the old build, if any.
        if old_build_name:
            supervisord.stop_and_remove(old_build_name)

        # update the build information on this instance.
        info.active = new_build_name
        info.active_port = port
        info.save()

        succeed_msg('Successfully activated build: "{0}"'.format(new_build_name))
        return new_build_name, port

    def deactivate(self):
        info = BuildInfo().load()
        if not info.active:
            return

        start_msg('Deactivating instance in role: "{0}":'.format(self._role.name))
        try:
            nginx.delete_server_config(info.active)
            nginx.reload_config()
        except:
            failed_msg('Error stopping Nginx; ignoring.')
            pass

        try:
            supervisord.stop_and_remove(info.active)
        except:
            failed_msg('Error stopping supervisor; ignoring.')
            pass
        succeed_msg('Finished deactivating instance in role: "{0}".'.format(self._role.name))

    def _build_gunicorn_cmd(self, spec, build_name):
        cmd = spec.get('script', 'gunicorn')
        app = spec.app_module
        cmd_path = path.join(ctx().build_path(build_name), 'bin')

        # allow overrides of some gunicorn options.
        port = unused_port()
        dct = dict(spec.get('options', {}))
        dct['bind'] = self._gunicorn_bind(port)

        if 'workers' not in dct:
            dct['workers'] = (2 * cpu_count()) + 1
        if 'name' not in dct:
            dct['name'] = build_name

        debug = dct.pop('debug', False)
        options = ' '.join(['--{0} {1}'.format(k,v) for k,v in dct.iteritems()])
        if debug:
            options += ' --debug'
        return '{cmd_path}/{cmd} {options} {app}'.format(**locals()), port

    def _gunicorn_bind(self, port):
        return '127.0.0.1:{0}'.format(port)

    def _log_root(self, build_name):
        return path.join(ctx().build_path(build_name), 'logs')

    def _start_gunicorn(self, spec, build_name):
        # create the command and write a new supervisor config for this build.
        # (this creates a [program:<build_name>] config section for supervisor).
        cmd, port = self._build_gunicorn_cmd(spec.get('gunicorn', {}), build_name)
        log_root = self._log_root(build_name)
        supervisord.write_program_config(build_name, cmd, ctx().builds_root(), log_root)

        # start it and wait until supervisor thinks its up and running, then test the
        # service by sending it the specified HTTP request.
        supervisord.start(build_name)
        if not supervisord.wait_until_running(build_name) or not self._http_test(spec, port):
            # cleanup and fail.
            supervisord.stop_and_remove(build_name)
            raise HaltError('Failed to start local server at: "{0}"'.format(self._gunicorn_bind(port)))

        message('Successfully started local server.')
        return port

    def _http_test(self, spec, port):
        http_path = spec.get('http_test_path', None)
        if not http_path:
            return True

        if http_path.startswith('/'):
            http_path = http_path[1:]

        url = 'http://{0}/{1}'.format(self._gunicorn_bind(port), http_path)
        start_msg('Local test URL: {url}'.format(**locals()))

        result = run('curl -I {url}'.format(**locals()))
        if result.failed:
            failed_msg('"{url}" failed: (result)'.format(**locals()))
            return False

        first_line = result.split('\r\n')[0]
        status = int(first_line.split()[1])
        if not (200 <= status < 500):
            failed_msg('"{url}" failed with status: "{status}"'.format(**locals()))

        succeed_msg('"{url}" succeeded with status: "{status}"'.format(**locals()))
        return True

    def _get_nginx_static(self, spec, build_name):
        static_spec = spec.get('static', None)
        if not static_spec:
            return ''

        dir = site_packages_dir(ctx().build_path(build_name))
        static = ''.join([
        "location {0} {{\n"
        "    alias {1};\n"
        "}}\n".format(d['url'], path.join(dir, d['local'])) for d in static_spec
        ])
        return static

    def _nginx_switch(self, spec, old_build_name, new_build_name, new_port):
        # write Nginx config for the new build.
        nginx.write_server_config(
            name=new_build_name,
            server_names=spec.get('server_names', env.host_string),
            proxy_pass='http://{0}'.format(self._gunicorn_bind(new_port)),
            static_locations=self._get_nginx_static(spec, new_build_name),
            log_root=self._log_root(new_build_name),
            listen=spec.get('listen', 80))

        # delete Nginx config for the old build if it exists.
        if old_build_name:
            nginx.delete_server_config(old_build_name)

        # reload configuration.
        nginx.reload_config()
