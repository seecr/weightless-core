## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2009 Seek You Too (CQ2) http://www.cq2.nl
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
from weightless import Reactor, local

class LocalTest(TestCase):

    def testOne(self):
        reactor = Reactor(select_func = lambda r,w,o,t: (r,w,o))
        results = []
        oneSharedLocal = local()
        def callback(c):
            oneSharedLocal.someGeneratorSpecificStuff = c
            yield
            results.append(oneSharedLocal.someGeneratorSpecificStuff)
            yield
        reactor.addReader(9, callback('a').next)
        reactor.addReader(8, callback('b').next)
        reactor.step()
        reactor.step()
        self.assertEquals(['b', 'a'], results)