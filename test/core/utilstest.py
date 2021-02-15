## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
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
from weightless.core.utils import isgeneratorfunction
from functools import partial

class UtilsTest(TestCase):
    def testIsGeneratorFunction(self):
        def a(x,y,z):
            yield 'a'

        class B(object):
            def method(self):
                yield 'b'

            @classmethod
            def class_method(cls):
                yield 'b'

            @staticmethod
            def static_method():
                yield 'b'

        def c(x,y,z):
            return 'c'

        class D(object):
            def method(self):
                return 'd'

            @classmethod
            def class_method(cls):
                return 'd'

            @staticmethod
            def static_method():
                return 'd'

        self.assertTrue(isgeneratorfunction(a))
        self.assertTrue(isgeneratorfunction(B().method))
        self.assertTrue(isgeneratorfunction(B.class_method))
        self.assertTrue(isgeneratorfunction(B.static_method))
        self.assertFalse(isgeneratorfunction(c))
        self.assertFalse(isgeneratorfunction(D().method))
        self.assertFalse(isgeneratorfunction(D.class_method))
        self.assertFalse(isgeneratorfunction(D.static_method))

    def testIsGeneratorFunctionForPartial(self):
        def a(x,y,z):
            yield 'a'

        def c(x,y,z):
            return 'c'

        e = partial(a, 1)
        f = partial(c, 1)

        self.assertFalse(isgeneratorfunction(e))
        self.assertFalse(isgeneratorfunction(f))

