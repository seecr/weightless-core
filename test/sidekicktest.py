from unittest import TestCase
from weightless.core import compose

class SidekickTest(TestCase):

    def testCallCallableWithSidekick(self):
        called = []
        def command(sidekick):
            called.append(sidekick)
        def f():
            yield 'a'
            yield command
            yield 'b'

        c = compose(f(), sidekick="sidekick")
        result = list(c)
        self.assertEquals(['a', 'b'], result)
        self.assertEquals(["sidekick"], called)


    def testCallableIsTransparent(self):
        data = []
        called = []
        def command(sidekick):
            called.append(sidekick)
        def f():
            a = yield None
            data.append(a)
            yield command
            b = yield None
            data.append(b)
            yield

        c = compose(f(), sidekick="sidekick")
        none = c.send(None)
        self.assertEquals(None, none)
        none = c.send('a')
        self.assertEquals(None, none)
        none = c.send('b')
        self.assertEquals(None, none)
        self.assertEquals(['a', 'b'], data)
        self.assertEquals(['sidekick'], called)

    def testCallableRaisesException(self):
        def command(sidekick):
            raise RuntimeError("runtimeError")
        def f():
            yield command
        c = compose(f(), sidekick=0)
        try:
            c.next()
            self.fail()
        except RuntimeError, e:
            self.assertEquals("runtimeError", str(e))

    def testCallableRaisesExceptionWhichIsCatchableByGenerators(self):
        def command(sidekick):
            raise RuntimeError("runtimeError")
        def f():
            try:
                yield command
            except RuntimeError, e:
                yield str(e)
        c = compose(f(), sidekick=0)
        self.assertEquals("runtimeError", c.next())

