#!/usr/bin/python
## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2007 Seek You Too B.V. (CQ2) http://www.cq2.nl
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

import wlfile
import select
import tempfile
import os
import hotshot, hotshot.stats, test.pystone

f = tempfile.NamedTemporaryFile()
try:
	for line in ('%08d' % n for n in xrange(513)):
		f.write(line)
	f.seek(0)

	def main():
		for n in range(1000):
			wlf = wlfile.WlFileReader(f.name)
			r, w, e = select.select([wlf], [], [], 1.0)
			data = wlf.recv('ignore this')
			r, w, e = select.select([wlf], [], [], 1.0)
			data = wlf.recv()

	prof = hotshot.Profile("stones.prof")
	prof.runcall(main)
	prof.close()
	os.system('python hotshot2kcachegrind.py -o cachegrind.out stones.prof; kcachegrind cachegrind.out')

finally:
	f.close()

