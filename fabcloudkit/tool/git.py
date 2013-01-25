from __future__ import absolute_import

# standard
import uuid

# pypi
from fabric.context_managers import cd
from fabric.decorators import task
from fabric.operations import put, run, sudo

# package
from fabcloudkit import ctx, start_msg, succeed_msg, message, HaltError


__all__ = ['clone', 'pull', 'head_commit', 'install_key_file', 'append_ssh_config',
           'clone_all', 'pull_all']


@task
def clone(url, name=None, parent_dir=None, repo_name=''):
    start_msg('----- Cloning git repo: "{url}"'.format(**locals()))
    if not name:
        name = ctx().name
        message('Using context name: "{0}"'.format(name))
    if not parent_dir:
        parent_dir = ctx().repos_root()
        message('Using parent directory: "{0}"'.format(parent_dir))

    # make sure the parent directory exists.
    result = sudo('mkdir -p -m 0777 {0}'.format(parent_dir))
    if result.failed:
        raise HaltError('Unable to create repo parent directory: {0}'.format(parent_dir))

    with cd(parent_dir):
        result = run('git clone {url} {repo_name}'.format(**locals()))
        if result.return_code != 0:
            raise HaltError('Failed to clone repo: "{url}"'.format(**locals()))
    succeed_msg('Clone successful.')

@task
def pull(repo_name=None, repo_dir=None):
    if not repo_dir:
        if not repo_name:
            raise HaltError('Either "repo_name" or "repo_dir" must be specified.')
        repo_dir = ctx().repo_path(repo_name)

    start_msg('Executing git pull in repo: "{0}"'.format(repo_dir))
    with cd(repo_dir):
        result = run('git pull')
        if result.failed:
            raise HaltError('Error during "git pull" ({0})'.format(result))
    succeed_msg('Pull successful ({0}).'.format(result))

@task
def head_commit(repo_name=None, repo_dir=None):
    if not repo_dir:
        if not repo_name:
            raise HaltError('Either "repo_name" or "repo_dir" must be specified.')
        repo_dir = ctx().repo_path(repo_name)

    start_msg('Getting commit ID in git repo: "{0}":'.format(repo_dir))
    with cd(repo_dir):
        # pipe the result through cat, otherwise the result that comes back from run()
        # is garbled and requires extensive weird parsing to extract the commit ID.
        result = run('git log -1 --pretty=format:%h | cat')
        if result.failed:
            raise HaltError('Error during "git log" ({0})'.format(result))
    succeed_msg('Got head commit ID ({0}).'.format(result))
    return result

@task
def install_key_file(local_key_file, target_name=None):
    """
    Copies the specified private key file to the host and updates the ssh config for github.com.

    Also sets permissions of the uploaded file to "0600". An entry is appended to the ssh config
    for the host github.com. This entry makes git more automation friendly by disabling the prompt
    to confirm the fingerprint and specifying to use the key file just uploaded.

    :param local_key_file: path to the local key file.
    :param target_name: specifies the name for the target file on the remote system. If None,
                        a hideous but unique name is generated and used.
    :return: None
    """
    start_msg('----- Installing key file: "{0}"'.format(local_key_file))
    remote_home = run('echo $HOME', warn_only=False, quiet=False)
    if not target_name:
        target_name = 'id_rsa_fck_{0}'.format(uuid.uuid4().hex)
    target_name = '{0}/.ssh/{1}'.format(remote_home, target_name)

    # first check for remote-file existence.
    result = run ('test -f {0}'.format(target_name))
    if result.return_code == 0:
        raise HaltError('File "{0}" already exists.'.format(target_name))

    # copy the file to the remote host and set it's permissions.
    result = put(local_key_file, target_name, mode=00600)
    if result.failed:
        raise HaltError('Failed to copy key file: "{0}"'.format(local_key_file))
    succeed_msg('Installed key file "{0}" to "{1}".'.format(local_key_file, target_name))

    # finally, modify the ssh config for github.com so that git won't prompt to
    # confirm the fingerprint, and will also use the key file we just uploaded.
    append_ssh_config(
        'github.com',
        ['StrictHostKeyChecking no', 'IdentityFile {0}'.format(target_name)])

@task
def append_ssh_config(host, opts):
    """
    Appends a "Host" entry to the ssh config file, and adds the specified options.

    :param host: the name of the host (e.g., "github.com")
    :param opts: an option string, or iterable of option strings (e.g., ['StrictKeyChecking no'])
    :return: None
    """
    if isinstance(opts, basestring):
        opts = [opts]

    start_msg('----- Appending to file: "~/.ssh/config":')
    str = 'Host {0}\n\t{1}\n'.format(host, '\n\t'.join(opts))
    result = run('echo -e "{0}" >> ~/.ssh/config'.format(str))
    if result.failed:
        raise HaltError('The "echo" command failed on the remote host. Permissions issue?')
    message('Appended entry to ssh config; setting permissions.')

    result = run('chmod 0600 ~/.ssh/config')
    if result.failed:
        raise HaltError('Unable to set permissions on file "~/.ssh.config".')
    succeed_msg('Success.')

@task
def clone_all():
    """
    Clones all repos defined in the current context.

    :return: None
    """
    for repo in ctx().repos():
        clone(repo['url'], repo_name=repo['dir'])

@task
def pull_all():
    """
    Performs a "pull" for all repos defined in the current context.

    :return: None
    """
    for repo in ctx().repos():
        pull(repo['dir'])
