## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    See http://weightless.io
#    Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
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

from unittest import TestCase
from sys import stdout, exc_info, getrecursionlimit, version_info
import gc
from weakref import ref
from types import GeneratorType
from weightless.core import autostart
from weightless.core.compose._local_py import local as pyLocal
from weightless.core.compose._compose_py import compose as pyCompose
from weightless.core.compose._tostring_py import tostring as pyTostring
from weightless.core.compose._compose_c import local as cLocal, compose as cCompose
from weightless.core.compose._compose_c import tostring as cTostring

class _ComposeTest(TestCase):

    def testCallCompose(self):
        try:
            compose()
            self.fail()
        except TypeError, e:
            self.assertTrue(
                    "compose() takes at least 1 argument (0 given)" in str(e)
                    or # (python 2.5/2.6 C-API differences)
                    "Required argument 'initial' (pos 1) not found" in str(e))
        self.assertRaises(TypeError, compose, 's')
        self.assertRaises(TypeError, compose, 0)

    def testGC(self):
        c = compose((x for x in []))
        gc.collect()
        del c
        gc.collect()

    def assertComposeImpl(self, impl):
        self.assertEquals(impl, compose)

    def testCreateSinglecompose(self):
        def multplyBy2(number): yield number * 2
        g = multplyBy2(2)
        wlt = compose(g)
        response = wlt.next()
        self.assertEquals(4, response)

    def testRunCompletely(self):
        wlt = compose(x for x in range(3))
        results = list(wlt)
        self.assertEquals([0,1,2], results)

    def testCreateNestedcompose(self):
        def multplyBy2(number): yield number * 2
        def delegate(number): yield multplyBy2(number * 2)
        wlt = compose(delegate(2))
        response = wlt.next()
        self.assertEquals(8, response)

    def testCreateTripleNextedcompose(self):
        def multplyBy2(number): yield number * 2
        def delegate(number): yield multplyBy2(number * 2)
        def master(number): yield delegate(number * 2)
        wlt = compose(master(2))
        response = wlt.next()
        self.assertEquals(16, response)

    def testResumecompose(self):
        def thread():
            yield 'A'
            yield 'B'
        wlt = compose(thread())
        response = wlt.next()
        self.assertEquals('A', response)
        response = wlt.next()
        self.assertEquals('B', response)

    def testResumeNestedcompose(self):
        def threadA():
            yield 'A'
            yield 'B'
        def threadB():
            yield 'C'
            yield threadA()
            yield 'D'
        wlt = compose(threadB())
        results = list(wlt)
        self.assertEquals(['C','A','B','D'], results)

    def testPassValueToRecursivecompose(self):
        def threadA():
            r = yield threadB()     # <= C
            yield r * 3                     # <= D
        def threadB():
            yield 7                     # <= A
            r = yield
            raise StopIteration(r * 2)     # <= B
        t = compose(threadA())
        self.assertEquals(7, t.next())              # 7 yielded at A
        t.next() # adhere to 'send on None' protocol
        self.assertEquals(18, t.send(3))        # 3 send to A, 6 yielded at B, as return value to C, then yielded at D

    def testReturnOne(self):
        data = []
        def child():
            raise StopIteration('result')
            yield
        def parent():
            result = yield child()
            data.append(result)
        g = compose(parent())
        list(g)
        self.assertEquals('result', data[0])

    def testReturnThree(self):
        data = []
        def child():
            raise StopIteration('result', 'remainingData1', 'other2')
            yield
        def parent():
            result = yield child()
            data.append(result)
            remainingData = yield None
            data.append(remainingData)
            other2 = yield None
            data.append(other2)
        g = compose(parent())
        list(g)
        self.assertEquals('result', data[0])
        self.assertEquals('remainingData1', data[1])
        self.assertEquals('other2', data[2])

    def testReturnAndCatchRemainingDataInNextGenerator(self):
        messages = []
        responses = []
        def child1():
            raise StopIteration('result', 'remainingData0', 'remainingData1')
            yield
        def child2():
            messages.append((yield 'A'))                # I want to 'send' and do not accept data
            messages.append((yield))                     # now accept 'remainingData0'
            messages.append((yield))                     # append 'remainingData1'
            messages.append((yield 'C'))               # append None (I want to send)
        def parent():
            messages.append((yield child1()))   # append 'result'
            messages.append((yield child2()))   # what does 'yield child2()' return???
        g = compose(parent())
        responses.append(g.send(None))
        responses.append(g.send(None))
        #responses.append(g.send(None))
        try:
            responses.append(g.send(None))
            self.fail()
        except StopIteration:
            pass
        self.assertEquals(['result', None, 'remainingData0', 'remainingData1', None, None], messages)
        self.assertEquals(['A', 'C'], responses)

    def testStopIterationWithReturnValue(self):
        def f():
            raise StopIteration('return value')
            yield 'something'
        def g():
            self.retval = yield f()
        list(compose(g()))
        self.assertEquals('return value', self.retval)

    def testReturnInNestedGeneratorQuiteTricky(self):
        r = []
        def ding1():
            dataIn = yield None     # receive 'dataIn'
            self.assertEquals('dataIn', dataIn)
            raise StopIteration('ding1retval', 'rest('+dataIn+')')
        def ding2():
            dataIn = yield None     # receive 'rest(dataIn)'
            #retval = RETURN, 'ding2retval', 'rest('+dataIn+')'
            raise StopIteration('ding2retval', 'rest('+dataIn+')')
        def child():
            ding1retval = yield ding1()
            r.append('child-1:' + str(ding1retval))
            ding2retval = yield ding2()
            r.append('child-2:' + str(ding2retval))
            raise StopIteration('childretval')
        def parent():
            childRetVal = yield child()
            self.assertEquals('childretval', childRetVal)
            rest = yield
            r.append('parent:'+rest)
        g = compose(parent())
        g.next()
        try:
            g.send('dataIn')
            self.fail()
        except StopIteration:
            pass
        self.assertEquals(['child-1:ding1retval', 'child-2:ding2retval', 'parent:rest(rest(dataIn))'], r)

    def testCheckForFreshGenerator(self):
        def sub():
            yield
            yield
        def main():
            s = sub()
            s.next() # start it already
            yield s
        c = compose(main())
        try:
            c.next()
            self.fail('must raise')
        except Exception, e:
            self.assertEquals('Generator already used.', str(e))

    def testForExhaustedGenerator(self):
        def sub():
            yield
        def main():
            s = sub()
            s.next()
            try:
                s.next()
                self.fail('must raise StopIteration')
            except StopIteration: pass
            yield s
        c = compose(main())
        try:
            c.next()
            self.fail('must not come here')
        except Exception, e:
            self.assertEquals('Generator is exhausted.', str(e))

    def testPassThrowCorrectly(self):
        class MyException(Exception): pass
        def child():
            try:
                yield 1
            except Exception, e:
                self.e = e
            yield 2
        g = compose(child())
        g.next()
        g.throw(MyException('aap'))
        self.assertEquals('aap', str(self.e))

    def testHandleAllDataAndDoAvoidSuperfluousSendCalls(self):
        data = []
        def f():
            x = yield
            data.append(x)
            raise StopIteration(*tuple(x))
        def g():
            r = yield f()
            data.append(r)
            while True:
                data.append((yield None))
        program = compose(g())
        program.next() # init
        program.send('mies')
        #program.next() # this is what we don't want and what we're testing here
        #program.next()
        #program.next()
        self.assertEquals('mies', data[0])
        self.assertEquals('m', data[1])
        self.assertEquals('i', data[2])
        self.assertEquals('e', data[3])
        self.assertEquals('s', data[4])
        program.close()

    def testHandleClose(self):
        r = []
        def f():
            try:
                yield None
            except BaseException, e:
                r.append(e)
                raise
        g = compose(f())
        g.next()
        g.close()
        self.assertEquals(GeneratorExit, type(r[0]))

    def testHandleStop(self):
        r = []
        def f():
            try:
                yield None
            except Exception, e:
                r.append(e)
                raise
        g = compose(f())
        g.next()
        try:
            g.throw(StopIteration)
        except:
            pass
        self.assertEquals(StopIteration, type(r[0]))

    def testPassException1(self):
        class MyException(Exception): pass
        class WrappedException(Exception): pass
        def child():
            raise MyException('abc')
            yield None
        def parent():
            try:
                yield child()
            except MyException, e:
                raise WrappedException(e)
        g = compose(parent())
        try:
            g.next()
            self.fail()
        except WrappedException, e:
            self.assertEquals('abc', str(e))

    def testDealloc(self):
        def f():
            yield 'A'
            yield (1,2,3,4)
            yield 'B'
            yield 'C'
            yield 'D'
        g = compose(f())
        g.next()
        g.next()
        del g

    def testPassException2(self):
        class MyException(Exception): pass
        class WrappedException(Exception): pass
        def child():
            yield None
            raise MyException('abc')
        def parent():
            try:
                yield child()
            except MyException, e:
                raise WrappedException(e)
        g = compose(parent())
        g.next()
        try:
            g.next()
            self.fail()
        except WrappedException, e:
            self.assertEquals('abc', str(e))

    def xtestPerformance(self):
        def f1(arg):
            r = yield None
            yield arg
            raise StopIteration('aap', 'rest')
        def f2(arg):
            r1 = yield f1('noot')
            r2 = yield f1('mies')
        def f3(arg):
            yield 'A'
            r = yield None
            yield 'B'
            a = yield f2('C')
            b = yield f2('D')
            yield a
            yield b
        # name, creates, runs
        #       f3          1           1
        #       f2          2           2
        #       f1          4           4
        #   total       7           7
        def baseline():
            list(f3('A'))   # 3     1
            list(f2('B'))   # 3     1
            list(f1('C'))   # 1     1
            list(f1('C'))   # 1     1
                                # 8     4  (versus 7        7)
        from time import time
        tg = tb = 0.0
        for i in range(10):
            stdout.write('*')
            stdout.flush()
            t0 = time()
            [list(compose(f3('begin'))) for i in xrange(100)]
            t1 = time()
            tg = tg + t1 - t0
            [baseline() for i in xrange(100)]
            t2 = time()
            tb = tb + t2 - t1
        print 'Overhead compose compared to list(): %2.2f %%' % ((tg/tb - 1) * 100.0)

    def testMemLeaks(self):
        def f1(arg):
            r = yield arg                       # None
            raise Exception()
        def f2(arg):
            r1 = yield None                 # 'A'
            try:
                r2 = yield f1(r1)
            except GeneratorExit:
                raise
            except Exception, e:
                raise StopIteration(e, 'more')
        def f3(arg):
            e = yield f2('aa')
            more = yield None
            try:
                yield more                      #   'X'
            except Exception:
                raise
        # runs this a zillion times and watch 'top'
        for i in xrange(1):
            g = compose(f3('noot'))
            g.next()
            g.send('A')
            g.send(None)
            try:
                g.throw(Exception('X'))
            except:
                pass

    def testNestedExceptionHandling(self):
        def f():
            yield 'A'
        def g():
            try:
                yield f()
            except Exception, e:
                raise Exception(e)
        c = compose(g())
        r = c.next()
        self.assertEquals('A', r)
        try:
            c.throw(Exception('wrong'))
            self.fail('must raise wrapped exception')
        except Exception, e:
            self.assertEquals("Exception(Exception('wrong',),)", repr(e))

    def testNestedClose(self):
        def f():
            yield 'A'
        def g():
            try:
                yield f()
            except BaseException, e:
                raise Exception(e)
        c = compose(g())
        r = c.next()
        self.assertEquals('A', r)
        try:
            c.close()
            self.fail('must raise wrapped CLOSE exception')
        except Exception, e:
            self.assertEquals("Exception(GeneratorExit(),)", repr(e))

    def testMaskException(self):
        def f():
            try:
                yield 'a'
            except:
                pass
        c = compose(f())
        c.next()
        try:
            c.throw(Exception('aap'))
        except StopIteration:
            pass
        except Exception, e:
            self.fail(str(e))

    def testThrowWithExceptionCaughtDoesNotDitchResponse(self):
        def f():
            try:
                yield 'response'
            except StopIteration:
                pass
            yield 'is this ditched?'
        c = compose(f())
        response = c.next()
        self.assertEquals('response', response)
        response = c.throw(StopIteration())
        self.assertEquals('is this ditched?', response)

    def testThrowWithExceptionCaughtDoesNotDitchResponseWhileInSubGenerator(self):
        def sub():
            try:
                yield 'response'
            except StopIteration:
                raise StopIteration('return')
        def f():
            ret = yield sub()
            self.assertEquals('return', ret)
            yield 'is this ditched?'
        c = compose(f())
        response = c.next()
        self.assertEquals('response', response)
        response = c.throw(StopIteration())
        self.assertEquals('is this ditched?', response)

    def testAdhereToYieldNoneMeansReadAndYieldValueMeansWriteWhenMessagesAreBuffered(self):
        done = []
        def bufferSome():
            raise StopIteration('retval', 'rest1', 'rest2')
            yield
        def writeSome():
            yield 'write this'
        def g():
            yield bufferSome()
            yield writeSome()
            data = yield 'write'
            self.assertEquals(None, data)
            data = yield
            self.assertEquals('rest1', data)
            done.append(True)
        g = compose(g())
        results = list(g)
        self.assertEquals([True], done)
        self.assertEquals(['write this', 'write'], results)

    def testAdhereToYieldNoneMeansReadAndYieldValueMeansWriteWhenMessagesAreBuffered2(self):
        done = []
        def bufferSome():
            raise StopIteration('retval', 'rest1', 'rest2')
            yield
        def writeSome():
            data = yield 'write this'
            self.assertEquals(None, data)
        def g():
            yield bufferSome()
            yield writeSome()
            data = yield
            self.assertEquals('rest1', data)
            done.append(True)
        g = compose(g())
        results = list(g)
        self.assertEquals([True], done)
        self.assertEquals(['write this'], results)

    def testDoNotSendSuperfluousNonesOrAdhereToNoneProtocol(self):
        def sub():
            jack = yield None
            none = yield 'hello ' + jack
            peter = yield None
            none = yield 'hello ' + peter
        c = compose(sub())
        self.assertEquals(None, c.send(None))           # 1 init with None, oh, it accepts data
        self.assertEquals('hello jack', c.send('jack')) # 2 send data, oh it has data
        self.assertEquals(None, c.send(None))           # 3 it had data, so send None to see what it wants next, oh, it accepts data
        self.assertEquals('hello peter', c.send('peter')) # 4 send data, oh, it has data

    def testUserAdheresToProtocol(self):
        def sub():
            yield 'response'
            yield 'response'
        c = compose(sub())
        self.assertEquals('response', c.next())
        try:
            c.send('message')
            self.fail('must raise exception')
        except AssertionError, e:
            self.assertEquals('Cannot accept data. First send None.', str(e))

    def testExceptionsHaveGeneratorCallStackAsBackTrace(self):
        def f():
            yield
        def g():
            yield f()
        c = compose(g())
        c.next()
        try:
            c.throw(Exception, Exception('ABC'))
            self.fail()
        except Exception:
            exType, exValue, exTraceback = exc_info()
            self.assertEquals('testExceptionsHaveGeneratorCallStackAsBackTrace', exTraceback.tb_frame.f_code.co_name)
            self.assertEquals('g', exTraceback.tb_next.tb_frame.f_code.co_name)
            self.assertEquals('f', exTraceback.tb_next.tb_next.tb_frame.f_code.co_name)
    
    def testToStringForSimpleGenerator(self):
        def f():
            yield
        g = f()
        soll = """  File "%s", line 594, in f
    def f():""" % __file__.replace('pyc', 'py')
        self.assertEquals(soll, tostring(g))
        g.next()
        soll = """  File "%s", line 595, in f
    yield""" % __file__.replace('pyc', 'py')
        self.assertEquals(soll, tostring(g))


    def testToStringGivesStackOfGeneratorsAKAcallStack(self):
        def f1():
            yield
        def f2():
            yield f1()
        c = compose(f2())
        result = """  File "%s", line 610, in f2
    yield f1()
  File "%s", line 608, in f1
    yield""" % (2*(__file__.replace('pyc', 'py'),))
        c.next()
        self.assertEquals(result, tostring(c), "\n%s\n!=\n%s\n" % (result, tostring(c)))

    def testToStringForUnstartedGenerator(self):
        def f1():
            yield
        def f2():
            yield f1()
        c = compose(f2())
        result = """  File "%s", line 622, in f2
    def f2():""" % __file__.replace('pyc', 'py')
        self.assertEquals(result, tostring(c))

    def testWrongArgToToString(self):
        try:
            tostring('x')
            self.fail('must raise TypeError')
        except TypeError, e:
            self.assertEquals("tostring() expects generator", str(e))

    def testFindLocalNotThere(self):
        def f1():
            yield f2()
        def f2():
            try:
                l = local('doesnotexist')
            except AttributeError, e:
                yield e
        f = compose(f1())
        result = f.next()
        self.assertEquals('doesnotexist', str(result))

    def testFindLocal(self):
        def f1():
            f1local = 'f1'
            yield f2()
        def f2():
            l = local('f1local')
            yield l
        f = compose(f1())
        result = f.next()
        self.assertEquals('f1', str(result))

    def testFindClosesedLocal(self):
        def f1():
            myLocal = 'f1'
            yield f2()
        def f2():
            myLocal = 'f2'
            yield f3()
        def f3():
            l = local('myLocal')
            yield l
        f = compose(f1())
        result = f.next()
        self.assertEquals('f2', str(result))

    def testOneFromPEP380(self):
        """
        Exceptions other than GeneratorExit thrown into the delegating
     generator are passed to the ``throw()`` method of the iterator.
     If the call raises StopIteration, the delegating generator is resumed.
     Any other exception is propagated to the delegating generator.
     (EG: rationale is that normally SystemExit is not catched, but it must
     trigger finally's to clean up.)
        """
        msg = []
        def f():
            try:
                yield g()
            except SystemExit, e:
                msg.append('see me')
            yield
        def g():
            try:
                yield
            except KeyboardInterrupt:
                msg.append('KeyboardInterrupt')
            try:
                yield
            except SystemExit:
                msg.append('SystemExit')
            try:
                yield
            except BaseException:
                msg.append('BaseException')
                raise SystemExit('see me')
            yield
        c = compose(f())
        c.next()
        c.throw(KeyboardInterrupt())
        self.assertEquals(['KeyboardInterrupt'], msg)
        c.throw(SystemExit())
        self.assertEquals(['KeyboardInterrupt', 'SystemExit'], msg)
        c.throw(SystemExit()) # second time
        self.assertEquals(['KeyboardInterrupt', 'SystemExit', 'BaseException', 'see me'], msg)

    def testTwoFromPEP380(self):
        """
        If a GeneratorExit exception is thrown into the delegating generator,
     or the ``close()`` method of the delegating generator is called, then
     the ``close()`` method of the iterator is called if it has one. If this
     call results in an exception, it is propagated to the delegating generator.
     Otherwise, GeneratorExit is raised in the delegating generator.
        """

        # First test some assumptions about close()

        @autostart
        def f1():
            try:
                yield
            except GeneratorExit:
                raise ValueError('1')
            yield
        g1 = f1()
        try:
            g1.close()
            self.fail('must raise ValueError')
        except ValueError, e:
            self.assertEquals('1', str(e))

        @autostart
        def f2():
            try:
                yield
            except GeneratorExit:
                pass
            # implicit raise StopIteration here

        g2 = f2()
        try:
            g2.close()
        except BaseException:
            self.fail('must not raise an exception')

        @autostart
        def f3():
            try:
                yield
            except GeneratorExit:
                pass
            yield  # does not raise an exception but yields None

        g3 = f3()
        try:
            g3.close()
            self.fail('must not raise an exception')
        except RuntimeError, e:
            self.assertEquals('generator ignored GeneratorExit', str(e))


        @autostart
        def f4():
            yield
            yield

        g4 = f4()
        try:
            g4.close()
        except BaseException, e:
            self.fail('must not raise an exception')

        # This is test one

        msg = []
        def f5():
            yield f6()
        def f6():
            try:
                yield
            except GeneratorExit:
                msg.append('GeneratorExit turned into StopIteration')
                raise StopIteration()  # <= this is the clue, see next test
        g5 = compose(f5())
        g5.next()
        try:
            g5.throw(GeneratorExit())
            self.fail('must reraise GeneratorExit if no exception by g1()')
        except GeneratorExit:
            pass
        self.assertEquals(['GeneratorExit turned into StopIteration'], msg)

        msg = []
        def f7():
            yield f8()
        def f8():
            try:
                yield
            except GeneratorExit:
                msg.append('GeneratorExit ignored')
            yield # <= this is the clue, see previous test
        g7 = compose(f7())
        g7.next()
        try:
            g7.throw(GeneratorExit())
            self.fail('must reraise RuntimeError(generator ignored GeneratorExit)')
        except RuntimeError:
            pass
        self.assertEquals(['GeneratorExit ignored'], msg)


        # Second case

        msg = []
        def f8():
            try:
                yield f9()
            #except RuntimeError, e:
            except ValueError, e:
                msg.append(str(e))
                raise StopIteration()
        def f9():
            try:
                yield
            except GeneratorExit:
                msg.append('GeneratorExit turned into ValueError')
                #raise RuntimeError('stop here')
                raise ValueError('stop here')
            yield

        g8 = compose(f8())
        g8.next()
        try:
            g8.throw(GeneratorExit())
            self.fail('must raise StopIteration')
        except StopIteration:
            pass
        self.assertEquals(['GeneratorExit turned into ValueError', 'stop here'], msg)

    def testYieldCompose(self):
        def f():
            yield "f"
        def g():
            yield compose(f())
        c = compose(g())
        self.assertEquals(['f'], list(c))

    def testComposeCompose(self):
        def f():
            yield
        c = compose(compose(f()))
        self.assertTrue(c)

    def testYieldComposeCloseAndThrow(self):
        def f():
            try:
                yield 42
            except Exception, e:
                yield 84

        c = compose(f())
        self.assertEquals(42, c.send(None))
        self.assertEquals(84, c.throw(Exception()))
        self.assertEquals(None, c.close())

    def testDecorator(self):
        from weightless.core import compose
        @compose
        def f():
            yield "a"
        self.assertEquals(["a"], list(f()))

    def get_tracked_objects(self):
        return [ref(o) for o in gc.get_objects() if type(o) in (compose, GeneratorType, Exception)]

    def setUp(self):
        gc.collect()
        self._baseline = self.get_tracked_objects()

    def tearDown(self):
        def tostr(o):
            try:
                return tostring(o)
            except:
                return repr(o)
        gc.collect()
        tracked_objs = self.get_tracked_objects()
        diff = set(self._baseline).difference(set(tracked_objs))
        self.assertEquals(diff, set(tostr(o.value) for o in diff))
        del diff
        gc.collect()

class ComposePyTest(_ComposeTest):
    def setUp(self):
        global local, tostring, compose
        local = pyLocal
        tostring = pyTostring
        compose = pyCompose
        _ComposeTest.setUp(self)

class ComposeCTest(_ComposeTest):
    def setUp(self):
        global local, tostring, compose
        local = cLocal
        tostring = cTostring
        compose = cCompose
        _ComposeTest.setUp(self)

    def testQueueSize(self):
        testrange = 9 #QUEUE SIZE = 10
        def f():
            raise StopIteration(*xrange(testrange))
            yield 'f done'
        def g():
            results = []
            x = yield f()
            results.append(x)
            for i in xrange(testrange-1):
                results.append((yield))
            yield results
        c = compose(g())
        self.assertEquals([range(testrange)], list(c))

    def testQueueSizeExceeded(self):
        testrange = 10 #QUEUE SIZE = 10
        def f():
            raise StopIteration(*xrange(testrange))
            yield
        def g():
            x = yield f()
        self.assertRaises(RuntimeError, compose(g()).next)

    def testStackOverflow(self):
        max_recursion_depth = getrecursionlimit()
        def f(recursion_depth=1):
            if recursion_depth < max_recursion_depth:
                yield f(recursion_depth + 1)
        c = compose(f())
        try:
            list(c)
        except RuntimeError, e:
            self.fail('must not raise %s' % e)

        max_recursion_depth += 1 # <== 
        c = compose(f())
        try:
            list(c)
            self.fail('must raise runtimeerror')
        except RuntimeError, e:
            self.assertEquals('maximum recursion depth exceeded (compose)', str(e))

    def testSelftest(self):
        from weightless.core.compose._compose_c import _selftest
        _selftest()


def gettypeerrormsg():
    def compose(initial, arg1 = None): pass
    try:
        compose()
    except TypeError, e:
        return str(e)
 
