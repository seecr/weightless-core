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
        self.assertEquals(('aap', {}), httpspec.parseHeaderFieldvalue('aap'))
        self.assertEquals(('aap', {'noot': 'mies'}), httpspec.parseHeaderFieldvalue('aap; noot=mies'))
        self.assertEquals(('aap', {'noot': 'mies', 'vis': 'vuur'}), httpspec.parseHeaderFieldvalue('aap; noot=mies; vis=vuur'))

    def testParseContentDispositionValues(self):
        self.assertEquals(('attachment', {}), httpspec.parseHeaderFieldvalue('attachment'))
        self.assertEquals(('attachment', {'filename': 'document.pdf'}),
            httpspec.parseHeaderFieldvalue('attachment; filename=document.pdf'))

        self.assertEquals(('attachment', {'filename': 'with a ;.pdf'}),
            httpspec.parseHeaderFieldvalue('attachment; filename="with a ;.pdf"'))

        self.assertEquals(('attachment', {'filename': 'document.pdf', 'filename*': 'another document.pdf'}),
            httpspec.parseHeaderFieldvalue('attachment; filename=document.pdf; filename*="another document.pdf"'))

        self.assertEquals(('attachment', {'filename': r'with a \".pdf'}),
            httpspec.parseHeaderFieldvalue(r'attachment; filename="with a \".pdf"'))

    def testBoundary(self):
        self.assertEqual(('multipart/form-data', {'boundary': '-=-=-=-=-=-=-=-=TestBoundary1234567890'}),
                httpspec.parseHeaderFieldvalue('multipart/form-data; boundary="-=-=-=-=-=-=-=-=TestBoundary1234567890"'))

