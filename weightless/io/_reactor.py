# -*- coding: utf-8 -*-
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2016, 2020-2021 Seecr (Seek You Too B.V.) https://seecr.nl
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

import sys

import threading
from select import epoll
from select import EPOLLIN, EPOLLOUT, EPOLLPRI, EPOLLERR, EPOLLHUP, EPOLLET, EPOLLONESHOT, EPOLLRDNORM, EPOLLRDBAND, EPOLLWRNORM, EPOLLWRBAND, EPOLLMSG
from socket import error as socket_error
from time import time
from errno import EBADF, EINTR, ENOENT
from weightless.core import local
from os import pipe, close, write, read
from inspect import getsourcelines, getsourcefile
from sys import stderr
from traceback import print_exc

class Reactor(object):
    """This Reactor allows applications to be notified of read, write or time events.  The callbacks being executed can contain instructions to modify the reader, writers and timers in the reactor.  Additions of new events are effective with the next step() call, removals are effective immediately, even if the actual event was already trigger, but the handler wat not called yet."""

    MAXPRIO = 10
    DEFAULTPRIO = 0

    def __init__(self):
        self._epoll = epoll()
        self._fds = {}
        self._badFdsLastCallback = []
        self._suspended = {}
        self._running = {}
        self._timers = []
        self._prio = -1
        self._epoll_ctrl_read, self._epoll_ctrl_write = pipe()
        self._epoll.register(fd=self._epoll_ctrl_read, eventmask=EPOLLIN)

        # per (part-of) step relevent state
        self.currentcontext = None
        self.currenthandle = None
        self._removeFdsInCurrentStep = set()
        self._listening = threading.Lock()
        self._loop = True

    def addReader(self, sok, sink, prio=None):
        """Adds a socket and calls sink() when the socket becomes readable."""
        self._addFD(fileOrFd=sok, callback=sink, intent=READ_INTENT, prio=prio)

    def addWriter(self, sok, source, prio=None):
        """Adds a socket and calls source() whenever the socket is writable."""
        self._addFD(fileOrFd=sok, callback=source, intent=WRITE_INTENT, prio=prio)

    def addProcess(self, process, prio=None):
        """Adds a process and calls it repeatedly."""
        if process in self._suspended:
            raise ValueError('Process is suspended')
        if process in self._running:
            raise ValueError('Process is already in processes')
        self._running[process] = _ProcessContext(process, prio)
        self._wake_up()

    def addTimer(self, seconds, callback):
        """Add a timer that calls callback() after the specified number of seconds. Afterwards, the timer is deleted.  It returns a token for removeTimer()."""
        timer = Timer(seconds, callback)
        self._timers.append(timer)
        self._timers.sort(key=_timeKey)
        self._wake_up()
        return timer

    def removeReader(self, sok):
        self._removeFD(fileOrFd=sok)

    def removeWriter(self, sok):
        self._removeFD(fileOrFd=sok)

    def removeProcess(self, process=None):
        if process is None:
            process = self.currentcontext.callback
        if process in self._running:
            del self._running[process]
            return True

    def removeTimer(self, token):
        self._timers.remove(token)

    def cleanup(self, sok):
        # Only use for Reader/Writer's!
        try:
            fd = _fdNormalize(sok)
        except _HandleEBADFError:
            self._cleanFdsByFileObj(sok)
            self._cleanSuspendedByFileObj(sok)
        else:
            self._fds.pop(fd, None)
            self._suspended.pop(fd, None)
            self._epollUnregisterSafe(fd=fd)

    def suspend(self):
        if self.currenthandle is None:
            raise RuntimeError('suspend called from a timer or when running a last-call callback for a bad file-descriptor.')

        if self.currenthandle in self._fds:
            self._removeFD(fileOrFd=self.currenthandle)
        elif self.removeProcess(self.currenthandle):
            pass
        else:
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
        self._running[handle] = self._suspended.pop(handle)
        self._wake_up()

    def shutdown(self):
        # Will be called exactly once; in testing situations 1..n times.
        for contextDict, info in [
            (self._fds, 'active'),
            (self._suspended, 'suspended')
        ]:
            for handle, context in list(contextDict.items()):
                contextDict.pop(handle)
                obj = context.fileOrFd if hasattr(context, 'fileOrFd') else context.callback
                if hasattr(obj, 'close'):
                    print(_shutdownMessage(message='closing - %s' % info, thing=obj, context=context))
                    _closeAndIgnoreFdErrors(obj)
                else:
                    print(_shutdownMessage(message='terminating - %s' % info, thing=handle, context=context))

        for handle, context in list(self._running.items()):
            self._running.pop(handle)
            if hasattr(handle, 'close'):
                print(_shutdownMessage(message='closing - active', thing=handle, context=context))
                _closeAndIgnoreFdErrors(handle)
            else:
                print(_shutdownMessage(message='terminating - active', thing=handle, context=context))
        del self._badFdsLastCallback[:]
        self._close_epoll_ctrl()
        _closeAndIgnoreFdErrors(self._epoll)

    def request_shutdown(self):
        self._loop = False

    def loop(self):
        try:
            while self._loop:
                self.step()
        finally:
            self.shutdown()

    def step(self):
        __reactor__ = self

        if self._badFdsLastCallback:
            self._lastCallbacks()
            return self

        self._prio = (self._prio + 1) % Reactor.MAXPRIO

        with self._listening:
            if self._running:
                timeout = 0
            elif self._timers:
                timeout = min(max(0, self._timers[0].time - time()), MAX_TIMEOUT_EPOLL)
            else:
                timeout = -1

            try:
                fdEvents = self._epoll.poll(timeout=timeout)
            except IOError as e:
                (errno, description) = e.args
                _printException()
                if errno == EINTR:
                    pass
                else:
                    raise
                return self
            except KeyboardInterrupt:
                self.shutdown()  # For testing purposes; normally loop's finally does this.
                raise

        self._clear_epoll_ctrl(fdEvents)

        self._removeFdsInCurrentStep = set([self._epoll_ctrl_read])

        self._timerCallbacks(self._timers)
        self._callbacks(fdEvents, self._fds, READ_INTENT)
        self._callbacks(fdEvents, self._fds, WRITE_INTENT)
        self._processCallbacks(self._running)

        return self

    def getOpenConnections(self):
        return len(self._fds)

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

    def _addFD(self, fileOrFd, callback, intent, prio, fdContext=None):
        context = fdContext or _FDContext(callback, fileOrFd, intent, prio)
        try:
            fd = _fdNormalize(fileOrFd)
            if fd in self._fds:
                # Otherwise epoll would give an IOError, Errno 17 / EEXIST.
                raise ValueError('fd already registered')
            if fd in self._suspended:
                raise ValueError('Socket is suspended')

            eventmask = EPOLLIN if intent is READ_INTENT else EPOLLOUT  # Change iff >2 intents exist.
            self._epollRegister(fd=fd, eventmask=eventmask)
        except _HandleEBADFError:
            self._raiseIfFileObjSuspended(obj=fileOrFd)
            self._badFdsLastCallback.append(context)
        except TypeError:
            _printException()  # Roughly same "whatever" behaviour of 'old.
            self._badFdsLastCallback.append(context)
        else:
            self._fds[fd] = context

    def _removeFD(self, fileOrFd):
        try:
            fd = _fdNormalize(fileOrFd)
        except _HandleEBADFError:
            self._cleanFdsByFileObj(fileOrFd)
            return

        if fd in self._fds:
            del self._fds[fd]
            self._epollUnregister(fd=fd)

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
                _printException()

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
                _printException()

    def _callbacks(self, fdEvents, fds, intent):
        for fd, eventmask in fdEvents:
            if fd in self._removeFdsInCurrentStep:
                continue

            try:
                context = fds[fd]
            except KeyError:
                self._removeFdsInCurrentStep.add(fd)
                sys.stderr.write('[Reactor]: epoll event fd %d does not exist in fds list.\n' % fd)
                sys.stderr.flush()
                continue

            if context.intent is not intent:
                continue

            if context.prio <= self._prio:
                self.currenthandle = fd
                self.currentcontext = context
                try:
                    context.callback()
                except (AssertionError, SystemExit, KeyboardInterrupt):
                    if self.currenthandle in fds:
                        del fds[self.currenthandle]
                        self._epollUnregisterSafe(fd=self.currenthandle)
                    raise
                except:
                    _printException()
                    if self.currenthandle in fds:
                        del fds[self.currenthandle]
                        self._epollUnregisterSafe(fd=self.currenthandle)

    def _processCallbacks(self, processes):
        for self.currenthandle, context in list(processes.items()):
            if self.currenthandle in processes and context.prio <= self._prio:
                self.currentcontext = context
                try:
                    context.callback()
                except:
                    self.removeProcess(self.currenthandle)
                    raise

    def _epollRegister(self, fd, eventmask):
        try:
            self._epoll.register(fd=fd, eventmask=eventmask)
        except IOError as e:
            (errno, description) = e.args
            _printException()
            if errno == EBADF:
                raise _HandleEBADFError()
            raise

    def _epollUnregister(self, fd):
        self._removeFdsInCurrentStep.add(fd)
        try:
            self._epoll.unregister(fd)
        except IOError as e:
            (errno, description) = e.args
            _printException()
            if errno == ENOENT or errno == EBADF:  # Already gone (epoll's EBADF automagical cleanup); not reproducable in Python's epoll binding - but staying on the safe side.
                pass
            else:
                raise

    def _epollUnregisterSafe(self, fd):
        "Ignores the expected (ENOENT & EBADF) and unexpected exceptions from epoll_ctl / unregister"
        self._removeFdsInCurrentStep.add(fd)
        try:
            if fd != -1:
                self._epoll.unregister(fd)
        except IOError as e:
            # If errno is either ENOENT or EBADF than the fd is already gone (epoll's EBADF automagical cleanup); not reproducable in Python's epoll binding - but staying on the safe side.
            (errno, description) = e.args
            # If errno is either ENOENT or EBADF than the fd is already gone (epoll's EBADF automagical cleanup); not reproducable in Python's epoll binding - but staying on the safe side.
            if errno == ENOENT or errno == EBADF:
                pass
            else:
                _printException()

    def _clear_epoll_ctrl(self, fdEvents):
        if (self._epoll_ctrl_read, EPOLLIN) in fdEvents:
          while True:
            try:
                read(self._epoll_ctrl_read, 1)
                break
            except (IOError, OSError) as e:
                (errno, description) = e.args
                if errno == EINTR:
                    _printException()
                else:
                    raise

    def _wake_up(self):
        if self._listening.locked():
          while True:
            try:
                write(self._epoll_ctrl_write, b'x')
                break
            except (IOError, OSError) as e:
                (errno, description) = e.args
                if errno == EINTR:
                    _printException()
                else:
                    raise

    def _raiseIfFileObjSuspended(self, obj):
        for handle, context in list(self._suspended.items()):
            if hasattr(context, 'fileOrFd') and context.fileOrFd == obj:
                raise ValueError('Socket is suspended')

    def _cleanFdsByFileObj(self, obj):
        for fd, context in list(self._fds.items()):
            if context.fileOrFd == obj:
                del self._fds[fd]
                self._epollUnregisterSafe(fd=fd)

    def _cleanSuspendedByFileObj(self, obj):
        for handle, context in list(self._suspended.items()):
            if hasattr(context, 'fileOrFd') and context.fileOrFd == obj:
                del self._suspended[handle]

    def _close_epoll_ctrl(self):
        # Will be called exactly once; in testing situations 1..n times.
        try:
            close(self._epoll_ctrl_read)
        except Exception:
            pass
        try:
            close(self._epoll_ctrl_write)
        except Exception:
            pass
        self._epoll_ctrl_read = None
        self._epoll_ctrl_write = None

def _printException():
    print_exc()
    stderr.flush()

def reactor():
    return local('__reactor__')

class Timer(object):
    def __init__(self, seconds, callback):
        assert seconds >= 0, 'Timeout must be >= 0. It was %s.' % seconds
        self.callback = callback
        if seconds > 0:
            seconds = seconds + EPOLL_TIMEOUT_GRANULARITY  # Otherwise seconds when (EPOLL_TIMEOUT_GRANULARITY > seconds > 0) is effectively 0(.0)
        self.time = time() + seconds


class _FDContext(object):
    def __init__(self, callback, fileOrFd, intent, prio):
        if prio is None:
            prio = Reactor.DEFAULTPRIO
        if not 0 <= prio < Reactor.MAXPRIO:
            raise ValueError('Invalid priority: %s' % prio)

        self.callback = callback
        self.fileOrFd = fileOrFd
        self.intent = intent
        self.prio = prio


class _ProcessContext(object):
    def __init__(self, callback, prio):
        if prio is None:
            prio = Reactor.DEFAULTPRIO
        if not 0 <= prio < Reactor.MAXPRIO:
            raise ValueError('Invalid priority: %s' % prio)

        self.callback = callback
        self.prio = prio


def _fdNormalize(fd):
    if hasattr(fd, 'fileno'):
        try:
            fileno = fd.fileno()
            if fileno == -1:
                print("Reactor: Bad file descriptor {}".format(fd), file=sys.stderr, flush=True)
                raise _HandleEBADFError()
            return fileno
        except (IOError, OSError, socket_error) as e:
            (errno, description) = e.args
            _printException()
            if errno == EBADF:
                raise _HandleEBADFError()
            raise

    return fd

def _fdOrNone(fd):
    "Only use for info/debugging - supresses errors without logging."
    if hasattr(fd, 'fileno'):
        try:
            fileno = fd.fileno()
            return None if fileno == -1 else fileno
        except (IOError, OSError, socket_error):
            return None
    return fd

def _closeAndIgnoreFdErrors(obj):
    try:
        obj.close()
    except (IOError, OSError, socket_error) as e:
        # EBADF, EIO or EINTR -- non of which are really relevant in our shutdown.
        # For why re-trying after EINTR is not a good idea for close(), see:
        #   http://lwn.net/Articles/576478/
        (errno, description) = e.args
        _printException()

def _shutdownMessage(message, thing, context):
    details = [str(thing)]
    if isinstance(context, _FDContext):
        details.append('(fd)')
        fd = _fdOrNone(context.fileOrFd)
        if fd is not None:
            details.append('with fd: %s' % fd)
    else:  # _ProcessContext
        details.append('(process)')

    callback = context.callback
    details.append('with callback: %s' % callback)

    try:
        try:
            sourceLines = getsourcelines(callback)
        except TypeError:
            try:
                # generator-method?
                _cb = getattr(getattr(callback, '__self__', None), 'gi_code', None)
                sourceLines = getsourcelines(_cb)
                callback = _cb
            except TypeError:
                # Callable instance?
                callback = getattr(callback, '__call__', None)
                sourceLines = getsourcelines(callback)

        details.append('at: %s: %d: %s' % (
            getsourcefile(callback),
            sourceLines[1],     # Line number
            sourceLines[0][0].strip(),  # Source of the first relevant line
        ))
    except (IndexError, IOError, TypeError):
        # IOError / TypeError: inspect getsourcefile / sourcelines
        # IndexError: unexpected sourcelines datastructure
        pass

    return ('Reactor shutdown: %s: ' %  message) + ' '.join(details)


class _HandleEBADFError(Exception):
    pass


_timeKey = lambda t: t.time

READ_INTENT = type('READ_INTENT', (object,), {})()
WRITE_INTENT = type('WRITE_INTENT', (object,), {})()

# In Python 2.7 - anything lower than 0.001 will become 0(.0); epoll.poll() may (and will IRL) return early - see: https://bugs.python.org/issue20311 (Python 3.x differs in behaviour :-s).
# TS: If this granularity (& related logic) is unwanted - start using timerfd_* system-calls.
EPOLL_TIMEOUT_GRANULARITY = 0.001
MAX_INT_EPOLL = 2**31 -1
MAX_TIMEOUT_EPOLL = MAX_INT_EPOLL / 1000 - 1

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
