## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2010 Seek You Too (CQ2) http://www.cq2.nl
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
from unittest import TestCase
from cq2utils import CallTrace

from weightless import Reactor, Suspend, HttpServer

class MockSocket(object):
    def close(self):
        self.closed = True

def mockselect(readers, writers, x, timeout):
    return readers, writers, x

class SuspendTest(TestCase):

    def testReactorSuspend(self):
        handle = ['initial value']
        reactor = Reactor(select_func=mockselect)
        def callback():
            handle[0] = reactor.suspend()
        sok = MockSocket()
        reactor.addReader(sok, callback)
        self.assertTrue(sok in reactor._readers)
        reactor.step()
        self.assertTrue(sok not in reactor._readers)

        sok = MockSocket()
        reactor.addWriter(sok, callback)
        self.assertTrue(sok in reactor._writers)
        reactor.step()
        self.assertTrue(sok not in reactor._writers)
        self.assertTrue(handle[0] != None)
        self.assertTrue(handle[0] != 'initial value')

    def testReactorResumeReader(self):
        handle = ['initial value']
        reactor = Reactor(select_func=mockselect)
        def callback():
            handle[0] = reactor.suspend()
            yield
            handle.append('resumed')
            yield
        sok = MockSocket()
        reactor.addReader(sok, callback().next)
        reactor.step()
        reactor.resumeReader(handle[0])
        reactor.step()
        self.assertEquals('resumed', handle[1])
        self.assertTrue(sok not in reactor._writers)
        self.assertTrue(sok in reactor._readers)
        self.assertRaises(KeyError, reactor.resumeReader, handle[0])

    def testReactorResumeWriter(self):
        handle = ['initial value']
        reactor = Reactor(select_func=mockselect)
        def callback():
            handle[0] = reactor.suspend()
            yield
            yield
        sok = MockSocket()
        reactor.addWriter(sok, callback().next)
        reactor.step()
        reactor.resumeWriter(handle[0])
        reactor.step()
        self.assertTrue(sok in reactor._writers)
        self.assertTrue(sok not in reactor._readers)
        self.assertRaises(KeyError, reactor.resumeReader, handle[0])
        self.assertRaises(KeyError, reactor.resumeWriter, handle[0])

    def testWrongUseAfterSuspending(self):
        reactor = Reactor(select_func=mockselect)
        handle = ['initial value']
        def callback():
            handle[0] = reactor.suspend()
        sok = MockSocket()
        reactor.addWriter(sok, callback)
        reactor.step()
        self.assertEquals(sok, handle[0])
        try:
            reactor.addWriter(sok, callback)
            self.fail("Exception not raised")
        except ValueError, e:
            self.assertEquals('Socket is suspended', str(e))
        try:
            reactor.addReader(sok, callback)
            self.fail("Exception not raised")
        except ValueError, e:
            self.assertEquals('Socket is suspended', str(e))

    def testShutdownReactor(self):
        reactor = Reactor(select_func=mockselect)
        sok1 = MockSocket()
        sok2 = MockSocket()
        sok3 = MockSocket()
        def callback():
            reactor.suspend()
        reactor.addReader(sok1, lambda: None)
        reactor.addWriter(sok2, lambda: None)
        reactor.addReader(sok3, callback)
        reactor.step()
        reactor.shutdown() 
        self.assertTrue(sok1.closed)
        self.assertTrue(sok2.closed)
        self.assertTrue(sok3.closed)

    def XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXxtestIntegration(self):
        d = {}
        def someAction(identifier):
            yield 'a'
            # triggerAsynchronousProccesing()
            s = Suspend()
            d[identifier] = s
            yield s # wait for asynchronous proccess to finish
            yield 'b'
        def asynchronousProcessFinished(identifier):
            d[identifier].resume()

    def testSuspendProtocol(self):
        data = []
        class MyMockSocket(object):
            def accept(self):
                return MyMockSocket(), None
            def setsockopt(self, *args):
                pass
            def recv(selfl, *args):
                return 'GET / HTTP/1.0\r\n\r\n'
            def getpeername(self):
                return 'itsme'
            def shutdown(self, *args):
                pass
            def close(self):
                pass
            def send(self, chunk, options):
                data.append(chunk)
                return len(chunk)
        reactor = Reactor(select_func=mockselect)
        def handler(**httpvars):
            print 'doe jij wat?'
            yield 'before suspend'
            s = Suspend()
            yield s
            yield 'after suspend'
        listener = MyMockSocket()
        httpserver = HttpServer(reactor, 9, handler, sok=listener)
        reactor.removeReader(listener) # avoid new connections
        httpserver._accept()
        reactor.step()
        reactor.step()
        reactor.step()
        self.assertEquals(['before suspend', 'after suspend'], data)
        # httpserver does: s(reactor)


