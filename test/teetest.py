#!/usr/bin/env python2.5
## begin license ##
#
#    "Weightless" is a package with a wide range of valuable tools.
#    Copyright (C) 2005, 2006 Seek You Too B.V. (CQ2) http://www.cq2.nl
#
#    This file is part of "Weightless".
#
#    "Weightless" is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    "Weightless" is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with "Weightless"; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##
#
from unittest import TestCase

from weightless.utils.tee import tee

class TeeTest(TestCase):

	def testSimple(self):
		g1 = (x for x in 'apno')
		g2 = (x for x in 'a ot')
		g = tee((g1, g2))
		response = ''.join(list(g))
		self.assertEquals('aap noot', response)

	def testOneGeneratorStopsBeforeTheOther(self):
		g1 = (x for x in 'apno is')
		g2 = (x for x in 'a otme')
		g = tee((g1, g2))
		response = ''.join(list(g))
		self.assertEquals('aap noot mies', response, 'What to do is this case?')

	def testSend(self):
		data = []
		def f1():
			data.append((yield ''))
		def f2():
			data.append((yield ''))
		g = tee((f1(), f2()))
		g.next()
		try: g.send('duplicate me')
		except StopIteration: pass
		self.assertEquals(['duplicate me', 'duplicate me'], data)

	def testGeneratorExit(self):
		done = []
		def f():
			try:
				yield ''
			except GeneratorExit:
				done.append(1)
				raise
		gens = (f(), f()) # keep em here to avoid the gc calling close()
		g = tee(gens)
		g.next()
		g.close()
		self.assertEquals(2, len(done))
