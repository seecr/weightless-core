## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2010-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012, 2015 Seecr (Seek You Too B.V.) http://seecr.nl
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
from sys import exc_info
from traceback import print_exc

from . import TimeoutException


class Suspend(object):
    def __init__(self, doNext=lambda this: None, timeout=None, onTimeout=None):
        self._doNext = doNext
        if (timeout is None) != (onTimeout is None):
            raise ValueError('Either both or neither of timeout and onTimeout must be set.')
        self._timeout = timeout
        self._onTimeout = onTimeout
        self._exception = None
        self._settled = False
        self._timer = None

    def __call__(self, reactor, whenDone):
        self._reactor = reactor
        try:
            self._doNext(self)
        except (AssertionError, KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self._exception = exc_info()
            print_exc()
        else:
            self._whenDone = whenDone
            if self._timeout is not None:
                self._timer = self._reactor.addTimer(seconds=self._timeout, callback=self._timedOut)
            self._handle = reactor.suspend()

    def resume(self, response=None):
        if self._settled:
            raise AssertionError('Suspend already settled.')
        if self._timer is not None:
            self._reactor.removeTimer(token=self._timer)

        self._response = response
        self._settled = True
        self._whenDone()

    def throw(self, exc_type, exc_value=None, exc_traceback=None):
        """Accepts either a full exception triple or only a single exception instance (not encouraged as it loses traceback information)."""
        if self._settled:
            raise AssertionError('Suspend already settled.')
        if self._timer is not None:
            self._reactor.removeTimer(token=self._timer)

        if exc_value is None and exc_traceback is None:
            self._exception = type(exc_type), exc_type, None
        else:
            self._exception = (exc_type, exc_value, exc_traceback)
        self._settled = True
        self._whenDone()

    def resumeReader(self):
        if hasattr(self, "_handle"):
            self._reactor.resumeReader(self._handle)

    def resumeWriter(self):
        if hasattr(self, "_handle"):
            self._reactor.resumeWriter(self._handle)

    def resumeProcess(self):
        if hasattr(self, "_handle"):
            self._reactor.resumeProcess(self._handle)

    def getResult(self):
        if self._exception:
            c, v, t = self._exception
            v = v if v else c()
            raise v.with_traceback(t)
        return self._response

    def _timedOut(self):
        self._timer = None
        try:
            self._onTimeout()
        except (AssertionError, KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            sys.stderr.write("Unexpected exception raised on Suspend's onTimeout callback (ignored):\n")
            print_exc()
        self.throw(TimeoutException, TimeoutException(), None)

