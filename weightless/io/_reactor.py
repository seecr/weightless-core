# -*- coding: utf-8 -*-
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2015 Seecr (Seek You Too B.V.) http://seecr.nl
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
from select import epoll, error as select_error
from select import EPOLLIN, EPOLLOUT, EPOLLPRI, EPOLLERR, EPOLLHUP, EPOLLET, EPOLLONESHOT, EPOLLRDNORM, EPOLLRDBAND, EPOLLWRNORM, EPOLLWRBAND, EPOLLMSG
from socket import error as socket_error
from time import time
from errno import EBADF, EINTR, EEXIST, ENOENT
from weightless.core import local
from os import pipe, close, write, read
import sys   # HCK

def reactor():
    return local('__reactor__')


class _FDContext(object):  # TS: TODO: Document Interface.
    def __init__(self, callback, fileOrFd, intent, prio):
        if prio is None:
            prio = Reactor.DEFAULTPRIO
        if not 0 <= prio < Reactor.MAXPRIO:
            raise ValueError('Invalid priority: %s' % prio)

        self.callback = callback
        self.fileOrFd = fileOrFd
        self.intent = intent
        self.prio = prio


class _ProcessContext(object):  # TS: TODO: Document Interface.
    def __init__(self, callback, prio):
        if prio is None:
            prio = Reactor.DEFAULTPRIO
        if not 0 <= prio < Reactor.MAXPRIO:
            raise ValueError('Invalid priority: %s' % prio)

        self.callback = callback
        self.prio = prio


class Timer(object):  # TS: TODO: Document Interface.
    def __init__(self, seconds, callback):
        assert seconds >= 0, 'Timeout must be >= 0. It was %s.' % seconds
        self.callback = callback
        if seconds > 0:
            seconds = seconds + EPOLL_TIMEOUT_GRANULARITY  # Otherwise seconds when (EPOLL_TIMEOUT_GRANULARITY > seconds > 0) is effectively 0(.0)
        self.time = time() + seconds


class Reactor(object):
    """This Reactor allows applications to be notified of read, write or time events.  The callbacks being executed can contain instructions to modify the reader, writers and timers in the reactor.  Additions of new events are effective with the next step() call, removals are effective immediately, even if the actual event was already trigger, but the handler wat not called yet."""

    MAXPRIO = 10
    DEFAULTPRIO = 0

    def __init__(self):
        self._epoll = epoll()
        self._fds = {}  # TS: TODO: Document Interface.
        self._badFdsLastCallback = []  # TS: TODO: Document Interface.
        self._suspended = {}
        self._processes = {}
        self._timers = []
        self._prio = -1
        self._processReadPipe, self._processWritePipe = pipe()
        self._epoll.register(fd=self._processReadPipe, eventmask=EPOLLIN)

    def addReader(self, sok, sink, prio=None):
        """Adds a socket and calls sink() when the socket becomes readable. It remains at the readers list."""
        if sok in self._suspended:
            raise ValueError('Socket is suspended')
        self._addFD(fileOrFd=sok, callback=sink, intent=READ_INTENT, prio=prio)

    def addWriter(self, sok, source, prio=None):
        """Adds a socket and calls source() whenever the socket is writable. It remains at the writers list."""
        if sok in self._suspended:
            raise ValueError('Socket is suspended')
        self._addFD(fileOrFd=sok, callback=source, intent=WRITE_INTENT, prio=prio)

    def addProcess(self, process, prio=None):
        if process in self._suspended:
            raise ValueError('Process is suspended')
        if process in self._processes:
            raise ValueError('Process is already in processes')
        self._processes[process] = _ProcessContext(process, prio)
        self._writeProcessPipe()

    def addTimer(self, seconds, callback):
        """Add a timer that calls callback() after the specified number of seconds. Afterwards, the timer is deleted.  It returns a token for removeTimer()."""
        timer = Timer(seconds, callback)
        self._timers.append(timer)
        self._timers.sort(key=_timeKey)
        return timer

    def _addFD(self, fileOrFd, callback, intent, prio, fdContext=None):
        print '_addFD'
        context = fdContext or _FDContext(callback, fileOrFd, intent, prio)
        try:
            fd = _fdNormalize(fileOrFd)
            if fd in self._fds:
                # Otherwise epoll would give an IOError, Errno 17 / EEXIST.
                raise ValueError('fd already registered')  # TS: TODO: Document Interface.
            if intent is READ_INTENT:  # TODO: Refactor if..elif..else+assert to 1x inline if..else for speed!
                eventmask = EPOLLIN
            elif intent is WRITE_INTENT:
                eventmask = EPOLLOUT
            else:
                raise AssertionError('Unknown intent %s' % (repr(intent)))
            self._epollRegister(fd=fd, eventmask=eventmask)
        except _HandleEBADFError:
            self._badFdsLastCallback.append(context)
        except TypeError:
            print_exc()  # Roughly same "whatever" behaviour of 'old.
            self._badFdsLastCallback.append(context)
        else:
            print '_addFD :: ok; fd:', fd
            self._fds[fd] = context

    def _removeFD(self, fileOrFd):
        try:
            fd = _fdNormalize(fileOrFd)
        except _HandleEBADFError:
            self._cleanFdsByFileObj(fileOrFd)  # TODO: TESTME
            return

        del self._fds[fd]
        try:
            self._epoll.unregister(fd)
        except TypeError:
            print_exc()  # Roughly same "whatever" behaviour of 'old.
        except IOError, (errno, description):
            print_exc()
            if errno == ENOENT or errno == EBADF:  # Already gone (epoll's EBADF automagical cleanup).
                pass  # TODO: TESTME
            else:
                raise

    def _cleanFdsByFileObj(self, obj):
        for handle, context in self._fds.items():
            if context.fileOrFd == obj:
                del self._fds[handle]

    def _cleanSuspendedByFileObj(self, obj):
        for handle, context in self._suspended.items():
            if hasattr(context, 'fileOrFd') and context.fileOrFd == obj:
                del self._suspended[handle]

    def _epollRegister(self, fd, eventmask):
        try:
            self._epoll.register(fd=fd, eventmask=eventmask)
        except IOError, (errno, description):
            print_exc()
            if errno == EBADF:
                raise _HandleEBADFError()
            raise

    def removeReader(self, sok):
        self._removeFD(fileOrFd=sok)

    def removeWriter(self, sok):
        self._removeFD(fileOrFd=sok)

    def removeProcess(self, process=None):
        if process is None:
            process = self.currentcontext.callback
        del self._processes[process]
        self._readProcessPipe()

    def removeTimer(self, token):
        self._timers.remove(token)

    def cleanup(self, sok):
        # Only use for Reader/Writer's!  TS: TODO: Document Interface.
        try:
            fd = _fdNormalize(sok)
        except _HandleEBADFError:
            self._cleanFdsByFileObj(fileOrFd)  # TODO: TESTME
            self._cleanSuspendedByFileObj(fileOrFd)  # TODO: TESTME
        else:
            self._fds.pop(fd, None)
            self._suspended.pop(fd, None)

    def suspend(self):
        if self.currenthandle is None:
            raise RuntimeError('suspend called from a timer or when running a last-call callback for a bad file-descriptor.')  # TS: TODO: Document Interface.

        if self.currenthandle in self._fds:
            # FIXME: testme.
            self._removeFD(fileOrFd=self.currenthandle)
        elif self._processes.pop(self.currenthandle, None) is not None:  # TS: FIXME: fd "0" would not have worken (stdin); does work now.
            self._readProcessPipe()
        else:
            # TS: TODO: Document Interface & Can give error i.s.o. b"ad action."
            raise RuntimeError('Current context not found!')
        self._suspended[self.currenthandle] = self.currentcontext
        return self.currenthandle

    def resumeReader(self, handle):
        context = self._suspended.pop(handle)
        self._addFD(fileOrFd=context.fileOrFd, callback=context.callback, intent=READ_INTENT, prio=context.prio, fdContext=context)

    def resumeWriter(self, handle):
        context = self._suspended.pop(handle)
        self._addFD(fileOrFd=context.fileOrFd, callback=context.callback, intent=WRITE_INTENT, prio=context.prio, fdContext=context)

    def resumeProcess(self, handle):
        self._processes[handle] = self._suspended.pop(handle)
        self._writeProcessPipe()

    def shutdown(self):
        # Will be called exactly once; in testing situations 1..n times.
        for contextDict in [
            self._fds,
            self._suspended
        ]:
            for handle, context in contextDict.items():
                contextDict.pop(handle)
                obj = context.fileOrFd if hasattr(context, 'fileOrFd') else context.callback
                if hasattr(obj, 'close'):
                    print 'Reactor shutdown: closing', obj
                    obj.close()
                else:  # TS: TODO: elif isinstance(handle, int): os.close(handle) ... something.
                    print 'Reactor shutdown: terminating %s' % handle

        for handle in self._processes.keys():
            self._processes.pop(handle)
            if hasattr(handle, 'close'):
                print 'Reactor shutdown: closing', handle
                handle.close()
            else:  # TS: TODO: elif isinstance(handle, int): os.close(handle) ... something.
                print 'Reactor shutdown: terminating %s' % handle
        del self._badFdsLastCallback[:]
        self._closeProcessPipe()
        self._epoll.close()

    def loop(self):
        try:
            while True:
                self.step()
        finally:
            self.shutdown()

    def step(self):
        __reactor__ = self

        if self._badFdsLastCallback:
            print ">>> PROCESSING _lastCallbacks()"; sys.stdout.flush()  # HCK
            self._lastCallbacks()
            return self

        self._prio = (self._prio + 1) % Reactor.MAXPRIO
        if self._timers:
            timeout = max(0, self._timers[0].time - time())
        else:
            timeout = -1

        try:
            fdEvents = self._epoll.poll(timeout=timeout)
            print '>>> afet poll; step:', fdEvents, timeout
        except (IOError, socket_error), (errno, description):  # Removed select_error (source: select module - only IOError can occur).
            # TS: FIXME: can socket_error be removed also???  (THINK SO: sok.fileno() can give socket_error (EBADF); .poll() does not call that).
            print_exc()
            #if errno == EBADF:            <-------+
            #    self._findAndRemoveBadFd()        |
            if errno == EINTR:  # was: "elif:" of -+
                pass
            else:
                raise
            return self
        except KeyboardInterrupt:
            self.shutdown()  # For testing purposes; normally loop's finally does this.
            raise

        self._timerCallbacks(self._timers)
        self._callbacks(fdEvents, self._fds, READ_INTENT)
        self._callbacks(fdEvents, self._fds, WRITE_INTENT)
        self._processCallbacks(self._processes)

        return self

    def getOpenConnections(self):
        return len(self._fds)

    def _lastCallbacks(self):
        while self._badFdsLastCallback:
            context = self._badFdsLastCallback.pop()
            self.currenthandle = None
            self.currentcontext = context
            try:
                self.currentcontext.callback()
            except (AssertionError, SystemExit, KeyboardInterrupt):
                raise
            except:
                print_exc()

    def _callbacks(self, fdEvents, fds, intent):
        print '>>> _callbacks'
        # @@ TODO: Fix multiple handling of one event !!!!!
        for fd, eventmask in fdEvents:
            print '>>> _callbacks :: (fd, intent)', (fd, intent)
            if fd == self._readProcessPipe:
                print '>>> _callbacks :: Nah 1...'
                continue

            try:
                context = fds[fd]
            except KeyError:
                print '>>> _callbacks :: Nah 2...'
                continue

            if context.intent is not intent:
                print '>>> _callbacks :: Nah 3...'
                continue

            if context.prio <= self._prio:
                self.currenthandle = fd
                self.currentcontext = context
                try:
                    print '>>> _callbacks :: context.callback() PRE'
                    context.callback()
                    print '>>> _callbacks :: context.callback() POST'
                except (AssertionError, SystemExit, KeyboardInterrupt):
                    if self.currenthandle in fds:
                        del fds[self.currenthandle]
                    raise
                except:
                    print_exc()
                    if self.currenthandle in fds:
                        del fds[self.currenthandle]

    def _timerCallbacks(self, timers):
        currentTime = time()
        for timer in timers[:]:
            if timer.time > (currentTime + EPOLL_TIMEOUT_GRANULARITY):
                break
            if timer not in timers:
                continue
            self.currenthandle = None
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
            if self.currenthandle in processes and context.prio <= self._prio:
                self.currentcontext = context
                try:
                    context.callback()
                except:
                    if self.currenthandle in processes:
                        del processes[self.currenthandle]
                    raise

    #def _findAndRemoveBadFd(self):
    #    for sok in self._readers:
    #        try:
    #            select([sok], [], [], 0)
    #        except Exception:
    #            self._readers.pop(sok).callback()
    #            return
    #    for sok in self._writers:
    #        try:
    #            select([], [sok], 0)
    #        except Exception:
    #            self._writers.pop(sok).callback()
    #            return

    def _closeProcessPipe(self):
        # Will be called exactly once; in testing situations 1..n times.
        try:
            close(self._processReadPipe)
        except Exception:
            pass
        try:
            close(self._processWritePipe)
        except Exception:
            pass
        self._processReadPipe = None
        self._processWritePipe = None

    def _readProcessPipe(self):
        read(self._processReadPipe, 1)

    def _writeProcessPipe(self):
        write(self._processWritePipe, 'x')

    def __enter__(self):
        "Usable as a context-manager for testing purposes"
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Assumes .step() is used to drive the reactor;
        so having an exception here does not mean shutdown has been called.
        """
        self.shutdown()
        return False


def _fdNormalize(fd):
    if hasattr(fd, 'fileno'):
        try:
            return fd.fileno()
        except (IOError, OSError, socket_error), (errno, description):
            print_exc()
            if errno == EBADF:
                raise _HandleEBADFError()
            raise

    return fd


class _HandleEBADFError(Exception):
    pass


_timeKey = lambda t: t.time

READ_INTENT = type('READ', (object,), {})()
WRITE_INTENT = type('READ', (object,), {})()

# In Python 2.7 - anything lower than 0.001 will become 0(.0); epoll.poll() may (and will IRL) return early - see: https://bugs.python.org/issue20311 (Python 3.x differs in behaviour :-s).
# TS: If this granularity (& related logic) is unwanted - start using timerfd_* system-calls.
EPOLL_TIMEOUT_GRANULARITY = 0.001

EPOLLRDHUP = int('0x2000', 16)
_EPOLL_CONSTANT_MAPPING = {  # Python epoll constants (missing EPOLLRDHUP - exists since Linux 2.6.17))
    EPOLLIN: 'EPOLLIN',            # Available for read
    EPOLLOUT: 'EPOLLOUT',          # Available for write
    EPOLLRDHUP: 'EPOLLRDHUP',  # (Exists since Linux 2.6.17, see Linux's: man epoll_ctl; and glibc / libc6-dev: sys/epoll.h)
                                      # Stream socket peer closed connection, or shut down writing half
                                      # of connection.  (This flag  is especially useful for writing
                                      # simple code to detect peer shutdown when using Edge Triggered
                                      # monitoring.)
    EPOLLPRI: 'EPOLLPRI',          # Urgent data for read
    # Note: just don't send socket data with the MSG_OOB flag specified and this will never happen. - TCP Out-of-Band communication is a bit of a protocol relic (though TELNET and FTP might use it (allowed by spec), decent people don't :-).
    EPOLLERR: 'EPOLLERR',          # Error condition happened on the assoc. fd
                                   # EPOLLERR and EPOLLHUP: will always be waited for, does not need to be specified in the eventmask (see Linux's: man epoll_ctl).
    EPOLLHUP: 'EPOLLHUP',          # Hang up happened on the assoc. fd
    EPOLLET: 'EPOLLET',            # Set Edge Trigger behavior, the default is Level Trigger behavior
    EPOLLONESHOT: 'EPOLLONESHOT',  # Set one-shot behavior. After one event is pulled out, the fd is internally disabled

    #
    # Don't use below here, please.

    # ...When compiling with _XOPEN_SOURCE defined... which convey no further information beyond the bits listed above ...  (see Linux's: man poll)
    EPOLLRDNORM: 'EPOLLRDNORM',    # Equivalent to EPOLLIN
    EPOLLRDBAND: 'EPOLLRDBAND',    # Priority data band can be read.
    EPOLLWRNORM: 'EPOLLWRNORM',    # Equivalent to EPOLLOUT
    EPOLLWRBAND: 'EPOLLWRBAND',    # Priority data may be written.

    # Linux ignores 'POLLMSG' (see Linux's: man poll)
    EPOLLMSG: 'EPOLLMSG',          # Ignored.
}

EPOLL_IN_ERR_HUP_COMBINED = EPOLLIN | EPOLLERR | EPOLLHUP

