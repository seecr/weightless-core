## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2015 Seecr (Seek You Too B.V.) http://seecr.nl
#
# This file is part of "Weightless"
#
# "Weightless" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# "Weightless" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with "Weightless"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

from os import getpid, listdir
from signal import setitimer, ITIMER_REAL, signal, SIGALRM
from socket import socket


def nrOfOpenFds():
    pid = getpid()
    return len(listdir('/proc/%d/fd' % pid))

def readAndWritable():
    return socket()

def installTimeoutSignalHandler():
    previousHandler = signal(SIGALRM, _signalHandler)
    def revertTimeoutSignalHandler():
        signal(SIGALRM, previousHandler)
    return revertTimeoutSignalHandler

def setTimeout(seconds=0.002, callback=None):
    if callback is None:
        callback = _default_handler
    _current_handler[0] = callback
    setitimer(ITIMER_REAL, seconds)

def abortTimeout():
    setitimer(ITIMER_REAL, 0)

def _signalHandler(signum, frame):
    _current_handler[0]()

def _default_handler():
    raise BlockedCallTimedOut()


class BlockedCallTimedOut(Exception):
    pass

_current_handler = [_default_handler]

