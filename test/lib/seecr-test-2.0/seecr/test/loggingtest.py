## begin license ##
#
# "Seecr Test" provides test tools.
#
# Copyright (C) 2012-2014, 2016, 2019 Seecr (Seek You Too B.V.) http://seecr.nl
# Copyright (C) 2012-2014 Stichting Bibliotheek.nl (BNL) http://www.bibliotheek.nl
# Copyright (C) 2016 Koninklijke Bibliotheek (KB) http://www.kb.nl
#
# This file is part of "Seecr Test"
#
# "Seecr Test" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# "Seecr Test" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with "Seecr Test"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

from os import stat
from os.path import isfile, join
from re import compile
from stat import ST_MTIME
from io import StringIO
from sys import stderr
from time import strftime, localtime
from unittest import TextTestRunner, TextTestResult, TestProgram


class LoggingTestProgram(TestProgram):
    def runTests(self):
        self.testRunner.verbosity = self.verbosity
        result = self.testRunner.run(self.test)
        exit(not result.wasSuccessful())


class LoggingTestRunner(TextTestRunner):
    def _makeResult(self):
        return _LoggingTextTestResult(self.stream, self.descriptions, self.verbosity)


class _LoggingTextTestResult(TextTestResult):
    def startTest(self, test):
        TextTestResult.startTest(self, test)
        self.stream.log.write(str(test))
        self.stream.log.write(" ... ")
        self.stream.log.flush()

    def addSuccess(self, test):
        TextTestResult.addSuccess(self, test)
        self.stream.log.write("ok\n")
        self.stream.log.flush()

    def addError(self, test, err):
        TextTestResult.addError(self, test, err)
        self.stream.log.write("ERROR\n")
        self.stream.log.flush()

    def addFailure(self, test, err):
        TextTestResult.addFailure(self, test, err)
        self.stream.log.write("FAIL\n")
        self.stream.log.flush()

    def addSkip(self, test, reason):
        TextTestResult.addSkip(self, test, reason)
        self.stream.log.write("skipped\n")
        self.stream.log.flush()

    def printResult(self, timeTaken):
        pass


class LoggingTestStream(object):
    def __init__(self, stream, logStream):
        self._stream = stream
        self._logStream = logStream

    @property
    def default(self):
        return self._stream

    @property
    def log(self):
        return self._logStream

    def write(self, aString):
        self.default.write(aString)

    def writeln(self, aString):
        self.default.writeln(aString)

    def flush(self):
        self.default.flush()


testNameRe = compile("([A-Z]+[a-z0-9]*)")
def formatTestname(testname):
    return ' '.join([part.lower() for part in testNameRe.split(testname) if part and part != 'test']).capitalize()

def readTestFile(*pathparts):
    fullFilename = join(*pathparts)
    if not isfile(fullFilename):
        return {}
    def l(testname, classname, _, status):
        return dict(testname=testname, classname=classname.replace('(', '').replace(')', ''), status=status)
    return {'timestamp':strftime("%Y-%m-%d %H:%M:%S", localtime(stat(fullFilename)[ST_MTIME])), 'tests': [
        l(*line.strip().split()) for line in open(fullFilename) if line.strip()]}

def runUnitTests(loggingFilepath=None):
    logStream = StringIO() if loggingFilepath is None else open(loggingFilepath, 'w')
    testStream = LoggingTestStream(stream=stderr, logStream=logStream)
    try:
        LoggingTestProgram(testRunner=LoggingTestRunner(stream=testStream))
    finally:
        logStream.close()

