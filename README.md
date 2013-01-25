fabcloudkit
===========
cloud machine management: provision, build, and deploy (experimental)

What is it?
-----------

(This readme is a work in progress.)

The fabcloudkit is a thin layer over the Fabric remote execution and deployment tool and the boto
AWS interface library. Its an experimental project for automated provisioning and management of
machines in the AWS cloud for running Python code.

In theory fabcloudkit could support other cloud platforms, but is only focused on AWS at the moment.
In theory it should also be able to support non-Python projects, but it doesn't right now.

The initial motivation for fabcloudkit was mostly cost and convenience: not wanting to invest in
something like Chef or Puppet for managing small-ish projects, and at the same time wanting to
automate machine provisioning, build and deployment of Python-based codebases.

What does it do?
----------------

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

A simple example
----------------

In this example there'll be two roles: a 'builder' role that just builds code, and a 'web' role
where the code is deployed. It assumes code is stored in a git repository.

Prerequisites are:

* You have an AWS account,
* You know your AWS access key and secret key,
* You've created and setup a key-pair,
* You've created an appropriate security group, and
* You know the SSH (not HTTPS) URL for your git repository(s).

With this stuff in hand, you'll need to create the following:

1. A "context" configuration file,
2. A "builder" role configuration file, and
3. A "web" role configuration file.

There are examples, with comments, of these files in the "examples" folder of the source.

### The context-configuration file

```
name: example
key_filename: ~/.ec2/keypair.pem
aws_key: !env AWS_ACCESS_KEY_ID
aws_secret: !env AWS_SECRET_ACCESS_KEY

keys:
  git:
    local_file: /Users/<USER>/.ssh/id_rsa_example_machine_user
    private: True

repos:
  fabcloudkit_example_repo:
    url: git@github.com:waxkinetic/fabcloudkit_example_repo.git

roles:
  - role_builder.yaml
  - role_web.yaml
```

Most of this stuff is pretty straightforward, but a few notes are in order.

Under "keys", the "git" key has to be specified in order to use "install_key_file" in the
role-configuration files. The git key is a private key for a git user account that has access
to your repo. If you're using git organizations, that user can have readonly access.

The "repos" section lists the git repositories that you'll be using.

The "roles" section points to the role-configuration files.

### The "builder" role-configuration file

```
name: builder
description: Build machine
user: ec2-user
aws:
  ami_id: ami-1624987f
  key_name: main
  security_groups: [default]
  instance_type: t1.micro

provision:
  tools: [__update_packages__, reboot,
          easy_install, python2.7, pip, virtualenv,
          git, gcc, python27-devel, mysql-devel, reboot]

  git:
    install_key_file: True
    clone: __all__

  allow_access:
    roles: web

build:
  plan:
    repos: __all__
    interpreter: python2.7
    tarball: True
```

A lot of this is straightforward too, but a few more notes.

The "user" is the account used for SSH login to the instance, and can be different for different
instance types (e.g., it's "ec2-user" for the Amazon Linux AMI, and "ubuntu" for the Ubuntu AMI).

The "aws" section gives defaults used for creating instances. These values can be overridden in
the call to create_instance().

The "provision" section describes a one-time preparation of the instance. The "tools" section
lists tools/packags to be installed. The "git" section says to install a private-key file for
access to git repositories, and to clone all repositories listed in the context-configuration file
(in this case, only the "fabcloudkit_example_repo"). The "allow_access" section says that instances
provisioned in the "web" role can have access to instances provisioned in the "builder" role.

The "build" section is a build plan. It says to pull all repos in the context-configuration, use
the Python2.7 interpreter in the build's virtualenv, and create a tarball when it's all finished.
Creating the tarball is important as we'll see in the "web" role-configuration file.

There aren't a ton of tools supported at the moment, but they're easy to add if you know the
yum and apt-get commands. Take a look at the fabcloudkit.yaml file in the source for this, and
send over any additions you make.

### The "web" role-configuration file

```
name: web
description: web server
user: ec2-user
aws:
  ami_id: ami-1624987f
  key_name: main
  security_groups: [default]
  instance_type: t1.micro

provision:
  create_key_pair: True

  tools: [__update_packages__, reboot,
          easy_install, python2.7, pip, virtualenv,
          supervisord, nginx, reboot]

  request_access:
    roles: builder

build:
  copy_from:
    role: builder

  post_build:
    - command: mkdir -p -m 0777 /some/important/dir
      sudo: True

activate:
  http_test_path: /

  gunicorn:
    script: gunicorn
    app_module: app:app
    options:
      debug: True
      log-level: DEBUG

  nginx:
    listen: 80
    #server_names: None

    static:
      - url: /static/
        local: app/static/
```

There's some of the same stuff here as in the "builder" role, but some differences too.

In the "provision" section "create_key_pair" causes a unique key-pair to be created for
the "web" instance, and "request_access" causes the public part of that key-pair to be shipped over
to the instance in the "builder" role.

In the "build" section, the build is copied from the instance in the "buider" role, and
the "post_build" commands are executed in the active build virtualenv after the build is
copied over and un-tarred.

The "activate" section describes how to activate the build. Activation means starting up
gunicorn to server the site on a port on the local machine, using supervisor to monitor the
gunicorn process, and using Nginx as the public-facing HTTP server but passing requests on
to the gunicorn process. The "static" section lets you use Nginx to serve static pages of
the site.

Again, there are fully-commmented examples of these files in the "examples" folder of the source
so they're a good resource to get a better understanding of the whole picture.

### Putting it all together

So now that you have all of the above, what can you do with it? Assuming your context and role-
configuration files are in the current directory:

```
>>> from fabcloudkit import Config, Context
>>> Config.load()
>>> context = Context('context.yaml')
>>> builder = context.get_role('builder')
>>> inst = builder.create_instance()
Instance:i-76b14906
>>>
```

All we did so far was load the default fabcloudkit configuration, load our "context" configuration file,
get access to the Role object, and create an instance. Pretty easy, but no big deal.

Now lets say that the 'builder' role-configuration file says that machines in the 'builder' role should
have all of the AMI default packages updated, install Python2.7, pip, virtualenv, gcc, git, install the
python-devel and mysql-devel packages, clone your git repo, and then reboot. You can do that:

```
>>> builder.provision_instance(inst)
Provisioning instance in role "builder":
# (a whole bunch of fabric/SSH output)
Provisioning completed successfully for role "builder".
>>>
```

A whole bunch of Fabric stuff will be spewed to the screen, but when it's done all of that provisioning
will be finished and the instance will be ready to do a build. To build your code as described earlier
is easy too:

```
>>> builder.build_instance(inst)
Executing build for instance in role "builder":
# (a whole bunch more fabric/SSH output)
Build completed successfully for role "builder".
>>>
```

Now we can create and provision an instance in the "web' role:

```
>>> web = ctx.get_role('web')
>>> inst = web.create_instance()
>>> web.provision_instance(inst)
Provisioning instance in role "web":
# (a whole bunch of fabric/SSH output)
Provisioning completed successfully for role "web".
>>>
```

Instances in the "web" role copy the build from the instance in the "builder" role, but the build
command is the same:

```
>>> web.build_instance(inst)
Executing build for instance in role "web":
# (a whole bunch of fabric/SSH output)
Build completed successfully for role "web".
>>>
```

Finally, you can activate the build on the "web" instance:

```
>>> web.activate_instance(inst)
Begin activation for instance in role: "web":
# (a whole bunch of fabric/SSH output)
Successfully activated build: "<build-name>"
>>>
```

Build names are automatically incremented. They contain your context-name, an auto-incrementing
build number, and the git commit ID of the most recent commit in your git repo. An example build
name is "example_00001_bfda687".

You can create, provision and build multiple instances this way. Lets say you did create multiple
instances in the "web" role. Then you went away, did some development, then came back and wanted to
update everything. It's easy:

```
>>> from fabcloudkit import Config, Context
>>> Config.load()
>>> context = Context('context.yaml')
>>> context.aws_sync()
>>>
>>> inst, builder = context.get_host_in_role('builder')
>>> builder.build_instance(inst)
Executing build for instance in role "builder":
# (fabric/SSH output)
Build completed successfully for role "builder".
>>>
>>> hosts, web = context.all_hosts_in_role('web')
>>> for inst in web_hosts:
...     web.build_instance(inst)
...
#(fabric/SSH output)
>>>
>>> for inst in web_hosts:
...     web.activate_instance(inst)
...
#(fabric/SSH output)
>>>
```

Finally, if you want to take the site down:

```
>>> for inst in web_hosts:
...   web.deactivate_instance(inst)
...
#(fabric/SSH output)
>>>
```

Poof. It's gone. That's the bulk of the functionality in a nutshell. The main classes you'll use are
Context and Role, but the underlying APIs are there too if you need them.

A note on git repositories and deploy keys
------------------------------------------

The fabcloudkit supports access to git repositories using the
"[machine user](https://help.github.com/articles/managing-deploy-keys)" approach. Using this you
can deploy straight from git, which might make sense if you have a pure-Python code base or are
comfortable having things like compilers on your public-facing machines. If not, then you can
use fabcloudkit to restrict building just one machine (or a few machines), and copy the entirely
built virtualenv to your public-facing machines and activate it there.


What's next?
------------

In no particular order, here are some ideas on the burner:

- Unittests
- Docs
- Support pip installations from a local cache instead of downloading
- Investigate using with Fabric's multi-processing capabilities
- Support non-Python people?
- Support other WSGI servers?
- Customization of the Nginx and supervisor configurations?


Caveats, acknowledgements, disclaimers and other stuff
------------------------------------------------------

Usage has been pretty light to date - this is experimental after all.

I really don't know anything about Django, so while the fabcloudkit might work with Django I
haven't tested it. You can, however, tell it to run "gunicorn_django" instead of "gunicorn".

The code has been tested mostly on the Amazon Linux AMI. It's also been run on the Ubuntu
AMI successfully several times. Won't work on Windows AMIs.

This is really my first experience setting up and using supervisor, Nginx, and gunicorn, so
there are likely to be improvements that could/should be made.

No docs at the moment (sorry), but there are some comments in the code.

No use/testing with fabric's multi-processing capabilities.

Only supports gunicorn HTTP-based binding (no socket-based binding).

Comments and contributions welcome.

Some ideas and code (heavily modified) taken from [Brent Tubb's silk-deployment
project](http://pypi.python.org/pypi/silk-deployment/0.3.14).
