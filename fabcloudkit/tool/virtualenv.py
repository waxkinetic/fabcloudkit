from __future__ import absolute_import

# standard
import posixpath as path

# pypi
from fabric.decorators import task
from fabric.operations import run, sudo

# package
from fabcloudkit.internal import *


@task
def tool_check():
    start_msg('----- Checking for "virtualenv" installation:')
    result = run('which virtualenv')
    if result.return_code != 0:
        failed_msg('"virtualenv" is not installed.')
        return False

    succeed_msg('"virtualenv" is installed ({0}).'.format(result))
    return True

@task
def tool_install():
    start_msg('----- Install "virtualenv" via "pip".')
    result = sudo('pip install -q virtualenv')
    if result.return_code != 0:
        HaltError('Failed to install "virtualenv".')

    result = run('which virtualenv')
    if result.return_code != 0:
        raise HaltError('Confusion: just installed "virtualenv" but its not there.')
    succeed_msg('"virtualenv" is installed ({0}).'.format(result))

@task
def tool_verify():
    if not tool_check():
        tool_install()

@task
def ensure(dir_name, interpreter=None, force_create=False):
    """
    Creates a new virtualenv using the specified directory name. The parameter dir_name can be either a
    relative or absolute path. If a relative path, the virtualenv is created relative to the current
    directory of fab, not necessarily the direction from which fab was run.

    Note: if the virtualenv exists with (say) python version 2.6, and you want an env with 2.7, this
    function will erroneously return True (unless force_create=True).

    :param dir_name: name of the virtualenv direction.
    :param interpreter: name of the python interpreter to use for the virtualenv (e.g., 'python2.7').
                        if not specified uses the python that virtualenv was installed with.
    :param force_create: if True, the virtualenv is always created. if False, the virtualenv is created
                         if the directory doesn't already exist and doesn't contain the "activate" script.
    :return: None
    """
    if force_create:
        # no tests necessary; just do it.
        create = True
    else:
        start_msg('----- Testing for virtualenv directory "{0}":'.format(dir_name))
        result = run('test -d {0}'.format(dir_name))
        if result.return_code != 0:
            message('Directory does not exist.')
            create = True
        else:
            message('Directory "{0}" exists; testing for scripts.'.format(dir_name))
            script_dir = path.join(dir_name, 'bin/activate')
            result = run('test -f {0}'.format(script_dir))
            if result.return_code == 0:
                message('virtualenv appears to exist in directory "{0}"'.format(dir_name))
                create = False
            else:
                message('Scripts not found; no virtualenv exists.')
                create = True

    if create:
        message('Creating virtualenv...')
        interpreter_arg = '' if not interpreter else ('-p ' + interpreter)
        result = run('virtualenv {0} {1}'.format(interpreter_arg, dir_name))
        if result.return_code != 0:
            raise HaltError('Failed to create virtualenv "{0}"'.format(dir_name))
        succeed_msg('Created virtualenv in directory "{0}"'.format(dir_name))
        if interpreter:
            succeed_msg('Used python interpreter: "{0}"'.format(interpreter))

def activate_prefix(dir):
    return 'source {0}'.format(path.join(dir, 'bin/activate'))
