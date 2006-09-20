import unittest
import wlthreadpool
import sys
from traceback import format_tb, print_tb


class WlThreadPoolTest(unittest.TestCase):

	def testOne(self):
		result = []
		def worker():
			result.append('aap')
			yield None
			result.append('noot')
		wlthreadpool.execute(worker())
		self.assertEquals(['aap','noot'], result)

	def testWrongInput(self):
		try:
			wlthreadpool.execute(None)
			self.fail()
		except TypeError, e:
			self.assertEquals('execute() expects a generator', str(e))

if __name__ == '__main__':
	unittest.main()