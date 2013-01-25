from __future__ import absolute_import

# standard
import os
import posixpath as path
import random

# pypi
from fabric.operations import run, put

# package
from .internal import *


def tmp_file_name(dir='/tmp', prefix='fck_tmp_', ext=''):
    """
    Generates a random filename in /tmp.

    Ripped off from Brent Tubbs "silk-deployment" project.
    """
    chars = "abcdefghijklmnopqrstuvwxyz1234567890"
    random_part = "".join([random.choice(chars) for _ in xrange(20)])
    return path.join(dir, '{prefix}{random_part}{ext}'.format(**locals()))

def put_string(str, remote_path, *args, **kwargs):
    name = tmp_file_name()
    with open(name, 'w') as f:
        f.write(str)
    result = put(name, remote_path, *args, **kwargs)
    os.remove(name)
    if result.failed:
        raise HaltError('Error from put. {0}'.format(result))

    # verify; the underlying put() appears to "succeed" even if the destination directory doesn't exist.
    result = run('test -f {0}'.format(remote_path))
    if result.failed:
        raise HaltError("Appeared to write file \"{0}\", but it's not there...?".format(remote_path))
    return result
