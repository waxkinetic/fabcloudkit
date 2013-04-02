"""
    fabcloudkit

    Functions for managing supervisor.

    This module provides functions that check for installation, install, and manage an
    installation of, supervisor. If an installation already exists (e.g., as part of an
    AMI), the files directories used by that installation are (for now) assumed to conform
    to the same files and directories used by these functions.

    The relevant files and directories are:

    /etc/init.d/supervisor:
        The "init script" for supervisor that allows supervisord to be automatically run
        automatically at system startup. Note that on some systems (e.g., Amazon Linux AMI)
        that the existence of this file isn't sufficient to guarantee automatic launch
        after boot, and use of the program chkconfig is required. The functions in this
        module will use chkconfig where necessary, if it exists.

    /etc/supervisord.conf:
        The root or main supervisor configuration file. This file is read by supervisord
        when it launches. This file contains an include directive that tells supervisord
        to also load configurations from a different directory.

    /etc/supervisor/conf.d/:
        The directory indicated by the include directive in the root supervisor configuration
        file. Individual program configurations, the "[program:x]" section for that program,
        are contained in files in this directory.

    /etc/supervisor/conf.d/*.conf:
        Individual program configuration files containing a program's "[program:x]" section.

    <deploy_root>/<name>/logs/supervisor.log:
        The supervisord log file for an individual program. This is the default location,
        and it can overridden in the call to write_program_config().

    For more information on supervisor check out: http://supervisord.org/
    Idea and code (heavily modified) for this module taken from Brent Tubb's "silk" project.

    :copyright: (c) 2013 by Rick Bohrer.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import

# standard
import posixpath as path
import time

# pypi
from fabric.operations import run, sudo

# package
from fabcloudkit import cfg, put_string
from ..internal import *
from ..toolbase import *


class SupervisorTool(Tool):
    def check(self, **kwargs):
        """
        Detects if supervisor is installed on the remote machine.

        :return: None
        """
        start_msg('----- Checking for "supervisord" installation:')
        result = run('supervisord --version')
        if result.return_code != 0:
            failed_msg('"supervisord" is not installed.')
            return False

        succeed_msg('"supervisord" is installed ({0}).'.format(result))
        return True

    def install(self, **kwargs):
        """
        Installs and configures supervisor on the remote machine.

        Supervisor is installed via easy_install, a supervisor.conf file is created with an entry
        to include additional conf files in the directory: cfg().supervisord_include_conf. An init.d
        script is written, and if the program "chkconfig" exists, supervisor is added.

        :return: None
        """
        start_msg('----- Install "supervisord" via "easy_install".')
        result = sudo('easy_install supervisor')
        if result.return_code != 0:
            HaltError('Failed to install "supervisord".')

        result = run('which supervisord')
        if result.return_code != 0:
            raise HaltError('Confusion: just installed "supervisord" but its not there?')

        message('Install successful; setting configuration.')

        # create the root supervisord.conf with an [include] entry that allows loading additional
        # from the folder: /etc/supervisor/conf.d/*.conf
        # we use this location for site-specific config (e.g., a site's [program] section).
        # start with the default conf file; the grep strips comment lines.
        result = run('echo_supervisord_conf | grep "^;.*$" -v')
        if result.failed:
            raise HaltError('Unable to retrieve default supervisord configuration.')

        # build the new configuration by just appending the include definition,
        # then write it to: /etc/supervisord.conf
        files = path.join(cfg().supervisord_include_conf, '*.conf')
        new_conf = '{result}\n\n[include]\nfiles = {files}\n'.format(**locals())
        put_string(new_conf, '/etc/supervisord.conf', use_sudo=True)

        # make sure the directory exists.
        result = sudo('mkdir -p {0}'.format(cfg().supervisord_include_conf))
        if result.failed:
            raise HaltError('Unable to create include dir: "{0}"'.format(cfg().supervisord_include_conf))

        # finally write an init-script to /etc/init.d so supervisord gets run at startup.
        # TODO: write system-dependent script using "uname -s": OSX=Darwin, Amazon Linux AMI=Linux, ??
        put_string(_INIT_SCRIPT_LINUX, '/etc/init.d/supervisor', use_sudo=True, mode=00755)

        # the Amazon Linux AMI uses chkconfig; the init.d script won't do the job by itself.
        # set supervisord so it can be managed by chkconfig; and turn on boot startup.
        # ubuntu (and Debian?) use UpStart or update-rc.d, so check them out.
        result = run('which chkconfig')
        if result.succeeded:
            message('System has chkconfig; configuring.')
            result = sudo('chkconfig --add supervisor')
            if result.failed:
                raise HaltError('"chkconfig --add supervisor" failed.')

            result = sudo('chkconfig supervisor on')
            if result.failed:
                raise HaltError('"chkconfig supervisor on" failed.')

        succeed_msg('"supervisord" is installed ({0}).'.format(result))
        return self

    def write_config(self, name, cmd, dir=None, log_root=None, env=None):
        """
        Writes a supervisor [program] entry to a "conf" file.

        The conf file is named "<name>.conf", and is located in the directory identified by:
        cfg().supervisord_include_conf

        Calling this function is typically followed soon after by a call to reload_config().

        :param name:
            specifies the program name.

        :param cmd:
            specifies the command to start the program.

        :param dir:
            specifies the directory to chdir to before executing command. default: no chdir.

        :param log_root:
            specifies the location for supervisor log file.
            default is 'logs' in the deployment root directory.

        :param env:
            specifies the child process environment. default: None.
        """
        start_msg('----- Writing supervisor conf file for "{0}":'.format(name))
        if dir is None: dir = ''
        if env is None: env = ''
        if not log_root:
            log_root = path.join(cfg().deploy_root, 'logs')

        # first be sure the log directory exists. if not supervisor will fail to load the config.
        result = sudo('mkdir -p {0}'.format(log_root))
        if result.failed:
            raise HaltError('Unable to create log directory: "{0}"'.format(log_root))

        # now write the entry.
        entry = (
            "[program:{name}]\n"
            "command={cmd}\n"
            "directory={dir}\n"
            "user=nobody\n"
            "autostart=true\n"
            "autorestart=true\n"
            "stdout_logfile={log_root}/supervisord.log\n"
            "redirect_stderr=True\n"
            "environment={env}\n".format(**locals()))

        dest = path.join(cfg().supervisord_include_conf, '{name}.conf'.format(**locals()))
        message('Writing to file: "{0}"'.format(dest))
        put_string(entry, dest, use_sudo=True)
        succeed_msg('Wrote conf file for "{0}".'.format(name))
        return self

    def delete_config(self, name):
        """
        Deletes a program entry previously written by write_program_config().

        :param name: specifies the program name used with write_program_config().
        :return: None
        """
        start_msg('----- Removing supervisor program entry for "{0}":'.format(name))
        dest = path.join(cfg().supervisord_include_conf, '{name}.conf'.format(**locals()))
        result = sudo('rm -f {dest}'.format(**locals()))
        if result.failed:
            raise HaltError('Unable to remove entry.')
        succeed_msg('Removed successfully.')
        return self

    def reload(self):
        """
        Tells supervisor to reload it's configuration. This method is normally used after writing
        or deleting program entries to update the currently running supervisord.

        :param name: identifies the program whose config should be activated. if none, no action is taken.
        :return: None
        """
        start_msg('----- Telling supervisor to reread configuration:')
        result = sudo('supervisorctl update')
        if result.failed or 'error' in result.lower():
            raise HaltError('"supervisorctl update" failed ({0}).'.format(result))
        succeed_msg('Successfully reloaded.')
        return self

    def start(self, name):
        """
        Starts monitoring the specified program.

        The write_program_config() function should have been called previously. This function will
        cause supervisor to reread its configuration, then it will add the specified program to
        the list of active programs.

        :param name: identifies the program name (same as that used with write_program_config()).
        :return: None
        """
        start_msg('----- Starting supervisord monitoring of "{0}":'.format(name))

        # reload configuration so supervisord knows about the program, then start monitoring.
        self.reload()
        result = sudo('supervisorctl add {0}'.format(name))
        if result.failed:
            raise HaltError('Failed to add "{0}" to supervisor.'.format(name))
        succeed_msg('Monitoring of "{0}" started.'.format(name))
        return self

    def stop_and_remove(self, name):
        """
        Stops monitoring the specified program.

        Stops monitoring, removes the program from the list of active programs, removes the programs
        config file using delete_program_config(), then causes supervisord to reread configuration.

        :param name: identifies the progra name (same as that used with write_program_config()).
        :return: None
        """
        start_msg('----- Stopping supervisord monitoring and removing program "{0}":'.format(name))

        # tell supervisord to stop and remove the program.
        result = sudo('supervisorctl stop {0}'.format(name))
        if result.failed:
            message('Ignoring "supervisorctl stop {0}" failure ({1})'.format(name, result))
        result = sudo('supervisorctl remove {0}'.format(name))
        if result.failed:
            message('Ignoring "supervisorctl remove {0}" failure ({1})'.format(name, result))

        # remove the program from configuration and reload.
        self.delete_config(name).reload()
        succeed_msg('Stopped monitoring and removed program "{0}".'.format(name))
        return self

    def get_status(self, name):
        """
        Returns the supervisor status for the specified program.

        :param name: name of the program (same as that used with write_program_config()).
        :return: status string (e.g., 'RUNNING', 'FATAL')
        """
        result = sudo('supervisorctl status {0}'.format(name))
        if result.failed:
            raise HaltError('Unable to get status for "{0}".'.format(name))
        return result.strip().split()[1]

    def wait_until_running(self, name, tries=3, wait=2):
        """
        Waits until the specific supervisor program has a running status or has failed.

        :param name: name of the program (same as that used with write_program_config()).
        :param tries: number of times to check status.
        :param wait: initial wait time between status checks.

        Given the name of a supervisord process, tell you whether it's running
        or not.  If status is 'starting', will wait until status has settled.
        # Status return from supervisorctl will look something like this::
        # mysite_20110623_162319 RUNNING    pid 628, uptime 0:34:13
        # mysite_20110623_231206 FATAL      Exited too quickly (process log may have details)
        """
        try:
            status = self.get_status(name)
        except HaltError:
            status = 'EXCEPTION'

        if status == 'RUNNING':
            succeed_msg('Found "RUNNING" status for program "{0}".'.format(name))
            return True
        elif status == 'FATAL':
            failed_msg('Program seems to have failed.')
            return False
        elif status == 'EXCEPTION':
            failed_msg('Unable to get program status; assuming it failed.')
            return False

        if tries > 0:
            message('Status({name})="{status}", waiting: tries={tries}, wait={wait}.'.format(**locals()))
            time.sleep(wait)
            return self.wait_until_running(name, tries-1, wait*2)

        failed_msg('Did not see a "RUNNING" status for program "{0}"; assuming it failed.'.format(name))
        return False


# register.
Tool.__tools__['supervisord'] = SupervisorTool

_INIT_SCRIPT_LINUX = """
#!/bin/sh
# Amazon Linux AMI startup script for a supervisor instance
#
# chkconfig: 2345 80 20
# description: Autostarts supervisord.

# Source function library.
. /etc/rc.d/init.d/functions

supervisorctl="/usr/bin/supervisorctl"
supervisord="/usr/bin/supervisord"
name="supervisor-python"

[ -f $supervisord ] || exit 1
[ -f $supervisorctl ] || exit 1

RETVAL=0

start() {
    echo -n "Starting $name: "
    $supervisord
    RETVAL=$?
    echo
    return $RETVAL
}

stop() {
    echo -n "Stopping $name: "
    $supervisorctl shutdown
    RETVAL=$?
    echo
    return $RETVAL
}

case "$1" in
     start)
        start
        ;;

    stop)
        stop
        ;;

    restart)
        stop
        start
        ;;
esac

exit $RETVAL
""".lstrip()

_INIT_SCRIPT_UBUNTU = """
#! /bin/sh
#
# skeleton	example file to build /etc/init.d/ scripts.
#		This file should be used to construct scripts for /etc/init.d.
#
#		Written by Miquel van Smoorenburg <miquels@cistron.nl>.
#		Modified for Debian
#		by Ian Murdock <imurdock@gnu.ai.mit.edu>.
#               Further changes by Javier Fernandez-Sanguino <jfs@debian.org>
#
# Version:	@(#)skeleton  1.9  26-Feb-2001  miquels@cistron.nl
#
### BEGIN INIT INFO
# Provides:          supervisor
# Required-Start:    $remote_fs $network $named
# Required-Stop:     $remote_fs $network $named
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Start/stop supervisor
# Description:       Start/stop supervisor daemon and its configured
#                    subprocesses.
### END INIT INFO


PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
DAEMON=/usr/bin/supervisord
NAME=supervisord
DESC=supervisor

test -x $DAEMON || exit 0

LOGDIR=/var/log/supervisor
PIDFILE=/var/run/$NAME.pid
DODTIME=5                   # Time to wait for the server to die, in seconds
                            # If this value is set too low you might not
                            # let some servers to die gracefully and
                            # 'restart' will not work

# Include supervisor defaults if available
if [ -f /etc/default/supervisor ] ; then
	. /etc/default/supervisor
fi

set -e

running_pid()
{
    # Check if a given process pid's cmdline matches a given name
    pid=$1
    name=$2
    [ -z "$pid" ] && return 1
    [ ! -d /proc/$pid ] &&  return 1
    (cat /proc/$pid/cmdline | tr "\000" "\n"|grep -q $name) || return 1
    return 0
}

running()
{
# Check if the process is running looking at /proc
# (works for all users)

    # No pidfile, probably no daemon present
    [ ! -f "$PIDFILE" ] && return 1
    # Obtain the pid and check it against the binary name
    pid=`cat $PIDFILE`
    running_pid $pid $DAEMON || return 1
    return 0
}

force_stop() {
# Forcefully kill the process
    [ ! -f "$PIDFILE" ] && return
    if running ; then
        kill -15 $pid
        # Is it really dead?
        [ -n "$DODTIME" ] && sleep "$DODTIME"s
        if running ; then
            kill -9 $pid
            [ -n "$DODTIME" ] && sleep "$DODTIME"s
            if running ; then
                echo "Cannot kill $LABEL (pid=$pid)!"
                exit 1
            fi
        fi
    fi
    rm -f $PIDFILE
    return 0
}

case "$1" in
  start)
	echo -n "Starting $DESC: "
	start-stop-daemon --start --quiet --pidfile $PIDFILE \
		--exec $DAEMON -- $DAEMON_OPTS
	test -f $PIDFILE || sleep 1
        if running ; then
            echo "$NAME."
        else
            echo " ERROR."
        fi
	;;
  stop)
	echo -n "Stopping $DESC: "
	start-stop-daemon --stop --quiet --oknodo --pidfile $PIDFILE
	echo "$NAME."
	;;
  force-stop)
	echo -n "Forcefully stopping $DESC: "
        force_stop
        if ! running ; then
            echo "$NAME."
        else
            echo " ERROR."
        fi
	;;
  #reload)
	#
	#	If the daemon can reload its config files on the fly
	#	for example by sending it SIGHUP, do it here.
	#
	#	If the daemon responds to changes in its config file
	#	directly anyway, make this a do-nothing entry.
	#
	# echo "Reloading $DESC configuration files."
	# start-stop-daemon --stop --signal 1 --quiet --pidfile \
	#	/var/run/$NAME.pid --exec $DAEMON
  #;;
  force-reload)
	#
	#	If the "reload" option is implemented, move the "force-reload"
	#	option to the "reload" entry above. If not, "force-reload" is
	#	just the same as "restart" except that it does nothing if the
	#   daemon isn't already running.
	# check wether $DAEMON is running. If so, restart
	start-stop-daemon --stop --test --quiet --pidfile \
		/var/run/$NAME.pid --exec $DAEMON \
	&& $0 restart \
	|| exit 0
	;;
  restart)
    echo -n "Restarting $DESC: "
	start-stop-daemon --stop --quiet --pidfile \
		/var/run/$NAME.pid --exec $DAEMON
	[ -n "$DODTIME" ] && sleep $DODTIME
	start-stop-daemon --start --quiet --pidfile \
		/var/run/$NAME.pid --exec $DAEMON -- $DAEMON_OPTS
	echo "$NAME."
	;;
  status)
    echo -n "$LABEL is "
    if running ;  then
        echo "running"
    else
        echo " not running."
        exit 1
    fi
    ;;
  *)
	N=/etc/init.d/$NAME
	# echo "Usage: $N {start|stop|restart|reload|force-reload}" >&2
	echo "Usage: $N {start|stop|restart|force-reload|status|force-stop}" >&2
	exit 1
	;;
esac

exit 0
""".lstrip()

