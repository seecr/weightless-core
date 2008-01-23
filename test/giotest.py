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
from weightless import Reactor, gio as gio1, gio2


class GioTest(TestCase):

    def testNonExistingFile(self):
        def eventGenerator():
            try:
                sok = yield self.gio.open('nonexisting')
            except IOError, e:
                self.assertEquals("[Errno 2] No such file or directory: 'nonexisting'", str(e))
        try:
            self.gio.Gio('reactor', eventGenerator())
        except IOError, e:
            self.fail(e)

    def testWriteRead(self):
        reactor = Reactor()
        def eventGenerator():
            sok = yield self.gio.open('data/tmp01', 'w')
            yield sok.write('ape')
            yield sok.close()
            sok = yield self.gio.open('data/tmp01')
            self.data = yield sok.read()
        self.gio.Gio(reactor, eventGenerator())
        reactor.step()
        reactor.step()
        self.assertEquals('ape', self.data)

    def testSokRead(self):
        reactor = Reactor()
        def eventGenerator():
            sok = yield self.gio.open('data/testdata5kb')
            self.data = yield sok.read()
        self.gio.Gio(reactor, eventGenerator())
        reactor.step()
        self.assertEquals('\xe4\xd5VHv\xa3V\x87Vi', self.data[:10])

    def testOpen(self):
        reactor = Reactor()
        def eventGenerator():
            self.sok = yield self.gio.open('data/testdata5kb')
        self.gio.Gio(reactor, eventGenerator())
        self.assertEquals('data/testdata5kb', self.sok._sok.name)

    def testGioAsIntendedToBeUsed(self):
        data = []
        def higherLevelHandler():
            while True:
                received = yield
                data.append(received)
                yield 'send this'
        def eventGenerator(next):
            sok = yield self.gio.open('data/testdata_asc_8kb', 'r')
            sok._recvSize = 10
            toBeSend = next.next() # start
            while True:
                data = yield sok.read()
                #if not data:
                #    next.stop()
                toBeSend = next.send(data)
                #yield sok.send(toBeSend)
        reactor = Reactor()
        self.gio.Gio(reactor, eventGenerator(higherLevelHandler()))
        reactor.step()
        reactor.step()
        reactor.step()
        self.assertEquals(['aaaaaaaaaa', 'aaaaaaaaaa'], data)

class Gio1Test(GioTest):

    def setUp(self):
        self.gio = gio1
        GioTest.setUp(self)

class Gio2Test(GioTest):

    def setUp(self):
        self.gio = gio2
        GioTest.setUp(self)