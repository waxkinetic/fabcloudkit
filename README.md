# fabcloudkit
cloud machine management: provision, build, and deploy (experimental)

## What is it?

The fabcloudkit is a thin layer over the Fabric remote execution and deployment tool and the boto
AWS interface library. Its an experimental project for automated provisioning and management of
machines in the AWS cloud for running Python code.

In theory fabcloudkit could support other cloud platforms, but is only focused on AWS at the moment.
In theory it should also be able to support non-Python projects, but it doesn't right now.

The initial motivation for fabcloudkit was mostly cost and convenience: not wanting to invest in
something like Chef or Puppet for managing small-ish projects, and at the same time wanting to
automate machine provisioning, build and deployment of Python-based projects.

## What does it do?

The fabcloudkit makes it relatively easy to

1. Create instances,
2. Provision them with the software you need (including from your own git repositories),
3. Build the code in your repos,
4. Optionally distribute the built code to other instances, and
5. Activate (or deploy) your code (using Nginx, gunicorn, and supervisor).

To do the above, fabcloudkit imposes a directory structure on your machines. The names of the
directories can be customized, but the structure stays the same. In brief, that structures looks
something like this:

```
/opt/www
    <name>
        builds
        <build-1>
        <build-2>
        ...
        <build-N>
    repos
        <repo-1>
        <repo-2>
        ...
        <repo-N>
```

The root (/opt/www) can be customized, and so can the names "builds" and "repos" if you want. The
actual build names are generated. Repo names are taken from the git URL, and you can override that
if you need something different.

The fabcloudkit also imposes a particular kind of build and deployment. Right now, deployments use
Nginx as the public-facing HTTP reverse-proxy server, gunicorn as the WSGI server, and supervisor
for process monitoring and control.

Builds require you to have a setup.py in your repo. A build includes the following:

1. Pull new code from all of your git repos,
2. Create a new virtualenv for the build,
3. Use your setup.py to create an "sdist" distribution for each repo,
4. Use pip to install each distribution into the virtualenv,
5. Run unittests (not implemented yet),
6. Build a tarball of the virtualenv, and
7. Optionally executing a set of post-build commands.

Once this is all done successfully, the tarball can be activated (that means installed, served
and monitored using Nginx, gunicorn and supervisor. The tarball can be activated on the machine
where it was built, or it can be copied to other machines and activated there.

So, fabcloudkit does a reasonable amount of useful stuff. There's also a lot it doesn't do right now.

## A simple example

  In this simple example there's just one type of machine, e.g., for a small and simple site that only
  needs web servers, or for a really small project that really only needs a single machine.

  The example assumes all of your code is in a git repository, and its all pure-Python (although
  pure-Python code is not a requirement of fabcloudkit.

  Prerequisites are:

  a) You have an AWS account,
  b) You know your AWS access key and secret key,
  c) You've created and setup a key-pair,
  d) You've created an appropriate security group, and
  e) You know the SSH (not HTTPS) URL for your git repository.

  With the above in hand, to setup fabcloudkit to manage this scenario, you'll need to do the following:

  1) Create a "setup.py" for your code (just like you're probably doing anyway),
  2) Create a small fabcloudkit context configuration file,
  2) Create a small fabcloudkit role configuration file for your single machine role.

  Lets take a look at each one of these.


A slightly more complicated example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

  At the moment, not much, but what little is there is sort of useful. Once an EC2 instance has been
  launched and the public DNS name is available, the fabcloudkit makes it pretty easy to:

  a) Check if TOOL is installed, and install it if not, where TOOL is:

     Python 2.7
     pip
     virtualenv
     git

  b) Create a virtualenv in a specified location.

  c) Clone a git repo.

     Currently, this is done by copying a private key file to "~/.ssh/id_rsa" (after checking if that
     file already exists), and disabling ssh StrictHostKeyChecking for github.com so there are no
     interactive prompts.

What's next?
~~~~~~~~~~~~

  In no particular order, here are some things on deck:

  - Unit tests
  - Limit pip installations from a local cache
  - Investigate using with Fabric's multi-processing capabilities

Caveats and other stuff
~~~~~~~~~~~~~~~~~~~~~~~

  I really don't know anything about Django, so while the fabcloudkit might work with Django I
  haven't tested it.

  The code has been tested mostly on the Amazon Linux AMI, but it's also been run on the Ubuntu
  AMI successfully several times. Won't work on Windows AMIs.

  This is really my first experience setting up and using supervisor, Nginx, and gunicorn, so
  there are likely to be improvements that could/should be made.

  No docs at the moment (sorry), but there are some comments in the code.

  No use/testing with fabric's multi-processing capabilities.

  Only supports gunicorn HTTP-based binding (no socket-based binding).

  Only used in straightforward EC2 deployments to date, e.g., no VPC, ELB, RDS, Dynamo, CloudFront, etc.

  Comments and contributions welcome.
