from __future__ import with_statement
## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2008 Seek You Too (CQ2) http://www.cq2.nl
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
from weightless import Reactor, giong


class GioNgTest(TestCase):

    def testOpenReturnsContextManager(self):
        result = giong.open('data/testdata5kb')
        self.assertTrue(hasattr(result, '__enter__'))
        self.assertTrue(hasattr(result, '__exit__'))

    def testGioAsContext(self):
        reactor = Reactor()
        def myProcessor():
            with giong.open('data/testdata_asc_5kb')as datastream:
                self.assertTrue(isinstance(datastream, giong.open))
                self.dataIn = yield
                print 'DONE'
                yield 'response'
        giong.Gio(reactor, myProcessor())
        reactor.step()
        self.assertEquals('0123456789abcdefghi', self.dataIn[:19])

