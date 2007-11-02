from unittest import TestCase
from cq2utils import CallTrace
from tempfile import mkstemp
from os import remove
from socket import socket
from select import select

from weightless.transparentsocket import TransparentSocket

class TransparentSocketTest(TestCase):

    def setUp(self):
        ignored, self._filename = mkstemp()

    def tearDown(self):
        remove(self._filename)

    def testDelegate(self):
        originalObject = CallTrace("Original")
        ts = TransparentSocket(originalObject)
        ts.methodCall('argument')
        self.assertEquals(1, len(originalObject.calledMethods))
        method = originalObject.calledMethods[0]
        self.assertEquals("methodCall", method.name)
        self.assertEquals("argument", method.arguments[0])

    def testRecordRecv(self):
        originalObject = CallTrace("Original")
        originalObject.returnValues={'recv':25*'1'}
        ts = TransparentSocket(originalObject, logFile=self._filename)
        data = ts.recv(1024)
        data = ts.recv(1024)
        self.assertEquals(25*'1', data)
        self.assertEquals('\nrecv:\n%s' % (50*'1'), open(self._filename).read())

    def testRecordRecvAndSendall(self):
        originalObject = CallTrace("Original")
        originalObject.returnValues={'recv':25*'0', 'sendall': None}
        ts = TransparentSocket(originalObject, logFile=self._filename)
        ts.recv(1024)
        ts.sendall("1" * 10)
        self.assertEquals('\nrecv:\n%s\nsend:\n%s' % (25*'0', 10 * '1'), open(self._filename).read())

    def testRecordSend(self):
        originalObject = CallTrace("Original")
        originalObject.returnValues={'send': 5, 'sendall': None}
        ts = TransparentSocket(originalObject, logFile=self._filename)
        byteSend = ts.send(10*'1')
        self.assertEquals(5, byteSend)
        byteSend = ts.send(5*'1')
        self.assertEquals(5, byteSend)

        logfileContents = open(self._filename).read()
        self.assertEquals("\nsend:\n%s" % (10 * '1'), logfileContents)

    def testSendAndSendallAreDisplayedAsSend(self):
        originalObject = CallTrace("Original")
        originalObject.returnValues={'send': 1, 'sendall': None}
        ts = TransparentSocket(originalObject, logFile=self._filename)
        ts.send('0')
        ts.sendall('1')
        logfileContents = open(self._filename).read()
        self.assertEquals("\nsend:\n01", logfileContents)

    def testWorksInSelect(self):
        s = socket()
        s.connect(('localhost', 22))
        ts = TransparentSocket(s)
        select([ts], [ts], [], 0)

