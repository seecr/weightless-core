## begin license ##
# 
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io 
# 
# Copyright (C) 2006-2008 Seek You Too (CQ2) http://www.cq2.nl
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
from random import choice, randint
from string import ascii_letters
from weightless.core import compose
from weightless.core.utils import copyBytes, readAll, readRe
from re import compile

def collector(basket, responses):
    responses = iter(responses)
    try:
        while True:
            basket.append((yield next(responses)))
    except StopIteration:
        pass
    yield

def feed(data, generator):
    responses = []
    for item in data:
        responses.append(generator.send(item))
    return responses

class GutilsTest(TestCase):

    def assertCopy(self, bytes, messages, responses, slice, remainder):
        basket = []
        restbasket = []
        def helper():
            c1 = collector(basket, responses); next(c1)
            yield copyBytes(bytes, c1)
            while True:
                restbasket.append((yield))
        responsesResult = feed([None]+messages, compose(helper()))
        self.assertEquals(responses, responsesResult) # I still don't know if this is relevant and how it must work
        self.assertEquals(slice, basket)
        self.assertEquals(remainder, restbasket)

    def testMessagesOfSizeOne(self):
        self.assertCopy(bytes=10, messages=['a','b','c'], responses=[None,None,None,None], slice=['a','b','c'], remainder=[])
        self.assertCopy(bytes= 3, messages=['a','b','c'], responses=[None,None,None,None], slice=['a','b','c'], remainder=[])
        self.assertCopy(bytes= 2, messages=['a','b','c'], responses=[None,None,None,None], slice=['a','b'], remainder=['c'])
        self.assertCopy(bytes= 1, messages=['a','b','c'], responses=[None,None,None,None], slice=['a'], remainder=['b','c'])
        self.assertCopy(bytes= 0, messages=['a','b','c'], responses=[None,None,None,None], slice=[], remainder=['a', 'b','c'])

    def testMessagesOfSizeTwo(self):
        self.assertCopy(bytes=10, messages=['ab','cd','ef'], responses=[None,None,None,None], slice=['ab','cd','ef'], remainder=[])
        self.assertCopy(bytes= 3, messages=['ab','cd','ef'], responses=[None,None,None,None], slice=['ab','c'], remainder=['d','ef'])
        self.assertCopy(bytes= 2, messages=['ab','cd','ef'], responses=[None,None,None,None], slice=['ab'], remainder=['cd','ef'])
        self.assertCopy(bytes= 1, messages=['ab','cd','ef'], responses=[None,None,None,None], slice=['a'], remainder=['b','cd','ef'])
        self.assertCopy(bytes= 0, messages=['ab','cd','ef'], responses=[None,None,None,None], slice=[], remainder=['ab', 'cd','ef'])

    def testRandom(self):
        for i in range(100):
            sliceLen = randint(0,100)
            basket = []
            restbasket = []
            def helper():
                c1 = collector(basket,[None for x in range(99999)]); next(c1)
                yield copyBytes(sliceLen, c1)
                while True:
                    restbasket.append((yield))
            g = compose(helper())
            next(g)
            totalLen = 0
            while totalLen < sliceLen:
                s = ''.join(choice(ascii_letters) for i in range(randint(0,100)))
                g.send(s)
                totalLen += len(s)
            self.assertEquals(sliceLen, len(''.join(basket)))
            self.assertEquals(totalLen-sliceLen, len(''.join(restbasket)))

    def testStopIterationBoundariesCollide(self):
        data = []
        def target():
            try:
                while True:
                    data.append((yield))
            except StopIteration:
                data.append('done')
        def helper():
            t = target(); next(t)
            yield copyBytes(2, t)
            try:
                yield t.throw(StopIteration)
            except:
                pass
            while True: yield
        g = compose(helper()); next(g)
        feed(['a','b','c'], g)
        self.assertEquals(['a','b', 'done'], data)

    def testStopIteration(self):
        data = []
        def target():
            try:
                while True:
                    data.append((yield))
            except StopIteration:
                data.append('done')
        def helper():
            t = target(); next(t)
            yield copyBytes(2, t)
            try:
                yield t.throw(StopIteration)
            except StopIteration:
                pass
            while True: yield
        g = compose(helper()); next(g)
        feed(['a','bc','d'], g)
        self.assertEquals(['a','b', 'done'], data)

    def testDoNotDitchResponse(self):
        def application():
            data = yield readAll()
            self.assertEquals('a', data)
            yield 'A'
        appl = compose(application()); next(appl)
        def protocol():
            yield copyBytes(1, appl)
            yield appl.throw(StopIteration)
            yield 'B'
            b = yield
            yield b
        g = compose(protocol()); 
        self.assertEquals(None, next(g))
        self.assertEquals('A', g.send('a'))
        self.assertEquals('B', g.send(None))
        self.assertEquals(None, g.send(None))
        self.assertEquals('b', g.send('b'))

    def testDoNotDitchResponseInCaseOfSplitMessages(self):
        def application():
            data = yield readAll()
            self.assertEquals('a', data)
            yield 'A'
        appl = compose(application()); next(appl)
        def protocol():
            yield copyBytes(1, appl)
            try:
                yield appl.throw(StopIteration)
            except StopIteration:
                pass
            yield 'B'
            yield 'C'
            b = yield
            yield b
        g = compose(protocol()); next(g)
        self.assertEquals('A', g.send('ab'))
        self.assertEquals('B', g.send(None))
        self.assertEquals('C', g.send(None))
        self.assertEquals('b', g.send(None))

    def testReadRe(self):
        x = readRe(compile('(?P<ape>xyz)'))
        next(x)
        try:
            x.send('xyz') # fail
            self.fail('must not come here')
        except StopIteration as s:
            self.assertEquals(({'ape': 'xyz'},), s.args)

    def testReadReWithMaximumBytes(self):
        x = readRe(compile('xyz'), 5)
        next(x)
        x.send('abc')
        try:
            x.send('abc') # fail
            self.fail('must not come here')
        except OverflowError as e:
            self.assertEquals('no match after 6 bytes', str(e))

    def testReadReEndOfStream(self):
        x = readRe(compile('.*'), 10)
        next(x)
        try:
            x.send(None)
            self.fail('must raise Exception')
        except Exception as e:
            self.assertEquals("no match at eof: ''", str(e))

