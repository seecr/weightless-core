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

class ListCTest(TestCase):
    def testSelftest(self):
        from weightless.core.compose._compose_c import List_selftest
        List_selftest()

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
        for _ in range(1000):
            list(compose(s.all.f()))
        t1 = time()
        # baseline: 0.027   ===> with --c: 0.013
        # __slots__ in Observable: 0.027
        # Defer with static tuple of observers: 0.023
        # Caching method in Defer.__getattr__: 0.021
        # Without checking resuls in MessageBase.all: 0.019 ==> C: 0.0068
        self.assertTrue(t1-t0 < 0.001, t1-t0)

