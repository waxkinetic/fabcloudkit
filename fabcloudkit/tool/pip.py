from __future__ import absolute_import

# standard
pass

# pypi
from fabric.decorators import task
from fabric.operations import run, sudo

# package
from fabcloudkit.internal import *


@task
def tool_check():
    start_msg('----- Checking for "pip" installation:')
    result = run('which pip')
    if result.return_code != 0:
        failed_msg('"pip" is not installed.')
        return False

    succeed_msg('"pip" is installed ({0}).'.format(result))
    return True

@task
def tool_install():
    start_msg('----- Attempting to download and install using "easy_install"...')
    try:
        import setuptools
    except ImportError:
        HaltError('setuptools is not installed. You may need to upgrade your python installation.')

    result = run('which easy_install')
    if result.return_code != 0:
        raise HaltError('"easy_install" not available; failed to install "pip".')

    result = sudo('easy_install pip')
    if result.return_code != 0:
        raise HaltError('Failed to install "pip".')
    succeed_msg('Successfully installed "pip".')

@task
def tool_verify():
    if not tool_check():
        tool_install()
