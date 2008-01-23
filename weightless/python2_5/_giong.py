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
from functools import partial as curry
import os
from time import time

def _get__socketstack__():
    frame = currentframe().f_back
    while frame and '__socketstack__' not in frame.f_locals:
        frame = frame.f_back
    if frame:
        return frame.f_locals['__socketstack__']

class Gio(object):

    def __init__(self, reactor, processor):
        self._processor = compose(processor)
        self._reactor = reactor
        self.__socketstack__ = []
        self._step(None)

    def _step(self, message):
        __socketstack__ = self.__socketstack__
        try:
            self._response = self._processor.send(message)
        except StopIteration:
                return
        sok = __socketstack__[-1]
        if self._response:
            self._reactor.addWriter(sok, curry(self._write, sok))
        else:
            self._reactor.addReader(sok, curry(self._read, sok))

    def _write(self, sok):
        self._reactor.removeWriter(sok)
        t0 = time()
        written = os.write(sok, self._response) # + MSG_DONTWAIT
        print 'Wrote %s of %s bytes in %s ms.' % (written, len(self._response), (time()-t0)*1000)
        self._step(None)

    def _read(self, sok):
        self._reactor.removeReader(sok)
        message = os.read(sok, os.fstat(sok).st_blksize)
        self._step(message)

class open(object):

    def __init__(self, uri, mode='r'):
        flags = os.O_NONBLOCK | os.O_RDWR
        self._sok = os.open(uri, flags)

    def __enter__(self, *args):
        _get__socketstack__().append(self._sok)
        return self

    def __exit__(self, type, value, traceback):
        if type == GeneratorExit:
            pass
        stack = _get__socketstack__()
        if stack:
            stack.pop()