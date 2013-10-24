# -*- coding: utf-8 -*-
## begin license ##
#
# "Seecr Test" provides test tools.
#
# Copyright (C) 2005-2009 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2012-2013 Seecr (Seek You Too B.V.) http://seecr.nl
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

from unittest import TestCase
from StringIO import StringIO
from functools import partial
from itertools import chain, ifilter
from os import getenv, close as osClose, remove, getpid
from os.path import join, isfile, realpath, abspath
from shutil import rmtree
from string import whitespace
from sys import path as systemPath, exc_info
from tempfile import mkdtemp, mkstemp
from timing import T

import pprint
import difflib

from lxml.etree import tostring, parse, Comment, PI, Entity


class SeecrTestCase(TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.tempdir = mkdtemp(prefix='test.%s.' % self.id())
        fd, self.tempfile = mkstemp(prefix='test.%s.' % self.id())
        osClose(fd)
        self.vmsize = self._getVmSize()

    def tearDown(self):
        rmtree(self.tempdir)
        remove(self.tempfile)
        TestCase.tearDown(self)

    def assertTiming(self, t0, t, t1):
        self.assertTrue(t0*T < t < t1*T, t/T)

    def select(self, aString, index):
        while index < len(aString):
            char = aString[index]
            index = index + 1
            if not char in whitespace:
                return char, index
        return '', index

    def cursor(self, aString, index):
        return aString[:index - 1] + "---->" + aString[index - 1:]

    def assertEqualsWS(self, s1, s2):
        index1 = 0
        index2 = 0
        while True:
            char1, index1 = self.select(s1, index1)
            char2, index2 = self.select(s2, index2)
            if char1 != char2:
                self.fail('%s != %s' % (self.cursor(s1, index1), self.cursor(s2, index2)))
            if not char1 or not char2:
                break

    def assertEqualsLxml(self, expected, result, matchPrefixes=True, showContext=True):
        compare = CompareXml(
            expectedNode=expected,
            resultNode=result,
            matchPrefixes=matchPrefixes,
            showContext=showContext,
        )
        compare.compare()

    def assertDictEqual(self, d1, d2, msg=None):
        # 'borrowed' from python2.7's unittest.
        self.assertTrue(isinstance(d1, dict), 'First argument is not a dictionary')
        self.assertTrue(isinstance(d2, dict), 'Second argument is not a dictionary')

        if d1 != d2:
            standardMsg = '%s != %s' % (safe_repr(d1, True), safe_repr(d2, True))
            diff = ('\n' + '\n'.join(difflib.ndiff(
                       pprint.pformat(dict(d1)).splitlines(),
                       pprint.pformat(dict(d2)).splitlines())))
            standardMsg += diff
            fullMsg = (msg + " : " if msg else '') + standardMsg
            self.fail(fullMsg)

    assertDictEquals = assertDictEqual

    def _getVmSize(self):
        status = open('/proc/%d/status' % getpid()).read()
        i = status.find('VmSize:') + len('VmSize:')
        j = status.find('kB', i)
        vmsize = int(status[i:j].strip())
        return vmsize

    def assertNoMemoryLeaks(self, bandwidth=0.8):
        vmsize = self._getVmSize()
        self.assertTrue(self.vmsize*bandwidth < vmsize < self.vmsize/bandwidth,
                "memory leaking: before: %d, after: %d" % (self.vmsize, vmsize))

    @staticmethod
    def binPath(executable, binDirs=None):
        allPath = [join(p, 'bin') for p in systemPath]
        allPath.extend([d for d in (binDirs or []) if d])
        if getenv('SEECRTEST_USR_BIN'):
            allPath.append(getenv('SEECRTEST_USR_BIN'))
        allPath.append('/usr/bin')
        for path in allPath:
            executablePath = join(path, executable)
            if isfile(executablePath):
                return realpath(abspath(executablePath))
        raise ValueError("No executable found for '%s'" % executable)


class CompareXml(object):
    def __init__(self, expectedNode, resultNode, matchPrefixes=True, showContext=False):
        self._expectedNode = getattr(expectedNode, 'getroot', lambda: expectedNode)()
        self._resultNode = getattr(resultNode, 'getroot', lambda: resultNode)()
        self._matchPrefixes = matchPrefixes
        if showContext != False:
            if isinstance(showContext, bool):
                self._context = 10
            else:
                self._context = showContext
        self._remainingContainer = None  # filled & used by compare and _compareNode
        for o in [self._expectedNode, self._resultNode]:
            if not getattr(o, 'getroottree', False):
                raise ValueError('Expected an Lxml Node- or Tree-like object, but got: "%s".' % str(o))

    def compare(self):
        self._remainingContainer = []

        expectedNodes = [self._expectedNode]
        if isRootNode(self._expectedNode):
            expectedNodes = previousNodes(self._expectedNode) + \
                [self._expectedNode] + \
                nextNodes(self._expectedNode)

        resultNodes = [self._resultNode]
        if isRootNode(self._resultNode):
            resultNodes = previousNodes(self._resultNode) + \
                [self._resultNode] + \
                nextNodes(self._resultNode)

        try:
            expectedNode = self._expectedNode
            resultNode = self._resultNode
            self._compareChildrenAndAddToQueue(
                    parent=None,
                    expectedChildren=expectedNodes,
                    resultChildren=resultNodes)

            while self._remainingContainer:
                expectedNode, resultNode = self._remainingContainer.pop(0)
                self._compareNode(expectedNode, resultNode)
        except AssertionError:
            c, v, t = exc_info()
            v = c(str(v) + self._contextStr(expectedNode, resultNode))
            raise c, v, t.tb_next

    def _contextStr(self, expectedNode, resultNode):
        if not hasattr(self, '_context'):
            return ''

        def reparseAndFindNode(root, node):
            refind = refindLxmlNodeCallback(root, node)
            text = tostring(root.getroottree() if isRootNode(root) else root, encoding='UTF-8')  # pretty_print input if you want to have pretty output.
            newTree = parse(StringIO(text))
            newNode = refind(newTree)
            return newTree, newNode, text

        def formatTextForNode(node, originalNode, label, colorCode, text):
            diffLines = []
            sourceline = node.sourceline
            origSourceline = originalNode.sourceline
            for i, line in ((i+1,l) for (i,l) in enumerate(text.split('\n'))):  # <node>.sourceline is one-based.
                if sourceline - self._context <= i <= sourceline + self._context:
                    diffLines.append((i, line))
                    digitLen = len('%d' % i)
            heading = '=== %s (line %s%s) ===\n' % (label, sourceline, '' if origSourceline == sourceline else (', sourceline %s' % origSourceline))
            footer = '=' * len(heading.strip()) + '\n'

            def renderLine(i, line):
                startMark = ''
                endMark = ''
                afterNumber = '-'
                if i == sourceline:
                    startMark = '\033[%sm' % colorCode  # 31 -> red, 32 -> green
                    afterNumber = ':'
                    endMark = '\033[0m'
                return startMark + '%%%sd%%s %%s' % digitLen % (i, afterNumber, line) + endMark

            text = heading + '\n'.join(
                renderLine(i, l)
                for (i,l) in diffLines
            )
            return text, footer

        tree, node, text = reparseAndFindNode(root=self._expectedNode, node=expectedNode)
        expectedText, _ = formatTextForNode(node=node, originalNode=expectedNode, label='expected', colorCode='31', text=text)

        tree, node, text = reparseAndFindNode(root=self._resultNode, node=resultNode)
        resultText, footer = formatTextForNode(node=node, originalNode=resultNode, label='result', colorCode='32', text=text)

        return '\n%s\n%s\n%s' % (expectedText, resultText, footer)

    def _compareNode(self, expectedNode, resultNode):
        if expectedNode.tag != resultNode.tag:
            raise AssertionError("Tags do not match '%s' != '%s' at location: '%s'" % (expectedNode.tag, resultNode.tag, self.xpathToHere(expectedNode)))

        if hasattr(expectedNode, 'target') and expectedNode.target != resultNode.target:  # Is a processing-instruction
            raise AssertionError("Processing-Instruction targets do not match '%s' != '%s' at location: '%s'" % (expectedNode.target, resultNode.target, self.xpathToHere(expectedNode)))

        if stripWSonly(expectedNode.text) != stripWSonly(resultNode.text) \
                or (
                    len(expectedNode.getchildren()) == 0 and \
                    expectedNode.text != resultNode.text
                ):
            raise AssertionError("Text difference: %s != %s\nAt location: '%s'" % (
                '>no|text<' if expectedNode.text is None else "'" + expectedNode.text + "'",
                '>no|text<' if resultNode.text is None else "'" + resultNode.text + "'",
                self.xpathToHere(expectedNode, includeCurrent=True)
            ))

        if stripWSonly(expectedNode.tail) != stripWSonly(resultNode.tail):
            raise AssertionError("Tail difference (text after closing of tag): %s != %s\nAt location: '%s'" % (
                '>no|tail<' if expectedNode.tail is None else "'" + expectedNode.tail + "'",
                '>no|tail<' if resultNode.tail is None else "'" + resultNode.tail + "'",
                self.xpathToHere(expectedNode, includeCurrent=True)
            ))

        if self._matchPrefixes and expectedNode.prefix != resultNode.prefix:
            raise AssertionError("Prefix difference %s != %s for namespace: '%s'\nAt location: '%s'" % (
                expectedNode.prefix,
                resultNode.prefix,
                expectedNode.nsmap[expectedNode.prefix],
                self.xpathToHere(expectedNode, includeCurrent=True)
            ))

        expectedAttrs = expectedNode.attrib
        expectedAttrsSet = set(expectedAttrs.keys())
        resultAttrs = resultNode.attrib
        resultAttrsSet = set(resultAttrs.keys())

        diff = expectedAttrsSet.difference(resultAttrsSet)
        if diff:
            raise AssertionError("Missing attributes %s at location: '%s'" % (
                    ', '.join(
                        (("'%s'" % a) for a in diff)),
                        self.xpathToHere(expectedNode, includeCurrent=True)
                ))
        diff = resultAttrsSet.difference(expectedAttrsSet)
        if diff:
            raise AssertionError("Unexpected attributes %s at location: '%s'" % (
                    ', '.join(
                        (("'%s'" % a) for a in diff)),
                        self.xpathToHere(expectedNode, includeCurrent=True)
                ))

        for attrName, expectedAttrValue in expectedAttrs.items():
            resultAttrValue = resultAttrs[attrName]
            if expectedAttrValue != resultAttrValue:
                raise AssertionError("Attribute '%s' has a different value ('%s' != '%s') at location: '%s'" % (attrName, expectedAttrValue, resultAttrValue, self.xpathToHere(expectedNode, includeCurrent=True)))

        expectedChildren = expectedNode.getchildren()
        resultChildren = resultNode.getchildren()
        self._compareChildrenAndAddToQueue(
                parent=expectedNode,
                expectedChildren=expectedChildren,
                resultChildren=resultChildren)

    def _compareChildrenAndAddToQueue(self, parent, expectedChildren, resultChildren):
        if len(expectedChildren) != len(resultChildren):
            tagsLandR = [
                (elementAsRepresentation(x), elementAsRepresentation(r))
                for x, r in izip_longest(expectedChildren, resultChildren)
            ]
            tagsLandR = '\n'.join([
                '    %s -- %s' % (x, r)
                 for x, r in tagsLandR
            ])
            path = self.xpathToHere(parent, includeCurrent=True) if parent is not None else ''
            raise AssertionError("Number of children not equal (expected -- result):\n%s\n\nAt location: '%s'" % (tagsLandR, path))
        self._remainingContainer[:0] = zip(expectedChildren, resultChildren)

    def xpathToHere(self, node, includeCurrent=False):
        path = []
        startNode = node
        if node.getparent() is not None and node != self._expectedNode:
            while node != self._expectedNode:
                node = node.getparent()
                path.insert(0, self._currentPointInTreeElementXpath(node))
        if includeCurrent:
            path.append(self._currentPointInTreeElementXpath(startNode))
        return '/'.join(path)

    def _currentPointInTreeElementXpath(self, node):
        nodeTag = nodeTagStr = node.tag
        if node == self._expectedNode:
            return nodeTag

        if nodeTag is Comment:
            nodeTagStr = 'comment()'
            if node.getparent() is None:
                nodeIndex, othersWithsameTagCount = self._rootlessNodeIndex(node, nodeTag)
            else:
                nodeIndex, othersWithsameTagCount = self._nodeIndex(
                    node=node,
                    iterator=node.getparent().iterchildren(tag=Comment))
        elif nodeTag is Entity:
            nodeTagStr = '?'  # No way to mention Entities in XPath (they're normally resolved), so don't try.
            if node.getparent() is None:
                nodeIndex, othersWithsameTagCount = self._rootlessNodeIndex(node, nodeTag)
            else:
                nodeIndex, othersWithsameTagCount = self._nodeIndex(
                    node=node,
                    iterator=node.getparent().iterchildren(tag=Entity))
        elif nodeTag is PI:
            nodeTagStr = "processing-instruction('%s')" % node.target
            if node.getparent() is None:
                nodeIndex, othersWithsameTagCount = self._rootlessNodeIndex(node, nodeTag)
            else:
                nodeIndex, othersWithsameTagCount = self._nodeIndex(
                    node=node,
                    iterator=ifilter(
                        lambda n: n.target == node.target,
                        node.getparent().iterchildren(tag=PI)))
        else:
            if not isinstance(nodeTag, basestring):
                raise TypeError("Unexpected Node-Type '%s'" % nodeTag)

            nodeIndex, othersWithsameTagCount = self._nodeIndex(
                    node=node,
                    iterator=node.getparent().iterfind(nodeTag))

        return '%s[%s]' % (nodeTagStr, nodeIndex) if othersWithsameTagCount else nodeTagStr

    def _nodeIndex(self, node, iterator):
        othersWithsameTagCount = 0
        for i, n in enumerate(iterator):
            if n == node:
                nodeIndex = i + XPATH_IS_ONE_BASED
            else:
                othersWithsameTagCount += 1
        return nodeIndex, othersWithsameTagCount

    def _rootlessNodeIndex(self, node, nodeTag):
        condition = lambda n: n.tag == nodeTag
        if nodeTag is PI:
            condition = lambda n: n.tag == nodeTag and n.target == node.target
        rootlessNodes = [n
            for n in chain(previousNodes(self._expectedNode), nextNodes(self._expectedNode))
            if condition(n)]

        othersWithsameTagCount = max(0, len(rootlessNodes) - 1)

        return rootlessNodes.index(node) + XPATH_IS_ONE_BASED, othersWithsameTagCount


def isRootNode(node):
    return True if node.getroottree().getroot() == node else False

def previousNodes(node):
    previousNodes = []
    n = node.getprevious()
    while n is not None:
        previousNodes.insert(0, n)
        n = n.getprevious()
    return previousNodes

def nextNodes(node):
    nextNodes = []
    n = node.getnext()
    while n is not None:
        nextNodes.append(n)
        n = n.getnext()
    return nextNodes

def refindLxmlNodeCallback(root, node):
    root = getattr(root, 'getroot', lambda: root)()
    operations = []
    if isRootNode(root):
        if node in previousNodes(root) + nextNodes(root):
            # getpath works OK for rootless-nodes since they are namespaceless
            path = root.getroottree().getpath(node)
            operations.insert(0, lambda n: n.getroottree().xpath(path)[0])

    n = node
    while n is not None or n == root:
        parent = n.getparent()
        if parent is not None:
            index = parent.index(n)
            operations.append(
                    partial(
                        lambda n, index: n.getchildren()[index],
                        index=index)
                )
        n = parent

    def refind(newRoot):
        node = getattr(newRoot, 'getroot', lambda: newRoot)()
        try:
            while True:
                op = operations.pop()
                node = op(node)
        except IndexError:
            return node
    return refind


def stripWSonly(aString):
    stripped = aString.strip() if aString else aString
    return aString if stripped else None

def elementAsRepresentation(el):
    tagName = getattr(el, 'tag', None)
    if tagName is Comment:
        tagName = 'comment|node'
    elif tagName is PI:
        tagName = "processing-instruction('%s')|node" % el.target
    elif tagName is Entity:
        tagName = 'entity|node'
    elif tagName is None:
        tagName = 'no|tag'
    else:
        tagName = "'%s'" % tagName
    return tagName


XPATH_IS_ONE_BASED = 1


try:
    from itertools import izip_longest
except ImportError:
    # Added for Python 2.5 compatibility
    from itertools import repeat, chain
    _SENTINEL = object()
    def next(iterable, default=_SENTINEL):
        try:
            retval = iterable.next()
        except StopIteration:
            if default is _SENTINEL:
                raise
            retval = default
        return retval

    # izip_longest code below from:
    #    http://docs.python.org/2/library/itertools.html#itertools.izip_longest
    #    For it's license see: http://docs.python.org/2/license.html#history-and-license
    class ZipExhausted(Exception):
        pass

    def izip_longest(*args, **kwds):
        # izip_longest('ABCD', 'xy', fillvalue='-') --> Ax By C- D-
        fillvalue = kwds.get('fillvalue')
        counter = [len(args) - 1]
        def sentinel():
            if not counter[0]:
                raise ZipExhausted
            counter[0] -= 1
            yield fillvalue
        fillers = repeat(fillvalue)
        iterators = [chain(it, sentinel(), fillers) for it in args]
        try:
            while iterators:
                yield tuple(map(next, iterators))
        except ZipExhausted:
            pass


_MAX_LENGTH = 80
def safe_repr(obj, short=False):
    try:
        result = repr(obj)
    except Exception:
        result = object.__repr__(obj)
    if not short or len(result) < _MAX_LENGTH:
        return result
    return result[:_MAX_LENGTH] + ' [truncated]...'

