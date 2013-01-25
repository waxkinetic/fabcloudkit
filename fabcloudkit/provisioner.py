from __future__ import absolute_import

# standard
from StringIO import StringIO

# pypi
from fabric.context_managers import cd, settings
from fabric.operations import get, run, sudo

# package
from fabcloudkit import cfg, ctx
import fabcloudkit.tool as tool
from .internal import *
from .util import *


def authorize_key(public_key_value):
    """
    Authorizes access to the current host, to whoever holds the private key associated with the
    specified public key value. This is done by adding the public key to the host's SSH
    authorized_keys file.

    :param public_key_value: the public key of the entity to be given access.
    :return: None
    """
    remote_key_file = tmp_file_name('~/.ssh', 'fck_key_', '.pub')
    with cd('~/.ssh'):
        put_string(public_key_value, remote_key_file)
        result = run('cat {0} >> authorized_keys'.format(remote_key_file))
        if result.failed:
            raise HaltError('Failed to write to "authorized_keys" file.')

def generate_key_pair():
    """
    Generates a private/public key-pair for the host, stored in the ~/.ssh/ directory.

    :return: None
    """
    if not has_key_pair():
        result = run('ssh-keygen -b 1024 -t rsa -N "" -f {0}'.format(cfg().machine_key_file()))
        if result.failed:
            raise HaltError('Unable to generate key pair.')

def get_public_key():
    """
    Returns a string containing the public key portion of the host's key-pair.

    The function generate_key_pair() should have already been called.

    :return: string containing the host's public key (empty if no key-pair has been generated).
    """
    stream = StringIO()
    if has_key_pair():
        result = get('{0}.pub'.format(cfg().machine_key_file()), stream)
        if result.failed:
            raise HaltError('Unable to retrieve public key file.')
    return stream.getvalue()

def has_key_pair():
    """
    Determines if a key-pair has been generated for this host by generate_key_pair().

    :return: True if a key-pair exists, False otherwise.
    """
    result = run('test -f {0}'.format(cfg().machine_key_file()))
    return result.succeeded


class Provisioner(object):
    def __init__(self, role):
        self._role = role

    def execute(self):
        start_msg('Provisioning instance in role "{0}":'.format(self._role.name))
        spec = self._role.provision
        self._create_dirs()
        if spec.get('create_key_pair', False):
            generate_key_pair()

        for tool_name in spec.get('tools', []):
            tool.verify(tool_name)

        self._execute_git_spec(spec.get('git', {}))
        self._execute_access_spec(spec.get('request_access', {}))
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

    def _execute_git_spec(self, git_spec):
        if git_spec.get('install_key_file', False):
            tool.git.install_key_file(ctx().get_key('git').local_file)

        clone_spec = git_spec.get('clone', [])
        if clone_spec == '__all__':
            repos = ctx().repos()
        else:
            if isinstance(clone_spec, basestring):
                clone_spec = [clone_spec]
            repos = [ctx().get_repo(name) for name in clone_spec]

        for repo in repos:
            tool.git.clone(repo.url, ctx().name, ctx().repos_root(), repo.dir)

    def _execute_access_spec(self, spec):
        access = spec.get('roles', [])
        if isinstance(access, basestring):
            access = [access]

        if access:
            public_key = get_public_key()
            for role_name in access:
                # check if access is allowed.
                target_role = ctx().get_role(role_name)
                if not target_role.allows_access_to(self._role.name):
                    raise RuntimeError('Role "{0}" does not allow access to role "{1}"'
                                       .format(target_role.name, self._role.name))

                # it is; put this host's public key in the target host's authorized_keys file.
                inst, role = ctx().get_host_in_role(role_name)
                with settings(host_string=inst.public_dns_name, user=role.user):
                    authorize_key(public_key)
