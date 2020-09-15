## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2015 Seecr (Seek You Too B.V.) http://seecr.nl
#
# This file is part of "Weightless"
#
# "Weightless" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# "Weightless" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with "Weightless"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

from seecr.test import SeecrTestCase, CallTrace
from seecr.test.io import stdout_replaced

from functools import partial

from weightless.core import identify, local, value_with_pushback
from weightless.io import Reactor, reactor, Suspend

from weightless.io.utils import asProcess


class AsProcessTest(SeecrTestCase):
    def testOnlyAcceptsAGeneratorOrGeneratorFunction(self):
        self.assertRaises(TypeError, lambda: asProcess())
        self.assertRaises(TypeError, lambda: asProcess(object()))
        def functionNotReturningAGenerator(whatever):
            return [whatever]
        self.assertRaises(TypeError, lambda: asProcess(functionNotReturningAGenerator)('whatever'))

        # Readable message
        try:
            asProcess(functionNotReturningAGenerator)('whatever')
            self.fail()
        except TypeError as e:
            self.assertEqual("asProcess() expects a generator, got ['whatever']", str(e))

        # decorator
        @asProcess
        def genFDecor():
            return 'ok'
            yield
        self.assertEqual('ok', genFDecor())

        # arguments passed into and returned as retval (normal and as decorator)
        def genF(a, b):
            return (a, b)
            yield
        self.assertEqual((1, 2), asProcess(genF)(1, b=2))
        self.assertEqual((1, 2), asProcess(genF(1, b=2)))

    def testDecorator(self):
        @asProcess
        def g():
            return 1
            yield
        self.assertEqual(1, g())

        class A(object):
            @staticmethod
            @asProcess
            def g():
                return 3
                yield
        self.assertEqual(3, A.g())

        def g(a):
            return a
            yield
        # Below does not work; because partials' output does not look like
        # a normal function.
        # Could be solved with a callable(g) check; though then @warps
        # does not work (expects attributes to be there - like a function).
        #
        # TS: Not worth the effort - just feed the generator (don't decorate)
        #     when using callable non-functions.
        self.assertRaises(TypeError, lambda: asProcess(partial(g, a=2)))

    def testMultipleSerialAsProcesses(self):
        events = []
        def multiple():
            def one():
                events.append('1 start')
                yield '/dev/null (1)'
                events.append('1 yielded')
                result = yield one_2()
                events.append('1 delegated')
                return result
            def one_2():
                events.append('1-2 called')
                return 1
                yield
            def two():
                events.append('2 start')
                yield '/dev/null (2)'
                events.append('2 yielded')
                return 2

            res1 = asProcess(one())
            res2 = asProcess(two())

            return (res1, res2)

        self.assertEqual([], events)

        result = multiple()
        self.assertEqual((1, 2), result)
        self.assertEqual([
                '1 start',
                '1 yielded',
                '1-2 called',
                '1 delegated',
                '2 start',
                '2 yielded',
            ], events)

    def testMultipleNestedAsProcesses(self):
        @asProcess
        def a():
            retval = b()
            return retval
            yield
        @asProcess
        def b():
            retval = c()
            return retval
            yield
        @asProcess
        def c():
            return 'c'
            yield

        self.assertEqual('c', a())

    def testAsProcessInAsyncGeneratorBehavesLikeASynchrounusFunction(self):
        # Internals not leaked, different Reactor, blocking!
        # White-box test; assumes all reactor methods explicitly used are intercepted & passed on to the realReactor.
        realReactor = reactor = Reactor()
        mockReactor = CallTrace("MockReactor", methods={
                'addProcess': realReactor.addProcess,
                'removeProcess': realReactor.removeProcess,
                'addTimer': realReactor.addTimer,
            }
        )
        realReactor.addProcess = mockReactor.addProcess
        realReactor.removeProcess = mockReactor.removeProcess
        realReactor.addTimer = mockReactor.addTimer

        def a():
            return (yield b())
            yield
        def b():
            return "retval"
            yield

        @identify
        def normalAsync():
            this = yield
            reactor.addProcess(this.__next__)
            yield # waiting for realReactor's step()
            result = asProcess(a())
            yield # waiting for another step()
            reactor.removeProcess(this.__next__)
            raise Exception(('Stop', result))

        def raiser():
            raise AssertionError('Failwhale!')
        reactor.addTimer(0.3, raiser)
        normalAsync()
        try:
            reactor.loop()
            self.fail()
        except AssertionError:
            raise
        except Exception as e:
            self.assertEqual(('Stop', 'retval'), e.args[0])

        self.assertEqual(['addTimer', 'addProcess', 'removeProcess'], mockReactor.calledMethodNames())

    def testAsyncReturnValuePassing(self):
        def noRetval():
            return
            yield
        def noneRetval():
            return None
            yield
        def oneRetval():
            return 1
            yield
        def oneRetvalWithIgnoredPushback():
            return value_with_pushback(1, 'p', 'u', 's', 'h')
            yield
        def retvalDependantOnPushbackEval():
            one_ = yield oneRetvalWithIgnoredPushback()
            for _ in ['p', 'u', 's']:
                _ = yield
            return (yield)
        self.assertEqual(None, asProcess(noRetval()))
        self.assertEqual(None, asProcess(noneRetval()))
        self.assertEqual(1, asProcess(oneRetval()))
        self.assertEqual(1, asProcess(oneRetvalWithIgnoredPushback()))
        self.assertEqual('h', asProcess(retvalDependantOnPushbackEval()))

    def testDecoratedFunctionRaises(self):
        def raiser():
            raise Exception('Boom!')
        self.assertRaises(Exception, lambda: asProcess(raiser)())

    def testNormalExceptionHandlingFromAsync(self):
        def g():
            raise Exception('Boom!')
            yield
        self.assertRaises(Exception, lambda: asProcess(g()))

        def g():
            raise BaseException('Boom!')
            yield
        self.assertRaises(BaseException, lambda: asProcess(g()))

    def testGeneratorOrReactorSpecialsExceptionHandlingFromAsync(self):
        # GeneratorExit, (AssertionError, KeyboardInterrupt, SystemExit); all still quit-the-loop; ...
        # shutdown call cannot "hang"; ...
        def gexit():
            raise GeneratorExit()
            yield
        self.assertRaises(GeneratorExit, lambda: asProcess(gexit()))

        def asserr():
            raise AssertionError()
            yield
        self.assertRaises(AssertionError, lambda: asProcess(asserr()))

        def keyint():
            raise KeyboardInterrupt()
            yield
        self.assertRaises(KeyboardInterrupt, lambda: asProcess(keyint()))

        def sysexit():
            raise SystemExit()
            yield
        self.assertRaises(SystemExit, lambda: asProcess(sysexit()))

    def testUnfinishedBusinessInReactorLogs(self):
        neverCalled = []
        def timeAfterFinished():
            assert local('__reactor__') is reactor()  # Code explaining code :-)
            currentReactor = reactor()
            currentReactor.addTimer(1.0, lambda: neverCalled.append(True))
            yield 'async work...'
            currentReactor.addProcess(lambda: neverCalled.append(True))
            return 42

        with stdout_replaced() as out:
            result = asProcess(timeAfterFinished())
            self.assertEqual(42, result)
            self.assertEqual(1, out.getvalue().count('Reactor shutdown:'), out.getvalue())

    def testSuspendProtocolForCallables(self):
        @identify
        def whileSuspended():
            this = yield
            suspend = yield
            suspend._reactor.addProcess(this.__next__)
            yield
            suspend._reactor.removeProcess(this.__next__)
            suspend.resume('whileSuspended')
            yield # Wait for GC
        def suspending():
            s = Suspend(whileSuspended().send)
            yield s
            return s.getResult()
        def thisAndThat():
            this = '42'
            that = yield suspending()
            return (this, that)
        self.assertEqual(('42', 'whileSuspended'), asProcess(thisAndThat()))
