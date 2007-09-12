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
from __future__ import with_statement

from select import select as original_select_func
from os import write, read
from traceback import print_exc

class ReadIteration(Exception): pass
class WriteIteration(Exception): pass
class SuspendIteration(Exception): pass

class Select:

	def __init__(self, select_func = original_select_func):
		self._select_func = select_func
		self._readers = set()
		self._writers = set()

	def add(self, sok, mode = 'r'):
		if mode == 'r':
			self._readers.add(sok)
		else:
			self._writers.add(sok)
		if self._inSelect:
			self._signaller.signal()

	def loop(self):
		while True:
			self._select()

	def _select(self):
		r, w, e = self._select_func(self._readers, self._writers, [])

		for readable in r:
			try:
				readable.readable()
			except WriteIteration:
				self._readers.remove(readable)
				self._writers.add(readable)
			except SuspendIteration:
				self._readers.remove(readable)
			except (StopIteration, GeneratorExit):
				self._readers.remove(readable)
				readable.close()
			except Exception:
				self._readers.remove(readable)
				readable.close()
				print_exc()

		for writable in w:
			try:
				writable.writable()
			except ReadIteration:
				self._writers.remove(writable)
				self._readers.add(writable)
			except SuspendIteration:
				self._writers.remove(writable)
			except (StopIteration, GeneratorExit):
				self._writers.remove(writable)
				writable.close()
			except Exception:
				self._writers.remove(writable)
				writable.close()
				print_exc()
