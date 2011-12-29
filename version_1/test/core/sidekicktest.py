## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    See http://weightless.io
#    Copyright (C) 2010-2011 Seek You Too (CQ2) http://www.cq2.nl
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
from weightless.core import compose
from sys import exc_info

class SidekickTest(TestCase):

    def testCallCallableWithSidekick(self):
        called = []
        def command(sidekick):
            called.append(sidekick)
        def f():
            yield 'a'
            yield command
            yield 'b'

        c = compose(f(), sidekick="sidekick")
        result = list(c)
        self.assertEquals(['a', 'b'], result)
        self.assertEquals(["sidekick"], called)


    def testCallableIsTransparent(self):
        data = []
        called = []
        def command(sidekick):
            called.append(sidekick)
        def f():
            a = yield None
            data.append(a)
            yield command
            b = yield None
            data.append(b)
            yield

        c = compose(f(), sidekick="sidekick")
        none = c.send(None)
        self.assertEquals(None, none)
        none = c.send('a')
        self.assertEquals(None, none)
        none = c.send('b')
        self.assertEquals(None, none)
        self.assertEquals(['a', 'b'], data)
        self.assertEquals(['sidekick'], called)

    def testCallableRaisesException(self):
        def command(sidekick):
            raise RuntimeError("runtimeError")
        def f():
            yield command
        c = compose(f(), sidekick="sidekick")
        try:
            c.next()
            self.fail()
        except RuntimeError, e:
            self.assertEquals("runtimeError", str(e))

    def testCallableRaisesExceptionWhichIsCatchableByGenerators(self):
        def command(sidekick):
            raise RuntimeError("runtimeError")
        def f():
            try:
                yield command
            except RuntimeError, e:
                yield str(e)
        c = compose(f(), sidekick="sidekick")
        self.assertEquals("runtimeError", c.next())

    def testProperTracebackForCallable(self):
        def command(sidekick):
            raise RuntimeError("runtimeError")
        def f():
            yield command
        c = compose(f(), sidekick="sidekick")
        try:
            c.next()
            self.fail()
        except RuntimeError, e:
            exType, exValue, exTraceback = exc_info()
            self.assertEquals('testProperTracebackForCallable', exTraceback.tb_frame.f_code.co_name)
            self.assertEquals('f', exTraceback.tb_next.tb_frame.f_code.co_name)
            self.assertEquals('command', exTraceback.tb_next.tb_next.tb_frame.f_code.co_name)
