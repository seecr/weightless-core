from unittest import TestCase

from wldict import WlDict

class WlDictTest(TestCase):
	def xxtestOne(self):
		d = WlDict()
		self.assertFalse(d.a)