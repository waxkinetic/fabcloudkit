from __future__ import absolute_import

# pypi
from fabric.context_managers import prefix

# package
from .tool.virtualenv import VirtualEnvTool
from .util import *


def unused_port():
    """
    Finds an unused port on the remote host. Note that the returned port could be taken by another
    process before it's used.

    :return: an unused port number.
    """
    _UNUSED_PORT_CMD = """
cat <<-EOF | python -
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('localhost', 0))
addr, port = s.getsockname()
s.close()
print(port)
EOF
""".lstrip()

    result = run(_UNUSED_PORT_CMD, quiet=True)
    if result.failed:
        raise HaltError('Failed to find unused port.')

    port = int(result)
    white_msg('Found unused port={0}'.format(port), bold=True)
    return port

def cpu_count():
    # note: requires python 2.6+.
    _CPU_CMD = """
cat <<-EOF | python -
import multiprocessing as mp
print(mp.cpu_count())
EOF
""".lstrip()

    result = run(_CPU_CMD, quiet=True)
    if result.failed:
        raise HaltError('Failed to retrieve CPU count.')

    count = int(result)
    white_msg('Found CPU count={0}'.format(count), bold=True)
    return count

def site_packages_dir(virtualenv_dir):
    _DIR_CMD = """
cat <<-EOF | python -
import os, sys
v=sys.version_info
print(os.path.join(sys.prefix, 'lib', 'python{0}.{1}'.format(v.major, v.minor), 'site-packages'))
EOF
""".lstrip()

    with prefix(VirtualEnvTool.activate_prefix(virtualenv_dir)):
        result = run(_DIR_CMD, quiet=True)
        if result.failed:
            raise HaltError('Failed to retrieve Python "site-packages" location.')
        white_msg('Python site-packages dir: "{0}"'.format(result))
        return result

def http_test(url):
    start_msg('Local test URL: {url}'.format(**locals()))

    result = run('curl -I {url}'.format(**locals()))
    if result.failed:
        failed_msg('"{url}" failed: (result)'.format(**locals()))
        return False

    first_line = result.split('\r\n')[0]
    status = int(first_line.split()[1])
    if not (200 <= status < 500):
        failed_msg('"{url}" failed with status: "{status}"'.format(**locals()))

    succeed_msg('"{url}" succeeded with status: "{status}"'.format(**locals()))
    return True

