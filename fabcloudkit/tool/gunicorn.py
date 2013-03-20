from __future__ import absolute_import

# standard
import posixpath as path


# package
from fabcloudkit import ctx
from ..remote_util import *
from .supervisord import SupervisorTool
from ..toolbase import Tool
from ..util import *


class GUnicornTool(Tool):
    def __init__(self):
        super(GUnicornTool,self).__init__()
        self._supervisor = SupervisorTool()

    def install(self, **kwargs):
        # gunicorn should be installed into the build virtualenv via setup.py
        # in the reference repo.
        raise HaltError('gunicorn should be installed via setup.py')

    def start(self, spec, build_name, prog_name):
        """Starts a gunicorn server running.

        Writes a supervisor configuration for the program, starts the program, and
        optionally verifies the service is running by making an HTTP request.

        :param spec:
            a dictionary containing the gunicorn specification. may contain the keys:

            'script':
                optional; the gunicorn command (e.g., 'gunicorn' or 'gunicorn_django')
                default: 'gunicorn'

            'options':
                optional; gunicorn "long-name" options. these are the same as the option names
                preceded with double-dash, i.e., use "name" and not "n". "bind" cannot be set
                because it's set automatically. "name" and "workers" have intelligent defaults,
                but can be overridden.

            'app_module':
                required; the python module:variable to run.

            'http_test_path':
                optional; if specified, a HTTP HEAD request is made to the gunicorn server
                using this path. if a 200, 300 or 400 response is received, the server is
                considered to be running, otherwise it is considered not running and an
                exception will be raised.

        :param build_name:
            name of the build directory/virtualenv containing gunicorn.

        :param prog_name:
            name of the gunicorn program.

        :return:
            the port number on which the server is running.
        """
        # create the command and write a new supervisor config for this build.
        # (this creates a [program:<prog_name>] config section for supervisor).
        cmd, port = self._get_cmd(spec, build_name, prog_name)
        log_root = path.join(ctx().build_path(build_name), 'logs')
        self._supervisor.write_config(prog_name, cmd, ctx().builds_root(), log_root)

        # start it and wait until supervisor thinks its up and running, then test the
        # service by sending it the specified HTTP request.
        self._supervisor.start(prog_name)
        http_path = spec.get('http_test_path', None)
        if not (self._supervisor.wait_until_running(prog_name) and self._http_test(http_path, port)):
            # cleanup and fail.
            self._supervisor.stop_and_remove(prog_name)
            raise HaltError('Failed to start local server at: "{0}"'.format(self._get_bind(port)))

        message('Successfully started local server.')
        return port, self._get_bind(port)

    def stop(self, prog_name):
        self._supervisor.stop_and_remove(prog_name)
        return self

    def _get_cmd(self, spec, build_name, prog_name):
        """Builds the gunicorn command.

        See documentation of start() for parameter descriptions.

        :return:
            the gunicorn command as a string.
        """
        cmd = spec.get('script', 'gunicorn')
        app = spec.get('app_module', None)
        cmd_path = path.join(ctx().build_path(build_name), 'bin')

        # allow overrides of some gunicorn options.
        port = unused_port()
        options = dict(spec.get('options', {}))
        options['bind'] = self._get_bind(port)

        if 'workers' not in options:
            options['workers'] = (2 * cpu_count()) + 1
        if 'name' not in options:
            options['name'] = prog_name

        debug = options.pop('debug', False)
        options = ' '.join(['--{0} {1}'.format(k,v) for k,v in options.iteritems()])
        if debug:
            options += ' --debug'
        return '{cmd_path}/{cmd} {options} {app}'.format(**locals()), port

    def _get_bind(self, port):
        return '127.0.0.1:{port}'.format(**locals())

    def _http_test(self, http_path, port):
        if not http_path:
            return True

        if http_path.startswith('/'):
            http_path = http_path[1:]
        url = 'http://{0}/{1}'.format(self._get_bind(port), http_path)
        return http_test(url)


# register
Tool.__tools__['gunicorn'] = GUnicornTool
