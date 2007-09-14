#!/usr/bin/env python2.5
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
#
from __future__ import with_statement

from unittest import TestCase
from weightless import Socket
from weightless._select import ReadIteration, WriteIteration
from cq2utils.calltrace import CallTrace
from select import select
from socket import gaierror

class SocketTest(TestCase):

	def testCreateSocketGetsReceiveBufferSizeFromSocketItself(self):
		socket = CallTrace()
		socket.returnValues['getsockopt'] = 98765  # kernel reports twice the size
		sok = Socket(socket)
		self.assertEquals('getsockopt(1, 8)', str(socket.calledMethods[0]))
		sok._recv()
		self.assertEquals('recv(49382)', str(socket.calledMethods[1]))

	def testSocketClose(self):
		socket = CallTrace(returnValues={'getsockopt':10})
		sok = Socket(socket)
		sok.close()
		self.assertEquals('close()', str(socket.calledMethods[1]))

	def testSinkNonGenerator(self):
		try:
			Socket(CallTrace(returnValues={'getsockopt':4096})).sink('wrong', None)
		except AssertionError, e:
			self.assertEquals('need generator', str(e))

	def testAddingExhaustedGeneratorRaisesException(self):
		sok = Socket(CallTrace(returnValues={'getsockopt':10}))
		try:
			sok.sink((i for i in []), None)
			self.fail()
		except ValueError, e:
			self.assertEquals('useless generator: exhausted at first next()', str(e))

	def testSink(self):
		socket = CallTrace(returnValues={'getsockopt':10})
		socket.returnValues['recv'] = 'aap noot mies'
		sok = Socket(socket)
		data = [None]
		def generator():
			data[0] = yield None
			data[1] = yield None
		sok.sink(generator(), CallTrace())
		sok.readable()
		self.assertEquals('aap noot mies', data[0])

	def testThrowGeneratorExitWhenEndOfFile(self):
		sok = Socket(CallTrace(returnValues = {'recv': '', 'getsockopt':4096}))
		stopped = [None]
		def sink():
			try:
				yield None
			except GeneratorExit:
				stopped[0] = True
				raise
			yield None
		sok.sink(sink(), CallTrace())
		try:
			sok.readable()
			self.fail('must raise StopIteration')
		except StopIteration, e:
			pass
		self.assertTrue(stopped[0])

	def testStartWithReading(self):
		sok = Socket(CallTrace(returnValues={'getsockopt':10}))
		mockSelect = CallTrace()
		sok.sink((x for x in [None]), mockSelect)
		self.assertEquals("add(<weightless._socket.Socket>, 'r')", str(mockSelect.calledMethods[0]))

	def testStartWithWriting(self):
		sok = Socket(CallTrace(returnValues={'getsockopt':10}))
		mockSelect = CallTrace()
		sok.sink((x for x in ['data']), mockSelect)
		self.assertEquals("add(<weightless._socket.Socket>, 'w')", str(mockSelect.calledMethods[0]))

	def testReadDataFromSocketAndSendToGenerator(self):
		mockSok = CallTrace(returnValues={'getsockopt':10})
		sok = Socket(mockSok)
		data = []
		def collect():
			while True:
				received = yield None
				data.append(received)
		sok.sink(collect(), CallTrace())
		mockSok.returnValues['recv'] = 'aap'
		sok.readable()
		self.assertEquals('aap', data[0])
		mockSok.returnValues['recv'] = 'noot'
		sok.readable()
		self.assertEquals('noot', data[1])

	def testGetDataFromGeneratorAndSendToSocket(self):
		mockSok = CallTrace(returnValues = {'send': 999, 'getsockopt': 10})
		sok = Socket(mockSok)
		sok.sink((data for data in ['aap', 'noot', 'mies']), CallTrace())
		sok.writable()
		sok.writable()
		self.assertEquals("send('aap')", str(mockSok.calledMethods[1]))
		self.assertEquals("send('noot')", str(mockSok.calledMethods[2]))

	def testSwitchFromReadingToWriting(self):
		mockSok = CallTrace(returnValues = {'send': 999, 'recv': 'keep things going', 'getsockopt': 10})
		sok = Socket(mockSok)
		mockSelect = CallTrace()
		sok.sink((data for data in [None, 'data to write', 'more', None, None, 'even more to write']), mockSelect)
		self.assertEquals("add(<weightless._socket.Socket>, 'r')", str(mockSelect.calledMethods[0]))
		try:
			sok.readable()
			self.fail()
		except WriteIteration:
			self.assertEquals('recv(5)', str(mockSok.calledMethods[1]))
		sok.writable()
		self.assertEquals("send('data to write')", str(mockSok.calledMethods[2]))
		try:
			sok.writable()
			self.fail()
		except ReadIteration:
			self.assertEquals("send('more')", str(mockSok.calledMethods[3]))
		sok.readable()
		self.assertEquals('recv(5)', str(mockSok.calledMethods[4]))
		try:
			sok.readable()
			self.fail()
		except WriteIteration:
			self.assertEquals('recv(5)', str(mockSok.calledMethods[5]))
		try:
			sok.writable()
			self.fail()
		except StopIteration:
			pass

	def testSendDidNotSendAllData(self):
		mockSok = CallTrace(returnValues = {'send': 5, 'getsockopt':10})
		sok = Socket(mockSok)
		sok.sink((data for data in ['send in chunks', 'more', 'and more']), CallTrace())
		sok.writable()
		self.assertEquals("send('send in chunks')", str(mockSok.calledMethods[1]))
		sok.writable()
		self.assertEquals("in chunks", str(mockSok.calledMethods[2].arguments[0]))
		sok.writable()
		self.assertEquals("unks", str(mockSok.calledMethods[3].arguments[0]))
		sok.writable()
		self.assertEquals("more", str(mockSok.calledMethods[4].arguments[0]))

	def testFromOneSocketToTheOther(self):
		# This is NOT A WORKING TEST, just an idea of how things are heading
		def wlopen(filename):
			fs = WlFileSocket()
			yield WlAsyncOpen(fs, filename)
			yield RETURN, InWithMagicallySourceThisGeneratorFrom(fs)
		def thisIsHowYouCanUseDifferentSocketsInOneGenerator(sokje):
			requestedFile = yield None
			yield 'header'
			source = yield wlopen('/tmp/somefile')	# A: open a socket
			with source:													# B: replace implicit socket in __enter__
				yield 'GET / HTTP/1.1'									# C: yield to new socket
																					# D: restore old socket in __exit__
			while True:
				with source:
					data = yield None
				yield data
			yield 'trailer'

	def testBufferedSendForAsyncSupport(self):
		# Eata comes in from One socket and sent to an Other. These both stream might need
		# some buffering to allow sufficient throughput if One is faster than the Other.
		# However, at some point, the One must be held to wait for the Other....
		mockSok = CallTrace(returnValues = {'send': 999, 'recv': 'keep things going', 'getsockopt': 10})
		sok = Socket(mockSok)
		sok.send('some data')
		sok.send('more data')
		self.assertEquals(['some data', 'more data'], sok._write_queue)
		sok.writable()
		self.assertEquals(['more data'], sok._write_queue)
		sok.send('even more')
		sok.writable()
		self.assertEquals(['even more'], sok._write_queue)
