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


class PipCommandTool(Tool):
    def check(self, **kwargs):
        # we always want to execute.
        return True

    def install(self, **kwargs):
        start_msg('----- Verifying that "pip" is installed...')
        result = run('which pip')
        if result.return_code != 0:
            HaltError('"pip" is not installed; it must be installed before using pip_command.')
            return False

        cmd_text = kwargs.get('command', None)
        if not cmd_text:
            failed_msg('no pip command specified; skipping.')
        else:
            cmd_text = sudo('pip {0}'.format(cmd_text))
            message('executing pip command: "{0}".'.format(cmd_text))
            result = sudo(cmd_text)
            if result.return_code != 0:
                raise HaltError('pip command "{0}" failed.'.format(cmd_text))

        succeed_msg('Successfully executed pip command: "{0}".'.format(cmd_text))
        return self


# register.
Tool.__tools__['pip_command'] = PipCommandTool
