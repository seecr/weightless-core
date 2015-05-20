# -*- coding: utf-8 -*-
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2010-2011 Seek You Too (CQ2) http://www.cq2.nl
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

from seecr.test import SeecrTestCase, CallTrace

from socket import SHUT_RDWR

from weightless.core import retval, be, Observable
from weightless.io import reactor
from weightless.io.utils import asProcess, sleep

from weightless.http import SocketPool


class SocketPoolTest(SeecrTestCase):
    ##
    ## Get & Put'ing
    def testGetOnEmptyPool(self):
        trace = CallTrace()
        sp = SocketPool(reactor=trace)
        self.assertEquals(None, retval(sp.getPooledSocket(host='x', port=1025)))
        self.assertEquals([], trace.calledMethodNames())

    def testPutThenGetThenEmpty(self):
        sp = SocketPool(reactor=CallTrace())
        result = retval(sp.putSocketInPool(host='x', port=1, sock='mock'))
        self.assertEquals(None, result)
        self.assertEquals('mock', retval(sp.getPooledSocket(host='x', port=1)))
        self.assertEquals(None, retval(sp.getPooledSocket(host='x', port=1)))

    def testPut3GetOnlyYours(self):
        sp = SocketPool(reactor=CallTrace())
        retval(sp.putSocketInPool(host='x', port=1, sock='A'))
        retval(sp.putSocketInPool(host='x', port=2, sock='B'))
        retval(sp.putSocketInPool(host='y', port=1, sock='C'))

        # Unknown host + port
        self.assertEquals(None, retval(sp.getPooledSocket(host='xx', port=1)))
        self.assertEquals(None, retval(sp.getPooledSocket(host='', port=1)))
        self.assertEquals(None, retval(sp.getPooledSocket(host=None, port=1)))
        self.assertEquals(None, retval(sp.getPooledSocket(host='x', port=0)))
        self.assertEquals(None, retval(sp.getPooledSocket(host='x', port=3)))

        # Retrieved once
        self.assertEquals('A', retval(sp.getPooledSocket(host='x', port=1)))

    def testPutNGetFIFO(self):
        sp = SocketPool(reactor=CallTrace())
        retval(sp.putSocketInPool(host='x', port=1, sock='A'))
        retval(sp.putSocketInPool(host='x', port=1, sock='B'))
        retval(sp.putSocketInPool(host='x', port=1, sock='C'))

        self.assertEquals('A', retval(sp.getPooledSocket(host='x', port=1)))
        self.assertEquals('B', retval(sp.getPooledSocket(host='x', port=1)))
        self.assertEquals('C', retval(sp.getPooledSocket(host='x', port=1)))
        self.assertEquals(None, retval(sp.getPooledSocket(host='x', port=1)))

    def testPutNGet1Put1StillFIFO(self):
        sp = SocketPool(reactor=CallTrace())
        retval(sp.putSocketInPool(host='example.org', port=80, sock='A'))
        retval(sp.putSocketInPool(host='example.org', port=80, sock='B'))

        self.assertEquals('A', retval(sp.getPooledSocket(host='example.org', port=80)))

        retval(sp.putSocketInPool(host='example.org', port=80, sock='C'))

        self.assertEquals('B', retval(sp.getPooledSocket(host='example.org', port=80)))
        self.assertEquals('C', retval(sp.getPooledSocket(host='example.org', port=80)))
        self.assertEquals(None, retval(sp.getPooledSocket(host='example.org', port=80)))

    def testPutEmptyPut(self):
        sp = SocketPool(reactor=CallTrace())
        retval(sp.putSocketInPool(host='10.0.0.1', port=60000, sock=0))
        retval(sp.putSocketInPool(host='10.0.0.1', port=60000, sock=1))

        for i in range(2):
            self.assertEquals(i, retval(sp.getPooledSocket(host='10.0.0.1', port=60000)))
        self.assertEquals(None, retval(sp.getPooledSocket(host='10.0.0.1', port=60000)))

        retval(sp.putSocketInPool(host='10.0.0.1', port=60000, sock=2))
        self.assertEquals(2, retval(sp.getPooledSocket(host='10.0.0.1', port=60000)))

    ##
    ## unusedTimeout (reactor interaction)
    def testUnusedTimeoutSetInitialisesTimer(self):
        # Whitebox (unusedTimeout -> addTimer)
        mockReactor = CallTrace()
        sp = SocketPool(reactor=mockReactor, unusedTimeout=0.02)
        self.assertEquals(['addTimer'], mockReactor.calledMethodNames())
        self.assertEquals(['seconds', 'callback'], mockReactor.calledMethods[0].kwargs.keys())
        self.assertEquals(0.02, mockReactor.calledMethods[0].kwargs['seconds'])

        # Blackbox
        def test():
            top = be((Observable(),
                (SocketPool(reactor=reactor(), unusedTimeout=0.02),),
            ))
            yield top.any.putSocketInPool(host='x', port=80, sock=MockSok('A'))
            yield top.any.putSocketInPool(host='x', port=80, sock=MockSok('B'))
            yield sleep(seconds=0.001)

            result = yield top.any.getPooledSocket(host='x', port=80)
            self.assertEquals('A', result)

            yield sleep(seconds=0.04)

            result = yield top.any.getPooledSocket(host='x', port=80)
            self.assertEquals(None, result)

        asProcess(test())

    def testUnusedTimeoutOnlyPurgesInactiveSocket(self):
        # Blackbox
        def test():
            sA, sB, sC, s1, s2, s3 = (MockSok(x) for x in ['A', 'B', 'C', 1, 2, 3])
            top = be((Observable(),
                (SocketPool(reactor=reactor(), unusedTimeout=0.025),),
            ))

            # Make sure 1st check all-sockets-ok
            yield sleep(seconds=(0.001))

            # Initial set
            yield top.any.putSocketInPool(host='x', port=80, sock=sA)
            yield top.any.putSocketInPool(host='x', port=80, sock=sB)
            yield top.any.putSocketInPool(host='x', port=80, sock=sC)

            yield top.any.putSocketInPool(host='example.org', port=8080, sock=s1)
            yield top.any.putSocketInPool(host='example.org', port=8080, sock=s2)
            yield top.any.putSocketInPool(host='example.org', port=8080, sock=s3)

            self.assertEquals([], s2.log.calledMethodNames())  # sample

            # Pass time, no timeout - 1st check always all-sockets-ok
            yield sleep(seconds=(0.025 + 0.022))  # +/- 0.003 until next mostly-fatal check
            self.assertEquals([], s2.log.calledMethodNames())  # sample

            # Use some, put some back
            _sockA = yield top.any.getPooledSocket(host='x', port=80)
            _sockB = yield top.any.getPooledSocket(host='x', port=80)
            _sock1 = yield top.any.getPooledSocket(host='example.org', port=8080)
            self.assertEquals([sA, sB, s1], [_sockA, _sockB, _sock1])
            self.assertEquals([], sA.log.calledMethodNames())
            self.assertEquals([], sB.log.calledMethodNames())
            self.assertEquals([], s1.log.calledMethodNames())

            yield top.any.putSocketInPool(host='x', port=80, sock=sA)
            yield top.any.putSocketInPool(host='example.org', port=8080, sock=s1)

            yield sleep(seconds=0.015)  # 0.025 - (0.015 - 0.003) = 0.013 until all-fatal check

            inPool = []
            while True:
                result = yield top.any.getPooledSocket(host='x', port=80)
                if result == None:
                    break
                inPool.append(result)

            while True:
                result = yield top.any.getPooledSocket(host='example.org', port=8080)
                if result == None:
                    break
                inPool.append(result)

            self.assertEquals([sA, s1], inPool)
            self.assertEquals([], sA.log.calledMethodNames())
            self.assertEquals([], s1.log.calledMethodNames())
            self.assertEquals(['shutdown', 'close'], s2.log.calledMethodNames())  # sample
            shutdown, close = s2.log.calledMethods
            self.assertEquals(((SHUT_RDWR,), {}), (shutdown.args, shutdown.kwargs))
            self.assertEquals(((), {}), (close.args, close.kwargs))

        asProcess(test())


class MockSok(object):
    def __init__(self, id):
        self._id = id
        self.log = CallTrace()
        self.close = self.log.close
        self.shutdown = self.log.shutdown

    def __eq__(self, other):
        return self._id == getattr(other, '_id', other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return self._id

    def __repr__(self):
        return '{0}(id={1})'.format(self.__class__.__name__, self._id)

