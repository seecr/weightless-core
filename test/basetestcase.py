## begin license ##
#
#    "CQ2 Utils" (cq2utils) is a package with a wide range of valuable tools.
#    Copyright (C) 2005-2008 Seek You Too (CQ2) http://www.cq2.nl
#
#    This file is part of "CQ2 Utils".
#
#    "CQ2 Utils" is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    "CQ2 Utils" is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with "CQ2 Utils"; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

import sys, unittest, string
from tempfile import mkdtemp, mkstemp
from shutil import rmtree
import os


class BaseTestCase(unittest.TestCase):

    def setUp(self):
        self.tempdir = mkdtemp()
        fd, self.tempfile = mkstemp()
        os.close(fd)

    def tearDown(self):
        rmtree(self.tempdir)
        os.remove(self.tempfile)

    def select(self, aString, index):
        while index < len(aString):
            char = aString[index]
            index = index + 1
            if not char in string.whitespace:
                return char, index
        return '', index

    def cursor(self, aString, index):
        return aString[:index - 1] + "---->" + aString[index - 1:]

    def assertEqualsWS(self, s1, s2):
        index1 = 0
        index2 = 0
        while True:
            char1, index1 = self.select(s1, index1)
            char2, index2 = self.select(s2, index2)
            if char1 != char2:
                self.fail('%s != %s' % (self.cursor(s1, index1), self.cursor(s2, index2)))
            if not char1 or not char2:
                break

class MatchAll(object):
    def __eq__(self, other):
        return True
    def __ne__(self, other):
        return False
    def __repr__(self):
        return '*MatchAll*'

MATCHALL = MatchAll()
