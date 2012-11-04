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

from unittest import TestCase
from time import time
from weightless.core import Observable, be, compose
from weightless.core.observable._observable_py import MessageBaseC, DeclineMessage

from gctestcase import GCTestCase

class MessageBaseCTest(GCTestCase):

    def testSelftest(self):
        from weightless.core.core_c import List_selftest
        List_selftest()

    def testCreate(self):
        self.assertEquals(
                "<class 'weightless.core.observable._observable_py.MessageBaseC'>",
                str(MessageBaseC))
        observer = "A"
        msg = MessageBaseC([observer, object()], 'strip')
        methods = msg.candidates()
        self.assertEquals((observer.strip,), methods)

    def testSubclass(self):
        class MsgA(MessageBaseC):
            altname = "alt_name"
        self.assertEquals("<class 'core.messagebasectest.MsgA'>", str(MsgA))
        class A(object):
            def alt_name(self, message):
                yield "this is alt_name for " + message
        a = A()
        msg = MsgA([a], 'f')
        methods = msg.candidates()
        self.assertEquals("this is alt_name for f", methods[0]().next())

    def testAllInC(self):
        class A(object):
            def f(self, a, b=None):
                yield "A" + a + b
        class B(object):
            def f(self, a, b=None):
                yield "B" + a + b
        a = MessageBaseC([A(),B()], "f").all("a", b="b")
        self.assertEquals(["Aab", "Bab"], list(g.next() for g in a))

    def testAllGeneratorHandlesFirstSend(self):
        msg = MessageBaseC([], "")
        a = msg.all()
        try:
            a.send(None)
            self.fail()
        except StopIteration:
            pass
        try:
            msg.all().send("not allowed")
            self.fail('fails here')
        except TypeError, e:
            self.assertEquals("can't send non-None value to a just-started generator", str(e))

    def testAllGeneratorChecksForIllegalDataSend(self):
        class A(object):
            def f(self):
                yield
        a = A()
        msg = MessageBaseC([a], "f")
        g = msg.all()
        g.next()
        try:
            g.send("not allowed")
        except AssertionError, e:
            self.assertEquals(str(a.f) + " returned 'not allowed'", str(e))

    def testDeclineMessage(self):
        class A(object):
            def f(self):
                raise DeclineMessage
        class B(object):
            def f(self):
                yield 42
        g = MessageBaseC([A(), B()], "f").all()
        self.assertEquals([42], list(g.next() for g in g))

    def testAssertOnResultType(self):
        class A(object):
            def f(self):
                return 'not a generator'
        a = A()
        try:
            list(MessageBaseC([a], 'f').all())
            self.fail()
        except AssertionError, e:
            self.assertEquals(str(a.f) + " should have resulted in a generator", str(e))

    def testGeneratorCanAlsoBeCompose(self):
        class A(object):
            def f(self):
                return compose(x for x in [1])
        self.assertEquals("?", list(MessageBaseC([A()], 'f').all()))

    def testPerformance(self):
        class Top(Observable):
            pass

        class Two(Observable):
            def f(self):
                yield 1

        class Three(Observable):
            def f(self):
                yield 2

        class Four(Observable):
            def f(self):
                yield 3

        s = be((Top(),
                   (Two(),),
                   (Three(),),
                   (Four(),),
                   ))
        self.assertEquals([1, 2, 3], list(compose(s.all.f())))
        t0 = time()
        for _ in range(10000):
            list(compose(s.all.f()))
        t1 = time()
        # baseline: 0.27   ===> with --c: 0.13
        # __slots__ in Observable: 0.27
        # Defer with static tuple of observers: 0.23
        # Caching method in Defer.__getattr__: 0.21
        # Without checking resuls in MessageBase.all: 0.19 ==> C: 0.068
        self.assertTrue(t1-t0 < 0.1, t1-t0)

    def testPerformanceOfLabelledInvocation(self):
        class Top(Observable):
            pass

        class Two(Observable):
            def f(self):
                yield 2

        class Three(Observable):
            def f(self):
                yield 3

        s = be((Top(),
                   (Two("two"),),
                   (Three("three"),),
                   ))
        self.assertEquals([2], list(compose(s.all['two'].f())))
        self.assertEquals([3], list(compose(s.all['three'].f())))
        # baseline (all opts from previous test): 0.128
        # with Defer(defaultdict) and __missing__: 0.058
        t0 = time()
        for _ in range(10000):
            list(compose(s.all['three'].f()))
        t1 = time()
        self.assertTrue(t1-t0 < 0.08, t1-t0)

