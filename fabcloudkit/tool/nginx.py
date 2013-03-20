"""
    fabcloudkit

    Functions for managing Nginx.

    This module provides functions that check for installation, install, and manage an
    installation of, Nginx.

    /etc/init.d/nginx:
        The "init-script" that allows Nginx to be run automatically at system startup.
        The existence of this file is verified, but it's assumed that the script is
        installed by the package manager that installed Nginx.

    /etc/nginx/nginx.conf:
        The main or root Nginx configuration file. This file is loaded by Nginx when
        it launches. The file contains an include directive that tells Nginx to
        load additional configurations from a different directory.

        Currently, this code writes a very basic nginx.conf file.

    /etc/nginx/conf.d/:
        The directory marked by the include directive in the nginx root configuration
        file. Individual server configurations are stored in files in this folder.

    /etc/nginx/conf.g/*.conf:
        Individual server configuration files.

    <deploy_root>/<name>/logs/ngaccess.log, ngerror.log:
        Default location of the access (ngaccess.log) and error (ngerror.log) log files
        for a specific server configuration. This location can be overridden in the call
        to write_server_config().

    For more information on Nginx check out: http://nginx.org, http://wiki.nginx.org

    :copyright: (c) 2013 by Rick Bohrer.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import

# standard
import posixpath as path

# pypi
from fabric.operations import run, sudo

# package
from fabcloudkit import cfg, put_string
from ..internal import *
from ..toolbase import Tool, SimpleTool


class NginxTool(Tool):
    def __init__(self):
        super(NginxTool,self).__init__()
        self._simple = SimpleTool.create('nginx')

    def check(self, **kwargs):
        return self._simple.check()

    def install(self, **kwargs):
        # install Nginx using the package manager.
        self._simple.install()

        start_msg('----- Configuring "Nginx":')
        # verify that there's an init-script.
        result = run('test -f /etc/init.d/nginx')
        if result.failed:
            raise HaltError('Uh oh. Package manager did not install an Nginx init-script.')

        # write nginx.conf file.
        dest = path.join(cfg().nginx_conf, 'nginx.conf')
        message('Writing "nginx.conf"')
        put_string(_NGINX_CONF, dest, use_sudo=True)

        # the Amazon Linux AMI uses chkconfig; the init.d script won't do the job by itself.
        # set Nginx so it can be managed by chkconfig; and turn on boot startup.
        result = run('which chkconfig')
        if result.succeeded:
            message('System has chkconfig; configuring.')
            result = sudo('chkconfig --add nginx')
            if result.failed:
                raise HaltError('"chkconfig --add nginx" failed.')

            result = sudo('chkconfig nginx on')
            if result.failed:
                raise HaltError('"chkconfig nginx on" failed.')

        succeed_msg('Successfully installed and configured "Nginx".')
        return self

    def write_config(self, name, server_names, proxy_pass, static_locations='', log_root=None, listen=80):
        """
        Writes an Nginx server configuration file.

        This function writes a specific style of configuration, that seems to be somewhat common, where
        Nginx is used as a reverse-proxy for a locally-running (e.g., WSGI) server.

        :param name: identifies the server name; used to name the configuration file.
        :param server_names:
        :param proxy_pass: identifies the local proxy to which Nginx will pass requests.
        """
        start_msg('----- Writing Nginx server configuration for "{0}":'.format(name))

        # be sure the log directory exists.
        if log_root is None:
            log_root = path.join(cfg().deploy_root, name, 'logs')
        result = sudo('mkdir -p {0}'.format(log_root))
        if result.failed:
            raise HaltError('Unable to create log directory: "{0}"'.format(log_root))

        # generate and write the configuration file.
        server_config = _NGINX_SERVER_CONF.format(**locals())
        dest = path.join(cfg().nginx_include_conf, '{name}.conf'.format(**locals()))
        message('Writing to file: "{0}"'.format(dest))
        put_string(server_config, dest, use_sudo=True)

        succeed_msg('Wrote conf file for "{0}".'.format(name))
        return self

    def delete_config(self, name):
        start_msg('----- Deleting server configuration for "{0}":'.format(name))

        # delete the file, but ignore any errors.
        config_name = '{name}.conf'.format(**locals())
        result = sudo('rm -f {0}'.format(path.join(cfg().nginx_include_conf, config_name)))
        if result.failed:
            failed_msg('Ignoring failed attempt to delete configuration "{0}"'.format(config_name))
        else:
            succeed_msg('Successfully deleted configuration "{0}".'.format(config_name))
        return self

    def reload(self):
        start_msg('----- Telling "Nginx" to reload configuration:')
        result = sudo('/etc/init.d/nginx reload')
        if result.failed:
            raise HaltError('"Nginx" configuration reload failed ({0})'.format(result))
        succeed_msg('Successfully reloaded.')
        return self


# register.
Tool.__tools__['nginx'] = NginxTool

_NGINX_SERVER_CONF = """
server {{
    listen   {listen};
    server_name {server_names};

    access_log  {log_root}/ngaccess.log;
    error_log  {log_root}/ngerror.log;
    location / {{
        proxy_pass {proxy_pass};
        proxy_redirect              off;
        proxy_set_header            Host $host;
        proxy_set_header            X-Real-IP $remote_addr;
        proxy_set_header            X-Forwarded-For $proxy_add_x_forwarded_for;
        client_max_body_size        10m;
        client_body_buffer_size     128k;
        proxy_connect_timeout       90;
        proxy_send_timeout          90;
        proxy_read_timeout          90;
        proxy_buffer_size           4k;
        proxy_buffers               4 32k;
        proxy_busy_buffers_size     64k;
        proxy_temp_file_write_size  64k;
    }}
    {static_locations}
}}
""".lstrip()

_NGINX_CONF = """
user  nginx;
worker_processes  1;
error_log  /var/log/nginx/error.log;
pid        /var/run/nginx.pid;
events {
    worker_connections  1024;
}
http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                      '$status $body_bytes_sent "$http_referer" '
                      '"$http_user_agent" "$http_x_forwarded_for"';

    access_log  /var/log/nginx/access.log  main;
    sendfile        on;
    keepalive_timeout  65;

    include /etc/nginx/conf.d/*.conf;
}
""".lstrip()
