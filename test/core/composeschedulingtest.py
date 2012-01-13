## begin license ##
# 
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io 
# 
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012 Seecr (Seek You Too B.V.) http://seecr.nl
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

from sys import stdout, exc_info, getrecursionlimit, version_info
from types import GeneratorType

from weightless.core import autostart, cpython
from weightless.core.compose._compose_py import __file__ as  _compose_py_module_file
from weightless.core.compose._compose_py import compose as pyCompose
from weightless.core.compose._compose_py import Yield as pyYield
from weightless.core.compose._tostring_py import tostring as pyTostring

from inspect import currentframe
from traceback import format_exc

fileDict = {
    '__file__': __file__.replace(".pyc", ".py").replace("$py.class", ".py"),
    'compose_py': _compose_py_module_file,
}

def __NEXTLINE__(offset=0):
    return currentframe().f_back.f_lineno + offset + 1

class _ComposeSchedulingTest(TestCase):
    pass

class ComposeSchedulingPyTest(_ComposeSchedulingTest):
    def setUp(self):
        global compose, Yield, tostring
        compose = pyCompose
        Yield = pyYield
        tostring = pyTostring
        _ComposeSchedulingTest.setUp(self)

    def testOneGenerator(self):
        def gen():
            yield "one"
            yield "two"

        composed = compose(gen(), stepping=True)

        self.assertEquals("one", composed.next())
        self.assertEquals("two", composed.next())
        try:
            composed.next()
        except StopIteration:
            pass
        else:
            self.fail("Should not happen.")

    def testTwoGenerators(self):
        def f():
            yield "one"
        def gen():
            yield f()
            yield "two"

        composed = compose(gen(), stepping=True)

        self.assertEquals(Yield, composed.next())
        self.assertEquals("one", composed.next())
        self.assertEquals("two", composed.next())

    def testMoreGenerators(self):
        def a():
            yield "three"
        def b():
            yield a()
        def c():
            yield b()
        def c2():
            yield "four"
        def d():
            yield "two"
            yield c()
            yield c2()
        def gen():
            yield "one"
            yield d()
            yield "five"

        composed = compose(gen(), stepping=True)

        self.assertEquals(
            ["one", Yield, "two", Yield, Yield, Yield, "three", Yield, "four", "five"],
            list(composed)
        )

    def testSteppingDoesNotDisturbNoneProtocol(self):
        def nextNr(number):
            yield number + 1
        def gen():
            number = yield
            yield nextNr(number)
         
        composed = compose(gen(), stepping=True)
        result = composed.next()
        self.assertEquals(None, result)
         
        result = composed.send(41)
        self.assertEquals(Yield, result)
         
        result = composed.next()
        self.assertEquals(42, result)
         
        try:
            composed.next()
        except StopIteration:
            pass
        else:
            self.fail("Should not happen.")

    # Adapted from composetest
    def testDoNotSendSuperfluousNonesOrAdhereToNoneProtocol(self):
        def hello(jack):
            yield 'hello ' + jack
        def sub():
            jack = yield None
            none = yield hello(jack)
            peter = yield None
            none = yield hello(peter)
        c = compose(sub(), stepping=True)
        self.assertEquals(None, c.send(None))      # 1 init with None, oh, it accepts data
        self.assertEquals(Yield, c.send('jack'))   # 2 send data, oh it gives Yield, do .next()
        self.assertEquals('hello jack', c.next())  # 3 oh it has data
        self.assertEquals(None, c.send(None))      # 4 it had data, so send None to see what it wants next, oh, it accepts data
        self.assertEquals(Yield, c.send('peter'))  # 5 send data, oh it gives Yield, do .next()
        self.assertEquals('hello peter', c.next()) # 6 oh, it has data

    def testYieldTransparentlyYieldedWhenStepping(self):
        def gen():
            data1 = yield
            yield Yield
            data2 = yield
            yield data1, data2
        composed = compose(gen(), stepping=True)

        self.assertEquals(None, composed.next())
        self.assertEquals(Yield, composed.send('data_a'))
        self.assertEquals(None, composed.next())
        self.assertEquals(('data_a', 'data_b'), composed.send('data_b'))

    def testToStringOnTransparentYield(self):
        line = __NEXTLINE__(offset=1)
        def gen():
            yield Yield
            yield 'pause'
        composed = compose(gen(), stepping=True)

        self.assertEquals(Yield, composed.next())
        self.assertEquals("""\
  File "%%(__file__)s", line %(line)s, in gen
    yield Yield""" % {'line': line} % fileDict, tostring(composed))

    def testExceptionOnSendData(self):
        def f():
            return
            yield
        def gen():
            yield f()
        composed = compose(gen(), stepping=True)

        self.assertEquals(Yield, composed.next())
        try:
            composed.send('data')
            self.fail('Should have failed')
        except AssertionError, e:
            self.assertEquals('Cannot accept data when stepping. First send None.', str(e))

    def testExceptionOnSendData_TransparentStepping(self):
        fLine = __NEXTLINE__(offset=1)
        def f():
            yield Yield  # second Yield
            yield 'data'
        gLine = __NEXTLINE__(offset=1)
        def g():
            yield f()  # first Yield
        c = compose(g(), stepping=True)
        self.assertEquals(Yield, c.next())
        self.assertEquals(Yield, c.next())
        try:
            cLine = __NEXTLINE__()
            c.send('data')
        except Exception:
            stackText = """\
Traceback (most recent call last):
  File "%%(__file__)s", line %(cLine)s, in testExceptionOnSendData_TransparentStepping
    c.send('data')
  File "%%(__file__)s", line %(gLine)s, in g
    yield f()  # first Yield
  File "%%(__file__)s", line %(fLine)s, in f
    yield Yield  # second Yield
  File "%%(compose_py)s", line 113, in _compose
    assert not ((message is not None) and (response is not None)), 'Cannot accept data. First send None.'
AssertionError: Cannot accept data. First send None.\n""" % {
                'cLine': cLine,
                'fLine': fLine,
                'gLine': gLine,
            } % fileDict
            tbString = format_exc()
            self.assertEquals(stackText, tbString)
        else:
            self.fail("Should not happen.")

    def testExceptionThrownInCompose_TransparentStepping(self):
        fLine = __NEXTLINE__(offset=1)
        def f():
            yield Yield  # second Yield
            yield 'data'
        gLine = __NEXTLINE__(offset=1)
        def g():
            yield f()  # first Yield
        c = compose(g(), stepping=True)
        self.assertEquals(Yield, c.next())
        self.assertEquals(Yield, c.next())
        try:
            cLine = __NEXTLINE__()
            c.throw(Exception("tripping compose"))
        except Exception:
            stackText = """\
Traceback (most recent call last):
  File "%%(__file__)s", line %(cLine)s, in testExceptionThrownInCompose_TransparentStepping
    c.throw(Exception("tripping compose"))
  File "%%(__file__)s", line %(gLine)s, in g
    yield f()  # first Yield
  File "%%(__file__)s", line %(fLine)s, in f
    yield Yield  # second Yield
  File "%%(compose_py)s", line 112, in _compose
    message = yield response
Exception: tripping compose\n""" % {
                'cLine': cLine,
                'fLine': fLine,
                'gLine': gLine,
            } % fileDict
            tbString = format_exc()
            self.assertEquals(stackText, tbString)
        else:
            self.fail("Should not happen.")

    def testToStringOnStateJustAfterStep(self):
        fLine = __NEXTLINE__()
        def f():
            yield "one"
        gYieldLine = __NEXTLINE__(offset=1)
        def gen():
            yield f()

        composed = compose(gen(), stepping=True)
        self.assertEquals(Yield, composed.next())

        stackText = """\
  File "%(__file__)s", line %(gYieldLine)s, in gen
    yield f()""" % {
            '__file__': fileDict['__file__'], 
            'fLine': fLine, 'gYieldLine': gYieldLine
        }
        trace = tostring(composed)
        self.assertEquals(stackText, trace, trace)

    def testUnsuitableGeneratorTracebackBeforeStepping(self):
        def f():
            yield "alreadyStarted"
            yield "will_not_get_here"
        genYieldLine = __NEXTLINE__(offset=3)
        def gen():
            genF = f()
            self.assertEquals("alreadyStarted", genF.next())
            yield genF

        composed = compose(gen(), stepping=True)
        
        composed.next()
        try:
            cLine = __NEXTLINE__()
            composed.next()
        except AssertionError, e:
            self.assertEquals('Generator already used.', str(e))
        
            stackText = """\
Traceback (most recent call last):
  File "%(__file__)s", line %(cLine)s, in testUnsuitableGeneratorTracebackBeforeStepping
    composed.next()
  File "%(__file__)s", line %(genYieldLine)s, in gen
    yield genF
AssertionError: Generator already used.\n""" % {
                '__file__': fileDict['__file__'],
                'cLine': cLine,
                'genYieldLine': genYieldLine,
            }
            tbString = format_exc()
            self.assertEquals(stackText, tbString)
        else:
            self.fail("Should not happen.")

    def testExceptionThrownInCompose(self):
        def f():
            yield 10
        def g():
            yield f()
        c = compose(g(), stepping=True)
        c.next()
        try:
            cLine = __NEXTLINE__()
            c.throw(Exception("tripping compose"))
        except Exception:
            stackText = """\
Traceback (most recent call last):
  File "%(__file__)s", line %(cLine)s, in testExceptionThrownInCompose
    c.throw(Exception("tripping compose"))
  File "%(compose_py)s", line 132, in _compose
    raise exception[0], exception[1], exception[2]
Exception: tripping compose\n""" % {
                '__file__': fileDict['__file__'],
                'cLine': cLine,
                'compose_py': fileDict['compose_py'],
            }
            tbString = format_exc()
            self.assertEquals(stackText, tbString)
        else:
            self.fail("Should not happen.")


