from unittest import TestCase
from weightless import Reactor, local

class LocalTest(TestCase):

    def testOne(self):
        reactor = Reactor(select_func = lambda r,w,o,t: (r,w,o))
        results = []
        oneSharedLocal = local()
        def callback(c):
            oneSharedLocal.someGeneratorSpecificStuff = c
            yield
            results.append(oneSharedLocal.someGeneratorSpecificStuff)
            yield
        reactor.addReader(9, callback('a').next)
        reactor.addReader(8, callback('b').next)
        reactor.step()
        reactor.step()
        self.assertEquals(['b', 'a'], results)
