## begin license ##
# 
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io 
# 
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

from unittest import TestCase, main

from weightless.core.utils import autostart

""" This code demonstrates the use of generators in Python.
It has been life coded on conferences SPA2008, AgileOpen2008 and the
Dutch Python day on October 4th, 2008.  The implementations below are in
order of increasing complexity, the tests are in reverse order!"""

def wordLengths1(words):
    """ implementation with lists for both input and output """
    result = []
    for word in words:
        result.append(len(word))
    return result

def wordLengths1_alternative(words):
    """ one could use list comprehension as well """
    return [len(word) for word in words]

def wordLengths2(words):
    """ implementation with list as input and generator as output """
    for word in words:
        yield len(word)

def wordLengths2_alternative(words):
    """ one could use a generator expression as well """
    return (len(word) for word in words)

@autostart
def wordLengths3():
    """ implementation with generator for both input and output """
    length = None
    while True:
        word = yield length
        length = len(word)

@autostart
def wordLengths4():
    """ a generator stops with StopIteration exception, which can be catched """
    length = None
    while True:
        try:
            word = yield length
        except StopIteration:
            yield 'done'
            return
        length = len(word)

@autostart
def explicitReturn():
    yield
    return

@autostart
def raiseStopIteration():
    yield
    raise StopIteration()

@autostart
def endOfFunction():
    yield

def withoutAutoStart():
    message = yield
    yield message

@autostart
def withAutoStart():
    message = yield
    yield message

class PythonTest(TestCase):
    """ last test on top """

    def testWhyAutoStart(self):
        firstTry = withoutAutoStart()
        try:
            firstTry.send('hello')
            self.fail()
        except TypeError as e:
            self.assertEqual("can't send non-None value to a just-started generator", str(e))
        secondTry = withoutAutoStart()
        next(secondTry) # 'start'
        message = secondTry.send('hello')
        self.assertEqual('hello', message)
        thirdTry = withAutoStart()
        message = thirdTry.send('hello')
        self.assertEqual('hello', message)

    def testThreeWaysOfStoping(self):
        f1 = explicitReturn()
        f2 = raiseStopIteration()
        f3 = endOfFunction()
        try:
            next(f1)
            self.fail()
        except StopIteration:
            pass
        try:
            next(f2)
            self.fail()
        except StopIteration:
            pass
        try:
            next(f3)
            self.fail()
        except StopIteration:
            pass

    def testStop(self):
        c = wordLengths4()
        c.send('python')
        c.send('day')
        k = c.throw(StopIteration())
        self.assertEqual('done', k)

    def testLineLengthsCoroutine(self):
        c = wordLengths3()
        self.assertEqual(6, c.send('python'))
        self.assertEqual(3, c.send('day'))

    def testLineLengthsWithGeneratorForOutput(self):
        g = wordLengths2(['python', 'day'])
        self.assertEqual([6,3], list(g))
        g = wordLengths2_alternative(['python', 'day'])
        self.assertEqual([6,3], list(g))

    def testLineLengths1(self):
        l = wordLengths1(['python', 'day'])
        self.assertEqual([6, 3], l)
        l = wordLengths1_alternative(['python', 'day'])
        self.assertEqual([6, 3], l)

main()
