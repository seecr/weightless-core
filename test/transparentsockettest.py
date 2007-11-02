from unittest import TestCase
from cq2utils import CallTrace
from tempfile import mkstemp
from os import remove

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
        self.assertEquals(25*'1', data)
        self.assertEquals('recv((1024,), {}) -> "%s"\n' % (25*'1'), open(self._filename).read())

    def testRecordSendAndSendall(self):
        originalObject = CallTrace("Original")
        originalObject.returnValues={'send': 5, 'sendall': None}
        ts = TransparentSocket(originalObject, logFile=self._filename)
        byteSend = ts.send(10*'1')
        self.assertEquals(5, byteSend)
        self.assertEquals(1, len(originalObject.calledMethods))
        method = originalObject.calledMethods[0]
        self.assertEquals("send", method.name)
        self.assertEquals(10*'1', method.arguments[0])
        logfileContents = open(self._filename).read()
        self.assertEquals("send(('1111111111',), {}) -> 5\n", logfileContents)

        result = ts.sendall(10*'0')
        self.assertEquals(None, result)
        self.assertEquals(2, len(originalObject.calledMethods))
        method = originalObject.calledMethods[1]
        self.assertEquals("sendall", method.name)
        self.assertEquals(10*'0', method.arguments[0])
        logfileContents = open(self._filename).read()
        self.assertEquals("send(('1111111111',), {}) -> 5\nsendall(('0000000000',), {})\n", logfileContents)

