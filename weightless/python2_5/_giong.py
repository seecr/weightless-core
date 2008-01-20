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
from weightless import compose
from inspect import currentframe

python_open = open

def _get__socketstack__():
    frame = currentframe().f_back
    while '__socketstack__' not in frame.f_locals:
        frame = frame.f_back
    return frame.f_locals['__socketstack__']

class Gio(object):

    def __init__(self, reactor, processor):
        self._processor = compose(processor)
        self._reactor = reactor
        self.__socketstack__ = []
        self._step(None)

    def _step(self, message):
        __socketstack__ = self.__socketstack__
        self._response = self._processor.send(message)
        if self._response:
            self._reactor.addWriter(__socketstack__[-1], self._write)
        else:
            self._reactor.addReader(__socketstack__[-1], self._read)

    def _write(self):
        self.__socketstack__[-1].send(self._response) # + MSG_DONTWAIT
        self._step(None)

    def _read(self):
        message = self.__socketstack__[-1].read(4096)
        self._step(message)

class open(object):

    def __init__(self, uri, mode='r'):
        self._sok = python_open(uri, mode)  # this MUST open/connect nonblocking

    def __enter__(self, *args):
        _get__socketstack__().append(self._sok)
        return self

    def __exit__(self, *args):
        _get__socketstack__().pop()