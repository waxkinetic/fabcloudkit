"""
    fabcloudkit

    :copyright: (c) 2013 by Rick Bohrer.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import

# standard
pass

# pypi
from fabric.operations import reboot, run, sudo

# package
from fabcloudkit import cfg
from fabcloudkit.host_vars import has_yum
from fabcloudkit.internal import *


def update_packages(reboot_after=True):
    # convenience method.
    install_internal('__update_packages__')
    if reboot_after:
        install('reboot')

def check(name):
    # if this tool has a special handler, delegate.
    # note: the special handler may call check_internal().
    handled, result = _handle_special(name, True)
    if handled:
        return result
    return check_internal(name)

def install(name):
    # if this tool has a special handler, delegate.
    # note: the special handler may call install_internal().
    handled, result = _handle_special(name, False)
    if handled:
        return result
    return install_internal(name)

def verify(name):
    if not check(name):
        install(name)

def check_internal(name):
    start_msg('----- Checking for tool "{0}":'.format(name))

    # if info for this tool isn't available, act as though the tool isn't present.
    info = cfg().tool_info(name)
    if not info:
        message('No information available for tool "{0}"'.format(name))
        return False

    # if there's no "check" command, act as though the tool isn't present.
    cmd = info.get('check', None)
    if not cmd:
        message('No check command for tool "{0}"; assuming not installed'.format(name))
        return False

    # otherwise run the check command.
    result = run(cmd, warn_only=True)
    if result.failed:
        failed_msg('Tool "{0}" is not installed.'.format(name))
        return False

    succeed_msg('Tool "{0}" is installed.'.format(name))
    return result.succeeded

def install_internal(name):
    start_msg('----- Running installation for: "{0}":'.format(name))

    info = cfg().tool_info(name)
    if not info:
        raise HaltError('No tool information available for: "{0}"'.format(name))

    cmd = info['yum'] if has_yum() else info['apt']
    result = sudo(cmd, warn_only=True)
    if result.failed:
        raise HaltError('Failed to install: "{0}".'.format(name))
    succeed_msg('Installed "{0}" successfully.'.format(name))

# -------------------- private implementation --------------------

_special_map = {
    'pip':         'fabcloudkit.tool.pip',
    'virtualenv':  'fabcloudkit.tool.virtualenv',
    'supervisord': 'fabcloudkit.tool.supervisord',
    'nginx':       'fabcloudkit.tool.nginx'
}

def _handle_special(name, check=True):
    from importlib import import_module

    module_name = _special_map.get(name, None)
    if module_name:
        mod = import_module(module_name)
        return (True, mod.tool_check() if check else mod.tool_install())

    if name == 'reboot':
        if check:
            return (True, False)
        else:
            start_msg('----- Rebooting instance (may take a few minutes):')
            reboot()
            succeed_msg('Rebooted successfully.')
            return (True, None)

    return (False, None)
