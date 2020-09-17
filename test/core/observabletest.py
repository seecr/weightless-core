# -*- coding: utf-8 -*-
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2007-2009 SURF Foundation. http://www.surf.nl
# Copyright (C) 2007 SURFnet. http://www.surfnet.nl
# Copyright (C) 2007-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2007-2009 Stichting Kennisnet Ict op school. http://www.kennisnetictopschool.nl
# Copyright (C) 2010 Stichting Kennisnet http://www.kennisnet.nl
# Copyright (C) 2011-2013, 2015 Seecr (Seek You Too B.V.) http://seecr.nl
# Copyright (C) 2015 Koninklijke Bibliotheek (KB) http://www.kb.nl
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

import gc
from sys import exc_info
from traceback import format_tb
from inspect import isframe, getframeinfo
from types import GeneratorType
from functools import partial
from weightless.core import compose, Yield, Observable, Transparent, be, tostring, NoneOfTheObserversRespond, DeclineMessage, cextension
from weightless.core._observable import AllMessage, AnyMessage, DoMessage, OnceMessage
from weightless.core import consume
from unittest import TestCase
from seecr.test import CallTrace
from seecr.test.utils import ignoreLineNumbers

fileDict = {
    '__file__' : __file__.replace(".pyc", ".py")
}


def skip_if(condition):
    class Noop(object): pass
    def do_not_skip(test): return test
    def do_skip(test): return Noop()
    return do_skip if condition else do_not_skip

class ObservableTest(TestCase):
    def testAllWithoutImplementers(self):
        observable = Observable()
        responses = observable.all.someMethodNobodyIsListeningTo()
        self.assertEqual([], list(compose(responses)))

    def testAllWithOneImplementer(self):
        class A(object):
            def f(self):
                yield A.f
        root = be((Observable(), (A(),),))
        self.assertEqual([A.f], list(compose(root.all.f())))

    def testAllWithOneImplementerButMoreListening(self):
        class A(object):
            pass
        class B(object):
            def f(self):
                yield B.f
        root = be((Observable(), (A(),), (B(),)))
        self.assertEqual([B.f], list(compose(root.all.f())))

    def testAllWithMoreImplementers(self):
        class A(object):
            def f(self):
                yield A.f
        class B(object):
            def f(self):
                yield B.f
        root = be((Observable(), (A(),), (B(),)))
        self.assertEqual([A.f, B.f], list(compose(root.all.f())))

    def testAllWithException(self):
        class A(object):
            def f(self):
                raise Exception(A.f)
                yield
        class B(object):
            def f(self):
                yield Yield
        root = be((Observable(), (A(),), (B(),)))
        c = compose(root.all.f())
        try:
            next(c)
            self.fail()
        except Exception as e:
            self.assertEqual(A.f, e.args[0])
        root = be((Observable(), (B(),), (A(),))) # other way around
        c = compose(root.all.f())
        next(c)
        try:
            next(c)
            self.fail()
        except Exception as e:
            self.assertEqual(A.f, e.args[0])

    def testAllUnknown(self):
        class A(object):
            def all_unknown(self, *args, **kwargs):
                yield args, kwargs
        root = be((Observable(), (A(),)))
        r = next(compose(root.all.unknownmessage(1, two=2)))
        self.assertEqual((('unknownmessage', 1), {'two': 2}), r)

    def testAllAssertsNoneReturnValues(self):
        class A(object):
            def f(self):
                return 1
                yield
            def all_unknown(self, message, *args, **kwargs):
                return 2
                yield
        root = be((Observable(), (A(),)))
        g = compose(root.all.f())
        try:
            next(g)
            self.fail("Should not happen")
        except AssertionError as e:
            self.assertTrue("<bound method ObservableTest.testAllAssertsNoneReturnValues.<locals>.A.f of <core.observabletest.ObservableTest.testAllAssertsNoneReturnValues.<locals>.A object at 0x" in str(e), str(e))
            self.assertTrue(">> returned '1'" in str(e), str(e))
        g = compose(root.all.x())
        try:
            next(g)
            self.fail("Should not happen")
        except AssertionError as e:
            self.assertTrue("> returned '2'" in str(e), str(e))
            if not cextension:
                self.assertTrue("<bound method ObservableTest.testAllAssertsNoneReturnValues.<locals>.A.all_unknown of <core.observabletest.ObservableTest.testAllAssertsNoneReturnValues.<locals>.A object at 0x" in str(e), str(e))

    @skip_if(cextension)
    def testAllAssertsResultOfCallIsGeneratorOrComposed(self):
        #Py3: traceback have _compose, all etc.. in them again
        class A(object):
            def f(self):
                return 42
            def all_unknown(self, message, *args, **kwargs):
                return 42
        root = be((Observable(), (Transparent(), (A(),))))
        g = compose(root.all.f())
        try:
            next(g)
            self.fail("Should not happen")
        except AssertionError as e:
            self.assertTrue("<bound method ObservableTest.testAllAssertsResultOfCallIsGeneratorOrComposed.<locals>.A.f of <core.observabletest.ObservableTest.testAllAssertsResultOfCallIsGeneratorOrComposed.<locals>.A object at 0x" in str(e), str(e))
            self.assertTrue(">> should have resulted in a generator." in str(e), str(e))
            self.assertFunctionsOnTraceback("testAllAssertsResultOfCallIsGeneratorOrComposed", "_compose", "all", "all_unknown", "all", "verifyMethodResult")

        g = compose(root.all.undefinedMethod())
        try:
            next(g)
            self.fail("Should not happen")
        except AssertionError as e:
            self.assertTrue("<bound method ObservableTest.testAllAssertsResultOfCallIsGeneratorOrComposed.<locals>.A.all_unknown of <core.observabletest.ObservableTest.testAllAssertsResultOfCallIsGeneratorOrComposed.<locals>.A object at 0x" in str(e), str(e))
            self.assertTrue(">> should have resulted in a generator." in str(e), str(e))

    def testOnceAssertsNoneReturnValues(self):
        # Py3: Output of strackstaces changed
        # OnceMessage assertion on None: #1a "normal object"
        class AnObject(object):
            def f(self):
                return 1
                yield

        # OnceMessage assertion on None: #1b "Observable"
        class AnObservable(Observable):
            def g(self):
                return 1
                yield

        root = be(
        (Observable(),
            (AnObject(),),
            (AnObservable(),),
        ))
        composed = compose(root.once.f())
        try:
            next(composed)
            self.fail("Should not happen")
        except AssertionError as e:
            self.assertTrue("<bound method ObservableTest.testOnceAssertsNoneReturnValues.<locals>.AnObject.f of <core.observabletest.ObservableTest.testOnceAssertsNoneReturnValues.<locals>.AnObject object at 0x" in str(e))
            #self.assertTrue("<bound method AnObject.f of <core.observabletest.AnObject object at 0x" in str(e), str(e))
            self.assertTrue(">> returned '1'" in str(e), str(e))

        root = be((Observable(), (AnObservable(),)))
        composed = compose(root.once.g())
        try:
            next(composed)
            self.fail("Should not happen")
        except AssertionError as e:
            self.assertEqual("<bound method ObservableTest.testOnceAssertsNoneReturnValues.<locals>.AnObservable.g of AnObservable(name=None)> returned '1'", str(e))
            #self.assertTrue("<bound method AnObservable.g of AnObservable(name=None)" in str(e), str(e))
            #self.assertTrue("> returned '1'" in str(e), str(e))

    def testOnceAssertsRecursivenessGivesNoReturnValue(self):
        # This will normally never happen.
        class AnObservable(Observable):
            def g(self):
                return 1
                yield
        class MockedOnceMessageSelf(OnceMessage):
            pass
        def retvalGen(*args, **kwargs):
            return 1
            yield
        oncedObservable = AnObservable()
        mockedSelf = MockedOnceMessageSelf(observers=oncedObservable._observers, message='noRelevantMethodHere', observable='AnObservableObject(name=None)')
        mockedSelf._callonce = retvalGen

        composed = compose(OnceMessage._callonce(mockedSelf, observers=[AnObservable()], args=(), kwargs={}, seen=set()))
        try:
            next(composed)
            self.fail("Should not happen")
        except AssertionError as e:
            self.assertEqual("OnceMessage of AnObservableObject(name=None) returned '1', but must always be None", str(e))

    def testAnyOrCallCallsFirstImplementer(self):
        class A(object):
            def f(self):
                return A.f
                yield
            def f_sync(self):
                return A.f
        class B(object):
            def f(self):
                return B.f
                yield
            def f_sync(self):
                return B.f
            def g(self):
                return B.g
                yield
            def g_sync(self):
                return B.g
        root = be((Observable(), (A(),), (B(),)))

        try:
            next(compose(root.any.f()))
            self.fail('Should not happen')
        except StopIteration as e:
            self.assertEqual((A.f,), e.args)
        try:
            next(compose(root.any.g()))
            self.fail('Should not happen')
        except StopIteration as e:
            self.assertEqual((B.g,), e.args)

        self.assertEqual(A.f, root.call.f_sync())
        self.assertEqual(B.g, root.call.g_sync())

    def testAnyViaOther(self):
        class A(Observable):
            def f(self):
                response = yield self.any.f()
                return response
        class B(object):
            def f(self):
                yield "data"
                return "retval"
        root = be((Observable(), ((A(), (B(),)))))
        self.assertEqual(GeneratorType, type(root.any.f()))
        self.assertEqual(["data"], list(compose(root.any.f())))

        composed = compose(root.any.f())
        try:
            next(composed)  # 'data'
            next(composed)  # return 'retval'
            self.fail('Should not happen')
        except StopIteration as e:
            self.assertEqual(('retval',), e.args)

    @skip_if(cextension)
    def testAnyAssertsResultOfCallIsGeneratorOrComposed(self):
        class A(object):
            def f(self):
                return 42
            def any_unknown(self, message, *args, **kwargs):
                return 42
        root = be((Observable(), (A(),)))
        try:
            next(compose(root.any.f()))
            self.fail('Should not happen')
        except AssertionError as e:
            self.assertTrue("<bound method ObservableTest.testAnyAssertsResultOfCallIsGeneratorOrComposed.<locals>.A.f of <core.observabletest.ObservableTest.testAnyAssertsResultOfCallIsGeneratorOrComposed.<locals>.A object at 0x" in str(e), str(e))
            self.assertTrue(">> should have resulted in a generator." in str(e), str(e))

        try:
            next(compose(root.any.undefinedMethod()))
            self.fail('Should not happen')
        except AssertionError as e:
            self.assertTrue("<bound method ObservableTest.testAnyAssertsResultOfCallIsGeneratorOrComposed.<locals>.A.any_unknown of <core.observabletest.ObservableTest.testAnyAssertsResultOfCallIsGeneratorOrComposed.<locals>.A object at 0x" in str(e), str(e))
            self.assertTrue(">> should have resulted in a generator." in str(e), str(e))

    def testAnyViaUnknown(self):
        class A(object):
            def any_unknown(self, message, *args, **kwargs):
                return (message, args, kwargs)
                yield
        root = be((Observable(), (A(),)))
        try: next(compose(root.any.f(1, a=2)))
        except StopIteration as e: r = e.args[0]
        self.assertEqual(('f', (1,), {'a': 2}), r)

    def testCallViaUnknown(self):
        class A(object):
            def call_unknown(self, message, *args, **kwargs):
                return message, args, kwargs
        root = be((Observable(), (A(),)))
        r = root.call.f(1, a=2)
        self.assertEqual(('f', (1,), {'a': 2}), r)

    def testDoReturnsNone(self):
        observable = Observable()
        r = observable.do.f()
        self.assertEqual(None, r)

    def testDoCallsAllObservers(self):
        called = []
        class A(object):
            def f(self):
                called.append(A.f)
        class B(object):
            def f(self):
                called.append(B.f)
        root = be((Observable(), (A(),), (B(),)))
        root.do.f()
        self.assertEqual([A.f, B.f], called)

    def testDoViaUnknown(self):
        called = []
        class A(object):
            def do_unknown(self, message, *args, **kwargs):
                called.append((message, args, kwargs))
        root = be((Observable(), (A(),)))
        root.do.f()
        self.assertEqual([('f', (), {})], called)

    @skip_if(cextension)
    def testDoAssertsIndividualCallsReturnNone(self):
        class A(object):
            def f(self):
                return
                yield
            def do_unknown(self, message, *args, **kwargs):
                return 42
        root = be((Observable(), (A(),)))

        try:
            root.do.f()
            self.fail('Should not happen')
        except AssertionError as e:
            self.assertTrue("<bound method ObservableTest.testDoAssertsIndividualCallsReturnNone.<locals>.A.f of <core.observabletest.ObservableTest.testDoAssertsIndividualCallsReturnNone.<locals>.A object at 0x" in str(e), str(e))
            self.assertTrue(">> returned '<generator object" in str(e), str(e))

        try:
            root.do.undefinedMethod()
            self.fail('Should not happen')
        except AssertionError as e:
            self.assertTrue("<bound method ObservableTest.testDoAssertsIndividualCallsReturnNone.<locals>.A.do_unknown of <core.observabletest.ObservableTest.testDoAssertsIndividualCallsReturnNone.<locals>.A object at 0x" in str(e), str(e))
            self.assertTrue(">> returned '42'" in str(e), str(e))

    def testUnknownDispatchingNoImplementation(self):
        observable = Observable()
        class A(object):
            pass
        observable.addObserver(A())
        retval = observable.all.unknown('non_existing_method', 'one')
        self.assertEqual([], list(compose(retval)))

    def testUnknownDispatching(self):
        observable = Observable()
        class Listener(object):
            def method(inner, one):
                return one + " another"
        observable.addObserver(Listener())
        retval = observable.call.unknown('method', 'one')
        self.assertEqual('one another', retval)

    def testUnknownDispatchingBackToUnknown(self):
        observable = Observable()
        class A(object):
            def call_unknown(self, message, one):
                return "via unknown " + one
        observable.addObserver(A())
        retval = observable.call.unknown('non_existing_method', 'one')
        self.assertEqual("via unknown one", retval)

    def testUnknownIsEquivalentToNormalCall(self):
        observable = Observable()
        class A(object):
            def normal(self):
                return 'normal'
            def call_unknown(self, message, *args, **kwargs):
                return 'normal'
        observable.addObserver(A())
        result1 = observable.call.unknown('normal')
        result2 = observable.call.unknown('other')
        self.assertEqual(result1, result2)

    def testBeOne(self):
        observer = Observable()
        root = be((observer,))
        self.assertEqual(root, observer)

    def testBeTwo(self):
        observable = Observable()
        child0 = Observable()
        child1 = Observable()
        root = be((observable, (child0,), (child1,)))
        self.assertEqual([child0, child1], observable._observers)

    def testBeTree(self):
        observable = Observable()
        child0 = Observable()
        child1 = Observable()
        root = be((observable, (child0, (child1,))))
        self.assertEqual([child0], root._observers)
        self.assertEqual([child1], child0._observers)

    def testAddStrandEmptyList(self):
        observable = Observable()
        observable.addStrand((), [])
        self.assertEqual([], observable._observers)

    def testProperErrorMessage(self):
        observable = Observable()
        try:
            answer = list(compose(observable.any.gimmeAnswer('please')))
            self.fail('should raise NoneOfTheObserversRespond')
        except NoneOfTheObserversRespond as e:
            # broken traceback cleaning: _compose
            self.assertFunctionsOnTraceback("testProperErrorMessage", "_compose", "any")
            self.assertEqual('None of the 0 observers respond to gimmeAnswer(...)', str(e))

    def testProperErrorMessageWhenArgsDoNotMatch(self):
        observable = Observable()
        class YesObserver:
            def yes(self, oneArg): pass
        observable.addObserver(YesObserver())
        try:
            answer = observable.call.yes()
            self.fail('should raise TypeError')
        except TypeError as e:
            self.assertEqual("yes() missing 1 required positional argument: 'oneArg'", str(e))

    def testWhatItIs(self):
        def anAction():
            pass
        events = []
        class A(Observable):
            def dataflow(this): #all
                yield this.all.dataflow()
            def interface(this): #call
                return this.call.interface()
            def async_interface(this): # any
                r = yield this.any.async_interface()
                return r
            def event(this): #do
                this.do.event()
        class B(Observable):
            def dataflow(this): #all
                yield this.all.dataflow()
            def interface(this): #call
                return this.call.interface()
            def async_interface(this): #any
                r = yield this.any.async_interface()
                return r
            def event(this): #do
                this.do.event()
        class C(Observable):
            def dataflow(this): #all
                x = yield
                yield x * 'C'
            def interface(this): #call
                return 'C'
            def async_interface(this): #any
                yield anAction
                x = yield
                yield x * 'C'
                return x
            def event(this): #do
                events.append('C')
        class D(Observable):
            def dataflow(this): #all
                x = yield
                yield x * 'D'
            def interface(this): #call
                raise Exception('hell')
            def async_interface(this): #any
                raise Exception('hell')
            def event(this): #do
                events.append('D')
        t = be((Observable(),
                    (A(),
                        (B(),
                            (C(),),
                            (D(),),
                        )
                    )
                ))
        result = compose(t.all.dataflow())
        next(result)
        r = result.send(2)
        self.assertEqual('CC', r)
        next(result)
        r = result.send(3)
        self.assertEqual('DDD', r)

        result = t.call.interface()
        self.assertEqual('C', result)

        noResult = t.do.event()
        self.assertEqual(None, noResult)
        self.assertEqual(['C', 'D'], events)

        result = compose(t.any.async_interface())
        an_action = next(result)
        self.assertEqual(anAction, an_action)
        next(result)
        r = result.send(5)
        self.assertEqual('CCCCC', r)
        try:
            next(result)
            self.fail()
        except StopIteration as e:
            self.assertEqual((5,), e.args)

    def testTransparentUnknownImplementationIsVisibleOnTraceback(self):
        # Due to broken traceback cleaning in py3 there are extra calls in the stracktrace
        # _compose, any, all, unknown and call should be filtered out.
        class Leaf(Observable):
            def aCall(self):
                raise RuntimeError('trace')
            def aAny(self):
                def lookBusy():
                    raise RuntimeError('trace')
                    return
                    yield
                ignored = yield lookBusy()
            def aAll(self):
                raise RuntimeError('trace')
                yield 'ignored'
            def aDo(self):
                raise RuntimeError('trace')
        root = be((Observable(),
            (Transparent(),
                (Leaf(),),
            ),
        ))

        try:
            root.call.aCall()
            self.fail('Should not happen')
        except RuntimeError:
            self.assertFunctionsOnTraceback('testTransparentUnknownImplementationIsVisibleOnTraceback', 'call', 'call_unknown', 'unknown', 'call', 'aCall')

        try:
            next(compose(root.any.aAny()))
            self.fail('Should not happen')
        except RuntimeError:
            self.assertFunctionsOnTraceback('testTransparentUnknownImplementationIsVisibleOnTraceback', '_compose', 'any', 'any_unknown', 'any', 'aAny', 'lookBusy')

        try:
            next(compose(root.all.aAll()))
            self.fail('Should not happen')
        except RuntimeError:
            self.assertFunctionsOnTraceback('testTransparentUnknownImplementationIsVisibleOnTraceback', '_compose', 'all', 'all_unknown', 'all', 'aAll')

        try:
            root.do.aDo()
            self.fail('Should not happen')
        except RuntimeError:
            self.assertFunctionsOnTraceback('testTransparentUnknownImplementationIsVisibleOnTraceback', 'do', 'all', 'do_unknown', 'unknown', 'do', 'all', 'aDo')

    def testFixUpExceptionTraceBack(self):
        # Py3: Tracebacks dont hide unwanted function calls anymore
        class A:
            def a(this):
                raise Exception('A.a')
            def any_unknown(this, msg, *args, **kwargs):
                yield this.a()
        observable = Observable()
        observable.addObserver(A())
        try:
            list(compose(observable.any.a()))
        except Exception as e:
            self.assertFunctionsOnTraceback("testFixUpExceptionTraceBack", "_compose", "any", "all", "a")
        else:
            self.fail('Should not happen.')

        try:
            list(compose(observable.all.a()))
        except Exception:
            self.assertFunctionsOnTraceback("testFixUpExceptionTraceBack", "_compose", "all", "a")
        else:
            self.fail('Should not happen.')

        try:
            observable.do.a()
        except Exception:
            self.assertFunctionsOnTraceback("testFixUpExceptionTraceBack", "do", "all", "a")
        else:
            self.fail('Should not happen.')

        try:
            observable.call.a()
        except Exception:
            self.assertFunctionsOnTraceback("testFixUpExceptionTraceBack", "call", "a")
        else:
            self.fail('Should not happen.')

        try:
            list(compose(observable.any.unknown('a')))
        except Exception:
            self.assertFunctionsOnTraceback("testFixUpExceptionTraceBack", "_compose", "any", "all", "a")
        else:
            self.fail('Should not happen.')

        try:
            list(compose(observable.any.somethingNotThereButHandledByUnknown('a')))
        except Exception:
            self.assertFunctionsOnTraceback("testFixUpExceptionTraceBack", "_compose", "any", "any_unknown", "a")
        else:
            self.fail('Should not happen.')

    def testMoreElaborateExceptionCleaning(self):
        # Py3: broken traceback cleanup
        class A(Observable):
            def a(self): return self.call.b()
        class B(Observable):
            def b(self): return self.call.c()
        class C(Observable):
            def c(self): return self.call.d()
        class D:
            def d(self): raise Exception('D.d')
        a = A()
        b = B()
        c = C()
        a.addObserver(b)
        b.addObserver(c)
        c.addObserver(D())
        try:
            a.a()
            self.fail('should raise exception')
        except:
            self.assertFunctionsOnTraceback('testMoreElaborateExceptionCleaning', 'a', 'call', 'b', 'call', 'c', 'call', 'd')
            #self.assertFunctionsOnTraceback("testMoreElaborateExceptionCleaning", "a", "b", "c", "d")

    def testObserverInit(self):
        initcalled = [0]
        class MyObserver(object):
            def observer_init(self):
                yield  # once is async
                initcalled[0] += 1
        root = be((Observable(), (MyObserver(),)))
        self.assertEqual([0], initcalled)
        consume(root.once.observer_init())
        self.assertEqual([1], initcalled)

    def testAddObserversOnce(self):
        class MyObservable(Observable):
            pass
        o1 = MyObservable(name='O1')
        o2 = MyObservable(name='O2')
        o3 = MyObservable(name='O3')
        o4 = MyObservable(name='O4')
        o5 = MyObservable(name='O5')
        helix = \
            (o1,
                (o2, )
            )
        dna =   (o3,
                    helix,
                    (o4,),
                    (o5, helix)
                 )
        root = be(dna)
        self.assertEqual([o2], o1._observers)
        self.assertEqual([], o2._observers)
        self.assertEqual([o1, o4, o5], o3._observers)
        self.assertEqual([], o4._observers)
        self.assertEqual([o1], o5._observers)

    def testOnceAndOnlyOnce(self):
        class MyObserver(Observable):
            def methodOnlyCalledOnce(self, aList):
                aList.append('once')
                return
                yield
        once = MyObserver()
        dna = \
            (Observable(),
                (once,),
                (once,)
            )
        root = be(dna)
        collector = []
        methodOnlyCalledOnce = root.once.methodOnlyCalledOnce
        consume(methodOnlyCalledOnce(collector))
        self.assertEqual(['once'], collector)
        self.assertTrue(once in methodOnlyCalledOnce.seen)
        self.assertTrue(once in methodOnlyCalledOnce.called)

    def testOnceCalledMethodsMustResultInAGeneratorOrComposeOrNone(self):
        callLog = []
        class MyObserver(Observable):
            def __init__(self):
                Observable.__init__(self)
                self.generatorReturningCallable = partial(lambda arg: (x for x in 'a'), arg='partialed')

            def noGeneratorFunction(self):
                callLog.append('function called')

            def valueReturningFunction(self):
                return 42

            def composedGenerator(self):
                return compose(x for x in 'a')

        once = MyObserver()
        dna = \
            (Observable(),
                (once,),
            )
        root = be(dna)
        list(compose(root.once.noGeneratorFunction()))
        self.assertEqual(['function called'], callLog)

        try:
            list(compose(root.once.valueReturningFunction()))
            self.fail("Should have gotten AssertionError because of unexpected return value")
        except AssertionError as e:
            self.assertEqual("<bound method ObservableTest.testOnceCalledMethodsMustResultInAGeneratorOrComposeOrNone.<locals>.MyObserver.valueReturningFunction of MyObserver(name=None)> returned '42'", str(e))
            #self.assertEqual("<bound method MyObserver.valueReturningFunction of MyObserver(name=None)> returned '42'", str(e))

        try:
            result = list(compose(root.once.composedGenerator()))
            self.assertEqual(['a'], result)
        except AssertionError as e:
            self.fail('Should not fail: %s' % e)

        try:
            result = list(compose(root.once.generatorReturningCallable()))
            self.assertEqual(['a'], result)
        except AssertionError as e:
            self.fail('Should not fail: %s' % e)

    def testOnceInDiamondWithTransparent(self):
        class MyObserver(Observable):
            def methodOnlyCalledOnce(self, aList):
                aList.append('once')
                return
                yield
        t1 = Transparent(name="A")
        t2 = Transparent(name="B")
        t3 = Transparent(name="C")
        once = MyObserver("D")
        diamond = \
            (t1,
                (t2,
                    (once,)
                ),
                (t3,
                    (once,)
                )
            )
        root = be(diamond)
        collector = []
        methodOnlyCalledOnce = root.once.methodOnlyCalledOnce
        consume(methodOnlyCalledOnce(collector))
        self.assertTrue(once in methodOnlyCalledOnce.seen)
        self.assertTrue(t2 in methodOnlyCalledOnce.seen)
        self.assertTrue(t3 in methodOnlyCalledOnce.seen)
        self.assertEqual(3, len(methodOnlyCalledOnce.seen))
        self.assertEqual(set([once]), methodOnlyCalledOnce.called)
        self.assertEqual(['once'], collector)

    def testPropagateThroughAllObservablesInDiamondWithNONTransparentObservablesWithoutUnknownMethodDelegatingUnknownCalls(self):
        class MyObserver(Observable):
            def methodOnlyCalledOnce(self, aList):
                aList.append('once')
                return
                yield
        once = MyObserver()
        diamond = \
            (Observable(),
                (Observable(),
                    (once,)
                ),
                (Observable(),
                    (once,)
                )
            )
        root = be(diamond)
        collector = []
        list(compose(root.once.methodOnlyCalledOnce(collector)))
        self.assertEqual(['once'], collector)

    def testNonObservableInTreeWithOnce(self):
        class MyObserver(object):
            def methodOnNonObservableSubclass(self, aList):
                aList.append('once')
                return
                yield
        once = MyObserver()
        dna =   (Observable(),
                    (once,)
                )
        root = be(dna)
        collector = []
        list(compose(root.once.methodOnNonObservableSubclass(collector)))
        self.assertEqual(['once'], collector)

    def testOnceAndOnlyOnceForMutuallyObservingObservables(self):
        class MyObserver(Observable):
            def methodOnlyCalledOnce(self, aList):
                aList.append(self)
                return
                yield
        ownobserverobserver = MyObserver()
        dna = \
            (Observable(),
                (ownobserverobserver,
                    (Observable("observer"),
                        (ownobserverobserver,),
                    )
                )
            )
        root = be(dna)
        collector = []
        list(compose(root.once.methodOnlyCalledOnce(collector)))
        self.assertEqual([ownobserverobserver], collector)

    def testOnceInternalsNotOnTracebackUnlessAssertsAndThenOnlyOnce(self):
        class OnceRaiser(object):
            def raisesOnCall(self):
                raise BaseException('Boom')
            def raisesOnCallGenerator(self):
                raise BaseException('Ka-Boom')
                yield

        dna = (Observable(),              # called-from
            (Observable(),                # 1
                (Observable(),            # 2
                    (Observable(),        # 3
                        (OnceRaiser(),),  # target
                    )
                )
            )
        )
        root = be(dna)

        try:
            list(compose(root.once.raisesOnCallGenerator()))
        except BaseException:
            self.assertFunctionsOnTraceback('testOnceInternalsNotOnTracebackUnlessAssertsAndThenOnlyOnce', '_compose', '_callonce', '_callonce', '_callonce', '_callonce', 'raisesOnCallGenerator')
            #self.assertFunctionsOnTraceback('testOnceInternalsNotOnTracebackUnlessAssertsAndThenOnlyOnce', 'raisesOnCallGenerator')
        else:
            self.fail('Should not happen')

        try:
            list(compose(root.once.raisesOnCall()))
        except BaseException:
            self.assertFunctionsOnTraceback('testOnceInternalsNotOnTracebackUnlessAssertsAndThenOnlyOnce', '_compose', '_callonce', '_callonce', '_callonce', '_callonce', 'raisesOnCall')
            #self.assertFunctionsOnTraceback('testOnceInternalsNotOnTracebackUnlessAssertsAndThenOnlyOnce', 'raisesOnCall')
        else:
            self.fail('Should not happen')

    @skip_if(cextension)
    def testNonGeneratorMethodMayNeverRaiseGeneratorExceptionsOnMessages(self):
        # Py3: broken tracebacks
        # any, all, do, call and once
        class OddObject(object):
            def stopIter(self):
                raise StopIteration('Stop!')
            def genExit(self):
                raise GeneratorExit('Exit!')

        dna = (Observable(),
            (Transparent(),
                (OddObject(),),
            )
        )
        root = be(dna)

        # Verify traceback's and wrapped-exception text is ok
        try: root.call.stopIter()
        except AssertionError as e:
            self.assertTrue(str(e).startswith('Non-Generator <bound method ObservableTest.testNonGeneratorMethodMayNeverRaiseGeneratorExceptionsOnMessages.<locals>.OddObject.stopIter of <core.observabletest.ObservableTest.testNonGeneratorMethodMayNeverRaiseGeneratorExceptionsOnMessages.<locals>.OddObject object at 0x'), str(e))
            #self.assertTrue(str(e).startswith('Non-Generator <bound method OddObject.stopIter of <core.observabletest.OddObject object at 0x'), str(e))
            expected = ignoreLineNumbers('''>> should not have raised Generator-Exception:
Traceback (most recent call last):
  File "%(__file__)s", line [#], in stopIter
    raise StopIteration('Stop!')
StopIteration: Stop!
''' % fileDict)
            self.assertTrue(ignoreLineNumbers(str(e)).endswith(expected), str(e))
            self.assertFunctionsOnTraceback('testNonGeneratorMethodMayNeverRaiseGeneratorExceptionsOnMessages', 'call', 'call_unknown', 'unknown', 'call', 'handleNonGeneratorGeneratorExceptions')
            #self.assertFunctionsOnTraceback(
            #    'testNonGeneratorMethodMayNeverRaiseGeneratorExceptionsOnMessages',
            #    'call_unknown',  # From Transparent, is supposed to be on the stack to aid retracing the path taken for a messages.
            #    'handleNonGeneratorGeneratorExceptions')
        else: self.fail('Should not happen')

        try: root.call.genExit()
        except AssertionError as e:
            self.assertTrue(str(e).startswith('Non-Generator <bound method ObservableTest.testNonGeneratorMethodMayNeverRaiseGeneratorExceptionsOnMessages.<locals>.OddObject.genExit of <core.observabletest.ObservableTest.testNonGeneratorMethodMayNeverRaiseGeneratorExceptionsOnMessages.<locals>.OddObject object at 0x'), str(e))
            #self.assertTrue(str(e).startswith('Non-Generator <bound method OddObject.genExit of <core.observabletest.OddObject object at 0x'), str(e))
            expected = ignoreLineNumbers('''>> should not have raised Generator-Exception:
Traceback (most recent call last):
  File "%(__file__)s", line [#], in genExit
    raise GeneratorExit('Exit!')
GeneratorExit: Exit!
''' % fileDict)
            self.assertTrue(ignoreLineNumbers(str(e)).endswith(expected), str(e))
            self.assertFunctionsOnTraceback('testNonGeneratorMethodMayNeverRaiseGeneratorExceptionsOnMessages', 'call', 'call_unknown', 'unknown', 'call', 'handleNonGeneratorGeneratorExceptions')
            #self.assertFunctionsOnTraceback(
            #    'testNonGeneratorMethodMayNeverRaiseGeneratorExceptionsOnMessages',
            #    'call_unknown',  # From Transparent, is supposed to be on the stack to aid retracing the path taken for a messages.
            #    'handleNonGeneratorGeneratorExceptions')
        else: self.fail('Should not happen')

        # Verify logic implemented in all messages, with traceback-manipulation
        for observableCallName, failMethod in [
                    ('do', 'stopIter'),
                    ('do', 'genExit'),
                    ('any', 'stopIter'),
                    ('any', 'genExit'),
                    ('all', 'stopIter'),
                    ('all', 'genExit'),
                    ('once', 'stopIter'),
                    ('once', 'genExit'),
                ]:
            try:
                _ = getattr(getattr(root, observableCallName), failMethod)()
                if observableCallName != 'do':
                    list(compose(_))
            except AssertionError as e:
                self.assertTrue('should not have raised Generator-Exception:' in str(e), str(e))
                expected = [
                    'testNonGeneratorMethodMayNeverRaiseGeneratorExceptionsOnMessages',
                    'handleNonGeneratorGeneratorExceptions',
                ]
                if observableCallName != 'once':
                    expected[1:1] = '%s_unknown' % observableCallName,  # From Transparent, is supposed to be on the stack to aid retracing the path taken for a messages.
                # Py3: Not what we expected but due to traceback being busted it is what it is
                functionsOnTraceback = self.getFunctionsOnTraceback()
                self.assertEqual("testNonGeneratorMethodMayNeverRaiseGeneratorExceptionsOnMessages", functionsOnTraceback[0])
                self.assertEqual("handleNonGeneratorGeneratorExceptions", functionsOnTraceback[-1])
                #self.assertFunctionsOnTraceback(*expected)
            else: self.fail('Should not happen')

    def testNoLeakingGeneratorsInCycle(self):
        class Responder(Observable):
            def message(self):
                yield 'response'
        obs = Observable()
        obs.addObserver(Responder())
        result = next(compose(obs.all.message()))
        self.assertEqual('response',result)
        del obs

    def testNoLeakingGeneratorsInMultiTransparents(self):
        class Responder(Observable):
            def message(self):
                return 'response'
        obs = Observable()
        t1 = Transparent()
        t2 = Transparent()
        obs.addObserver(t1)
        t1.addObserver(t2)
        t2.addObserver(Responder())
        result = obs.call.message()
        self.assertEqual('response', result)
        del obs, t1, t2, result

    def testMatchingBasedOnDefaultArgs(self):
        class A(object):
            def a(x, y=10, z=11):
                p = 1
                q = 2
                yield
        a = A()
        func = a.a
        code = func.__code__
        func_defaults = func.__defaults__
        self.assertEqual((10,11), func_defaults)
        argcount = code.co_argcount
        self.assertEqual(3, argcount)
        varnames = code.co_varnames
        self.assertEqual(('x', 'y', 'z', 'p', 'q'), varnames)
        argnames = varnames[:argcount]
        self.assertEqual(('x','y','z'), argnames)
        kwargsnames = argnames[-len(func_defaults):]
        self.assertEqual(('y','z'), kwargsnames)
        kwargdefaults = dict(list(zip(kwargsnames, func_defaults)))
        self.assertEqual({'y':10, 'z':11}, kwargdefaults)
        self.assertEqual({'z':11, 'y':10}, kwargdefaults)
        func.__dict__['kwargdefaults'] = kwargdefaults
        self.assertEqual({'z':11, 'y':10}, func.kwargdefaults)

        class Wildcard(object):
            def __eq__(self, other):
                return True
        self.assertTrue({'z':11, 'y':10} == {'z':11, 'y': Wildcard()})

    def testTransparentInCaseNoneOfTheObserversRespond(self):
        root = be((Observable(),
            (Transparent(),),
            (Transparent(),
                (Transparent(),
                   (object(),)
                ),
            ),
            (Responder(42),),
        ))

        self.assertEqual(42, root.call.m())

        try:
            g = compose(root.any.m())
            self.assertEqual(42, next(g))
            next(g)
            self.fail("Should have raised StopIteration")
        except StopIteration as e:
            self.assertEqual((42,), e.args)

    def testObserverAttributeErrorNotIgnored(self):
        class GetAttr(object):
            def __init__(self, attrName):
                self.attrName = attrName
            def call_unknown(self, message, *args, **kwargs):
                return getattr(self, self.attrName)
            def any_unknown(self, message, *args, **kwargs):
                return getattr(self, self.attrName)
                yield

        root = be((Observable(),
            (Transparent(),
                (GetAttr('doesnotexist'),)
            ),
            (GetAttr('__class__'),)
        ))

        try:
            result = root.call.someMessage()
            self.fail("should not get here: %s" % result)
        except AttributeError as e:
            self.assertEqual("'GetAttr' object has no attribute 'doesnotexist'", str(e))

        try:
            list(compose(root.any.someMessage()))
            self.fail("should not get here")
        except AttributeError as e:
            self.assertEqual("'GetAttr' object has no attribute 'doesnotexist'", str(e))

    def testThrow(self):
        class A(Observable):
            def f1(self):
                yield "A:f1-1"
                yield "A:f1-2"
                yield "A:f1-3"
        class B(Observable):
            def f1(self):
                yield "B:f1-1"
                yield "B:f1-2"
                yield "B:f1-3"
        root = Observable()
        root.addObserver(A())
        root.addObserver(B())
        g = compose(root.all.f1())
        next(g)
        r = g.throw(DeclineMessage)
        self.assertEqual("B:f1-1", r)

    def testRaisingDeclineMessageResultsInCallOnNextObservable(self):
        class SemiTransparent(Observable):
            def call_unknown(self, message, *args, **kwargs):
                if message == 'theMessage':
                    return self.call.unknown(message, *args, **kwargs)
                raise DeclineMessage

            def any_unknown(self, message, *args, **kwargs):
                if message == 'theMessage':
                    value = yield self.any.unknown(message, *args, **kwargs)
                    return value
                raise DeclineMessage

        root = be((Observable(),
            (SemiTransparent(),
                (Responder(41),)
            ),
            (Responder(42),)
        ))

        self.assertEqual([42], list(compose(root.any.message())))
        self.assertEqual(42, root.call.anotherMessage())

    def testRaisingDeclineMessageFromAllMakesNoDifference(self):
        class SemiTransparent(Observable):
            def all_unknown(self, message, *args, **kwargs):
                if message == 'theMessage':
                    yield self.all.unknown(message, *args, **kwargs)
                raise DeclineMessage

        root = be((Observable(),
            (SemiTransparent(),
                (Responder(41),)
            ),
            (Responder(42),)
        ))

        self.assertEqual([41, 42], list(compose(root.all.theMessage())))
        self.assertEqual([42], list(compose(root.all.message())))

    def testRaisingDeclineMessageFromDoMakesNoDifference(self):
        class SemiTransparent(Observable):
            def do_unknown(self, message, *args, **kwargs):
                if message == 'theMessage':
                    self.do.unknown(message, *args, **kwargs)
                raise DeclineMessage

        observer1 = CallTrace('observer1')
        observer2 = CallTrace('observer2')
        root = be((Observable(),
            (SemiTransparent(),
                (observer1,)
            ),
            (observer2,)
        ))

        root.do.theMessage()
        self.assertEqual(['theMessage'], [m.name for m in observer1.calledMethods])
        self.assertEqual(['theMessage'], [m.name for m in observer2.calledMethods])

        observer1.calledMethods.reset()
        observer2.calledMethods.reset()
        root.do.message()
        self.assertEqual([], [m.name for m in observer1.calledMethods])
        self.assertEqual(['message'], [m.name for m in observer2.calledMethods])

    def testDeferredObjectsAreCached(self):
        class A(object):
            def a(self):
                pass
        observable = Observable()
        observable.addObserver(A())
        f1 = observable.all.f
        f2 = observable.all.f
        self.assertEqual(f1, f2)

    def testRebuildDefersAfterAddObserver(self):
        observable = Observable()
        called = []
        class A(Observable):
            def method(this):
                called.append("A")
                return
                yield
        class B(Observable):
            def method(this):
                called.append("B")
                return
                yield
        observable.addObserver(A())
        list(compose(observable.all.method()))
        self.assertEqual(['A'], called)
        del called[:]
        observable.addObserver(B())
        list(compose(observable.all.method()))
        self.assertEqual(['A', 'B'], called)

    def xxtestRelativeSpeedOfAll(self):
        from time import time
        class A(Observable):
            def f(self):
                return
                yield
        root = Observable()
        connector = Transparent()
        root.addObserver(connector)
        connector.addObserver(A())
        connector.addObserver(A())
        connector.addObserver(A())
        connector.addObserver(A())
        connector.addObserver(A())
        connector.addObserver(A())
        connector.addObserver(A())
        t = 0.0
        for _ in range(10000):
            g = compose(root.all.f())
            t0 = time()
            for _ in g:
                next(g)
            t1 = time()
            t += t1 - t0

        def f():
            for _ in range(10000):
                g = compose(root.all.f())
                for _ in g:
                    next(g)
        #from hotshot import Profile
        #p = Profile("profile.prof", lineevents=1, linetimings=1)
        #p.runcall(f)

    def printFunctionsOnTraceback(self):
        print(", ".join(["'{}'".format(each) for each in self.getFunctionsOnTraceback()]))

    def getFunctionsOnTraceback(self):
        names = []
        _, _, tb = exc_info()
        while tb:
            names.append(tb.tb_frame.f_code.co_name)
            tb = tb.tb_next
        return names

    def assertFunctionsOnTraceback(self, *args):
        names = self.getFunctionsOnTraceback()
        self.assertEqual(list(args), names, names)

    def get_tracked_objects(self):
        return [o for o in gc.get_objects() if type(o) in
                (compose, GeneratorType, Exception,
                    AllMessage, AnyMessage, DoMessage, OnceMessage)]

    def setUp(self):
        TestCase.setUp(self)
        gc.collect()
        self._baseline = self.get_tracked_objects()

    def tearDown(self):
        def tostr(o):
            if isframe(o):
                return getframeinfo(o)
            try:
                return tostring(o)
            except:
                return repr(o)
        gc.collect()
        diff = set(self.get_tracked_objects()) - set(self._baseline)
        for obj in list(diff):
            if getattr(getattr(obj, 'gi_code', None), 'co_name', None) in {'testPartExecutor'}:
                diff.remove(obj)
        self.assertEqual(set(), diff)
        for obj in diff:
            print("Leak:")
            print(tostr(obj))
            print("Referrers:")
            for o in gc.get_referrers(obj):
                print(tostr(o))
        del self._baseline
        gc.collect()
        TestCase.tearDown(self)


class Responder(Observable):
    def __init__(self, value):
        self._value = value
    def any_unknown(self, message, *args, **kwargs):
        yield self._value
        return self._value
    def call_unknown(self, message, *args, **kwargs):
        return self._value
    def all_unknown(self, message, *args, **kwargs):
        yield self._value
