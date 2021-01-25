## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2020-2021 Seecr (Seek You Too B.V.) https://seecr.nl
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
from types import GeneratorType
from weightless.core import Observable, compose, local, cextension
from weightless.core.ext import AllGenerator, DeclineMessage


def m1():
    return "m1"
def m2():
    return "m2"
def m3():
    raise DeclineMessage
def m4(i, a=None):
    return i
def m5(i, a=None):
    return a

class Observable_C_Test(TestCase):

    def testImportAllGenerator(self):
        from weightless.core.ext import AllGenerator
        self.assertTrue(AllGenerator is not None)

    def testCreateAllGeneratorWithWrongArgs(self):
        try: AllGenerator(); self.fail()
        except TypeError as e:
            if not cextension:
                self.assertEqual("Required argument 'methods' (pos 1) not found", str(e))
            else:
                self.assertEqual("__new__() missing required argument 'methods' (pos 1)", str(e))

        try: AllGenerator({}); self.fail()
        except TypeError as e:
            self.assertEqual("__new__() argument 1 must be tuple, not dict", str(e))

        try: AllGenerator(()); self.fail()
        except TypeError as e:
            if not cextension:
                self.assertEqual("Required argument 'args' (pos 2) not found", str(e))
            else:
                self.assertEqual("__new__() missing required argument 'args' (pos 2)", str(e))

        try: AllGenerator((), {}); self.fail()
        except TypeError as e:
            self.assertEqual("__new__() argument 2 must be tuple, not dict", str(e))

        try: AllGenerator((), ()); self.fail()
        except TypeError as e:
            if not cextension:
                self.assertEqual("Required argument 'kwargs' (pos 3) not found", str(e))
            else:
                self.assertEqual("__new__() missing required argument 'kwargs' (pos 3)", str(e))

        try: AllGenerator((), (), ()); self.fail()
        except TypeError as e:
            self.assertEqual("__new__() argument 3 must be dict, not tuple", str(e))

    def testCreateAllGenerator(self):
        g = AllGenerator((), (), {})
        self.assertTrue(g)

    def testEmpty(self):
        g = AllGenerator((), (), {})
        r = list(g)
        self.assertEqual([], r)

    def testOneMethod(self):
        g = AllGenerator((m1,), (), {})
        r = list(g)
        self.assertEqual(["m1"], r)

    def testTwoMethods(self):
        g = AllGenerator((m1, m2), (), {})
        r = list(g)
        self.assertEqual(["m1", "m2"], r)

    def testSendError(self):
        g = AllGenerator((), (), {})
        try:
            g.send("Value")
            self.fail()
        except TypeError as e:
            self.assertEqual("can't send non-None value to a just-started generator", str(e))

    def testSendValueNotAllowed(self):
        g = AllGenerator((m1,m2), (), {})
        next(g)
        try:
            g.send("s1")
            self.fail()
        except AssertionError as e:
            self.assertEqual("%s returned 's1'" % m1, str(e))
        x = g.send(None)
        self.assertEqual("m2", x)

    def testThrow(self):
        g = AllGenerator((m1, m2), (), {})
        try: g.throw(NameError("A")); self.fail()
        except NameError as e:
            self.assertEqual("A", str(e))

        next(g)

        try: g.throw(NameError("B")); self.fail()
        except NameError as e:
            self.assertEqual("B", str(e))

    def testDeclineMessage(self):
        g = AllGenerator((m1, m2), (), {})
        next(g)
        r = g.throw(DeclineMessage) # effectively skips one result
        self.assertEqual("m2", r)

        g = AllGenerator((m1, m3, m2), (), {})
        r = list(g)
        self.assertEqual(["m1", "m2"], r)

    def testArgs(self):
        g = AllGenerator((m4, m5), (1,), {"a": "A"})
        r = list(g)
        self.assertEqual([1, "A"], r)

    def testAllGeneratorIsCallable(self):
        g = AllGenerator((m1,), (), {})
        r = g()
        self.assertEqual("m1", r)
        

    def testAllGeneratorWithCompose(self):
        from weightless.core import compose
        def f1():
            yield 3
        def f2():
            yield f1()
        g = AllGenerator((f2,), (), {})
        c = compose(g)
        self.assertEqual([3], list(c))

    def testAllGeneratorWithLocal(self):
        class B(Observable):
            def f(self):
                aLocal = 42
                yield self.all.f()
        class A(Observable):
            def f(self):
                v = local("aLocal")
                yield v
        a = A()
        b = B()
        b.addObserver(a)
        g = compose(b.f())
        r = list(g)
        self.assertEqual([42], r)
