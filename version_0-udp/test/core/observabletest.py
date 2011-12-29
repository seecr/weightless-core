# -*- coding: utf-8 -*-
## begin license ##
#
#    Meresco Core is an open-source library containing components to build
#    searchengines, repositories and archives.
#    Copyright (C) 2007-2011 Seek You Too (CQ2) http://www.cq2.nl
#    Copyright (C) 2007-2009 SURF Foundation. http://www.surf.nl
#    Copyright (C) 2007-2009 Stichting Kennisnet Ict op school.
#       http://www.kennisnetictopschool.nl
#    Copyright (C) 2007 SURFnet. http://www.surfnet.nl
#    Copyright (C) 2010 Stichting Kennisnet http://www.kennisnet.nl
#
#    This file is part of Meresco Core.
#
#    Meresco Core is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    Meresco Core is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Meresco Core; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

import gc
from sys import exc_info
from traceback import format_tb
from inspect import isframe, getframeinfo
from types import GeneratorType
from weightless.core import compose, Observable, Transparant, be, tostring
from weightless.core._observable import AllMessage, AnyMessage, DoMessage, OnceMessage, DeferredMessage, AsyncanyMessage, AsyncdoMessage
from calltrace import CallTrace
from unittest import TestCase

class Interceptor(Observable):
    def unknown(self, message, *args, **kwargs):
        self.message = message
        self.args = args
        self.kwargs = kwargs

class ObservableTest(TestCase):

    def testTransparentUnknownWithAny(self):
        class A(Observable):
            def a(self):
                return self.any.c()
        class B1(Observable):
            def unknown(self, message, *args, **kwargs):
                return self.all.unknown(message, *args, **kwargs)
        class B2(Observable):
            def unknown(self, message, *args, **kwargs):
                return self.all.unknown(message, *args, **kwargs)
        class C(object):
            def c(self):
                return (ch for ch in 'see')
        a = A()
        b1 = B1()
        b2 = B2()
        c = C()
        a.addObserver(b1)
        b1.addObserver(b2)
        b2.addObserver(c)
        self.assertEquals('see', ''.join(a.a()))
        del a, b1, b2, c

    def testObserverInit(self):
        initcalled = [0]
        class MyObserver(object):
            def observer_init(self):
                initcalled[0] += 1
        root = be((Observable(), (MyObserver(),)))
        root.once.observer_init()
        self.assertEquals([1], initcalled)

    def testAllWithoutImplementers(self):
        observable = Observable()
        responses = observable.all.someMethodNobodyIsListeningTo()
        self.assertEquals(GeneratorType, type(responses))

    def testAllWithMoreImplementers(self):
        observable = Observable()
        observerOne = CallTrace(returnValues={'aMethod': 'one'})
        observerTwo = CallTrace(returnValues={'aMethod': 'two'})
        root = be((observable, (observerOne,), (observerTwo,)))
        responses = root.all.aMethod()
        self.assertEquals(GeneratorType, type(responses))
        self.assertEquals(['one', 'two'], list(responses))

    def testAnyCallsFirstImplementer(self):
        observable = Observable()
        observerA = ObserverA()
        observerAB = ObserverAB()
        root = be((observable, (observerA,), (observerAB,)))
        resultA = root.any.methodA(0)
        resultB = root.any.methodB(1, 2)
        self.assertEquals([("Method A", (0,))], observerA.notifications)
        self.assertEquals([("Method B", (1, 2))], observerAB.notifications)
        self.assertEquals("A.methodA", resultA)
        self.assertEquals("AB.methodB", resultB)

    def testAnyCallsFirstImplementerNotReturningNone(self):
        class A(object):
            def do(self, x):
                if x == 1: return 'A'
        class B(object):
            def do(self, x):
                if x == 2: return 'B'
        root = be((Observable(), (A(),), (B(),)))
        result = root.any.do(1)
        self.assertEquals('A', result)
        result = root.any.do(2)
        self.assertEquals('B', result)

    def testAllException(self):
        observable = Observable()
        class ExceptionRaiser(MockObserver):
            def mayRaiseException(self, *args):
                raise TestException
        class Safe(MockObserver):
            def mayRaiseException(self, *args):
                self.notifications.append(("mayRaiseException", args))
        observable.addObserver(ExceptionRaiser())
        safe = Safe()
        observable.addObserver(safe)
        try:
            list(observable.all.mayRaiseException())
            self.fail()
        except TestException:
            pass
        self.assertEquals([], safe.notifications)

    def testDo(self):
        observable = Observable()
        retvalIsAlwaysNone = observable.do.oneWayMethodWithoutReturnValue()
        self.assertEquals(None, retvalIsAlwaysNone)
        observer = CallTrace("Observer")
        observer.something = lambda x,y: x.append(y)
        observable.addObserver(observer)
        value = []
        observable.do.something(value, 1)
        self.assertEquals([1], value)

    def testAsyncdoReturnsGenerator(self):
        observable = Observable()
        retval = observable.asyncdo.oneWayMethodWithoutReturnValue()
        self.assertRaises(StopIteration, retval.next)

    def testAsyncdoEmptyGenerator(self):
        observable = Observable()
        called=[]
        class Listener(object):
            def message(this):
                yield 'a'
                called.append(True)
                yield 'b'
        observable.addObserver(Listener())
        retval = observable.asyncdo.message()
        self.assertRaises(StopIteration, retval.next)
        self.assertEquals([True], called)

    def testAsyncdoYieldsCallables(self):
        observable = Observable()
        called=[]
        def callable():
            pass
        class Listener(object):
            def message(this):
                yield 'a'
                yield callable
                yield 'b'
                called.append(True)
        observable.addObserver(Listener())
        retval = observable.asyncdo.message()
        self.assertEquals(callable, retval.next())
        self.assertRaises(StopIteration, retval.next)
        self.assertEquals([True], called)

    def testAsyncAnyNoSuchMessage(self):
        observable = Observable()
        try:
            observable.asyncany.notExisting().next()
            self.fail('fail')
        except AttributeError, e:
            self.assertEquals('None of the 0 observers responds to asyncany.notExisting(...)', str(e))

    def testAsyncAny2(self):
        observable = Observable()
        done = []
        def callable():
            pass
        class Caller(Observable):
            def useasyncany(this):
                result = yield this.asyncany.message()
                self.assertEquals("the answer", result)
                yield
        class Listener(object):
            def message(this):
                yield callable
                done.append(0)
                raise StopIteration("the answer")
        caller = Caller()
        caller.addObserver(Listener())
        observable.addObserver(caller)
        generator = compose(observable.all.useasyncany())
        self.assertEquals(callable, generator.next())
        retval = generator.next()
        self.assertEquals([0], done)
 
    def testAddStrandEmptyList(self):
        observable = Observable()
        observable.addStrand((), [])
        self.assertEquals([], observable._observers)

    def testBeOne(self):
        observer = CallTrace()
        root = be((observer,))
        self.assertEquals(root, observer)

    def testBeTwo(self):
        observable = Observable()
        child0 = Observable()
        child1 = Observable()
        root = be((observable, (child0,), (child1,)))
        self.assertEquals([child0, child1], observable._observers)

    def testBeTree(self):
        observable = Observable()
        child0 = Observable(name='child0')
        child1 = Observable(name='child1')
        strand = (observable, (child0, (child1,)))
        root = be(strand)
        self.assertEquals([child0], root._observers)
        self.assertEquals([child1], child0._observers)

    def testBeToExplainTheIdeaWhithoutTestingSomethingNew(self):
        observable = Observable()
        child0 = Observable(name='child0')
        child1 = Observable(name='child1')
        child2 = Observable(name='child2')
        tree = (observable, (child0, (child1, (child2,))))
        root = be(tree)
        self.assertEquals([child0], observable._observers)
        self.assertEquals([child1], child0._observers)
        self.assertEquals([child2], child1._observers)

    def testAny(self):
        class A(Observable):
            def myThing(self):
                return self.any.myThing()
        class B(Observable):
            def myThing(self):
                yield "data"
        a = A()
        b = B()
        a.addObserver(b)
        self.assertEquals(GeneratorType, type(a.any.myThing()))
        self.assertEquals(["data"], list(a.any.myThing()))

    def testAllUnknown(self):
        class Interceptor(Observable):
            def unknown(self, message, *args, **kwargs):
                self.message = message
                self.args = args
                self.kwargs = kwargs
        interceptor = Interceptor()
        root = Observable()
        root.addObserver(interceptor)
        list(root.all.anUnknownMessage('with', unknown='arguments'))

        self.assertEquals('anUnknownMessage', interceptor.message)
        self.assertEquals(('with',), interceptor.args)
        self.assertEquals({'unknown': 'arguments'}, interceptor.kwargs)

    def testUnknownDispatchingNoImplementation(self):
        observable = Observable()
        class Listener(object):
            pass
        observable.addObserver(Listener())
        retval = observable.all.unknown('non_existing_method', 'one')
        self.assertEquals([], list(retval))

    def testUnknownDispatching(self):
        observable = Observable()
        class Listener(object):
            def method(inner, one):
                return one + " another"
        observable.addObserver(Listener())
        retval = observable.any.unknown('method', 'one')
        self.assertEquals('one another', retval)

    def testUnknownDispatchingBackToUnknown(self):
        observable = Observable()
        class Listener(object):
            def unknown(self, methodName, one):
                return ("via unknown " + one for x in [1])
        observable.addObserver(Listener())
        retval = observable.any.unknown('non_existing_method', 'one')
        self.assertEquals("via unknown one", retval)

    def testUnknownIsEquivalentToNormalCall(self):
        observable = Observable()
        class Listener(object):
            def normal(self):
                return 'normal'
            def unknown(self, message, *args, **kwargs):
                yield self.normal()
        observable.addObserver(Listener())
        result1 = observable.any.unknown('normal')
        result2 = observable.any.unknown('other')
        self.assertEquals(result1, result2)

    def testSyntacticSugarIsPreserved(self):
        class WithUnknown(Observable):
            def unknown(self, methodName, *args):
                return self.all.unknown(methodName, "extra arg", *args)

        observer = CallTrace("Observer")

        withUnknown = WithUnknown()
        withUnknown.addObserver(observer)

        source = Observable()
        source.addObserver(withUnknown)
        source.do.someMethod("original arg")
        #if syntactic sugar (i.e. "do") is preseverd, it would force the call self.all.unknown directly
        self.assertEquals(1, len(observer.calledMethods))
        self.assertEquals("someMethod('extra arg', 'original arg')", str(observer.calledMethods[0]))

    def testProperErrorMessage(self):
        observable = Observable()
        try:
            answer = observable.any.gimmeAnswer('please')
            self.fail('shoud raise AttributeError')
        except AttributeError, e:
            self.assertEquals('None of the 0 observers responds to any.gimmeAnswer(...)', str(e))

    def testProperErrorMessageWhenArgsDoNotMatch(self):
        from traceback import print_exc
        observable = Observable()
        class YesObserver:
            def yes(self, oneArg): pass
        observable.addObserver(YesObserver())
        try:
            answer = observable.any.yes()
            self.fail('shoud raise AttributeError')
        except TypeError, e:
            self.assertEquals('yes() takes exactly 2 arguments (1 given)', str(e))

    def testNestedAllWithDoOnlyExecutesTheHighestLevelCalls(self):
        done = []
        class A(Observable):
            def a(this):
                done.append('A')
                return this.all.a()
        class B(Observable):
            def a(this):
                done.append('B')
                return this.all.a()
        class C(Observable):
            def a(this):
                done.append('C')
                self.done = True
        t = be((Observable(),
                    (A(),
                        (B(),
                            (C(),)
                        )
                    )
                ))
        result = t.do.a()
        self.assertEquals(None, result)
        self.assertEquals(['A'], done)

    def testFixUpExceptionTraceBack(self):
        class A:
            def a(self):
                raise Exception('A.a')
            def unknown(self, msg, *args, **kwargs):
                yield self.a()
        observable = Observable()
        observable.addObserver(A())
        try:
            observable.any.a()
        except Exception:
            self.assertFunctionsOnTraceback("testFixUpExceptionTraceBack", "a")
        try:
            list(observable.all.a())
        except Exception:
            self.assertFunctionsOnTraceback("testFixUpExceptionTraceBack", "a")

        try:
            observable.do.a()
        except Exception:
            self.assertFunctionsOnTraceback("testFixUpExceptionTraceBack", "a")

        try:
            list(observable.asyncdo.a())
        except Exception:
            self.assertFunctionsOnTraceback("testFixUpExceptionTraceBack", "a")

        try:
            observable.any.unknown('a')
        except Exception:
            self.assertFunctionsOnTraceback("testFixUpExceptionTraceBack", "a")

        try:
            observable.any.somethingNotThereButHandledByUnknown('a')
        except Exception:
            self.assertFunctionsOnTraceback("testFixUpExceptionTraceBack", "unknown", "a")

    def assertFunctionsOnTraceback(self, *args):
        na, na, tb = exc_info()
        for functionName in args:
            self.assertEquals(functionName, tb.tb_frame.f_code.co_name)
            tb = tb.tb_next
        self.assertEquals(None, tb)

    def testMoreElaborateExceptionCleaning(self):
        class A(Observable):
            def a(self): return self.any.b()
        class B(Observable):
            def b(self): return self.any.c()
        class C(Observable):
            def c(self): return self.any.d()
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
            self.assertFunctionsOnTraceback("testMoreElaborateExceptionCleaning", "a", "b", "c", "d")

    def testAddObserversOnce(self):
        class  MyObservable(Observable):
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
        self.assertEquals([o2], o1._observers)
        self.assertEquals([], o2._observers)
        self.assertEquals([o1, o4, o5], o3._observers)
        self.assertEquals([], o4._observers)
        self.assertEquals([o1], o5._observers)

    def testResolveCallStackVariables(self):
        class StackVarHolder(Observable):
            def unknown(self, name, *args, **kwargs):
                __callstack_var_myvar__ = []
                for result in self.all.unknown(name, *args, **kwargs):
                    pass
                yield __callstack_var_myvar__

        class StackVarUser(Observable):
            def useVariable(self):
                self.ctx.myvar.append('Thingy')

        dna = \
            (Observable(),
                (StackVarHolder(),
                    (StackVarUser(),)
                )
            )
        root = be(dna)
        self.assertEquals(['Thingy'], root.any.useVariable())

    def testOnceAndOnlyOnce(self):
        class MyObserver(Observable):
            def methodOnlyCalledOnce(self, aList):
                aList.append('once')
        once = MyObserver()
        dna = \
            (Observable(),
                (once,),
                (once,)
            )
        root = be(dna)
        collector = []
        root.once.methodOnlyCalledOnce(collector)
        self.assertEquals(['once'], collector)

    def testOnceInDiamondWithTransparant(self):
        class MyObserver(Observable):
            def methodOnlyCalledOnce(self, aList):
                aList.append('once')
        once = MyObserver()
        diamond = \
            (Transparant(),
                (Transparant(),
                    (once,)
                ),
                (Transparant(),
                    (once,)
                )
            )
        root = be(diamond)
        collector = []
        root.once.methodOnlyCalledOnce(collector)
        self.assertEquals(['once'], collector)

    def testPropagateThroughAllObservablesInDiamondWithNONTransparantObservablesWithoutUnknownMethodDelegatingUnknownCalls(self):
        class MyObserver(Observable):
            def methodOnlyCalledOnce(self, aList):
                aList.append('once')
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
        root.once.methodOnlyCalledOnce(collector)
        self.assertEquals(['once'], collector)

    def testNonObservableInTreeWithOnce(self):
        class MyObserver(object):
            def methodOnNonObservableSubclass(self, aList):
                aList.append('once')
        once = MyObserver()
        dna =   (Observable(),
                    (once,)
                )
        root = be(dna)
        collector = []
        root.once.methodOnNonObservableSubclass(collector)
        self.assertEquals(['once'], collector)

    def testOnceAndOnlyOnceForMutuallyObservingObservables(self):
        class MyObserver(Observable):
            def methodOnlyCalledOnce(self, aList):
                aList.append(self)
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
        root.once.methodOnlyCalledOnce(collector)
        self.assertEquals([ownobserverobserver], collector)

    def testNoLeakingGeneratorsInCycle(self):

        class Responder(Observable):
            def message(self):
                return 'response'
        obs = Observable()
        obs.addObserver(Responder())
        result = obs.all.message().next()
        self.assertEquals('response',result)
        del obs

    def testNoLeakingGeneratorsInMultiTransparants(self):
        class Responder(Observable):
            def message(self):
                return 'response'
        obs = Observable()
        t1 = Transparant()
        t2 = Transparant()
        obs.addObserver(t1)
        t1.addObserver(t2)
        t2.addObserver(Responder())
        result = obs.any.message()
        self.assertEquals('response', result)
        del obs, t1, t2, result

    def testMatchingBasedOnDefaultArgs(self):
        class A(object):
            def a(x, y=10, z=11):
                p = 1
                q = 2
                yield
        a = A()
        func = a.a
        code = func.func_code
        func_defaults = func.func_defaults
        self.assertEquals((10,11), func_defaults)
        argcount = code.co_argcount
        self.assertEquals(3, argcount)
        varnames = code.co_varnames
        self.assertEquals(('x', 'y', 'z', 'p', 'q'), varnames)
        argnames = varnames[:argcount]
        self.assertEquals(('x','y','z'), argnames)
        kwargsnames = argnames[-len(func_defaults):]
        self.assertEquals(('y','z'), kwargsnames)
        kwargdefaults = dict(zip(kwargsnames, func_defaults))
        self.assertEquals({'y':10, 'z':11}, kwargdefaults)
        self.assertEquals({'z':11, 'y':10}, kwargdefaults)
        func.__dict__['kwargdefaults'] = kwargdefaults
        self.assertEquals({'z':11, 'y':10}, func.kwargdefaults)

        class Wildcard(object):
            def __eq__(self, other):
                return True
        self.assertTrue({'z':11, 'y':10} == {'z':11, 'y': Wildcard()})

    def get_tracked_objects(self):
        return [o for o in gc.get_objects() if type(o) in 
                (compose, GeneratorType, Exception,
                    AllMessage, AnyMessage, DoMessage, OnceMessage, DeferredMessage,
                    AsyncdoMessage, AsyncanyMessage)]
 
    def setUp(self):
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
        #self.assertEquals(set(), diff)
        #for obj in diff:
        #    print "Leak:"
        #    print tostr(obj)
        #    print "Referrers:"
        #    for o in  gc.get_referrers(obj):
        #        print tostr(o)
        del self._baseline


class TestException(Exception):
    pass

class MockObserver:

    def __init__(self):
        self.notifications = []

class ObserverA(MockObserver):

    def methodA(self, *args):
        self.notifications.append(("Method A", args))
        return "A.methodA"

class ObserverAB(MockObserver):

    def methodA(self, *args):
        self.notifications.append(("Method A", args))
        return "AB.methodA"

    def methodB(self, *args):
        self.notifications.append(("Method B", args))
        return "AB.methodB"

class DoesNotReturn(MockObserver):

    def methodA(self, *args):
        self.notifications.append(("Method A", args))
