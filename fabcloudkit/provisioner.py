"""
    fabcloudkit

    :copyright: (c) 2013 by Rick Bohrer.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import

# pypi
from fabric.operations import sudo

# package
from fabcloudkit import ctx
from .internal import *
from .toolbase import *


class Provisioner(object):
    def __init__(self, role):
        self._role = role

    def execute(self):
        start_msg('Provisioning instance in role "{0}":'.format(self._role.name))
        spec = self._role.get('provision', None)
        if not spec:
            succeed_msg('Nothing to provision.')
            return

        self._create_dirs()
        for tool_def in spec:
            Tool.execute(tool_def.keys()[0], tool_def.values()[0])
        succeed_msg('Provisioning completed successfully for role "{0}".'.format(self._role.name))

    def _create_dirs(self):
        # repos directory.
        result = sudo('mkdir -p -m 0777 {0}'.format(ctx().repos_root()))
        if result.failed:
            HaltError('Unable to create root directory for repo storage.')

        # builds directory.
        result = sudo('mkdir -p -m 0777 {0}'.format(ctx().builds_root()))
        if result.failed:
            HaltError('Unable to create root directory for builds.')
