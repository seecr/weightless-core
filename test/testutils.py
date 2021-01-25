## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2015, 2020-2021 Seecr (Seek You Too B.V.) https://seecr.nl
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
from contextlib import contextmanager

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

@contextmanager
def clientget(host, port, path):
    client = socket()
    client.connect((host,  port))
    request = 'GET {} HTTP/1.1\r\n\r\n'.format(path)
    client.send(request.encode())
    try:
        yield client
    finally:
        client.close()

def traceback_co_names(tb):
    names = []
    cursor = tb
    while not cursor is None:
        names.append(cursor.tb_frame.f_code.co_name)
        cursor = cursor.tb_next
    return names


_current_handler = [_default_handler]
