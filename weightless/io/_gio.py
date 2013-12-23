## begin license ##
# 
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io 
# 
# Copyright (C) 2006-2009 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012 Seecr (Seek You Too B.V.) http://seecr.nl
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

from functools import partial as curry
import os
from socket import SOL_SOCKET, SO_RCVBUF, SHUT_RDWR
from weightless.core import compose, local

class InitialContext(object):
    def handle(self, response, generator):
        try:
            response = generator.next()
            #print "================", response
        except StopIteration:
            yield
        #print "Main thread about to be finished?????"
        raise StopIteration(response)

class Gio(object):
    def __init__(self, reactor, generator):
        self._reactor = reactor
        self._generator = compose(generator)
        self._contextstack = [InitialContext()]
        self._callback2generator = compose(self.callback2generator())
        self._callback2generator.next()

    def __repr__(self):
        return repr(self._generator)

    def close(self):
        #self._generator.throw(Exception('premature close'))
        pass

    def __call__(self):
        self._callback2generator.next()

    def callback2generator(self):
        __gio__ = self
        __reactor__ = self._reactor
        response = None
        while True:
            assert self._contextstack, 'Gio: No context available.'
            context = self._contextstack[-1]
            response = yield context.handle(response, self._generator)
            #print "context", response

    def throw(self, exception):
        try:
            return self._callback2generator.throw(exception)
        except exception.__class__:
            pass

    def pushContext(self, context):
        self._contextstack.append(context)

    def popContext(self):
        self._contextstack.pop()

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

class ThreadContext(Context):

    def __enter__(self):
        from threading import Thread
        super(ThreadContext, self).__enter__()
        self._thread = Thread(target=self.wrap)
        print "__enter__ created thread", self._thread
        return self

    def wrap(self):
        self._p()
        print "warp: Thread done: ", self._thread
        # after this, the last Context must continue... how?
        # the last context ran the the previous thread

    def __exit__(self, ex_type, ex_value, ex_tb):
        super(ThreadContext, self).__exit__(ex_type, ex_value, ex_tb)
        print "__exit__ thread", self._thread

    def handle(self, response, generator):
        print "handle start thread", self._thread
        self._p = generator.next
        self._thread.start()
        yield

class FdContext(Context):

    def __init__(self, fd):
        Context.__init__(self)
        assert type(fd) == int
        self._fd = fd
        self._msg = None

    def __enter__(self):
        super(FdContext, self).__enter__()
        self.reactor = local("__reactor__")
        return self

    def fileno(self):
        return self._fd

    def close(self):
        Context.close(self)
        os.close(self._fd)

    def write(self,response):
        self.reactor.addWriter(self, self.gio)
        self.onExit(curry(self.reactor.removeWriter, self))
        buff = response
        try:
            while len(buff) > 0:
                yield
                written = os.write(self._fd, buff)
                buff = buffer(buff, written)
        finally:
            self.reactor.removeWriter(self)

    def read(self):
        self.reactor.addReader(self, self.gio)
        self.onExit(curry(self.reactor.removeReader, self))
        try:
            yield
            message = os.read(self._fd, self.readBufSize)
        finally:
            self.reactor.removeReader(self)
        raise StopIteration(message)

    def handle(self, response, generator):
        try:
            if response:
                yield self.write(response)
                self._message = None
            else:
                self._message = yield self.read()
                if self._message == '': # peer closed connection
                    try:
                        response = generator.throw(CloseException())
                    except CloseException:
                        yield
                    finally:
                        self.close()
            response = None
        except TimeoutException, e:
            response = generator.throw(e)
        if not response:
            try:
                response = generator.send(self._message)
            except StopIteration:
                yield #'return' to reactor
            raise StopIteration(response)

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
