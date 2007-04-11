from __future__ import with_statement

from wltestcase import TestCase
from wlsocket import WlFileSocket
from cq2utils.calltrace import CallTrace
from functools import partial as curry
import select

from wlsocket import wlfilesocket
from wlthread import WlPool
wlfilesocket._pool = WlPool(with_status_and_bad_performance = True)

class WlFileSocketTest(TestCase):

	def testOpenAndReadAsyncFileLowLevelWhiteBoxTest(self):
		with self.mktemp('aap noot mies') as f:
			wlf = WlFileSocket(f.name)
			wlf.sink((i for i in range(999)), CallTrace())
			r, w, e = select.select([wlf], [], [], 1.0)
			self.assertEquals([wlf], r)
			data = wlf._recv()
			self.assertEquals('aap noot mies', data)

	def testReadChuncksEvenMoreWhiteBoxToTestTheStreamingHappeningInASeparateThread(self):
		with self.mktemp('%08d' % n for n in xrange(513)) as f:
			wlf = WlFileSocket(f.name)
			wlf.sink((i for i in range(999)), CallTrace()) # fake stuff
			r, w, e = select.select([wlf], [], [], 1.0)
			self.assertEquals([wlf], r)
			data = wlf._sok.recv(24)
			self.assertEquals('000000000000000100000002', data)
			r, w, e = select.select([wlf], [], [], 1.0)
			data = wlf._sok.recv(16)
			self.assertEquals('0000000300000004', data)
			data = wlf._sok.recv(99999)
			self.assertEquals('00000512', data[4056:])
			select.select([wlf], [wlf], [wlf], 1.0)
			data = wlf._sok.recv(99999)
			self.assertEquals('', data) # EOF

	def testHighLevelAsItShouldBeUsed(self):
		with self.mktemp('aap noot mies') as f:
			wlf = WlFileSocket(f.name)
			data = []
			def collector():
				received = yield None
				data.append(received)
			wlf.sink(collector(), CallTrace())
			wlf.readable()
		self.assertEquals('aap noot mies', data[0])

	def testHighLevelAsItShouldBeUsedWithLittleChunks(self):
		with self.mktemp('aap noot mies') as f:
			wlf = WlFileSocket(f.name)
			wlf._recv = curry(wlf._sok.recv, 2) # poke read method
			data = []
			def collector():
				while True:
					received = yield None
					data.append(received)
			wlf.sink(collector(), CallTrace())
			wlf.readable()
			wlf.readable()
			wlf.readable()
			wlf.readable()
			wlf.readable()
			wlf.readable()
			wlf.readable()
		self.assertEquals('aa', data[0])
		self.assertEquals('p ', data[1])
		self.assertEquals('no', data[2])
		self.assertEquals('ot', data[3])
		self.assertEquals(' m', data[4])
		self.assertEquals('ie', data[5])
		self.assertEquals('s', data[6])

