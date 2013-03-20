from __future__ import absolute_import

# standard
from StringIO import StringIO

# pypi
from fabric.context_managers import cd
from fabric.state import env
from fabric.operations import get, run

# package
from fabcloudkit import cfg, ctx
from ..toolbase import Tool
from ..util import *


class KeyPairTool(Tool):
    """Manages a key pair on the current host machine.

    Allows creation of a new key pair, and retrieval of the public key. Used to setup
    SSH access from one machine to another.
    """
    def check(self, **kwargs):
        """Determines if a key-pair has been generated for this host.

        :return: True if a key-pair exists, False otherwise.
        """
        result = run('test -f {0}'.format(cfg().machine_key_file()))
        return result.succeeded

    def install(self, **kwargs):
        """Generates a private/public key-pair for the host, stored in the ~/.ssh/ directory.

        :return: self
        """
        result = run('ssh-keygen -b 1024 -t rsa -N "" -f {0}'.format(cfg().machine_key_file()))
        if result.failed:
            raise HaltError('Unable to generate and install key pair.')
        succeed_msg('Key pair generated.')
        return self

    def get_public_key(self):
        """Returns a string containing the public key portion of the host's key-pair.

        The key_pair() should have already been installed.

        :return: string containing the host's public key (empty if no key-pair has been generated).
        """
        stream = StringIO()
        if self.check():
            result = get('{0}.pub'.format(cfg().machine_key_file()), stream)
            if result.failed:
                raise HaltError('Unable to retrieve public key file.')
        return stream.getvalue()


class RequestAccessTool(Tool):
    def __init__(self):
        super(RequestAccessTool,self).__init__()
        self._key_pair = KeyPairTool()

    def install(self, roles):
        if isinstance(roles, basestring):
            roles = [roles]

        if not roles:
            raise HaltError('No roles specified for request_access.')

        public_key = self._key_pair.get_public_key()
        for role_name in roles:
            # check if access is allowed.
            target_role = ctx().get_role(role_name)
            if not target_role.allows_access_to(env.role_name):
                raise RuntimeError('Role "{0}" does not allow access to role "{1}"'
                                   .format(target_role.name, env.role_name))

            # it is; put this host's public key in the target host's authorized_keys file.
            inst, role = ctx().get_host_in_role(role_name)
            with role.and_instance(inst):
                self._authorize_key(public_key)
        succeed_msg('Access granted to instances in role(s): {0}'.format(roles))
        return self

    def _authorize_key(self, public_key_value):
        """Grants the current host machine access to a machine in a specified role.

        Grants access to the current host, to whoever holds the private key associated with the
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
        return self


# register.
Tool.__tools__['key_pair'] = KeyPairTool
Tool.__tools__['request_access'] = RequestAccessTool
