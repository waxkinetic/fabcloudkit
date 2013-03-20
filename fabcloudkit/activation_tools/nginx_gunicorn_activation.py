from __future__ import absolute_import

# standard
import posixpath as path
import re

# pypi
from fabric.state import env

# package
from ..build import BuildInfo
from fabcloudkit import ctx
from ..remote_util import site_packages_dir
from ..tool.gunicorn import GUnicornTool
from ..tool.nginx import NginxTool
from ..toolbase import Tool
from ..util import *


class NginxGUnicornActivationTool(Tool):
    def __init__(self):
        super(NginxGUnicornActivationTool,self).__init__()
        self._nginx = NginxTool()
        self._gunicorn = GUnicornTool()

    def activate(self, name, gunicorn, nginx, force=False):
        """Starts a new Nginx server backed by the new gunicorn.

        Starts a new gunicorn server with the last good build, verifies that it's running,
        the starts an Nginx server backed by the gunicorn server. If this all succeeds,
        any previously running gunicorn and Nginx servers are stopped.

        :param name:
            name of what's being activated. allows distinction between multiple
            services being activated on the same instance.

        :param gunicorn:
            see GUnicornTool::start() for details.

        :param nginx:
            required; nginx configuration options dict. may contain the keys:

            'server_names':
                optional; interface on which Nginx listens.
                default: "", causing Nginx to listen on all interfaces.

            'listen':
                optional; port where Nginx listens.
                default: 80

            'static':
                optional; list of dicts, each containing the keys:
                'url':
                    identifies the URL path of the static resource

                'local':
                    identifies the corresponding physical path of the static resource.
                    note: path is relative to the build location implied by new_build_name.

        :param force:
            optional; True to force activation even if the last good build is already active.
        """
        start_msg('Begin activation for instance in role: "{0}":'.format(env.role_name))

        info = _BuildInfoHelper(self._get_name(name))
        if not info.needs_activation(force):
            succeed_msg('The last known good build is already active.')
            env.role.set_env(activation_result=(None, None))
            return

        # start gunicorn and Nginx for the new build.
        message('Last build: {0}; New build: {1}'.format(info.old_build_name, info.new_build_name))
        gunc_port, gunc_host = self._gunicorn.start(
            gunicorn, info.new_build_name, info.new_prog_name)
        try:
            self._nginx_switch(
                nginx, info.old_prog_name,
                info.new_build_name, info.new_prog_name, gunc_host)
        except:
            self._gunicorn.stop(info.new_prog_name)
            failed_msg('Activation failed for instance in role: "{0}"'.format(env.role_name))
            raise

        # delete the supervisor config for the old build, if any.
        if info.old_build_name:
            self._gunicorn.stop(info.old_prog_name)

        # update the build information on this instance.
        info.update_active(info.new_build_name, gunc_port)
        succeed_msg('Successfully activated build: "{0}"'.format(info.new_build_name))
        env.role.set_env(activation_result=(info.new_build_name, gunc_port))
        return self

    def deactivate(self, name):
        name = self._get_name(name)
        info = BuildInfo().load()
        active = info.active(name)
        if not active.build:
            return

        start_msg('Deactivating instance in role: "{0}":'.format(env.role_name))
        prog_name = info.full_name(active.build, active.name)
        try:
            self._nginx.delete_config(prog_name)
            self._nginx.reload()
        except:
            failed_msg('Error stopping Nginx; ignoring.')
            pass

        try:
            self._gunicorn.stop(prog_name)
        except:
            failed_msg('Error stopping gunicorn server; ignoring.')
            pass

        active.build = None
        info.save()
        succeed_msg('Finished deactivating instance in role: "{0}".'.format(env.role_name))
        return self

    def _get_name(self, name):
        if not name or _NAME_REGEX.search(name):
            raise HaltError('name not specified or invalid (only numbers, letters, underscore, dash)')
        return name

    def _get_nginx_static(self, options, build_name):
        static_spec = options.get('static', None)
        if not static_spec:
            return ''

        dir = site_packages_dir(ctx().build_path(build_name))
        static = ''.join([
        "location {0} {{\n"
        "    alias {1};\n"
        "}}\n".format(d['url'], path.join(dir, d['local'])) for d in static_spec
        ])
        return static

    def _log_root(self, build_name):
        return path.join(ctx().build_path(build_name), 'logs')

    def _nginx_switch(self, options, old_prog_name, new_build_name, new_prog_name, gunc_host):
        """Starts a new Nginx server backed by the new gunicorn.

        :param options:
            see activate() documentation for details.

        :param old_prog_name:
            required; the old 'program' name from the previous build.

        :param new_build_name:
            required; the new 'build' name. used as the root directory for serving
            static files.

        :param new_prog_name:
            required; the new 'program' name for the current build. used for naming the
            nginx configuration fie for this program, so must be different than old_prog_name.

        :param gunc_host:
            required; the gunicorn host:port, usually 127.0.0.1:<port>.
        """
        # write Nginx config for the new build.
        self._nginx.write_config(
            name=new_prog_name,
            server_names=options.get('server_names', '\"\"'),
            proxy_pass='http://{0}'.format(gunc_host),
            static_locations=self._get_nginx_static(options, new_build_name),
            log_root=self._log_root(new_prog_name),
            listen=options.get('listen', 80))

        # delete Nginx config for the old program if it exists.
        if old_prog_name:
            self._nginx.delete_config(old_prog_name)

        # reload configuration.
        self._nginx.reload()


# register.
Tool.__tools__['nginx_gunicorn'] = NginxGUnicornActivationTool

# private.
_NAME_REGEX = r = re.compile('[^0-9a-zA-Z_-]+')

class _BuildInfoHelper(object):
    def __init__(self, name):
        info = BuildInfo().load()
        active = info.active(name)

        # the old build is what's currently active; last good build is being activated.
        self.old_build_name = active.build
        self.old_prog_name = info.full_name(active.build, active.name)

        self.new_build_name = info.last
        self.new_prog_name = info.full_name(info.last, active.name)
        self.build_info = info
        self.active = active

    def needs_activation(self, force):
        return force\
            or self.build_info.last != self.active.build\
            or self.active.build is None

    def update_active(self, build_name, port):
        self.active.build = build_name
        self.active.port = port
        self.build_info.save()
