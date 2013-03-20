"""
    fabcloudkit

    :copyright: (c) 2013 by Rick Bohrer.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import

# pypi
from fabric.operations import run

# package
from ..internal import *


def check_version(ver):
    start_msg('----- Checking for python version "{0}":'.format(ver))

    # only works on linux, darwin.
    result = run('test -f /usr/bin/python{0}'.format(ver))
    if result.return_code != 0:
        failed_msg('Python version "{0}" not found.'.format(ver))
        return False

    succeed_msg('python version OK ({0}).'.format(ver))
    return True
