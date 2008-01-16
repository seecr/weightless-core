## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2008 Seek You Too (CQ2) http://www.cq2.nl
#
#    This file is part of Weightless
#
#    Weightless is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    Weightless is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Weightless; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##
from socket import SOL_SOCKET, SO_RCVBUF
from weightless import compose
import os

python_open = open

class Gio(object):

    def __init__(self, reactor, eventGenerator):
        self._eventGenerator = compose(eventGenerator)
        self.reactor = reactor
        self.next(None)

    def next(self, value):
        try:
            event = self._eventGenerator.send(value)
            event.initialize(self)
        except StopIteration:
            pass

    def error(self, exception):
        #event = self._eventGenerator.throw(exception)
        #event.initialize(self)
        pass

class open(object):

    def __init__(self, uri, mode='r'):
        self._uri = uri
        self._mode = mode

    def initialize(self, gio):
        try:
            self._sok = python_open(self._uri, self._mode)
            #self._recvSize = self._sok.getsockopt(SOL_SOCKET, SO_RCVBUF) / 2 # kernel reports twice the useful size
            self._recvSize = 4096
            gio.next(self)
        except IOError, e:
            gio.error(e)

    def read(self):
        return _read(self)

    def write(self, data):
        return _write(self, data)

    def close(self):
        return _close(self)

class _read(object):

    def __init__(self, sok):
        self._sok = sok

    def initialize(self, gio):
        self._gio = gio
        self._gio.reactor.addReader(self._sok._sok, self._doread)

    def _doread(self):
        self._gio.reactor.removeReader(self._sok._sok)
        self._gio.next(os.read(self._sok._sok.fileno(), self._sok._recvSize))

class _write(object):

    def __init__(self, sok, data):
        self._sok = sok
        self._data = data

    def initialize(self, gio):
        self._gio = gio
        self._gio.reactor.addWriter(self._sok._sok, self._dowrite)

    def _dowrite(self):
        self._gio.reactor.removeWriter(self._sok._sok)
        self._gio.next(self._sok._sok.write(self._data))

class _close(object):

    def __init__(self, sok):
        self._sok = sok

    def initialize(self, gio):
        gio.next(self._sok._sok.close())
