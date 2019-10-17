# -*- encoding: utf-8 -*-
## begin license ##
#
# "Seecr Test" provides test tools.
#
# Copyright (C) 2012-2015 Seecr (Seek You Too B.V.) http://seecr.nl
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

import sys
from ast import parse, ClassDef
from functools import partial
from imp import load_module, get_suffixes
from os import makedirs, walk, popen
from os.path import abspath, dirname, isdir, join, splitext, basename
from re import DOTALL, compile, sub
from socket import socket, AF_INET, SOCK_STREAM, IPPROTO_TCP
from io import StringIO
from sys import getdefaultencoding
from time import sleep
from urllib.parse import urlencode

from lxml.etree import parse as parse_xml, XMLSyntaxError, HTMLParser
from lxml.etree import HTMLParser, HTML

_scriptTagRegex = compile("<script[\s>].*?</script>", DOTALL)
_entities = {
    '&nbsp;': ' ',
    '&ndash;': "&#8211;",
    '&mdash;': "&#8212;",
    '&lsquo;': "‘",
    '&rsquo;': "’",
    '&larr;': "&lt;-",
    '&rarr;': "-&gt;",
}

def parseHtmlAsXml(body):
    def forceXml(body):
        newBody = body
        for entity, replacement in list(_entities.items()):
            newBody = newBody.replace(entity, replacement)
        newBody = _scriptTagRegex.sub('', newBody)
        return newBody
    try:
        return parse_xml(StringIO(forceXml(body)))
    except XMLSyntaxError:
        print(body)
        raise

def getPage(port, path, arguments=None, expectedStatus="200", sessionId=None, headers=None):
    headers = headers or {}
    if sessionId:
        headers['Cookie'] = 'session=' + sessionId
    header, body = getRequest(
        port=port,
        path=path,
        arguments=arguments,
        parse=False,
        additionalHeaders=headers)
    assertHttpOK(header, body, expectedStatus=expectedStatus)
    return header, body

def postToPage(port, path, data, expectedStatus="302", sessionId=None, headers=None):
    headers = headers or {}
    if sessionId:
        headers['Cookie'] = 'session=' + sessionId
    postBody = urlencode(data, doseq=True)
    header, body = postRequest(
        port=port,
        path=path,
        data=postBody,
        contentType='application/x-www-form-urlencoded',
        parse=False,
        additionalHeaders=headers)
    assertHttpOK(header, body, expectedStatus=expectedStatus)
    return header, body

def assertHttpOK(header, body, expectedStatus="200"):
    try:
        assertSubstring("HTTP/1.0 %s" % expectedStatus, header)
        assertNotSubstring("Traceback", header + "\r\n\r\n" + body)
    except AssertionError as e:
        print(header, body)
        raise

def assertSubstring(value, s):
    if not value in s:
        raise AssertionError("assertSubstring fails: '%s' must occur in '%s'" % (value, s))

def assertNotSubstring(value, s):
    if value in s:
        raise AssertionError("assertNotSubstring fails: '%s' must not occur in '%s'" % (value, s))


def _socket(port, timeOutInSeconds):
    sok = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)
    sok.connect(('localhost', port))
    sok.settimeout(5.0 if timeOutInSeconds is None else timeOutInSeconds)
    return sok

def createReturnValue(header, body, parse):
    if parse and body.strip() != '':
        try:
            body = parse_xml(StringIO(body))
        except:
            try:
                body = HTML(body, HTMLParser(recover=True))
            except:
                print("Exception parsing:")
                print(body)
                raise
    return header, body


def httpRequest(port, path, data=None, arguments=None, contentType=None, parse=True, timeOutInSeconds=None, host=None, method='GET', additionalHeaders=None):
    additionalHeaders = additionalHeaders or {}
    if type(data) is str:
        data = data.encode(getdefaultencoding())
    sok = _socket(port, timeOutInSeconds)
    try:
        contentLength = len(data) if data else 0
        requestString = path
        if arguments:
            requestString = path + '?' + urlencode(arguments, doseq=True)
        httpVersion = '1.0'
        lines = [
            '%(method)s %(requestString)s HTTP/%(httpVersion)s',
            'Content-Length: %(contentLength)s'
        ]
        if host:
            httpVersion = '1.1'
            lines.append('Host: %(host)s')
        if contentType:
            lines.append('Content-Type: %(contentType)s')
        lines += ["%s: %s" % (k, v) for k, v in list(additionalHeaders.items())]
        lines += ['', '']
        sendBuffer = ('\r\n'.join(lines) % locals()).encode() + (data or b'')
        totalBytesSent = 0
        bytesSent = 0
        while totalBytesSent != len(sendBuffer):
            bytesSent = sok.send(sendBuffer[totalBytesSent:])
            totalBytesSent += bytesSent
        response = receiveFromSocket(sok)
        header, body = splitHttpHeaderBody(response)
        return createReturnValue(header, body, parse)
    finally:
        sok.close()

postRequest = partial(httpRequest, method='POST', contentType='text/xml; charset="utf-8"')
putRequest = partial(httpRequest, method='PUT')
deleteRequest = partial(httpRequest, method='DELETE')

def getRequest(port, path, arguments=None, **kwargs):
    return httpRequest(port=port, path=path, arguments=arguments, method='GET', **kwargs)

def postMultipartForm(port, path, formValues, parse=True, timeOutInSeconds=None, **kwargs):
    boundary = '-=-=-=-=-=-=-=-=TestBoundary1234567890'
    body = createPostMultipartForm(boundary, formValues)
    return postRequest(
        port,
        path,
        body,
        contentType='multipart/form-data; boundary=' + boundary,
        parse=parse,
        timeOutInSeconds=timeOutInSeconds,
        **kwargs)

def createPostMultipartForm(boundary, formValues):
    strm = StringIO()
    for valueDict in formValues:
        fieldType = valueDict['type']
        headers = {}
        headers['Content-Disposition'] = 'form-data; name="%(name)s"' % valueDict
        if fieldType == 'file':
            headers['Content-Disposition'] = headers['Content-Disposition'] + '; filename="%(filename)s"' % valueDict
            headers['Content-Type'] = valueDict['mimetype']

        strm.write('--' + boundary + '\r\n')
        for item in list(headers.items()):
            strm.write('%s: %s\r\n' % item)
        strm.write('\r\n')
        strm.write(valueDict['value'])
        strm.write('\r\n')
    strm.write('--' + boundary + '--\r\n')
    return strm.getvalue()

def receiveFromSocket(sok):
    response = part = sok.recv(1024)
    while part != None:
        part = sok.recv(1024)
        if not part:
            break
        response += part
    return response

def splitHttpHeaderBody(response):
    try:
        header, body = response.split(b'\r\n\r\n', 1)
    except ValueError as e:
        raise ValueError("%s can not be split into a header and body" % repr(response))
    else:
        return header, body

def headerToDict(header):
   return dict(
       tuple(s.strip() for s in line.split(':', 1))
       for line in header.split('\r\n')
       if ':' in line
   )

def sleepWheel(seconds, callback=None, interval=0.2):
    parts = ['\\', '|', '/', '-']
    for i in range(int(seconds/interval)):
        sys.stdout.write(parts[i%len(parts)])
        sys.stdout.flush()
        sleep(interval)
        sys.stdout.write("\b")
        sys.stdout.flush()
        if not callback is None:
            if callback():
                return True
    return False

def ignoreLineNumbers(s):
    return sub("line \d+,", "line [#],", s)

def openConsole():
    from code import InteractiveConsole
    from inspect import currentframe

    frame = currentframe().f_back

    d={'_frame':frame}         # Allow access to frame object.
    d.update(frame.f_globals)  # Unless shadowed by global
    d.update(frame.f_locals)

    message = "Break in %s:%s" % (frame.f_code.co_filename, frame.f_lineno)

    i = InteractiveConsole(d)
    i.interact(message)

def findTag(tag, body, **attrs):
    xpathExpr = "//%s" % tag
    if attrs:
        xpathExpr += "[%s]" % ' and '.join('@%s="%s"' % item for item in attrs.items())

    return htmlXPath(xpathExpr, body)

def htmlXPath(xpathExpr, body):
    try:
        xmlNode = parse_xml(StringIO(body), parser=HTMLParser()).getroot()
    except XMLSyntaxError:
        print(body)
        raise

    for result in xmlNode.xpath(xpathExpr):
        yield result

def includeParentAndDeps(filename, systemPath=None, cleanup=True, additionalPaths=None):
    raise NotImplementedError("includeParentAndDeps moved to seecr.deps package. Change import to: 'from seecr.deps import includeParentAndDeps'")

def mkdir(*args):
    path = join(*args)
    if not isdir(path):
        makedirs(path)
    return path

def loadTestsFromPath(testRoot, _globals=None):
    if not isdir(testRoot):
        testRoot = dirname(abspath(testRoot))
    _globals = globals() if _globals is None else _globals
    pySuffix = [(suffix, mode, suffixType) for (suffix, mode, suffixType) in get_suffixes() if suffix == ".py"][0]
    for path, dirs, files in walk(testRoot):
        for filename in [join(path, filename) for filename in files if splitext(filename)[-1] == '.py']:
            tree = parse(open(filename).read())

            for each in tree.body:
                if type(each) is ClassDef and each.bases[0].id in ['TestCase', 'SeecrTestCase']:
                    fullFilename = join(path, filename)
                    with open(fullFilename) as fp:
                        mod = load_module(each.name, fp, fullFilename, pySuffix)
                        key = each.name
                        if key in _globals:
                            key = "{}.{}".format(basename(path), key)
                        _globals[key] = getattr(mod, each.name)


def vpnIp():
    for line in popen('ip addr show eth0').readlines():
        if 'inet 10.9.' in line:
            return line.strip().split(' ')[1].split('/')[0]
