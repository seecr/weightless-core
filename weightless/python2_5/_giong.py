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
from weightless import compose_py as compose
from inspect import currentframe
from functools import partial as curry
import os
from time import time
from socket import SOL_SOCKET, SO_RCVBUF

def _get__contextstack__():
    frame = currentframe().f_back
    while frame and '__contextstack__' not in frame.f_locals:
        frame = frame.f_back
    if frame:
        return frame.f_locals['__contextstack__']

class Gio(object):

    def __init__(self, reactor, processor):
        self._processor = compose(processor)
        self._reactor = reactor
        self.__contextstack__ = []
        self._step(None)

    def _step(self, message):
        __contextstack__ = self.__contextstack__
        try:
            self._response = self._processor.send(message)
        except StopIteration:
            return
        context = __contextstack__[-1]
        if self._response:
            self._reactor.addWriter(context, curry(self._write, context))
        else:
            self._reactor.addReader(context, curry(self._read, context))

    def _write(self, context):
        written = os.write(context.fileno(), self._response)
        if written < len(self._response):
            self._response = buffer(self._response, written)
        else:
            self._reactor.removeWriter(context)
            self._step(None)

    def _read(self, context):
        self._reactor.removeReader(context)
        message = os.read(context.fileno(), context.readBufSize)
        self._step(message)

class FdContext(object):

    def __init__(self, fd):
        assert type(fd) == int
        self._fd = fd

    def fileno(self):
        return self._fd

    def __enter__(self, *args):
        _get__contextstack__().append(self)
        return self

    def __exit__(self, type, value, traceback):
        if type == GeneratorExit:
            pass
        stack = _get__contextstack__()
        if stack:
            stack.pop()

class zocket(FdContext):
    def __init__(self, sok):
        self.readBufSize = sok.getsockopt(SOL_SOCKET, SO_RCVBUF) / 2
        sok.setblocking(0)
        FdContext.__init__(self, sok.fileno())

class open(FdContext):
    def __init__(self, uri, mode='r'):
        flags = 'w' in mode and os.O_RDWR or os.O_RDONLY
        f = os.open(uri, flags | os.O_NONBLOCK)
        self.readBufSize = os.fstat(f).st_blksize
        FdContext.__init__(self, f)