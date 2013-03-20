"""
    fabcloudkit

    :copyright: (c) 2013 by Rick Bohrer.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import

# pypi
from fabric.context_managers import cd, prefix, settings
from fabric.operations import run, sudo
from fabric.state import env

# package
from fabcloudkit import ctx
from ..build import build_repo, BuildInfo
from ..internal import *
from ..toolbase import Tool
from ..tool.virtualenv import VirtualEnvTool
from ..util import copy_file_from


class PythonBuildTool(Tool):
    def build(self, repos, reference_repo=None, post_build=None, interpreter=None, tarball=False, unittest=None):
        """Performs a 'python' build.

        Performs a python build by running setup.py in each identified repo. If desired, repos can
        be refreshed first (e.g., via git pull).

        :param repos:
            specifies the list of repos in which to run setup.py.

        :param reference_repo:
            optional; the reference repo from which to retrieve the head commit id.
            this id used as a component of the build name. if not specified, the
            first repo in the context is used.

        :param post_build:
            a list of post-build commands. a list of dictionaries. each dict must
            contain the key "command" that specifies the command to execute. optionally,
            it may include a "sudo" value of [True|False], and an "ignore_fail" value
            of [True|False].

        :param interpreter:
            specifies the Python interpreter to use in the build's virtualenv. if
            not specified, the operating system default interpreter is used. note
            that the interpreter must already exist on the system.

        :param tarball:
            True to create a tarball of the build; this is required if any other
            instance will use "copy_from".

        :param unittest:
            TBD

        :return:
            the new build name
        """
        start_msg('Executing build for instance in role "{0}":'.format(env.role_name))

        # increment the build name and create a new virtualenv for the build.
        build_name = self._increment_name(reference_repo)
        build_env_dir = ctx().build_path(build_name)
        VirtualEnvTool().ensure(build_env_dir, interpreter)

        # run "setup.py install" in each repo.
        for repo_name in ([repos] if isinstance(repos, basestring) else repos):
            build_repo(build_env_dir, ctx().get_repo(repo_name))

        # run tests.
        self._unittest(unittest, build_name)

        # save the last known good build-name.
        BuildInfo.set_last_good(build_name)
        if tarball:
            self._tarball(build_name)

        # execute any post-build commands.
        if post_build:
            self._execute_post_build(post_build, build_name)

        # make the build_name available to the caller; it'll be set as an instance-tag.
        succeed_msg('Build completed successfully for role "{0}".'.format(env.role_name))
        env.role.set_env(build_result=build_name)
        return self

    def copy_from(self, role_name, post_build=None, delete_tar=True):
        """Copies an existing build from an instance in the specified role.

        Instead of building itself, a build is copied from another instance to the current
        instance.

        :param role_name: the role of the instance to copy the build tarball from.
        :param post_build: list of post-build commands to execute.
        :param delete_tar: True to delete the tarball, False otherwise.
        :return: the name of the copied build.
        """
        # get the last known good build from the source machine.
        # note: we could alternatively get this from an instance tag.
        message('Copying build from instance in role: "{0}"'.format(role_name))
        inst, role = ctx().get_host_in_role(role_name)
        with settings(host_string=inst.public_dns_name, user=role.user):
            message('Getting last good build-name from: "{0}"'.format(role_name))
            src_build_name = BuildInfo().get_last_good()

        # copy it from the source machine. note that all machines must have been provisioned
        # properly to allow the current machine access to the source machine.
        tarball = self._tarball_name(src_build_name)
        path = ctx().build_path(tarball)
        copy_file_from(role.user, inst.private_dns_name, path, path)

        with cd(ctx().builds_root()):
            # untar it.
            command = 'tar -x --file={tarball}'.format(**locals())
            result = run(command)
            if result.failed:
                raise HaltError('Failed to untar: "{0}"'.format(path))

            # delete the tar.
            if delete_tar:
                run('rm {tarball}'.format(**locals()))

        # update the build information.
        BuildInfo().set_last_good(src_build_name)

        # execute any post-build commands.
        if post_build:
            self._execute_post_build(post_build, src_build_name)

        succeed_msg('Successfully copied build: "{0}"'.format(src_build_name))
        return src_build_name

    def _execute_post_build(self, cmd_lst, build_name):
        message('Running post-build commands:')
        with prefix(VirtualEnvTool.activate_prefix(ctx().build_path(build_name))):
            for desc in cmd_lst:
                f = sudo if desc.get('sudo', False) else run
                result = f(desc['command'])
                if result.failed and not desc.get('ignore_fail', False):
                    raise HaltError('Post-build command failed: "{0}"'.format(desc['command']))
        message('Completed post-build commands.')
        return self

    def _increment_name(self, ref_repo_name):
        # some projects have more than one repo. in this case one is designated as the "reference".
        # the reference repo gives it's most recent commit ID that's used in the new build name.
        # if no reference is given, just use the first (hopefully, the only) repo in the Context.
        if ref_repo_name:
            ref_repo = ctx().get_repo(ref_repo_name)
        else:
            ref_repo = ctx().repos()[0]

        name = BuildInfo.next(ref_repo.dir)
        succeed_msg('Created new build name: "{0}"'.format(name))
        return name

    def _tarball(self, build_name):
        tarball = self._tarball_name(build_name)
        dir_to_tar = ctx().build_path(build_name)

        with cd(ctx().builds_root()):
            options = '--create --gzip --format=ustar --owner=0 --group=0'
            command = 'tar {options} --file={tarball} {build_name}'.format(**locals())
            result = run(command)

        if result.failed:
            raise HaltError('Failed to create tarball for: "{0}"'.format(dir_to_tar))
        succeed_msg('Created build tarball: "{0}"'.format(tarball))
        return self

    def _tarball_name(self, build_name):
        return '{build_name}.tar.gz'.format(**locals())

    def _unittest(self, plan, build_name):
        failed_msg('The action "unittest" is not implemented (yet).')
        return self


# register.
Tool.__tools__['python_build'] = PythonBuildTool
