# -*- coding: utf-8 -*-
## begin license ##
# 
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io 
# 
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
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

from traceback import print_exc
from select import select, error
from time import time
from errno import EBADF, EINTR
from weightless.core import local

def reactor():
    return local('__reactor__')


class Context(object):
    def __init__(self, callback, prio):
        if prio is None:
            prio = Reactor.DEFAULTPRIO
        if not 0 <= prio < Reactor.MAXPRIO:
            raise ValueError('Invalid priority: %s' % prio)

        self.callback = callback
        self.prio = prio


class Timer(Context):
    def __init__(self, seconds, callback):
        Context.__init__(self, callback, Reactor.DEFAULTPRIO)
        assert seconds >= 0, 'Timeout must be >= 0. It was %s.' % seconds
        self.time = time() + seconds

    def __cmp__(self, rhs):
        if not rhs:
            return 1
        return cmp(self.time, rhs.time)


class Reactor(object):
    """This Reactor allows applications to be notified of read, write or time events.  The callbacks being executed can contain instructions to modify the reader, writers and timers in the reactor.  Additions of new events are effective with the next step() call, removals are effective immediately, even if the actual event was already trigger, but the handler wat not called yet."""

    MAXPRIO = 10
    DEFAULTPRIO = 0

    def __init__(self, select_func = select):
        self._readers = {}
        self._writers = {}
        self._suspended = {}
        self._processes = {}
        self._timers = []
        self._select = select_func
        self._prio = -1

    def addReader(self, sok, sink, prio=None):
        """Adds a socket and calls sink() when the socket becomes readable. It remains at the readers list."""
        if sok in self._suspended:
            raise ValueError('Socket is suspended')
        self._readers[sok] = Context(sink, prio)

    def addWriter(self, sok, source, prio=None):
        """Adds a socket and calls source() whenever the socket is writable. It remains at the writers list."""
        if sok in self._suspended:
            raise ValueError('Socket is suspended')
        self._writers[sok] = Context(source, prio)

    def addProcess(self, process, prio=None):
        if process in self._suspended:
            raise ValueError('Process is suspended')
        if process in self._processes:
            raise ValueError('Process is already in processes')
        self._processes[process] = Context(process, prio)

    def addTimer(self, seconds, callback):
        """Add a timer that calls callback() after the specified number of seconds. Afterwards, the timer is deleted.  It returns a token for removeTimer()."""
        timer = Timer(seconds, callback)
        self._timers.append(timer)
        self._timers.sort()
        return timer

    def removeReader(self, sok):
        del self._readers[sok]

    def removeWriter(self, sok):
        del self._writers[sok]

    def removeProcess(self, process=None):
        if process is None:
            process = self.currentcontext.callback
        del self._processes[process]

    def removeTimer(self, token):
        self._timers.remove(token)

    def cleanup(self, sok):
        self._writers.pop(sok, None)
        self._readers.pop(sok, None)
        self._suspended.pop(sok, None)

    def suspend(self):
        self._readers.pop(self.currenthandle, None)
        self._writers.pop(self.currenthandle, None)
        self._processes.pop(self.currenthandle, None)
        self._suspended[self.currenthandle] = self.currentcontext
        return self.currenthandle

    def resumeReader(self, handle):
        self._readers[handle] = self._suspended.pop(handle)

    def resumeWriter(self, handle):
        self._writers[handle] = self._suspended.pop(handle)

    def resumeProcess(self, handle):
        self._processes[handle] = self._suspended.pop(handle)

    def shutdown(self):
        for contextDict in [
            self._readers, 
            self._writers, 
            self._processes, 
            self._suspended
        ]:
            for handle in contextDict.keys():
                contextDict.pop(handle)
                if hasattr(handle, 'close'):
                    print 'Reactor shutdown: closing', handle
                    handle.close()
                else:
                    print 'Reactor shutdown: terminating %s' % handle

    def loop(self):
        try:
            while True:
                self.step()
        finally:
            self.shutdown()

    def step(self):
        __reactor__ = self

        self._prio = (self._prio + 1) % Reactor.MAXPRIO
        if self._timers:
            timeout = max(0, self._timers[0].time - time())
        else:
            timeout = None

        if self._processes:
            timeout = 0

        try:
            rReady, wReady, ignored = self._select(self._readers.keys(), self._writers.keys(), [], timeout)
        except TypeError:
            print_exc()
            self._findAndRemoveBadFd()
            return self
        except error, (errno, description):
            print_exc()
            if errno == EBADF:
                self._findAndRemoveBadFd()
            elif errno == EINTR:
                pass
            else:
                raise
            return self
        except KeyboardInterrupt:
            self.shutdown()
            raise


        self._timerCallbacks(self._timers)
        self._callbacks(rReady, self._readers)
        self._callbacks(wReady, self._writers)
        self._processCallbacks(self._processes)

        return self

    def getOpenConnections(self):
        return len(self._readers) + len(self._writers)

    def _callbacks(self, ready, soks):
        for self.currenthandle in ready:
            if self.currenthandle in soks:
                context = soks[self.currenthandle]
                if context.prio <= self._prio:
                    self.currentcontext = context
                    try:
                        context.callback()
                    except (AssertionError, SystemExit, KeyboardInterrupt):
                        if self.currenthandle in soks:
                            del soks[self.currenthandle]
                        raise
                    except:
                        print_exc()
                        if self.currenthandle in soks:
                            del soks[self.currenthandle]

    def _timerCallbacks(self, timers):
        currentTime = time()
        for timer in timers[:]:
            if timer.time > currentTime:
                break
            self.currentcontext = timer
            self.removeTimer(timer)
            try:
                timer.callback()
            except (AssertionError, SystemExit, KeyboardInterrupt):
                raise
            except:
                print_exc()

    def _processCallbacks(self, processes):
        for self.currenthandle, context in processes.items():
            if context.prio <= self._prio:
                self.currentcontext = context
                try:
                    context.callback()
                except:
                    if self.currenthandle in processes:
                        del processes[self.currenthandle]
                    raise

    def _findAndRemoveBadFd(self):
        for sok in self._readers:
            try:
                select([sok], [], [], 0)
            except:
                del self._readers[sok]
                return
        for sok in self._writers:
            try:
                select([], [sok], 0)
            except:
                del self._writers[sok]
                return

