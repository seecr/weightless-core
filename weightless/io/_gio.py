## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2009 Seek You Too (CQ2) http://www.cq2.nl
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
from functools import partial as curry
import os
from socket import SOL_SOCKET, SO_RCVBUF, SHUT_RDWR
from weightless.core import compose, local

class Gio(object):
    def __init__(self, reactor, generator):
        self._reactor = reactor
        self._generator = compose(generator)
        self._contextstack = []
        self._callback2generator = compose(self.callback2generator())
        self._callback2generator.next()

    def __repr__(self):
        return repr(self._generator)

    def close(self):
        #self._generator.throw(Exception('premature close'))
        pass

    def callback2generator(self):
        __gio__ = self
        message = None
        response = None
        while True:
            if not response:
                try:
                    response = self._generator.send(message)
                except StopIteration:
                    yield #'return' without StopIteration
            try:
                assert self._contextstack, 'Gio: No context available.'
                context = self._contextstack[-1]
                if response:
                    yield context.write(response)
                    message = None
                else:
                    message = yield context.read()
                    if message == '': # peer closed connection
                        try:
                            response = self._generator.throw(CloseException())
                        except CloseException:
                            yield
                        finally:
                            context.close()
                response = None
            except TimeoutException, e:
                response = self._generator.throw(e)

    def throw(self, exception):
        try:
            return self._callback2generator.throw(exception)
        except exception.__class__:
            pass

    def pushContext(self, context):
        self._contextstack.append(context)

    def popContext(self):
        self._contextstack.pop()

    def addWriter(self, context):
        self._reactor.addWriter(context, self._callback2generator.next)

    def removeWriter(self, context):
        self._reactor.removeWriter(context)

    def addReader(self, context):
        self._reactor.addReader(context, self._callback2generator.next)

    def removeReader(self, context):
        self._reactor.removeReader(context)

    def addTimer(self, time, timeout):
        return self._reactor.addTimer(time, timeout)

    def removeTimer(self, timer):
        self._reactor.removeTimer(timer)

class Context(object):

    def __enter__(self):
        self.gio = local('__gio__')
        self.gio.pushContext(self)
        return self

    def __exit__(self, type, value, traceback):
        self.gio.popContext()
        if type == GeneratorExit:
            self._onExit()
            return True

    def onExit(self, method):
        self._onExit = method

    def __repr__(self):
        return 'Context (most recent call last):' + repr(self.gio)

    def close(self):
        self.gio.close()

class FdContext(Context):

    def __init__(self, fd):
        Context.__init__(self)
        assert type(fd) == int
        self._fd = fd

    def fileno(self):
        return self._fd

    def close(self):
        Context.close(self)
        os.close(self._fd)

    def write(self,response):
        self.gio.addWriter(self)
        self.onExit(curry(self.gio.removeWriter, self))
        buff = response
        try:
            while len(buff) > 0:
                yield
                written = os.write(self._fd, buff)
                buff = buffer(buff, written)
        finally:
            self.gio.removeWriter(self)

    def read(self):
        self.gio.addReader(self)
        self.onExit(curry(self.gio.removeReader, self))
        try:
            yield
            message = os.read(self._fd, self.readBufSize)
        finally:
            self.gio.removeReader(self)
        raise StopIteration(message)

class SocketContext(FdContext):

    def __init__(self, sok):
        self.readBufSize = sok.getsockopt(SOL_SOCKET, SO_RCVBUF) / 2
        sok.setblocking(0)
        FdContext.__init__(self, sok.fileno())
        self._save_sok_from_gc = sok
        self.shutdown = sok.shutdown

class FileContext(FdContext):

    def __init__(self, uri, mode='r'):
        flags = 'w' in mode and os.O_RDWR or os.O_RDONLY
        f = os.open(uri, flags | os.O_NONBLOCK)
        self.readBufSize = os.fstat(f).st_blksize
        FdContext.__init__(self, f)

def open(*args, **kwargs):
    return FileContext(*args, **kwargs)

class TimeoutException(Exception):
    pass

class CloseException(Exception):
    pass

class Timer(object):

    def __init__(self, timeout):
        self.gio = local('__gio__')
        self._timeout = timeout
        self._timer = None

    def __enter__(self):
        self._timer = self.gio.addTimer(self._timeout, self._timedOut)

    def __exit__(self, *args, **kwargs):
        if self._timer:
            self.gio.removeTimer(self._timer)
            self._timer = None

    def _timedOut(self):
        self._timer = None
        self.gio.throw(TimeoutException())
