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
from weightless import Reactor, gio

class GioTest(TestCase):

    def testOpen(self):
        reactor = Reactor()
        def eventGenerator():
            self.sok = yield gio.open('data/testdata5kb')
        gio.Gio(reactor, eventGenerator())
        self.assertEquals('data/testdata5kb', self.sok._sok.name)

    def testSokRead(self):
        reactor = Reactor()
        def eventGenerator():
            sok = yield gio.open('data/testdata5kb')
            self.data = yield sok.read()
        gio.Gio(reactor, eventGenerator())
        reactor.step()
        self.assertEquals('\xe4\xd5VHv\xa3V\x87Vi', self.data[:10])

    def testWriteRead(self):
        reactor = Reactor()
        def eventGenerator():
            sok = yield gio.open('data/tmp01', 'w')
            yield sok.write('ape')
            yield sok.close()
            sok = yield gio.open('data/tmp01')
            self.data = yield sok.read()
        gio.Gio(reactor, eventGenerator())
        reactor.step()
        reactor.step()
        self.assertEquals('ape', self.data)

    def testNonExistingFile(self):
        def eventGenerator():
            try:
                sok = yield gio.open('nonexisting')
            except IOError, e:
                self.assertEquals("[Errno 2] No such file or directory: 'nonexisting'", str(e))
        try:
            gio.Gio('reactor', eventGenerator())
        except IOError, e:
            self.fail(e)
