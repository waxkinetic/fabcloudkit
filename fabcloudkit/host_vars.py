"""
    fabcloudkit

    :copyright: (c) 2013 by Rick Bohrer.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import


# pypi
from fabric.api import env
from fabric.operations import run


__all__ = ['has_yum', 'get_value', 'set_value']


# internal dictionary; caches host-specific information.
# top-level key is env.host_string, top-level value is a dict of host settings.
_hosts = dict()


def has_yum():
    return _has_exe('has_yum', 'yum')

def get_value(key, default=None):
    return _get_host().get(key, default)

def set_value(key, value):
    host = _get_host()
    host[key] = value


def _has_exe(key_name, exe_name):
    host = _get_host()
    is_exe = host.get(key_name, None)
    if is_exe is None:
        result = run('which {0}'.format(exe_name), quiet=True)
        is_exe = result.succeeded
        host[key_name] = is_exe
    return is_exe

def _get_host():
    host = _hosts.get(env.host_string, None)
    if not host:
        host = dict()
        _hosts[env.host_string] = host
    return host
