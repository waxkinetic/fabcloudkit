"""
    fabcloudkit

Build plan variables:

  repos:
    Specifies a list of git repositories in which to execute a "git pull".
    May also be a string identifying a single repository.
    The special string "__all__" means to pull from all repositories.
    The repository name specifies an entry in the "repos" section of the context yaml.

  reference_repo:
    Specifies the reference repo. The reference repo gives it's current commit ID, which is
    used in the build name. If not specified, the first (or only) repo in "repos" is used.

  interpreter:
    Specifies the Python interpreter to use in the build's virtualenv. If not specified, the
    operating system default Python interpreter is used. Note that if this value is specified
    the interpreter must exist on the system (e.g., installed via a tool specification in the
    "provision" section of the role yaml.

  unittest:
    TBD

  tarball:
    A simple True/False value. If True, a successful build - the entire virtualenv - is tarballed
    up in a file next to the build directory. The tarball has the same name as the directory
    except for a ".tar.gz" extension. This file can be copied to other machines using the
    "copy_from" build specification in the role yaml.

    :copyright: (c) 2013 by Rick Bohrer.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import

# pypi
from fabric.context_managers import cd, prefix, settings
from fabric.operations import run, sudo

# package
from fabcloudkit import cfg, ctx
from fabcloudkit.tool import git, virtualenv
from .build import build_repo, BuildInfo
from .internal import *


def copy_file_from(from_user, from_host, from_path, to_path):
    result = run(
        'scp -o StrictHostKeyChecking=no -i {key} {from_user}@{from_host}:{from_path} {to_path}'
        .format(key=cfg().machine_key_file(), **locals()))
    if result.failed:
        raise HaltError('Unable to copy from {0}:{1}'.format(from_host, from_path))


class Builder(object):
    def __init__(self, role):
        self._role = role

    def execute(self):
        start_msg('Executing build for instance in role "{0}":'.format(self._role.name))
        spec = self._role.build
        self._validate(spec)
        plan = spec.get('plan', None)
        if not plan:
            copy_spec = spec.get('copy_from', {})
            build_name = self._copy_from(copy_spec)
        else:
            self._pull_repos(plan.get('repos', []))
            build_name = self._build(plan)
            self._tarball(plan, build_name)

        # execute any post-build commands.
        self._execute_post_build(spec.get('post_build', {}), build_name)

        # return the build_name to the caller; it'll be set as an instance-tag.
        succeed_msg('Build completed successfully for role "{0}".'.format(self._role.name))
        return build_name

    def _build(self, plan):
        # increment the build name and create a new virtualenv for the build.
        build_name = self._increment_name(plan)
        build_env_dir = ctx().build_path(build_name)
        virtualenv.ensure(build_env_dir, plan.get('interpreter', None))

        # run "setup.py install" in each repo.
        for repo in self._get_repos(plan.get('repos', [])):
            build_repo(build_env_dir, repo)

        # run tests.
        self._unittest(plan, build_name)

        # save the last known good build-name.
        BuildInfo.set_last_good(build_name)
        return build_name

    def _copy_from(self, copy_spec):
        from_role_name = copy_spec.get('role', None)
        if not from_role_name:
            return None

        # get the last known good build from the source machine.
        # note: we could alternatively get this from an instance tag.
        inst, role = ctx().get_host_in_role(from_role_name)
        with settings(host_string=inst.public_dns_name, user=role.user):
            message('Getting last good build-name from: "{0}"'.format(from_role_name))
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
            if copy_spec.get('delete_tar', True):
                run('rm {tarball}'.format(**locals()))

        # update the build information.
        BuildInfo().set_last_good(src_build_name)
        succeed_msg('Successfully copied build: "{0}"'.format(src_build_name))
        return src_build_name

    def _execute_post_build(self, post_spec, build_name):
        message('Running post-build commands:')
        with prefix(virtualenv.activate_prefix(ctx().build_path(build_name))):
            for desc in post_spec:
                f = sudo if desc.get('sudo', False) else run
                result = f(desc['command'])
                if result.failed and not desc.get('ignore_fail', False):
                    raise HaltError('Post-build command failed: "{0}"'.format(desc['command']))
        message('Completed post-build commands.')

    def _get_repos(self, repo_names):
        if repo_names == '__all__':
            return ctx().repos()

        if isinstance(repo_names, basestring):
            repo_names = [repo_names]
        return [ctx().get_repo(name) for name in repo_names]

    def _increment_name(self, plan):
        # some projects have more than one repo. in this case one is designated as the "reference".
        # the reference repo gives it's most recent commit ID that's used in the new build name.
        ref_name = plan.get('reference_repo', None)
        if ref_name:
            ref_repo = ctx().get_repo(ref_name)
        else:
            ref_repo = self._get_repos(plan.get('repos', []))[0]

        name = BuildInfo.next(ref_repo.dir)
        succeed_msg('Created new build name: "{0}"'.format(name))
        return name

    def _pull_repos(self, repo_names):
        for repo in self._get_repos(repo_names):
            git.pull(repo_name=repo.dir)

    def _tarball(self, plan, build_name):
        if not plan.get('tarball', False):
            return

        tarball = self._tarball_name(build_name)
        dir_to_tar = ctx().build_path(build_name)

        with cd(ctx().builds_root()):
            options = '--create --gzip --format=ustar --owner=0 --group=0'
            command = 'tar {options} --file={tarball} {build_name}'.format(**locals())
            result = run(command)

        if result.failed:
            raise HaltError('Failed to create tarball for: "{0}"'.format(dir_to_tar))
        succeed_msg('Created build tarball: "{0}"'.format(tarball))

    def _tarball_name(self, build_name):
        return '{build_name}.tar.gz'.format(**locals())

    def _unittest(self, plan, build_name):
        failed_msg('The action "unittest" is not implemented (yet).')

    def _validate(self, spec):
        if spec.get('build', None) and spec.get('copy_from'):
            raise ValueError('The "build" section cannot contain both "plan" and "copy_from".')

        plan = spec.get('plan', None)
        if plan and not plan.get('repos', None):
            raise ValueError('No repos specified in build plan.')

        copy_spec = spec.get('copy_from', None)
        if copy_spec and not copy_spec.get('role', None):
            raise ValueError('No role specified in "copy_from".')
