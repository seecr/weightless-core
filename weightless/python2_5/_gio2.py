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
from functools import partial as curry
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
        self._eventGenerator.throw(exception)

class AsyncDecorator(object):

    def __init__(self, generator):
        self._generator = generator
        generator.next()

    def initialize(self, gio):
        self._gio = gio
        try:
            self._generator.send(gio.reactor)(self.finalize)
        except Exception, e:
            gio.error(e)

    def finalize(self):
        self._generator.next()()
        response = self._generator.next()
        self._gio.next(response)

def asyncdecorator(func):
    def helper(*args, **kwargs):
        return AsyncDecorator(func(*args, **kwargs))
    return helper

@asyncdecorator
def open(uri, mode='r'):
    reactor = yield
    sok = Zocket(python_open(uri, mode))
    yield lambda x: x()
    yield lambda: None
    yield sok

class Zocket(object):

    def __init__(self, sok):
        self._sok = sok
        self._recvSize = 9999

    @asyncdecorator
    def read(self):
        reactor = yield
        yield curry(reactor.addReader, self._sok)
        yield curry(reactor.removeReader, self._sok)
        yield os.read(self._sok.fileno(), self._recvSize)

    @asyncdecorator
    def write(self, data):
        reactor = yield
        yield curry(reactor.addWriter, self._sok)
        yield curry(reactor.removeWriter, self._sok)
        yield self._sok.write(data)

    @asyncdecorator
    def close(self):
        reactor = yield
        yield lambda x: x()
        yield lambda: None
        yield self._sok.close()
