from __future__ import absolute_import

from setuptools import setup, find_packages

readme = open('README.md').read()

setup(
    name='fabcloudkit',
    version='0.021',
    url='http://github.com/waxkinetic/fabcloudkit',
    license='BSD',

    author='Rick Bohrer',
    author_email='waxkinetic@gmail.com',

    description='An AWS provisioning, build, and deployment library built on Fabric and Boto.',
    long_description=readme,

    zip_safe=False,
    include_package_data=True,

    packages=find_packages(),

    setup_requires=[
        'setuptools-git >= 1.0b1'
    ],

    install_requires=[
        'boto >= 2.7.0',
        'fabric >= 1.5.2',
        'pyaml >= 13.01.0'
    ]
)
