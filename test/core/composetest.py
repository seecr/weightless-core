## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012, 2015 Seecr (Seek You Too B.V.) http://seecr.nl
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

from unittest import TestCase
from functools import reduce
from sys import stdout, exc_info, getrecursionlimit, version_info
from types import GeneratorType
from weakref import ref
import gc
from weightless.core import autostart, cpython, value_with_pushback
from weightless.core._local_py import local as pyLocal
from weightless.core._compose_py import compose as pyCompose
import weightless.core._compose_py as _compose_py_module
from weightless.core._tostring_py import tostring as pyTostring
try:
    from weightless.core.ext import local as cLocal, compose as cCompose
    from weightless.core.ext import tostring as cTostring
except ImportError:
    pass

from weightless.core import is_generator
from inspect import currentframe
from traceback import format_exc

fileDict = {
    '__file__' : __file__.replace(".pyc", ".py").replace("$py.class", ".py"),
    'py_compose': _compose_py_module.__file__.replace(".pyc", ".py").replace("$py.class", ".py"),
}

def __NEXTLINE__(offset=0):
    return currentframe().f_back.f_lineno + offset + 1

class ATrackedObj(object):
    def __init__(self):
        self.l = []

class _ComposeTest(TestCase):

    def testCallCompose(self):
        try:
            compose()
            self.fail()
        except TypeError as e:
            self.assertTrue(
                    "compose() missing 1 required positional argument: 'initial'" in str(e)
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
        self.assertEqual(impl, compose)

    def testCreateSinglecompose(self):
        def multplyBy2(number): yield number * 2
        g = multplyBy2(2)
        wlt = compose(g)
        response = next(wlt)
        self.assertEqual(4, response)

    def testRunCompletely(self):
        wlt = compose(x for x in range(3))
        results = list(wlt)
        self.assertEqual([0,1,2], results)

    def testCreateNestedcompose(self):
        def multplyBy2(number): yield number * 2
        def delegate(number): yield multplyBy2(number * 2)
        wlt = compose(delegate(2))
        response = next(wlt)
        self.assertEqual(8, response)

    def testCreateTripleNextedcompose(self):
        def multplyBy2(number): yield number * 2
        def delegate(number): yield multplyBy2(number * 2)
        def master(number): yield delegate(number * 2)
        wlt = compose(master(2))
        response = next(wlt)
        self.assertEqual(16, response)

    def testNoneProtocolNotFalsyProtocol_Responses(self):
        def gen(firstResponse):
            data = yield firstResponse
            yield data

        composed = compose(gen(firstResponse=False))
        self.assertEqual(False, next(composed))
        try:
            composed.send(5)
            self.fail('AssertionError not raised')
        except AssertionError as e:
            self.assertEqual('Cannot accept data. First send None.', str(e))
        finally:
            composed.close()

        composed = compose(gen(firstResponse=None))
        self.assertEqual(None, next(composed))
        try:
            composed.send(5)
        except AssertionError as e:
            self.fail('NoneProtocol not triggered!, got AssertionError: %s' % str(e))
        finally:
            composed.close()

    def testNoneProtocolNotFalsyProtocol_Messages(self):
        def gen():
            yield 'response'
            data = yield  # naughty programmer!, first yield None

        composed = compose(gen())
        self.assertEqual('response', next(composed))
        try:
            composed.send(False)
            self.fail('AssertionError not raised')
        except AssertionError as e:
            self.assertEqual('Cannot accept data. First send None.', str(e))
        finally:
            composed.close()

        composed = compose(gen())
        next(composed)
        try:
            composed.send(None)
        except AssertionError as e:
            self.fail('NoneProtocol not triggered!, got AssertionError: %s' % str(e))
        finally:
            composed.close()

    def testResumecompose(self):
        def thread():
            yield 'A'
            yield 'B'
        wlt = compose(thread())
        response = next(wlt)
        self.assertEqual('A', response)
        response = next(wlt)
        self.assertEqual('B', response)

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
        self.assertEqual(['C','A','B','D'], results)

    def testPassValueToRecursivecompose(self):
        def threadA():
            r = yield threadB()     # <= C
            yield r * 3                     # <= D
        def threadB():
            yield 7                     # <= A
            r = yield
            return r * 2     # <= B
        t = compose(threadA())
        self.assertEqual(7, next(t))              # 7 yielded at A
        next(t) # adhere to 'send on None' protocol
        self.assertEqual(18, t.send(3))        # 3 send to A, 6 yielded at B, as return value to C, then yielded at D

    def testReturnOne(self):
        data = []
        def child():
            return 'result'
            yield
        def parent():
            result = yield child()
            data.append(result)
        g = compose(parent())
        list(g)
        self.assertEqual('result', data[0])

    def testReturnEmptyString(self):
        data = []
        def child():
            return ''
            yield
        def parent():
            result = yield child()
            data.append(result)
        g = compose(parent())
        list(g)
        self.assertEqual('', data[0])

    def testReturnThree(self):
        data = []
        def child():
            return value_with_pushback('result', 'remainingData1', 'other2')
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
        self.assertEqual('result', data[0])
        self.assertEqual('remainingData1', data[1])
        self.assertEqual('other2', data[2])

    def testReturnAndCatchRemainingDataInNextGenerator(self):
        messages = []
        responses = []
        def child1():
            return value_with_pushback('result', 'remainingData0', 'remainingData1')
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
        self.assertEqual(['A', 'C'], responses)
        self.assertEqual(['result', None, 'remainingData0', 'remainingData1', None, None], messages)

    def testStopIterationWithReturnValue(self):
        def f():
            return value_with_pushback('return value')
            yield 'something'
        def g():
            self.retval = yield f()
        list(compose(g()))
        self.assertEqual('return value', self.retval)

    def testReturnInNestedGeneratorQuiteTricky(self):
        r = []
        def ding1():
            dataIn = yield None     # receive 'dataIn'
            self.assertEqual('dataIn', dataIn)
            return value_with_pushback('ding1retval', 'rest('+dataIn+')')
        def ding2():
            dataIn = yield None     # receive 'rest(dataIn)'
            #retval = RETURN, 'ding2retval', 'rest('+dataIn+')'
            return value_with_pushback('ding2retval', 'rest('+dataIn+')')
        def child():
            ding1retval = yield ding1()
            r.append('child-1:' + str(ding1retval))
            ding2retval = yield ding2()
            r.append('child-2:' + str(ding2retval))
            return 'childretval'
        def parent():
            childRetVal = yield child()
            self.assertEqual('childretval', childRetVal)
            rest = yield
            r.append('parent:'+rest)
        g = compose(parent())
        next(g)
        try:
            g.send('dataIn')
            self.fail()
        except StopIteration:
            pass
        self.assertEqual(['child-1:ding1retval', 'child-2:ding2retval', 'parent:rest(rest(dataIn))'], r)

    def testCheckForFreshGenerator(self):
        if not cpython: return
        def sub():
            yield
            yield
        def main():
            s = sub()
            next(s) # start it already
            yield s
        c = compose(main())
        try:
            next(c)
            self.fail('must raise')
        except Exception as e:
            self.assertEqual('Generator already used.', str(e))

    def testForExhaustedGenerator(self):
        if not cpython: return
        def sub():
            yield
        def main():
            s = sub()
            next(s)
            try:
                next(s)
                self.fail('must raise StopIteration')
            except StopIteration: pass
            yield s
        c = compose(main())
        try:
            next(c)
            self.fail('must not come here')
        except Exception as e:
            self.assertEqual('Generator is exhausted.', str(e))

    def testPassThrowCorrectly(self):
        class MyException(Exception): pass
        def child():
            try:
                yield 1
            except Exception as e:
                self.e = e
            yield 2
        g = compose(child())
        next(g)
        g.throw(MyException('aap'))
        self.assertEqual('aap', str(self.e))

    def testThrowWithLocalCorrectly(self):
        class MyException(Exception): pass
        def child(x):
            try:
                yield 1
            except Exception as e:
                yield f2()
        def f2():
            self.e = local("x")
            yield 2
        a = compose(child("test"))
        g = compose(child("aap"))
        next(g)
        g.throw(MyException())
        self.assertEqual('aap', str(self.e))

    def testHandleAllDataAndDoAvoidSuperfluousSendCalls(self):
        data = []
        def f():
            x = yield
            data.append(x)
            return value_with_pushback(*tuple(x))
        def g():
            r = yield f()
            data.append(r)
            while True:
                data.append((yield None))
        program = compose(g())
        next(program) # init
        program.send('mies')
        #program.next() # this is what we don't want and what we're testing here
        #program.next()
        #program.next()
        self.assertEqual('mies', data[0])
        self.assertEqual('m', data[1])
        self.assertEqual('i', data[2])
        self.assertEqual('e', data[3])
        self.assertEqual('s', data[4])
        program.close()

    def testHandleClose(self):
        r = []
        def f():
            try:
                yield None
            except BaseException as e:
                r.append(e)
                raise
        g = compose(f())
        next(g)
        g.close()
        self.assertEqual(GeneratorExit, type(r[0]))

    def testCloseWithLocalCorrectly(self):
        class MyException(Exception): pass
        def child(x):
            yield f2()
        def f2():
            try:
                yield 1
            except BaseException as e:
                self.e = local("x")
                raise
        g = compose(child("aap"))
        next(g)
        g.close()
        self.assertEqual('aap', str(self.e))

    def testHandleStop(self):
        r = []
        def f():
            try:
                yield None
            except Exception as e:
                r.append(e)
                raise
        g = compose(f())
        next(g)
        try:
            g.throw(StopIteration)
        except:
            pass
        self.assertEqual(StopIteration, type(r[0]))

    def testPassException1(self):
        class MyException(Exception): pass
        class WrappedException(Exception): pass
        def child():
            raise MyException('abc')
            yield None
        def parent():
            try:
                yield child()
            except MyException as e:
                raise WrappedException(e)
        g = compose(parent())
        try:
            next(g)
            self.fail()
        except WrappedException as e:
            self.assertEqual('abc', str(e))

    def testDealloc(self):
        def f():
            yield 'A'
            yield (1,2,3,4)
            yield 'B'
            yield 'C'
            yield 'D'
        g = compose(f())
        next(g)
        next(g)
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
            except MyException as e:
                raise WrappedException(e)
        g = compose(parent())
        next(g)
        try:
            next(g)
            self.fail()
        except WrappedException as e:
            self.assertEqual('abc', str(e))

    def xtestPerformance(self):
        def f1(arg):
            r = yield None
            yield arg
            return value_with_pushback('aap', 'rest')
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
            [list(compose(f3('begin'))) for i in range(100)]
            t1 = time()
            tg = tg + t1 - t0
            [baseline() for i in range(100)]
            t2 = time()
            tb = tb + t2 - t1
        print('Overhead compose compared to list(): %2.2f %%' % ((tg/tb - 1) * 100.0))

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
            except Exception as e:
                return value_with_pushback(e, 'more')
        def f3(arg):
            e = yield f2('aa')
            more = yield None
            try:
                yield more                      #   'X'
            except Exception:
                raise
        # runs this a zillion times and watch 'top'
        for i in range(1):
            g = compose(f3('noot'))
            next(g)
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
            except Exception as e:
                raise Exception(e)
        c = compose(g())
        r = next(c)
        self.assertEqual('A', r)
        try:
            c.throw(Exception('wrong'))
            self.fail('must raise wrapped exception')
        except Exception as e:
            self.assertEqual("Exception(Exception('wrong'))", repr(e))

    def testNestedClose(self):
        def f():
            yield 'A'
        def g():
            try:
                yield f()
            except BaseException as e:
                raise Exception(e)
        c = compose(g())
        r = next(c)
        self.assertEqual('A', r)
        try:
            c.close()
            self.fail('must raise wrapped CLOSE exception')
        except Exception as e:
            self.assertEqual("Exception(GeneratorExit())", repr(e))

    def testMaskException(self):
        def f():
            try:
                yield 'a'
            except:
                pass
        c = compose(f())
        next(c)
        try:
            c.throw(Exception('aap'))
        except StopIteration:
            pass
        except Exception as e:
            self.fail(str(e))

    def testThrowWithExceptionCaughtDoesNotDitchResponse(self):
        def f():
            try:
                yield 'response'
            except StopIteration:
                pass
            yield 'is this ditched?'
        c = compose(f())
        response = next(c)
        self.assertEqual('response', response)
        response = c.throw(StopIteration())
        self.assertEqual('is this ditched?', response)

    def testThrowWithExceptionCaughtDoesNotDitchResponseWhileInSubGenerator(self):
        def sub():
            try:
                yield 'response'
            except StopIteration:
                return 'return'
        def f():
            ret = yield sub()
            self.assertEqual('return', ret)
            yield 'is this ditched?'
        c = compose(f())
        response = next(c)
        self.assertEqual('response', response)
        response = c.throw(StopIteration())
        self.assertEqual('is this ditched?', response)

    def testAdhereToYieldNoneMeansReadAndYieldValueMeansWriteWhenMessagesAreBuffered(self):
        done = []
        def bufferSome():
            return value_with_pushback('retval', 'rest1', 'rest2')
            yield
        def writeSome():
            yield 'write this'
        def g():
            yield bufferSome()
            yield writeSome()
            data = yield 'write'
            self.assertEqual(None, data)
            data = yield
            self.assertEqual('rest1', data)
            done.append(True)
        g = compose(g())
        results = list(g)
        self.assertEqual([True], done)
        self.assertEqual(['write this', 'write'], results)

    def testAdhereToYieldNoneMeansReadAndYieldValueMeansWriteWhenMessagesAreBuffered2(self):
        done = []
        def bufferSome():
            return value_with_pushback('retval', 'rest1', 'rest2')
            yield
        def writeSome():
            data = yield 'write this'
            self.assertEqual(None, data)
        def g():
            yield bufferSome()
            yield writeSome()
            data = yield
            self.assertEqual('rest1', data)
            done.append(True)
        g = compose(g())
        results = list(g)
        self.assertEqual([True], done)
        self.assertEqual(['write this'], results)

    def testDoNotSendSuperfluousNonesOrAdhereToNoneProtocol(self):
        def sub():
            jack = yield None
            none = yield 'hello ' + jack
            peter = yield None
            none = yield 'hello ' + peter
        c = compose(sub())
        self.assertEqual(None, c.send(None))           # 1 init with None, oh, it accepts data
        self.assertEqual('hello jack', c.send('jack')) # 2 send data, oh it has data
        self.assertEqual(None, c.send(None))           # 3 it had data, so send None to see what it wants next, oh, it accepts data
        self.assertEqual('hello peter', c.send('peter')) # 4 send data, oh, it has data

    def testUserAdheresToProtocol(self):
        def sub():
            yield 'response'
            yield 'response'
        c = compose(sub())
        self.assertEqual('response', next(c))
        try:
            c.send('message')
            self.fail('must raise exception')
        except AssertionError as e:
            self.assertEqual('Cannot accept data. First send None.', str(e))

    def testExceptionsHaveGeneratorCallStackAsBackTrace(self):
        def f():
            yield
        def g():
            yield f()
        c = compose(g())
        next(c)
        try:
            c.throw(Exception, Exception('ABC'))
            self.fail()
        except Exception:
            exType, exValue, exTraceback = exc_info()
            self.assertEqual('testExceptionsHaveGeneratorCallStackAsBackTrace', exTraceback.tb_frame.f_code.co_name)
            # TS: FIXME: traceback cleaning broken in PY3: ('_compose' below)
            self.assertEqual('_compose', exTraceback.tb_next.tb_frame.f_code.co_name)
            self.assertEqual('g', exTraceback.tb_next.tb_next.tb_frame.f_code.co_name)
            self.assertEqual('f', exTraceback.tb_next.tb_next.tb_next.tb_frame.f_code.co_name)

    def testToStringForSimpleGenerator(self):
        line = __NEXTLINE__()
        def f():
            yield
        g = f()
        soll = """  File "%s", line %s, in f
    %s""" % (fileDict['__file__'], line if cpython else '?', "def f():" if cpython else "<no source line available>")
        self.assertEqual(soll, tostring(g))
        next(g)
        soll = """  File "%s", line %s, in f
    yield""" % (fileDict['__file__'], line + 1)
        self.assertEqual(soll, tostring(g))


    def testToStringGivesStackOfGeneratorsAKAcallStack(self):
        l1 = __NEXTLINE__(+1)
        def f1():
            yield
        l2 = __NEXTLINE__(+1)
        def f2():
            yield f1()
        c = compose(f2())
        result = """  File "%s", line %s, in f2
    yield f1()
  File "%s", line %s, in f1
    yield""" % (fileDict['__file__'], l2, fileDict['__file__'], l1)
        next(c)
        self.assertEqual(result, tostring(c), "\n%s\n!=\n%s\n" % (result, tostring(c)))

    def testToStringForUnstartedGenerator(self):
        def f1():
            yield
        line = __NEXTLINE__()
        def f2():
            yield f1()
        c = compose(f2())
        if cpython:
            result = """  File "%s", line %s, in f2\n    def f2():""" % (fileDict['__file__'], line)
        else:
            result = """  File "%s", line '?' in _compose\n    <no source line available>""" % fileDict['__file__']
        self.assertEqual(result, tostring(c))

    def testWrongArgToToString(self):
        try:
            tostring('x')
            self.fail('must raise TypeError')
        except TypeError as e:
            self.assertEqual("tostring() expects generator", str(e))

    def testFindLocalNotThere(self):
        def f1():
            yield f2()
        def f2():
            try:
                l = local('doesnotexist')
            except AttributeError as e:
                yield e
        f = compose(f1())
        result = next(f)
        self.assertEqual('doesnotexist', str(result))

    def testFindLocal(self):
        def f1():
            someLocal = 'f1'
            yield f3()
        def f2():
            someLocal = 'f2'
            yield f3()
        def f3():
            l = local('someLocal')
            yield l
        f = compose(f1())
        result = next(f)
        self.assertEqual('f1', str(result))
        self.assertEqual('f2', str(next(compose(f2()))))

    def testFindLocalWithComposeUnassignedToVariable(self):
        def f1():
            f1local = 'f1'
            yield f2()
        def f2():
            l = local('f1local')
            yield l
        self.assertEqual('f1', next(compose(f1())))

    def testFindClosestLocal(self):
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
        result = next(f)
        self.assertEqual('f2', str(result))

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
            except SystemExit as e:
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
        next(c)
        c.throw(KeyboardInterrupt())
        self.assertEqual(['KeyboardInterrupt'], msg)
        c.throw(SystemExit())
        self.assertEqual(['KeyboardInterrupt', 'SystemExit'], msg)
        c.throw(SystemExit()) # second time
        self.assertEqual(['KeyboardInterrupt', 'SystemExit', 'BaseException', 'see me'], msg)

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
        except ValueError as e:
            self.assertEqual('1', str(e))

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
        except RuntimeError as e:
            self.assertEqual('generator ignored GeneratorExit', str(e))


        @autostart
        def f4():
            yield
            yield

        g4 = f4()
        try:
            g4.close()
        except BaseException as e:
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
                return # <= this is the clue, see next test
        g5 = compose(f5())
        next(g5)
        try:
            g5.throw(GeneratorExit())
            self.fail('must reraise GeneratorExit if no exception by g1()')
        except GeneratorExit:
            pass
        self.assertEqual(['GeneratorExit turned into StopIteration'], msg)

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
        next(g7)
        try:
            g7.throw(GeneratorExit)
            self.fail('must reraise RuntimeError(generator ignored GeneratorExit)')
        except RuntimeError:
            pass
        self.assertEqual(['GeneratorExit ignored'], msg)


        # Second case

        msg = []
        def f8():
            try:
                yield f9()
            except ValueError as e:
                msg.append(str(e))
                return
        def f9():
            try:
                yield
            except GeneratorExit:
                msg.append('GeneratorExit turned into ValueError')
                #raise RuntimeError('stop here')
                raise ValueError('stop here')
            yield

        g8 = compose(f8())
        next(g8)
        try:
            g8.throw(GeneratorExit())
            self.fail('must raise StopIteration')
        except StopIteration:
            pass
        self.assertEqual(['GeneratorExit turned into ValueError', 'stop here'], msg)

    def testYieldCompose(self):
        def f():
            yield "f"
        def g():
            yield compose(f())
        c = compose(g())
        self.assertEqual(['f'], list(c))

    def testComposeCompose(self):
        def f():
            yield
        c = compose(compose(f()))
        self.assertTrue(c)

    def testCollectInComposeObject(self):
        from sys import getrefcount
        def f():
            gc.collect()
            yield
        next(compose(f()))

    def testYieldComposeCloseAndThrow(self):
        def f():
            try:
                yield 42
            except Exception as e:
                yield 84

        c = compose(f())
        self.assertEqual(42, c.send(None))
        self.assertEqual(84, c.throw(Exception()))
        self.assertEqual(None, c.close())

    def testMessagesAndResponseAreFreed(self):
        def f():
            v = yield ATrackedObj() # some that is tracked
        self.assertTrue('ATrackedObj' in str(next(compose(f()))))

    def testDecorator(self):
        from weightless.core import compose
        @compose
        def f():
            yield "a"
        self.assertEqual(["a"], list(f()))
        self.assertEqual('f', f.__name__)

    def testEmptyArgsInStopIteration(self):
        def f1():
            return
            yield
        def f2():
            x = yield f1()
            yield x
        g = compose(f2())
        self.assertEqual([None], list(g))

    def testArgsIsNoIterable(self):
        # because the Python VM checks this, we test the assumtion only
        si = StopIteration()
        try:
            si.args = 9 # not a tuple. Actually checked by StopIteration itself!
        except TypeError as e:
            self.assertEqual("'int' object is not iterable", str(e))

    def testArgsIsNoTuple(self):
        # because the Python VM turns the args into a tuple, we only test this
        si = StopIteration()
        si.args = [2] # not a tuple. VM turns this into tuple
        self.assertEqual((2,), si.args)

    def testComposeType(self):
        from weightless.core import ComposeType
        self.assertEqual(type, type(ComposeType))
        self.assertEqual(ComposeType, type(compose((n for n in []))))

    def testRaiseStopIterationWithRemainingMessages(self):
        def f0():
            return
            yield
        def f1():
            return 1
            yield
        def f2():
            return value_with_pushback(2,3)
            yield
        def f3():
            return value_with_pushback(4,5,6)
            yield
        try: next(f0())
        except StopIteration as e: self.assertEqual(None, e.value)
        try: next(f1())
        except StopIteration as e: self.assertEqual(1, e.value)
        try: next(f2())
        except StopIteration as e: self.assertEqual((value_with_pushback, 2, (3,)), (type(e.value), e.value.value, e.value.pushback))
        try: next(f3())
        except StopIteration as e: self.assertEqual((value_with_pushback, 4, (5,6)), (type(e.value), e.value.value, e.value.pushback))

    def testRaisStopIterationWithTupleValue(self):
        def f0():
            return value_with_pushback((1, 2))
            yield
        def f1():
            result = yield f0()
            yield result
        # Before fix C compose considered tuple elements as separate arguments to be passed into send()
        self.assertEqual([(1,2)], list(compose(f1())))

    def testConcurrentFlow(self):
        def f():
            first_msg = yield
            return value_with_pushback(*first_msg.split())
        def g():
            first = yield f()
            yield "response" # in between receiving msgs
            msg = yield
            second_msg = yield
            yield second_msg
        p = compose(g())
        next(p)
        p.send("first msg")
        p.send(None)
        x = p.send("second msg")
        self.assertEqual('second msg', x)

    def testRaiseRemainingMessages(self):
        def f():
            return value_with_pushback(1,2,3)
            yield
        def g():
            one = yield f()
            self.assertEqual(1, one)
            two = yield
            self.assertEqual(2, two)
        c = compose(g())
        try:
            next(c)
        except StopIteration as e:
            self.assertEqual((value_with_pushback, None, (3,)), (type(e.value), e.value.value, e.value.pushback))

    def testComposeInCompose(self):
        def f():
            yield 'a'
        g = compose(f())
        c = compose(g)
        self.assertEqual(['a'], list(c))

    def testIsGeneratorOrComposed(self):
        def f():
            yield

        self.assertTrue(is_generator(f()))
        self.assertTrue(is_generator(compose(f())))
        self.assertFalse(is_generator(lambda: None))
        self.assertFalse(is_generator(None))

    def testUnsuitableGeneratorTraceback(self):
        def f():
            yield "alreadyStarted"
            yield "will_not_get_here"
        genYieldLine = __NEXTLINE__(offset=3)
        def gen():
            genF = f()
            self.assertEqual("alreadyStarted", next(genF))
            yield genF

        composed = compose(gen())

        try:
            cLine = __NEXTLINE__()
            next(composed)
        except AssertionError as e:
            self.assertEqual('Generator already used.', str(e))

            # TS: FIXME: traceback cleaning broken in PY3: ('_compose' below)
            stackText = """\
Traceback (most recent call last):
  File "%(__file__)s", line %(cLine)s, in testUnsuitableGeneratorTraceback
    next(composed)
  File "%(py_compose)s", line 143, in _compose
    raise exception[1].with_traceback(exception[2])
  File "%(__file__)s", line %(genYieldLine)s, in gen
    yield genF
AssertionError: Generator already used.\n""" % {
                '__file__': fileDict['__file__'],
                'py_compose': fileDict['py_compose'],
                'cLine': cLine,
                'genYieldLine': genYieldLine,
            }
            tbString = format_exc()
            self.assertEqual(stackText, tbString)
        else:
            self.fail("Should not happen.")

    def testAssertionsInComposeAreFatal(self):
        def f():
            yield
        startedGen = f()
        next(startedGen)
        ok = []
        def gen():
            try:
                yield startedGen
                self.fail('Should not happen')
            except AssertionError as e:
                self.assertEqual("Generator already used.", str(e))
        def anotherGen():
            try:
                yield gen()
            finally:
                ok.append(True)
        composed = compose(anotherGen())


        try:
            next(composed)
        except StopIteration:
            pass
        else:
            self.fail('Expected StopIteration to be raised')
        finally:
            self.assertEqual([True], ok)

    def get_tracked_objects(self):
        return [o for o in gc.get_objects() if type(o) in
                (compose, GeneratorType, Exception, StopIteration, ATrackedObj)]

    def setUp(self):
        TestCase.setUp(self)
        if cpython:
            gc.collect()
            self._baseline = self.get_tracked_objects()

    def tearDown(self):
        if cpython:
            def tostr(o):
                try:
                    return tostring(o)
                except:
                    return repr(o)
            gc.collect()
            for obj in self.get_tracked_objects():
                if obj not in self._baseline:
                    if thrush(obj,
                              fpartial(ga, 'gi_code'),
                              fpartial(ga, 'co_name')) \
                       in {'testPartExecutor'}:
                        continue
                    #else:
                    #    print("1:", repr(obj))
                    #    print("2:", type(obj))
                    #    print("3:", dir(obj))

                #continue
                self.assertTrue(obj in self._baseline, obj) #tostr(obj))
            del self._baseline
            gc.collect()
        TestCase.tearDown(self)


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
            return value_with_pushback(*range(testrange))
            yield 'f done'
        def g():
            results = []
            x = yield f()
            results.append(x)
            for i in range(testrange-1):
                results.append((yield))
            yield results
        c = compose(g())
        self.assertEqual([list(range(testrange))], list(c))

    def testQueueSizeExceeded(self):
        testrange = 10 #QUEUE SIZE = 10
        def f():
            return value_with_pushback(*range(testrange))
            yield
        def g():
            x = yield f()
        self.assertRaises(RuntimeError, compose(g()).__next__)

    def testStackOverflow(self):
        max_recursion_depth = getrecursionlimit()
        def f(recursion_depth=1):
            if recursion_depth < max_recursion_depth:
                yield f(recursion_depth + 1)
        c = compose(f())
        try:
            list(c)
        except RuntimeError as e:
            self.fail('must not raise %s' % e)

        max_recursion_depth += 1 # <==
        c = compose(f())
        try:
            list(c)
            self.fail('must raise runtimeerror')
        except RuntimeError as e:
            self.assertEqual('maximum recursion depth exceeded (compose)', str(e))

    def testDECREF_in_compose_clear(self):
        """A bit strange, but this triggers a bug with
        DECREF(<temporary>) in compose_clear()"""
        def f():
            msg = yield
            return value_with_pushback(*msg.split())

        r = compose(f())
        next(r)
        try:
            r.send("ab an")
        except StopIteration as e:
            self.assertEqual(('ab', 'an'), e.args)

    def testAlreadyStartedCompose(self):
        def f():
            yield
            yield
        def g():
            h = compose(f())
            next(h)
            yield h
        c = compose(g())
        try:
            next(c)
            self.fail("must raise check already started generator failure")
        except AssertionError as e:
            self.assertEqual("Generator already used.", str(e))

    def testSelftest(self):
        from weightless.core.ext import Compose_selftest
        Compose_selftest()


def gettypeerrormsg():
    def compose(initial, arg1 = None): pass
    try:
        compose()
    except TypeError as e:
        return str(e)

def thrush(*a):
   "Thrush operator for python!  Should be called with an initial value and 1 or more fns to make sense."
   # See: http://blog.fogus.me/2010/09/28/thrush-in-clojure-redux/
   return reduce(lambda acc, fn: fn(acc), a)

def fpartial(f, *a, **kw):       # similar to: https://github.com/clojurewerkz/support/blob/master/src/clojure/clojurewerkz/support/fn.clj - but *only* first-arg is allowed & required.
    def _wrap(arg):
        return f(arg, *a, **kw)
    return _wrap

def ga(o, name):
    return getattr(o, name, None)
