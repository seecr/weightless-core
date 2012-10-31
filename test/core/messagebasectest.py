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
from weightless.core.observable._observable_py import MessageBaseC

from gctestcase import GCTestCase

class MessageBaseCTest(GCTestCase):

    def testSelftest(self):
        from weightless.core.compose._compose_c import List_selftest
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
                return "this is alt_name for " + message
        a = A()
        msg = MsgA([a], 'f')
        methods = msg.candidates()
        self.assertEquals("this is alt_name for f", methods[0]())

    def testAllInC(self):
        class A(object):
            def f(self):
                return 1
        class B(object):
            def f(self):
                return 2
        msg = MessageBaseC([A(),B()], "f")
        self.assertEquals([1,2], list(msg.all()))

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

