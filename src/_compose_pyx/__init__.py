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
from os import system
from os.path import dirname, isfile, join, getmtime

mydir = dirname(__file__)
solib = join(mydir, 'compose.so')
pyxsource = join(mydir, 'compose.pyx')

if not isfile(solib):
	print '* Extension compose.so not found,'
	if isfile(pyxsource):
		print '* but PyRex source found, assuming development environment'
		print '* Now compiling compose.so extension.'
		system("cd %s; python2.5 setup.py build_ext --inplace" % mydir)
	else:
		print '* and no PyRex source found.  Your installation is broken.'
		raise ImportError('no compose.so and no compose.pyx either.')
else:
	if isfile(pyxsource) and getmtime(solib) < getmtime(pyxsource):
		print '* Extension compose.so found, but newer Pyrex source also found.'
		print '* Recompiling compose extension'
		system("cd %s; python2.5 setup.py build_ext --inplace" % mydir)

from compose import compose, RETURN

