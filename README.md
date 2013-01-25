# fabcloudkit
cloud machine management: provision, build, and deploy (experimental)

## What is it?

(This readme is a work in progress.)

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

In this example assume there's just one type of machine, e.g., for a small and simple site that only
needs web servers, or for a really small project that really only needs a single machine.

The example assumes all of your code is in a git repository, and its all pure-Python (although
pure-Python code isn't a requirement of fabcloudkit).

Prerequisites are:

* You have an AWS account,
* You know your AWS access key and secret key,
* You've created and setup a key-pair,
* You've created an appropriate security group, and
* You know the SSH (not HTTPS) URL for your git repository(s).

I'll get to what to do with this stuff in a minute, but assuming you've created a "context" configuration
file and one "role" configuration file for the 'builder' role, here are a few things you could do:

```
>>> from fabcloudkit import Config, Context
>>> Config.load()
>>> context = Context('context.yaml')
>>> builder = context.get_role('builder')
>>> builder.create_instance()
Instance:i-76b14906
>>>
```

All we did so far was load the default fabcloudkit configuration, load our "context" configuration file,
get access to the Role object, and create an instance. Pretty easy, but no big deal.

Now lets say that the 'builder' role-configuration file says that machines in the 'builder' role should
have all of the AMI default packages updated, install Python2.7, pip, virtualenv, gcc, git, install the
python-devel and mysql-devel packages, clone your git repo, and then reboot. You can do that:

```
>>> inst, role = context.get_host_in_role('builder')
>>> role.provision_instance(inst)
Provisioning instance in role "builder":
# (a whole bunch of fabric/SSH output)
Provisioning completed successfully for role "builder".
>>>
```

A whole bunch of Fabric stuff will be spewed to the screen, but when it's done all of that provisioning
will be finished and the instance will be ready to do a build. To build your code as described earlier
is easy too:

```
>>> role.build_instance(inst)
Executing build for instance in role "builder":
# (a whole bunch more fabric/SSH output)
Build completed successfully for role "builder".
>>>
```

## What's next?

In no particular order, here are some ideas on the burner:

- Unittests
- Docs
- Support pip installations from a local cache instead of downloading
- Investigate using with Fabric's multi-processing capabilities
- Support non-Python people
- Support other WSGI servers

## Caveats, acknowledgements, disclaimers and other stuff

I really don't know anything about Django, so while the fabcloudkit might work with Django I
haven't tested it.

The code has been tested mostly on the Amazon Linux AMI, but it's also been run on the Ubuntu
AMI successfully several times. Won't work on Windows AMIs.

This is really my first experience setting up and using supervisor, Nginx, and gunicorn, so
there are likely to be improvements that could/should be made.

No docs at the moment (sorry), but there are some comments in the code.

No use/testing with fabric's multi-processing capabilities.

Only supports gunicorn HTTP-based binding (no socket-based binding).

Comments and contributions welcome.

Some ideas and code (heavily modified) taken from Brent Tubb's silk-deployment project at:
http://pypi.python.org/pypi/silk-deployment/0.3.14
