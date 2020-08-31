## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2009-2011 Seek You Too (CQ2) http://www.cq2.nl
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

from unittest import TestCase
from sys import exc_info
from weightless.core import local, consume, cextension


class LocalTest(TestCase):

    def testScope(self):
        _some_var_on_the_callstack_ = 'aap'
        v = local('_some_var_on_the_callstack_')
        self.assertEqual('aap', v)

    def testNone(self):
        var = None
        self.assertEqual(None, local('var'))

    def testNotFound(self):
        try:
            v = local('no_such_thing')
            print("V", v)
            self.fail()
        except AttributeError:
            pass

    def testNotFoundStacktraceCleanNormalFunctions(self):
        def a():
            b()
        def b():
            local('no_such_thing')
        try:
            a()
            self.fail()
        except AttributeError:
            c, v, t = exc_info()
            self.assertEqual("no_such_thing", str(v))
            names = []
            while t:
                names.append(t.tb_frame.f_code.co_name)
                t = t.tb_next
            self.assertEqual(['testNotFoundStacktraceCleanNormalFunctions', 'a', 'b'] + ([] if cextension else ['local']), names)

    def testNotFoundStacktraceCleanGeneratorFunctions(self):
        def a():
            yield b()
        def b():
            yield c()
        def c():
            yield local('no_such_thing')

        try:
            consume(a())
            self.fail()
        except AttributeError:
            c, v, t = exc_info()
            self.assertEqual("no_such_thing", str(v))
            names = []
            while t:
                names.append(t.tb_frame.f_code.co_name)
                t = t.tb_next
            self.assertEqual(['testNotFoundStacktraceCleanGeneratorFunctions', 'consume', 'a', 'b', 'c'] + ([] if cextension else ['local']), names)

    def testVariousTypes(self):
        strArgument = 'string'
        self.assertEqual('string', local('strArgument'))
        intArgument = 1
        self.assertEqual(1, local('intArgument'))

        class MyObject(object):
            pass
        objArgument = MyObject()
        self.assertEqual(objArgument, local('objArgument'))

    def testScoping(self):
        class MyObject(object):
            pass
        refs = []
        def function():
            toplevel=MyObject()
            refs.append(local('toplevel'))
        function()
        self.assertEqual(1, len(refs))
        self.assertEqual(MyObject, type(refs[0]))

    def testOne(self):
        a=1
        b=2
        c=3
        def f1():
            d=4
            a=10
            b=6
            self.assertEqual(4, local('d'))
            self.assertEqual(10, local('a'))
        f1()
        self.assertEqual(2, local('b'))
        self.assertEqual(1, local('a'))

    def testWithGenerator(self):
        results = []
        _z_ = 9
        def e():
            yield
            results.append(local('_x_'))
            yield
            results.append(local('_y_'))
            yield
            results.append(local('_z_'))
        def f():
            _x_ = 10
            yield
            _y_ = 11
            list(e())
        list(f())
        self.assertEqual([10,11,9], results)

    def testLookupSelfWhileBeingInitialized(self):
        try:
            tx = local('tx')
            self.fail()
        except AttributeError:
            pass

