# The contents of this file are subject to the MonetDB Public License
# Version 1.1 (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
# http://www.monetdb.org/Legal/MonetDBLicense
#
# Software distributed under the License is distributed on an "AS IS"
# basis, WITHOUT WARRANTY OF ANY KIND, either express or implied. See the
# License for the specific language governing rights and limitations
# under the License.
#
# The Original Code is the MonetDB Database System.
#
# The Initial Developer of the Original Code is CWI.
# Portions created by CWI are Copyright (C) 1997-July 2008 CWI.
# Copyright August 2008-2015 MonetDB B.V.
# All Rights Reserved.

import platform
from datetime import datetime as dt
from monetdb import mapi
from monetdb.exceptions import OperationalError, InterfaceError


def parse_statusline(line):
    """
    parses a sabdb format status line. Support v1 and v2.

    """
    if line.startswith("="):
        line = line[1:]
    if not line.startswith('sabdb:'):
        raise OperationalError('wrong result recieved')

    code, prot_version, rest = line.split(":", 2)

    if prot_version not in ["1", "2"]:
        raise InterfaceError("unsupported sabdb protocol")
    else:
        prot_version = int(prot_version)

    subparts = rest.split(',')
    sub_iter = iter(subparts)

    info = {}

    info['name'] = next(sub_iter)
    info['path'] = next(sub_iter)
    info['locked'] = next(sub_iter) == "1"
    info['state'] = int(next(sub_iter))
    info['scenarios'] = next(sub_iter).split("'")
    if prot_version == 1:
        next(sub_iter)
    info['start_counter'] = int(next(sub_iter))
    info['stop_counter'] = int(next(sub_iter))
    info['crash_counter'] = int(next(sub_iter))
    info['avg_uptime'] = int(next(sub_iter))
    info['max_uptime'] = int(next(sub_iter))
    info['min_uptime'] = int(next(sub_iter))
    last_crash = int(next(sub_iter))
    info['last_crash'] = dt.fromtimestamp(int(last_crash)) if last_crash >= 0 else None
    info['last_start'] = dt.fromtimestamp(int(next(sub_iter)))
    if prot_version > 1:
        value = int(next(sub_iter))
        if value > -1:
            info['last_stop'] = dt.fromtimestamp(value)
        else:
            info['last_stop'] = None
    info['crash_avg1'] = next(sub_iter) == "1"
    info['crash_avg10'] = float(next(sub_iter))
    info['crash_avg30'] = float(next(sub_iter))

    return info


def isempty(result):
    """ raises an exception if the result is not empty"""
    if result != "":
        raise OperationalError(result)
    else:
        return True


class Control:
    """
    Use this module to manage your MonetDB databases. You can create, start,
    stop, lock, unlock, destroy your databases and request status information.
    """
    def __init__(self, hostname=None, port=50000, passphrase=None,
                 unix_socket=None):

        if not unix_socket:
            unix_socket = "/tmp/.s.merovingian.%i" % port

        if platform.system() == "Windows" and not hostname:
            hostname = "localhost"

        self.server = mapi.Connection()
        self.hostname = hostname
        self.port = port
        self.passphrase = passphrase
        self.unix_socket = unix_socket

        # check connection
        self.server.connect(hostname=hostname, port=port, username='monetdb',
                            password=passphrase,
                            database='merovingian', language='control',
                            unix_socket=unix_socket)
        self.server.disconnect()

    def _send_command(self, database_name, command):
        self.server.connect(hostname=self.hostname, port=self.port,
                            username='monetdb', password=self.passphrase,
                            database='merovingian', language='control',
                            unix_socket=self.unix_socket)
        try:
            return self.server.cmd("%s %s\n" % (database_name, command))
        finally:
            # always close connection
            self.server.disconnect()

    def create(self, database_name):
        """
        Initialises a new database or multiplexfunnel in the MonetDB Server.
        A database created with this command makes it available  for use,
        however in maintenance mode (see monetdb lock).
        """
        return isempty(self._send_command(database_name, "create"))

    def destroy(self, database_name):
        """
        Removes the given database, including all its data and
        logfiles.  Once destroy has completed, all data is lost.
        Be careful when using this command.
        """
        return isempty(self._send_command(database_name, "destroy"))

    def lock(self, database_name):
        """
        Puts the given database in maintenance mode.  A database
        under maintenance can only be connected to by the DBA.
        A database which is under maintenance is not started
        automatically.  Use the "release" command to bring
        the database back for normal usage.
        """
        return isempty(self._send_command(database_name, "lock"))

    def release(self, database_name):
        """
        Brings back a database from maintenance mode.  A released
        database is available again for normal use.  Use the
        "lock" command to take a database under maintenance.
        """
        return isempty(self._send_command(database_name, "release"))

    def status(self, database_name=False):
        """
        Shows the state of a given glob-style database match, or
        all known if none given.  Instead of the normal mode, a
        long and crash mode control what information is displayed.
        """
        if database_name:
            raw = self._send_command(database_name, "status")
            return parse_statusline(raw)
        else:
            raw = self._send_command("#all", "status")
            return [parse_statusline(line) for line in raw.split("\n")]

    def start(self, database_name):
        """
        Starts the given database, if the MonetDB Database Server
        is running.
        """
        return isempty(self._send_command(database_name, "start"))

    def stop(self, database_name):
        """
        Stops the given database, if the MonetDB Database Server
        is running.
        """
        return isempty(self._send_command(database_name, "stop"))

    def kill(self, database_name):
        """
        Kills the given database, if the MonetDB Database Server
        is running.  Note: killing a database should only be done
        as last resort to stop a database.  A database being
        killed may end up with data loss.
        """
        return isempty(self._send_command(database_name, "kill"))

    def set(self, database_name, property_, value):
        """
        sets property to value for the given database
        for a list of properties, use `monetdb get all`
        """
        return isempty(self._send_command(database_name, "%s=%s" % (property_,
                                                                    value)))

    def get(self, database_name):
        """
        gets value for property for the given database, or
        retrieves all properties for the given database
        """
        properties = self._send_command(database_name, "get")
        values = {}
        for line in properties.split("\n"):
            if line.startswith("="):
                line = line[1:]
            if not line.startswith("#"):
                if "=" in line:
                    split = line.split("=")
                    values[split[0]] = split[1]
        return values

    def inherit(self, database_name, property_):
        """
        unsets property, reverting to its inherited value from
        the default configuration for the given database
        """
        return isempty(self._send_command(database_name, property_ + "="))

    def rename(self, old, new):
        return self.set(old, "name", new)

    def defaults(self):
        return self.get("#defaults")

    def neighbours(self):
        return self._send_command("anelosimus", "eximius")
