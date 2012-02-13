## begin license ##
# 
# "Seecr Test" provides test tools. 
# 
# Copyright (C) 2005-2009 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2012 Seecr (Seek You Too B.V.) http://seecr.nl
# 
# This file is part of "Seecr Test"
# 
# "Seecr Test" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# "Seecr Test" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with "Seecr Test"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# 
## end license ##

from unittest import TestCase
from string import whitespace
from tempfile import mkdtemp, mkstemp
from shutil import rmtree
import os
from timing import T

class SeecrTestCase(TestCase):

    def setUp(self):
        TestCase.setUp(self)
        self.tempdir = mkdtemp()
        fd, self.tempfile = mkstemp()
        os.close(fd)
        self.vmsize = self._getVmSize()

    def tearDown(self):
        rmtree(self.tempdir)
        os.remove(self.tempfile)
        TestCase.tearDown(self)

    def assertTiming(self, t0, t, t1):
        self.assertTrue(t0*T < t < t1*T, t/T)

    def select(self, aString, index):
        while index < len(aString):
            char = aString[index]
            index = index + 1
            if not char in whitespace:
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

    def _getVmSize(self):
        status = open('/proc/%d/status' % os.getpid()).read()
        i = status.find('VmSize:') + len('VmSize:')
        j = status.find('kB', i)
        vmsize = int(status[i:j].strip())
        return vmsize

    def assertNoMemoryLeaks(self, bandwidth=0.8):
        vmsize = self._getVmSize()
        self.assertTrue(self.vmsize*bandwidth < vmsize < self.vmsize/bandwidth,
                "memory leaking: before: %d, after: %d" % (self.vmsize, vmsize))


