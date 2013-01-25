                                // fabcloudkit //

                        cloud machine management; experimental

What is it?
~~~~~~~~~~~

  The fabcloudkit is a thin layer over the Fabric remote execution and deployment tool and the boto
  AWS interface library. Its an experimental project for automated provisioning and management of
  machines in the AWS cloud.

  In theory fabcloudkit could support other cloud platforms, but is only focused on AWS at the moment.

  The initial motivation for fabcloudkit was mostly cost and convenience: not wanting to invest in
  something like Chef or Puppet for managing small-ish projects, and at the same time wanting to
  automate machine provisioning, build and deployment of Python-based projects.

What does it do?
~~~~~~~~~~~~~~~~

--REWRITE:
  The fabcloudkit lets you easily declare machine "roles", examples might be a builder role for building
  your code, and a web role for running the code. Then using these roles you can easily create and
  provision instances, build, and deploy code.
--END REWRITE:

  In doing the above fabcloudkit makes assumptions about directory structure on your instances (the
  actual directory names used can be customized but the structure is the same).

  Also, at the moment, fabcloudkit only supports a particular type of deployment configuration too: it
  uses Nginx, gunicorn, and supervisor.

A simple example
~~~~~~~~~~~~~~~~

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
