from __future__ import absolute_import

# pypi
from fabric.operations import reboot, run, sudo

# package
from fabcloudkit import cfg
from fabcloudkit.host_vars import has_yum
from fabcloudkit.internal import *


class Tool(object):
    # every tool (except a SimpleTool) registers itself here.
    # key is the tool name, value is the tool class.
    __tools__ = dict()

    @classmethod
    def create(cls, name):
        """Creates a Tool-derived class based on the tool name.

        :param name: the name of the tool to create.
        :return: the Tool-derived object.
        """
        # look first for a registered tool, fallback to a simple tool.
        tool_cls = cls.__tools__.get(name, None)
        return tool_cls() if tool_cls else SimpleTool.create(name)

    @classmethod
    def execute(cls, tool_name, dct):
        """Executes a standard/compliant tool definition.

        A standard tool-definition is a dict that contains two entries: 'command' and optionally
        'options'. The former specifies the name of the command to execute, the latter specifies
        named arguments.

        :param tool_name: the name of the tool to execute.
        :param dct: the standard/compliant tool definition.
        :return: the result of calling the named command on the tool.
        """
        if dct is None:
            dct = {}
        tool = cls.create(tool_name)
        cmd_name = dct.get('command', 'install')
        dc = dct.copy()
        del dc['command']
        return tool.command(cmd_name, **dc)

    def check(self, **kwargs):
        # tools should override.
        return False

    def install(self, **kwargs):
        # tools should override.
        raise NotImplementedError()

    def command(self, _cmd_name_, **kwargs):
        cmd = getattr(self, _cmd_name_, None)
        if cmd is None or not callable(cmd):
            raise ValueError('Tool {0} has no command "{1}"'.format(self.__class__.__name__, _cmd_name_))
        return cmd(**kwargs)

    def verify(self, **kwargs):
        if not self.check(**kwargs):
            self.install(**kwargs)

    def _tool_list(self, lst):
        for tool_def in lst:
            # yield name and spec.
            yield(tool_def.keys()[0], tool_def.values()[0])


class SimpleTool(Tool):
    @classmethod
    def create(cls, name):
        info = cfg().tool_info(name)
        if not info:
            raise HaltError('There is no tool-definition for "{0}"'.format(name))
        return SimpleTool(name, info)

    def __init__(self, name, info):
        self.name = name
        self.info = info

    def check(self, **kwargs):
        start_msg('----- Checking for tool "{0}":'.format(self.name))

        # if there's no "check" command, act as though the tool isn't present.
        cmd = self.info.get('check', None)
        if not cmd:
            message('No check command for tool "{0}"; assuming not installed'.format(self.name))
            return False

        # otherwise run the check command.
        result = run(cmd, warn_only=True)
        if result.failed:
            failed_msg('Tool "{0}" is not installed.'.format(self.name))
            return False

        succeed_msg('Tool "{0}" is installed.'.format(self.name))
        return result.succeeded

    def install(self, **kwargs):
        start_msg('----- Running installation for: "{0}":'.format(self.name))
        cmd = self.info['yum'] if has_yum() else self.info['apt']
        result = sudo(cmd, warn_only=True)
        if result.failed:
            raise HaltError('Failed to install: "{0}".'.format(self.name))
        succeed_msg('Installed "{0}" successfully.'.format(self.name))


class RebootTool(Tool):
    def install(self, **kwargs):
        start_msg('----- Rebooting instance (may take a few minutes):')
        reboot()
        succeed_msg('Rebooted successfully.')
        return self


class ToolsTool(Tool):
    def install(self, options):
        for name in options:
            tool = Tool.create(name)
            tool.verify()
        return self


# register.
Tool.__tools__['reboot'] = RebootTool
Tool.__tools__['tools'] = ToolsTool
