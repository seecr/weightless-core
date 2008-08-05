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
from traceback import print_exc
from inspect import currentframe
from select import select, error
from time import time
from errno import EBADF, EINTR
import os

def reactor():
    frame = currentframe().f_back
    while '__reactor__' not in frame.f_locals:
        frame = frame.f_back
    return frame.f_locals['__reactor__']

class Timer(object):
    def __init__(self, seconds, callback):
        assert seconds >= 0, 'Timeout must be >= 0. It was %s.' % seconds
        self.time = time() + seconds
        self.callback = callback

    def __cmp__(self, rhs):
        if not rhs:
            return 1
        return cmp(self.time, rhs.time)

    def __eq__(self, other):
        return other and \
                other.__class__ == Timer and \
                other.time == self.time and \
                other.callback == self.callback

class Reactor(object):
    """This Reactor allows applications to be notified of read, write or time events.  The callbacks being executed can contain instructions to modify the reader, writers and timers in the reactor.  Additions of new events are effective with the next step() call, removals are effective immediately, even if the actual event was already trigger, but the handler wat not called yet."""

    MAXPRIO = 10
    DEFAULTPRIO = 1

    def __init__(self, select_func = select):
        self._readers = {}
        self._writers = {}
        self._timers = []
        self._select = select_func
        self._prio = 0

    def addReader(self, sok, sink, prio=None):
        """Adds a socket and calls sink() when the socket becomes readable. It remains at the readers list."""
        if not prio:
            prio = Reactor.DEFAULTPRIO
        if not 0 <= prio < Reactor.MAXPRIO:
            raise ValueError('Invalid priority: %s' % prio)
        self._readers[sok] = (sink, prio)

    def addWriter(self, sok, source, prio=1):
        """Adds a socket and calls source() whenever the socket is writable. It remains at the writers list."""
        self._writers[sok] = (source, prio)

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

    def removeTimer(self, token):
        self._timers.remove(token)

    def shutdown(self):
        for sok in self._readers: sok.close()
        for sok in self._writers: sok.close()

    def loop(self):
        try:
            while True:
                self.step()
        finally:
            self.shutdown()

    def step(self):
        __reactor__ = self

        aTimerTimedOut = False
        self._prio = (self._prio + 1) % Reactor.MAXPRIO
        if self._timers:
            timeout = max(0, self._timers[0].time - time())
        else:
            timeout = None

        try:
            rReady, wReady, ignored = self._select(self._readers.keys(), self._writers.keys(), [], timeout)
        except TypeError:
            print_exc()
            self._findAndRemoveBadFd()
            return
        except error, (errno, description):
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

        for timer in self._timers:
            if timer.time > time():
                break
            try:
                timer.callback()
            except AssertionError:
                raise
            except:
                print_exc()
            finally:
		del self._timers[0]

        self._callback(rReady, self._readers)
        self._callback(wReady, self._writers)

        return self

    def _callback(self, ready, soks):
        for sok in ready:
            if sok in soks:
                try:
                    __callback__, prio = soks[sok]
                    if prio <= self._prio:
                        __callback__()
                except AssertionError:
                    raise
                except:
                    print_exc()
                    if sok in soks:
                        del soks[sok]

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

