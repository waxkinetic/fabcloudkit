"""
    fabcloudkit

    Functions for managing Redis: checking for existence, installation, configuration,
    and management. This implementation uses supervisord for monitoring and control
    of the redis-server process since Fabric doesn't work well with init scripts.

    /etc/init.d/redis-server:
        The "init script" that allows redis-server to be run at startup.

    /etc/redis/redis.conf:
        The Redis configuration file. This file is written by calling the
        config function.

    /usr/local/bin:
        Where Redis executables (e.g., redis-server, redis-cli) are installed.

    ~/redis-src:
        Temporary directory for downloaded Redis source code, and files generated
        during the build process. Deleted after build/install.

    Credit: thanks to the Redis docs and this article for code and instructions:
    http://www.codingsteps.com/install-redis-2-6-on-amazon-ec2-linux-ami-or-centos/

    :copyright: (c) 2013 by Rick Bohrer.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import

# standard
import time

# pypi
from fabric.context_managers import cd
from fabric.operations import run, sudo

# package
from ..util import put_string
from ..internal import *
from .supervisord import SupervisorTool
from ..toolbase import Tool


class RedisTool(Tool):
    def __init__(self):
        super(RedisTool,self).__init__()
        self._supervisor = SupervisorTool()

    def check(self, **kwargs):
        start_msg('----- Checking for "Redis" installation:')
        result = run('redis-server --version')
        if result.return_code != 0:
            failed_msg('"Redis" is not installed.')
            return False

        succeed_msg('"Redis" is installed ({0}).'.format(result))
        return True

    def install(self, **kwargs):
        start_msg('----- Attempting to download and install "Redis":')

        # base Redis version to install.
        base = 'redis-2.6.11'

        # the name of the file to download and unpack.
        file_name = '{base}.tar.gz'.format(**locals())

        # tmp/scratch directory to hold src and build.
        src_dir = _SRC_DIR

        result = run('rm -rf {src_dir}'.format(**locals()))
        if result.return_code != 0:
            raise HaltError('Failed to remove old directory ({0})'.format(result))

        result = run('mkdir {src_dir}'.format(**locals()))
        if result.return_code != 0:
            raise HaltError('Failed to make "{src_dir}" directory.'.format(**locals()))

        message('Downloading and unpacking "Redis":')
        with cd(src_dir):
            result = run('wget http://redis.googlecode.com/files/{file_name}'.format(**locals()))
            if result.return_code != 0:
                raise HaltError('Unable to download "Redis".')
            result = run('tar -xzf {file_name}'.format(**locals()))
            if result.return_code != 0:
                raise HaltError('Unable to unpack "Redis".')

        message('Building and installing "Redis":')
        with cd('{src_dir}/{base}'.format(**locals())):
            result = run('make')
            if result.return_code != 0:
                raise HaltError('Error occurred while building "Redis".')

        # note: can't use cd() context manager here along with sudo('make install');
        # fabric implementation details cause "~" to be expanded as root.
        result = run('cd {src_dir}/{base} && sudo make install'.format(**locals()))
        if result.return_code != 0:
            raise HaltError('Error occurred while installing "Redis".')

        # final verification.
        result = run('redis-server --version')
        if result.return_code != 0:
            raise HaltError('Appeared to install Redis successfully but its not there...?')

        # delete source and build files.
        run('rm -rf {src_dir}'.format(**locals()))
        succeed_msg('Successfully installed "Redis".')
        return self

    def config(self, options):
        # since we're using supervisord with redis, don't let redis daemonize. if it does
        # supervisor views it as a premature exit and misbehaves.
        options = options.copy()
        options['daemonize'] = 'no'

        self.shutdown()
        conf = '\n'.join(['{0} {1}'.format(k,v) for k,v in options.items()])
        message('Writing "redis.conf" file:-----\n{conf}\n-----'.format(**locals()))
        sudo('mkdir /etc/redis', quiet=True)
        put_string(conf, _CONF_FILE, use_sudo=True)
        return self.start()

    def is_running(self):
        # redis-server is running if the grep returns results.
        result = run('ps -A | grep redis-server', quiet=True)
        return result.return_code == 0

    def wait_for_shutdown(self, max_tries=5, wait=2):
        if max_tries == 0:
            failed_msg('redis-server did not shutdown.')
            return False

        message('Waiting for redis-server to quit.')
        if self.is_running():
            time.sleep(wait)
            return self.wait_for_shutdown(max_tries-1, wait*2)
        message('redis-server has shutdown.')
        return True

    def start(self):
        # we use supervisord for monitoring and boot-startup; fabric doesn't work well
        # with init scripts: http://docs.fabfile.org/en/1.4.2/faq.html#init-scripts-don-t-work
        self._supervisor.write_config(_SUPERVISOR_NAME,
            '/usr/local/bin/redis-server {0}'.format(_CONF_FILE), dir='/tmp', log_root='/tmp')
        self._supervisor.reload()
        self._supervisor.wait_until_running(_SUPERVISOR_NAME)
        return self

    def stop(self):
        self.shutdown()

    def shutdown(self):
        message('Telling redis-server to shutdown.')
        self._supervisor.stop_and_remove(_SUPERVISOR_NAME)

        # do this just to be sure; ignore return code in case redis isn't running.
        run('redis-cli shutdown', quiet=True)
        return self.wait_for_shutdown()


# register.
Tool.__tools__['redis'] = RedisTool


# private constants.
_SUPERVISOR_NAME = 'redis'
_CONF_FILE = '/etc/redis/redis.conf'
_SRC_DIR = '~/redis-src'
