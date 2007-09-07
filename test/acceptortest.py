from unittest import TestCase
from weightless import Acceptor
from cq2utils import CallTrace
from random import randint

class AcceptorTest(TestCase):

    def testStartListening(self):
        reactor = CallTrace()
        acceptor = Acceptor(randint(2**10, 2**16), reactor, None)
        self.assertEquals('addReader', reactor.calledMethods[0].name)
        sok = reactor.calledMethods[0].args[0]
        self.assertEquals(3, sok.fileno())
        sok.close()
        callback = reactor.calledMethods[0].args[1]
        self.assertTrue(callable(callback))

    def testConnect(self):
        reactor = CallTrace()
        acceptor = Acceptor(randint(2**10, 2**16), reactor, lambda x,y: None)
        self.assertEquals('addReader', reactor.calledMethods[0].name)
        self.assertEquals(3, reactor.calledMethods[0].args[0].fileno())
        reactor.calledMethods[0].args[0].close()
        accept = reactor.calledMethods[0].args[1]
        newSok = CallTrace()
        sok = CallTrace(returnValues={'accept': (newSok, '1.2.3.4')})
        accept(reactor, sok)
        self.assertEquals('accept', sok.calledMethods[0].name)
        self.assertEquals('addReader', reactor.calledMethods[1].name)
        self.assertEquals(newSok, reactor.calledMethods[1].args[0])

    def testCreateSink(self):
        reactor = CallTrace('reactor')
        class sinkFactory(object):
            def __init__(inner, *args, **kwargs): self.args, self.kwargs = args, kwargs
        acceptor = Acceptor(randint(2**10, 2**16), reactor, sinkFactory)
        reactor.calledMethods[0].args[0].close()
        accept = reactor.calledMethods[0].args[1]
        newSok = CallTrace('newSok')
        sok = CallTrace(returnValues={'accept': (newSok, '1.2.3.4')})
        accept(reactor, sok)
        self.assertEquals('addReader', reactor.calledMethods[1].name)
        sink = reactor.calledMethods[1].args[1]
        self.assertEquals((reactor, newSok), self.args)

    def testReadData(self):
        reactor = CallTrace('reactor')
        class sinkFactory(object):
            def __init__(inner, *args, **kwargs):
                self.args, self.kwargs = args, kwargs
            def next(inner):
                self.next = True
        acceptor = Acceptor(randint(2**10, 2**16), reactor, sinkFactory)
        reactor.calledMethods[0].args[0].close()
        accept = reactor.calledMethods[0].args[1]
        newSok = CallTrace('newSok')
        sok = CallTrace(returnValues={'accept': (newSok, '1.2.3.4')})
        accept(reactor, sok)
        sink = reactor.calledMethods[1].args[1]
        self.next = False
        sink.next()
        self.assertTrue(self.next)