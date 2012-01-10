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

class _ComposeFilterTest(TestCase):
    pass

class ComposeFilterPyTest(_ComposeFilterTest):
    def setUp(self):
        global compose, Yield, tostring
        compose = pyCompose
        Yield = pyYield
        tostring = pyTostring
        _ComposeFilterTest.setUp(self)

    def testOneGeneratorNoFiltering(self):
        def gen():
            yield "one"
            yield "two"
        composed = compose(gen(), stepping=True, filter=lambda o: False)
        self.assertEquals(['one', 'two'], list(composed))

    def testFilterUseCase_responses(self):
        def f():
            yield "one"
            result = yield "filter me"
            yield "two"
            yield result
            yield "three"
        def g():
            yield "g1"
            for x in f():
                yield x
            yield "g2"

        composed = compose(g(), filter=lambda o: o == "filter me")
        self.assertEquals(['g1', 'one', 'filter me', 'two', None, 'three', 'g2'], list(composed))

    def testFilterUseCaseWithoutResult_responses(self):
        def gen():
            yield "one"
            result = yield Query("query")
            self.assertEquals(None, result)
            yield "two"
            yield "three"

        theFilter = lambda o: isinstance(o, Query)
        composed = compose(gen(), stepping=True, filter=theFilter)

        self.assertEquals("one", composed.next())

        qObj = composed.next()
        self.assertTrue(theFilter(qObj))
        self.assertEquals("query", qObj.query)
        self.assertEquals("two", composed.send(None))  # or .next()

        self.assertEquals("three", composed.next())
        # Whitebox testing 'no more messages'
        self.assertEquals([], composed.gi_frame.f_locals['messages'])
        self.assertRaises(StopIteration, composed.next)

    def testFilterUseCase_messages(self):
        msgs = []
        def gen():
            msgs.append((yield)) # one
            msgs.append((yield)) # two
            result = yield Query("query")
            msgs.append((yield)) # three
            msgs.append((yield)) # four
            msgs.append((yield)) # None -> OK to give responses
            yield result         # hand over the query response.

        theFilter = lambda o: isinstance(o, Query)
        composed = compose(gen(), stepping=True, filter=theFilter)

        self.assertEquals(None, composed.next())
        self.assertEquals(None, composed.send("one"))

        qObj = composed.send("two")
        self.assertTrue(theFilter(qObj))
        self.assertEquals("query", qObj.query)
        self.assertEquals(None, composed.send("result-of-query"))

        self.assertEquals(None, composed.send("three"))
        self.assertEquals(None, composed.send("four"))
        # Whitebox testing 'no more messages'
        self.assertEquals([], composed.gi_frame.f_locals['messages'])
        self.assertEquals("result-of-query", composed.send(None))  # or .next()
        # Whitebox testing 'no more messages'
        self.assertEquals([], composed.gi_frame.f_locals['messages'])
        self.assertRaises(StopIteration, composed.next)
        self.assertEquals(['one', 'two', 'three', 'four', None], msgs)

    def testFilterUseCaseWithoutResult_messages(self):
        msgs = []
        def gen():
            msgs.append((yield)) # one
            msgs.append((yield)) # two
            result = yield Query("query")
            msgs.append((yield)) # three
            msgs.append((yield)) # four

        theFilter = lambda o: isinstance(o, Query)
        composed = compose(gen(), stepping=True, filter=theFilter)

        self.assertEquals(None, composed.next())
        self.assertEquals(None, composed.send("one"))

        qObj = composed.send("two")
        self.assertTrue(theFilter(qObj))
        self.assertEquals("query", qObj.query)
        self.assertEquals(None, composed.send(None))  # or .next()

        self.assertEquals(None, composed.send("three"))

        try:
            # Whitebox testing 'no more messages'
            self.assertEquals([], composed.gi_frame.f_locals['messages'])
            composed.send("four")
        except StopIteration, e:
            self.assertTrue(e.args == tuple(), e.args)
        else:
            self.fail("Should have raise StopIteration")
        self.assertEquals(['one', 'two', 'three', 'four'], msgs)

    def testFilteringDoesNotDisturbNoneProtocol(self):
        def nextNr(number):
            result = yield Query('whats_next_after:%s' % number)
            yield result
        def gen():
            number = yield
            yield nextNr(number)

        theFilter = lambda o: isinstance(o, Query)
        composed = compose(gen(), stepping=True, filter=theFilter)
         
        result = composed.next()
        self.assertEquals(None, result)
         
        result = composed.send(41)
        self.assertEquals(Yield, result)

        qObj = composed.next()
        self.assertTrue(theFilter(qObj))
        self.assertEquals('whats_next_after:41', qObj.query)
        result = composed.send(42)

        self.assertEquals(42, result)
         
        try:
            composed.next()
        except StopIteration:
            pass
        else:
            self.fail("Should not happen.")

    def testToStringOnFilteredObjPassedOnState(self):
        fYieldLine = __NEXTLINE__(offset=1)
        def f():
            result = yield 42
            yield "won't-come-here"
        genYieldLine = __NEXTLINE__(offset=1)
        def gen():
            yield f()

        composed = compose(gen(), stepping=True, filter=lambda o: type(o) == int)
        self.assertEquals(Yield, composed.next())

        self.assertEquals(42, composed.next())

        stackText = """\
  File "%(__file__)s", line %(genYieldLine)s, in gen
    yield f()
  File "%(__file__)s", line %(fYieldLine)s, in f
    result = yield 42""" % {
            '__file__': fileDict['__file__'], 
            'genYieldLine': genYieldLine,
            'fYieldLine': fYieldLine,
        }
        self.assertEquals(stackText, tostring(composed))


class Query(object):
    def __init__(self, query):
        self.query = query

