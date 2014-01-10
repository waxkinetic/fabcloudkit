"""
    fabcloudkit

    :copyright: (c) 2013 by Rick Bohrer.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import

# standard
pass

# pypi
from fabric.operations import run, sudo

# package
from ..internal import *
from ..toolbase import Tool


class PipTool(Tool):
    def check(self, **kwargs):
        start_msg('----- Checking for "pip" installation:')
        result = run('which pip')
        if result.return_code != 0:
            failed_msg('"pip" is not installed.')
            return False

        succeed_msg('"pip" is installed ({0}).'.format(result))
        return True

    def install(self, **kwargs):
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

        message('upgrading setuptools for pip/wheels support.')
        result = sudo('pip install -q --upgrade --no-use-wheel setuptools')
        if result.return_code != 0:
            raise HaltError('Failed to upgrade "setuptools" for pip/wheels support.')

        succeed_msg('Successfully installed "pip".')
        return self


# register.
Tool.__tools__['pip'] = PipTool
