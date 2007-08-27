#!/usr/bin/python2.5
from __future__ import with_statement
import unittest
import contextlib
import tempfile

class TestCase(unittest.TestCase):

	@contextlib.contextmanager
	def mktemp(self, data):
		f = tempfile.NamedTemporaryFile('w')
		for line in data:
			f.write(line)
		f.seek(0)
		yield f
