# -*- coding: utf-8 -*-
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2010-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2015 Seecr (Seek You Too B.V.) http://seecr.nl
# Copyright (C) 2015 Koninklijke Bibliotheek (KB) http://www.kb.nl
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
from seecr.test.io import stderr_replaced

from socket import SHUT_RDWR

from weightless.core import retval, be, Observable
from weightless.io import reactor
from weightless.io.utils import asProcess, sleep

from weightless.http import SocketPool, EmptySocketPool


class SocketPoolTest(SeecrTestCase):
    ##
    ## Get & Put'ing
    def testGetOnEmptyPool(self):
        trace = CallTrace()
        sp = SocketPool(reactor=trace)
        self.assertEqual(None, retval(sp.getPooledSocket(host='x', port=1025)))
        self.assertEqual([], trace.calledMethodNames())

    def testPutThenGetThenEmpty(self):
        sp = SocketPool(reactor=CallTrace())
        result = retval(sp.putSocketInPool(host='x', port=1, sock='mock'))
        self.assertEqual(None, result)
        self.assertEqual('mock', retval(sp.getPooledSocket(host='x', port=1)))
        self.assertEqual(None, retval(sp.getPooledSocket(host='x', port=1)))

    def testPut3GetOnlyYours(self):
        sp = SocketPool(reactor=CallTrace())
        retval(sp.putSocketInPool(host='x', port=1, sock='A'))
        retval(sp.putSocketInPool(host='x', port=2, sock='B'))
        retval(sp.putSocketInPool(host='y', port=1, sock='C'))

        # Unknown host + port
        self.assertEqual(None, retval(sp.getPooledSocket(host='xx', port=1)))
        self.assertEqual(None, retval(sp.getPooledSocket(host='', port=1)))
        self.assertEqual(None, retval(sp.getPooledSocket(host=None, port=1)))
        self.assertEqual(None, retval(sp.getPooledSocket(host='x', port=0)))
        self.assertEqual(None, retval(sp.getPooledSocket(host='x', port=3)))

        # Retrieved once
        self.assertEqual('A', retval(sp.getPooledSocket(host='x', port=1)))

    def testPutNGetLIFO(self):
        sp = SocketPool(reactor=CallTrace())
        retval(sp.putSocketInPool(host='x', port=1, sock='A'))
        retval(sp.putSocketInPool(host='x', port=1, sock='B'))
        retval(sp.putSocketInPool(host='x', port=1, sock='C'))

        self.assertEqual('C', retval(sp.getPooledSocket(host='x', port=1)))
        self.assertEqual('B', retval(sp.getPooledSocket(host='x', port=1)))
        self.assertEqual('A', retval(sp.getPooledSocket(host='x', port=1)))
        self.assertEqual(None, retval(sp.getPooledSocket(host='x', port=1)))

    def testPutNGet1Put1StillLIFO(self):
        sp = SocketPool(reactor=CallTrace())
        retval(sp.putSocketInPool(host='example.org', port=80, sock='A'))
        retval(sp.putSocketInPool(host='example.org', port=80, sock='B'))

        self.assertEqual('B', retval(sp.getPooledSocket(host='example.org', port=80)))

        retval(sp.putSocketInPool(host='example.org', port=80, sock='C'))

        self.assertEqual('C', retval(sp.getPooledSocket(host='example.org', port=80)))
        self.assertEqual('A', retval(sp.getPooledSocket(host='example.org', port=80)))
        self.assertEqual(None, retval(sp.getPooledSocket(host='example.org', port=80)))

    def testPutEmptyPut(self):
        sp = SocketPool(reactor=CallTrace())
        retval(sp.putSocketInPool(host='10.0.0.1', port=60000, sock=0))
        retval(sp.putSocketInPool(host='10.0.0.1', port=60000, sock=1))

        for i in reversed(list(range(2))):
            self.assertEqual(i, retval(sp.getPooledSocket(host='10.0.0.1', port=60000)))
        self.assertEqual(None, retval(sp.getPooledSocket(host='10.0.0.1', port=60000)))

        retval(sp.putSocketInPool(host='10.0.0.1', port=60000, sock=2))
        self.assertEqual(2, retval(sp.getPooledSocket(host='10.0.0.1', port=60000)))

    def testEmptySocketPool_put_noErrors(self):
        sok = MockSok('s')
        sp = EmptySocketPool()
        result = retval(sp.putSocketInPool(host='whatever', port=-1, sock=sok))
        self.assertEqual(None, result)
        self.assertEqual(['shutdown', 'close'], sok.log.calledMethodNames())
        self.assertEqual(((SHUT_RDWR,), {}), (sok.log.calledMethods[0].args, sok.log.calledMethods[0].kwargs))
        self.assertEqual(((), {}), (sok.log.calledMethods[1].args, sok.log.calledMethods[1].kwargs))

    def testEmptySocketPool_put_nonfatalErrors(self):
        sok = MockSok('s')
        def shutdown(*a, **kw):
            raise Exception('xcptn')
        sok.log.methods['shutdown'] = shutdown
        sp = EmptySocketPool()
        result = retval(sp.putSocketInPool(host='secure.example.org', port=9999, sock=sok))
        self.assertEqual(None, result)
        self.assertEqual(['shutdown', 'close'], sok.log.calledMethodNames())
        self.assertEqual(((SHUT_RDWR,), {}), (sok.log.calledMethods[0].args, sok.log.calledMethods[0].kwargs))
        self.assertEqual(((), {}), (sok.log.calledMethods[1].args, sok.log.calledMethods[1].kwargs))

    def testEmptySocketPool_put_fatalErrors(self):
        exceptions = [AssertionError('x'), KeyboardInterrupt('x'), SystemExit('x')]
        def t():
            sok = MockSok('s')
            current_exc = []
            def shutdown(*a, **kw):
                e = exceptions.pop(0)
                current_exc.append(e)
                raise e
            sok.log.methods['shutdown'] = shutdown
            sp = EmptySocketPool()
            try:
                retval(sp.putSocketInPool(host='secure.example.org', port=9999, sock=sok))
            except type(current_exc[0]):
                pass
            else:
                self.fail()
            self.assertEqual(['shutdown'], sok.log.calledMethodNames())
            self.assertEqual(((SHUT_RDWR,), {}), (sok.log.calledMethods[0].args, sok.log.calledMethods[0].kwargs))

        for i in range(3):
            t()

        self.assertEqual(0, len(exceptions))

    def testEmptySocketPool_get(self):
        sp = EmptySocketPool()
        self.assertEqual(None, retval(sp.getPooledSocket(host='whatever', port=-1)))
        self.assertEqual(None, retval(sp.getPooledSocket(host='secure.example.org', port=1010)))

    ##
    ## Poolsize global limit
    def testLimitsMustBeKnown(self):
        self.assertRaises(TypeError, lambda: SocketPool(reactor='x', limits={'unknown': 'limit'}))

    def testLimitSetNotReached(self):
        def test():
            sp = SocketPool(reactor=CallTrace(), limits={'totalSize': 3})  # Limits enforced on put, not async.
            def fillAndEmpty():
                yield sp.putSocketInPool(host='h', port=1, sock='s2')
                yield sp.putSocketInPool(host='h', port=1, sock='s1')
                yield sp.putSocketInPool(host='h', port=1, sock='s0')

                for i in range(3):
                    self.assertEqual('s{0}'.format(i), (yield sp.getPooledSocket(host='h', port=1)))
            yield fillAndEmpty()
            yield fillAndEmpty()

        asProcess(test())

    def testLimitSetReached(self):
        def test():
            sp = SocketPool(reactor=CallTrace(), limits={'totalSize': 2})  # Limits enforced on put, not async.
            def stillPooled():
                wasStillPooled = []
                while True:  # do ... while (fromPool is not None)
                    fromPool = yield sp.getPooledSocket(host='h', port=1)
                    if fromPool:
                        wasStillPooled.append(fromPool)

                    if fromPool is None: break
                raise StopIteration(wasStillPooled)

            s0 = MockSok('s0')
            s1 = MockSok('s1')
            yield sp.putSocketInPool(host='h', port=1, sock=s0)
            yield sp.putSocketInPool(host='h', port=1, sock=s1)
            with stderr_replaced() as err:
                yield sp.putSocketInPool(host='h', port=1, sock=MockSok('s2'))
                self.assertEqual('', err.getvalue(), err.getvalue())  #@@
            wasStillPooled = yield stillPooled()
            self.assertEqual(['s2', 's0'], wasStillPooled)
            self.assertEqual(['shutdown', 'close'], s1.log.calledMethodNames())
            shutCall, closeCall = s1.log.calledMethods
            self.assertEqual(((SHUT_RDWR,), {}), (shutCall.args, shutCall.kwargs))
            self.assertEqual(((), {}), (closeCall.args, closeCall.kwargs))
            self.assertEqual([], s0.log.calledMethodNames())

            yield sp.putSocketInPool(host='h', port=1, sock=MockSok('s0'))
            yield sp.putSocketInPool(host='h', port=1, sock=MockSok('s1'))
            yield sp.putSocketInPool(host='h', port=1, sock=MockSok('s2'))
            yield sp.putSocketInPool(host='h', port=1, sock=MockSok('s3'))
            wasStillPooled = yield stillPooled()
            self.assertEqual(['s3', 's0'], wasStillPooled)

        asProcess(test())

    def testLimitSetReachedWithDifferentDestinations(self):
        def test():
            sp = SocketPool(reactor=CallTrace(), limits={'totalSize': 2})  # Limits enforced on put, not async.
            def stillPooled():
                wasStillPooled = []
                for destHost, destPort in [('h', 1), ('i', 2), ('j', 3)]:
                    while True:  # do ... while (fromPool is not None)
                        fromPool = yield sp.getPooledSocket(host=destHost, port=destPort)
                        if fromPool:
                            wasStillPooled.append(fromPool)

                        if fromPool is None: break
                raise StopIteration(wasStillPooled)

            yield sp.putSocketInPool(host='h', port=1, sock=MockSok('sH'))
            yield sp.putSocketInPool(host='i', port=2, sock=MockSok('sI'))
            with stderr_replaced() as err:
                yield sp.putSocketInPool(host='j', port=3, sock=MockSok('sJ'))
                self.assertEqual('', err.getvalue(), err.getvalue())
            wasStillPooled = yield stillPooled()
            self.assertEqual(2, len(wasStillPooled))
            self.assertTrue(set(wasStillPooled).issubset(set(['sH', 'sI', 'sJ'])))

        asProcess(test())

    def testLimitDestinationReached(self):
        def test():
            sp = SocketPool(reactor=CallTrace(), limits={'destinationSize': 2})  # Limits enforced on put, not async.
            def stillPooled():
                wasStillPooled = []
                for destHost, destPort in [('h', 1), ('i', 2), ('j', 3)]:
                    while True:  # do ... while (fromPool is not None)
                        fromPool = yield sp.getPooledSocket(host=destHost, port=destPort)
                        if fromPool:
                            wasStillPooled.append(fromPool)

                        if fromPool is None: break
                raise StopIteration(wasStillPooled)

            sJ = MockSok('sJ')
            sJ2 = MockSok('sJ2')
            yield sp.putSocketInPool(host='h', port=1, sock=MockSok('sH'))
            yield sp.putSocketInPool(host='i', port=2, sock=MockSok('sI'))
            yield sp.putSocketInPool(host='j', port=3, sock=sJ)
            yield sp.putSocketInPool(host='j', port=3, sock=sJ2)
            with stderr_replaced() as err:
                yield sp.putSocketInPool(host='j', port=3, sock=MockSok('sJ3'))
                self.assertEqual('', err.getvalue(), err.getvalue())
            wasStillPooled = yield stillPooled()
            self.assertEqual(4, len(wasStillPooled))
            self.assertEqual(['sH', 'sI', 'sJ3', 'sJ2'], wasStillPooled)
            self.assertEqual(['shutdown', 'close'], sJ.log.calledMethodNames())

        asProcess(test())

    ##
    ## unusedTimeout (reactor interaction)
    def testUnusedTimeoutSetInitialisesTimer(self):
        # Whitebox (unusedTimeout -> addTimer)
        mockReactor = CallTrace()
        SocketPool(reactor=mockReactor, unusedTimeout=0.02)
        self.assertEqual(['addTimer'], mockReactor.calledMethodNames())
        self.assertEqual(['seconds', 'callback'], list(mockReactor.calledMethods[0].kwargs.keys()))
        self.assertEqual(0.02, mockReactor.calledMethods[0].kwargs['seconds'])

        # Blackbox
        def test():
            top = be((Observable(),
                (SocketPool(reactor=reactor(), unusedTimeout=0.02),),
            ))
            yield top.any.putSocketInPool(host='x', port=80, sock=MockSok('A'))
            yield top.any.putSocketInPool(host='x', port=80, sock=MockSok('B'))
            yield sleep(seconds=0.001)

            result = yield top.any.getPooledSocket(host='x', port=80)
            self.assertEqual('B', result)

            yield sleep(seconds=0.04)

            result = yield top.any.getPooledSocket(host='x', port=80)
            self.assertEqual(None, result)

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

            self.assertEqual([], s2.log.calledMethodNames())  # sample

            # Pass time, no timeout - 1st check always all-sockets-ok
            yield sleep(seconds=(0.025 + 0.022))  # +/- 0.003 until next mostly-fatal check
            self.assertEqual([], s2.log.calledMethodNames())  # sample

            # Use some, put some back
            _sockC = yield top.any.getPooledSocket(host='x', port=80)
            _sockB = yield top.any.getPooledSocket(host='x', port=80)
            _sock3 = yield top.any.getPooledSocket(host='example.org', port=8080)
            self.assertEqual([sC, sB, s3], [_sockC, _sockB, _sock3])
            self.assertEqual([], sC.log.calledMethodNames())
            self.assertEqual([], sB.log.calledMethodNames())
            self.assertEqual([], s3.log.calledMethodNames())

            yield top.any.putSocketInPool(host='x', port=80, sock=sC)
            yield top.any.putSocketInPool(host='example.org', port=8080, sock=s3)

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

            self.assertEqual([sC, s3], inPool)
            self.assertEqual([], sC.log.calledMethodNames())
            self.assertEqual([], s3.log.calledMethodNames())
            self.assertEqual(['shutdown', 'close'], s1.log.calledMethodNames())  # sample
            shutdown, close = s1.log.calledMethods
            self.assertEqual(((SHUT_RDWR,), {}), (shutdown.args, shutdown.kwargs))
            self.assertEqual(((), {}), (close.args, close.kwargs))

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

    def __hash__(self):
        return hash(self._id)

    def __repr__(self):
        return '{0}(id={1})'.format(self.__class__.__name__, self._id)
