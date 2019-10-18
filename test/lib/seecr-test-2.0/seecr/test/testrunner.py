## begin license ##
#
# "Seecr Test" provides test tools.
#
# Copyright (C) 2012, 2014-2015, 2018 Seecr (Seek You Too B.V.) http://seecr.nl
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

import types
from sys import stdout, stderr, exit
from time import time
from traceback import print_exc
from unittest import TestSuite as UnitTestTestSuite, TestLoader as UnitTestTestLoader, TestResult as UnitTestResult, TestCase
from optparse import OptionParser


class TestResult(UnitTestResult):
    def __init__(self, stream=stdout, errStream=stderr, verbosity=1):
        UnitTestResult.__init__(self)
        self.showAll = verbosity > 1
        self.dots = verbosity == 1
        self._errStream = errStream
        self._stream = stream

    def startTest(self, test):
        UnitTestResult.startTest(self, test)
        if self.showAll:
            self._errWrite(str(test))
            self._errWrite(' ... ')

    def addError(self, test, err):
        UnitTestResult.addError(self, test, err)
        if self.showAll:
            self._errWrite('ERROR\n')
        elif self.dots:
            self._errWrite('E')

    def addFailure(self, test, err):
        UnitTestResult.addFailure(self, test, err)
        if self.showAll:
            self._errWrite('FAIL\n')
        elif self.dots:
            self._errWrite('F')

    def addSuccess(self, test):
        UnitTestResult.addSuccess(self, test)
        if self.showAll:
            self._errWrite('ok\n')
        elif self.dots:
            self._errWrite('.')

    def addSkip(self, test, reason):
        UnitTestResult.addSkip(self, test, reason)
        if self.showAll:
            self._errWrite('skip {0!r}\n'.format(reason))
        elif self.dots:
            self._errWrite('s')

    def addExpectedFailure(self, test, err):
        UnitTestResult.addExpectedFailure(self, test, err)
        if self.showAll:
            self._errWrite('expected failure\n')
        elif self.dots:
            self._errWrite('e')

    def printResult(self, timeTaken):
        self._write('\n')
        self._printErrorList('ERROR', self.errors)
        self._printErrorList('FAIL', self.failures)
        run = self.testsRun
        self._write(sep2)
        self._write('\033[1;%sm' % (32 if self.wasSuccessful() else 31))
        self._write("Ran %d test%s in %.3fs\n" % (run, run != 1 and "s" or "", timeTaken))
        self._write("\n")
        if not self.wasSuccessful():
            output = "FAILED ("
            failed, errored = list(map(len, (self.failures, self.errors)))
            if failed:
                output += "failures=%d" % failed
            if errored:
                if failed: output += ", "
                output += "errors=%d" % errored
            self._write(output + ")")
        else:
            self._write("OK")
        skipped = len(self.skipped)
        if skipped:
            self._write(' skipped=%d' % skipped)
        self._write('\n\033[0m')

    def _printErrorList(self, flavour, errors):
        for test, err in errors:
            self._write(sep1)
            self._write("%s: %s\n" % (flavour, test.shortDescription() or str(test)))
            self._write(sep2)
            self._write("%s\n" % err)

    def _errWrite(self, aString):
        self._errStream.write(aString)
        self._errStream.flush()

    def _write(self, aString):
        self._stream.write(aString)
        self._stream.flush()


class TestGroup(object):
    def __init__(self, name, classnames=None, state=None):
        self.name = name
        self._classes = {}
        for classname in (classnames or []):
            self._loadClass(classname)
        self._loader = TestLoader()
        self.setUp = state.setUp
        self.tearDown = state.tearDown
        self.state = state

    def _loadClass(self, classname):
        moduleName, className = classname.rsplit('.', 1)
        cls = getattr(__import__(moduleName, globals(), locals(), [className]), className)
        self._classes[className] = cls

    def createSuite(self, testnames=None):
        if not testnames:
            testnames = sorted(self._classes.keys())
        suite = TestSuite()
        for testname in testnames:
            testcase = testname.split('.')
            testclass = self._classes.get(testcase[0], None)
            if not testclass:
                continue
            if len(testcase) == 1:
                suite.addTest(self._loader.loadTestsFromTestCase(testclass))
            else:
                suite.addTest(self._loader.loadTestsFromName(testcase[1], testclass))
        return suite


class TestArguments(object):
    def __init__(self, args=None):
        if args is None:
            from sys import argv
            args = argv[1:]
        parser = OptionParser()
        parser.add_option('-g', '--group', help='Group', default=None)
        parser.add_option('-l', '--list', default=False, action='store_true', help='List groups')
        parser.add_option('', '--fast', action="store_true", help='Enable fastmode', default=False)
        parser.add_option('-v', '--verbose', action="store_true", help='Be more verbose', default=False)
        options, self.testnames = parser.parse_args(args)
        self.groupnames = None if options.group is None else [options.group]
        self.fastMode = options.fast
        self.verbose = options.verbose
        self.listGroups = options.list

class TestRunner(object):
    def __init__(self, verbose=None):
        self._groups = []
        self._stream = stdout
        self._args = self.parseArgs()
        if verbose is None:
            verbose = self._args.verbose
        self._verbosity = 2 if verbose else 1
        self.fastMode = self._args.fastMode

    def addGroup(self, *args, **kwargs):
        self._groups.append(TestGroup(*args, **kwargs))

    @staticmethod
    def parseArgs(args=None):
        return TestArguments(args=args)

    def run(self, testnames='?', groupnames='?'):
        if groupnames == '?':
            groupnames = self._args.groupnames
        if testnames == '?':
            testnames = self._args.testnames
        t0 = time()
        testResult = TestResult(verbosity=self._verbosity)
        groups = self._groups
        if self._args.listGroups:
            print('Groups:')
            for g in sorted(groups):
                print(' -', g.name)
            exit(0)
        if groupnames:
            groups = (group for group in self._groups if group.name in groupnames)
        for group in groups:
            suite = group.createSuite(testnames)
            if not suite.countTestCases():
                continue
            try:
                group.setUp()
                suite.run(result=testResult, state=group.state)
            except:
                print_exc()
                break
            finally:
                group.tearDown()
        timeTaken = time() - t0
        testResult.printResult(timeTaken)
        exit(not testResult.wasSuccessful())



class TestSuite(UnitTestTestSuite):

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)

    def run(self, result=None, state=None):
        for test in self._tests:
            if result.shouldStop:
                break
            test(result=result, state=state)
        return result

class TestLoader(UnitTestTestLoader):
    suiteClass = TestSuite

    def loadTestsFromName(self, name, module=None):
        """Return a suite of all tests cases given a string specifier.

        The name may resolve either to a module, a test case class, a
        test method within a test case class, or a callable object which
        returns a TestCase or TestSuite instance.

        The method optionally resolves the names relative to a given module.
        """
        parts = name.split('.')
        if module is None:
            parts_copy = parts[:]
            while parts_copy:
                try:
                    module = __import__('.'.join(parts_copy))
                    break
                except ImportError:
                    del parts_copy[-1]
                    if not parts_copy: raise
            parts = parts[1:]
        obj = module
        for part in parts:
            parent, obj = obj, getattr(obj, part)

        if type(obj) == types.ModuleType:
            return self.loadTestsFromModule(obj)
        elif (isinstance(obj, type) and
              issubclass(obj, TestCase)):
            return self.loadTestsFromTestCase(obj)
        elif (type(obj) == types.UnboundMethodType and
              isinstance(parent, type) and
              issubclass(parent, TestCase)):
            return TestSuite([parent(obj.__name__)])
        elif isinstance(obj, TestSuite):
            return obj
        elif hasattr(obj, '__call__'):
            test = obj()
            if isinstance(test, TestSuite):
                return test
            elif isinstance(test, TestCase):
                return TestSuite([test])
            else:
                raise TypeError("calling %s returned %s, not a test" %
                                (obj, test))
        else:
            raise TypeError("don't know how to make test from: %s" % obj)


sep1 = '=' * 70 + '\n'
sep2 = '-' * 70 + '\n'
