"""
    fabcloudkit

    :copyright: (c) 2013 by Rick Bohrer.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import

# package
from .toolbase import Tool
from .util import *


class Builder(object):
    def __init__(self, role):
        self._role = role

    def execute(self):
        spec = self._role.get('build', None)
        if not spec:
            succeed_msg('Nothing to build.')
            return None

        for tool_def in spec:
            Tool.execute(tool_def.keys()[0], tool_def.values()[0])

        return self._role.env.get('build_result', None)
