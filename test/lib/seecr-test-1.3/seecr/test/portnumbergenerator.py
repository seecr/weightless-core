## begin license ##
# 
# "Seecr Test" provides test tools. 
# 
# Copyright (C) 2012 Seecr (Seek You Too B.V.) http://seecr.nl
# 
# This file is part of "Seecr Test"
# 
# "Seecr Test" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# "Seecr Test" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with "Seecr Test"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# 
## end license ##

from socket import socket, SO_LINGER, SOL_SOCKET, SO_REUSEADDR
from struct import pack
from time import sleep

class PortNumberGenerator(object):
    _ephemeralPortLow, _ephemeralPortHigh = [int(p) for p in open('/proc/sys/net/ipv4/ip_local_port_range', 'r').read().strip().split('\t', 1)]  # low\thigh
    _maxTries = (_ephemeralPortHigh - _ephemeralPortLow) / 2
    _usedPorts = set([])

    @classmethod
    def next(cls):
        for i in range(cls._maxTries):
            sok = socket()
            sok.setsockopt(SOL_SOCKET, SO_LINGER, pack('ii', 0, 0))
            sok.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            sok.bind(('127.0.0.1', 0))
            ignoredHost, port = sok.getsockname()
            sok.close()
            if port not in cls._usedPorts:
                cls._usedPorts.add(port)
                return port

        raise RuntimeError('Not been able to get an new uniqe free port within a reasonable amount (%s) of tries.' % cls._maxTries)

