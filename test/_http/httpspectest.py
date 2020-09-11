## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012, 2018-2020 Seecr (Seek You Too B.V.) http://seecr.nl
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

from weightless.http import httpspec

class HttpSpecTest(TestCase):
    def testParseHeader(self):
        self.assertEqual((b'aap', {}), httpspec.parseHeaderFieldvalue(b'aap'))
        self.assertEqual((b'aap', {b'noot': b'mies'}), httpspec.parseHeaderFieldvalue(b'aap; noot=mies'))
        self.assertEqual((b'aap', {b'noot': b'mies', b'vis': b'vuur'}), httpspec.parseHeaderFieldvalue(b'aap; noot=mies; vis=vuur'))

    def testParseContentDispositionValues(self):
        self.assertEqual((b'attachment', {}), httpspec.parseHeaderFieldvalue(b'attachment'))
        self.assertEqual((b'attachment', {b'filename': b'document.pdf'}),
            httpspec.parseHeaderFieldvalue(b'attachment; filename=document.pdf'))

        self.assertEqual((b'attachment', {b'filename': b'with a ;.pdf'}),
            httpspec.parseHeaderFieldvalue(b'attachment; filename="with a ;.pdf"'))

        self.assertEqual((b'attachment', {b'filename': b'document.pdf', b'filename*': b'another document.pdf'}),
            httpspec.parseHeaderFieldvalue(b'attachment; filename=document.pdf; filename*="another document.pdf"'))

        self.assertEqual((b'attachment', {b'filename': r'with a \".pdf'.encode()}),
            httpspec.parseHeaderFieldvalue(r'attachment; filename="with a \".pdf"'.encode()))

    def testBoundary(self):
        self.assertEqual((b'multipart/form-data', {b'boundary': b'-=-=-=-=-=-=-=-=TestBoundary1234567890'}),
                httpspec.parseHeaderFieldvalue(b'multipart/form-data; boundary="-=-=-=-=-=-=-=-=TestBoundary1234567890"'))

