# -*- encoding: utf-8 -*-
## begin license ##
#
# "Seecr Test" provides test tools.
#
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

from re import DOTALL, compile, sub
from StringIO import StringIO
from lxml.etree import parse as parse_xml, XMLSyntaxError
from socket import socket
from urllib import urlencode
import sys
from sys import getdefaultencoding
from time import sleep

_scriptTagRegex = compile("<script[\s>].*?</script>", DOTALL)
_entities = {
    '&nbsp;': ' ',
    '&ndash;': "&#8211;",
    '&mdash;': "&#8212;",
    '&lsquo;': "‘",
    '&rsquo;': "’",
    '&larr;': "&lt;-",
}

def parseHtmlAsXml(body):
    def forceXml(body):
        newBody = body
        for entity, replacement in _entities.items():
            newBody = newBody.replace(entity, replacement)
        newBody = _scriptTagRegex.sub('', newBody)
        return newBody
    try:
        return parse_xml(StringIO(forceXml(body)))
    except XMLSyntaxError:
        print body
        raise

def getPage(port, path, arguments=None, expectedStatus="200", sessionId=None):
    additionalHeaders = {}
    if sessionId:
        additionalHeaders['Cookie'] = 'session=' + sessionId
    header, body = getRequest(
        port,
        path,
        arguments,
        parse=False,
        additionalHeaders=additionalHeaders)
    assertHttpOK(header, body, expectedStatus=expectedStatus)
    return header, body

def postToPage(port, path, data, expectedStatus="302", sessionId=None):
    additionalHeaders = {}
    if sessionId:
        additionalHeaders['Cookie'] = 'session=' + sessionId
    postBody = urlencode(data, doseq=True)
    header, body = postRequest(
        port,
        path,
        data=postBody,
        contentType='application/x-www-form-urlencoded',
        parse=False,
        additionalHeaders=additionalHeaders)
    assertHttpOK(header, body, expectedStatus=expectedStatus)
    return header, body

def assertHttpOK(header, body, expectedStatus="200"):
    try:
        assertSubstring("HTTP/1.0 %s" % expectedStatus, header)
        assertNotSubstring("Traceback", header + "\r\n\r\n" + body)
    except AssertionError, e:
        print header, body
        raise

def assertSubstring(value, s):
    if not value in s:
        raise AssertionError("assertSubstring fails: '%s' must occur in '%s'" % (value, s))

def assertNotSubstring(value, s):
    if value in s:
        raise AssertionError("assertNotSubstring fails: '%s' must not occur in '%s'" % (value, s))


def _socket(port, timeOutInSeconds):
    sok = socket()
    sok.connect(('localhost', port))
    sok.settimeout(5.0 if timeOutInSeconds is None else timeOutInSeconds)
    return sok

def createReturnValue(header, body, parse):
    if parse and body.strip() != '':
        body = parse_xml(StringIO(body))
    return header, body


def postRequest(port, path, data, contentType='text/xml; charset="utf-8"', parse=True, timeOutInSeconds=None, additionalHeaders=None):
    additionalHeaders = additionalHeaders or {}
    if type(data) is unicode:
        data = data.encode(getdefaultencoding())
    sok = _socket(port, timeOutInSeconds)
    try:
        contentLength = len(data)
        lines = [
            'POST %(path)s HTTP/1.0',
            'Content-Type: %(contentType)s',
            'Content-Length: %(contentLength)s'
        ]
        lines += ["%s: %s" % (k, v) for k, v in additionalHeaders.items()]
        lines += ['', '']
        sendBuffer = ('\r\n'.join(lines) % locals()) + data
        totalBytesSent = 0
        bytesSent = 0
        while totalBytesSent != len(sendBuffer):
            bytesSent = sok.send(sendBuffer[totalBytesSent:])
            totalBytesSent += bytesSent
        header, body = splitHttpHeaderBody(receiveFromSocket(sok))
        return createReturnValue(header, body, parse)
    finally:
        sok.close()

def postMultipartForm(port, path, formValues, parse=True, timeOutInSeconds=None):
    boundary = '-=-=-=-=-=-=-=-=TestBoundary1234567890'
    body = createPostMultipartForm(boundary, formValues)
    return postRequest(
        port,
        path,
        body,
        contentType='multipart/form-data; boundary=' + boundary,
        parse=parse,
        timeOutInSeconds=timeOutInSeconds)

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
        for item in headers.items():
            strm.write('%s: %s\r\n' % item)
        strm.write('\r\n')
        strm.write(valueDict['value'])
        strm.write('\r\n')
    strm.write('--' + boundary + '--\r\n')
    return strm.getvalue()

def getRequest(port, path, arguments=None, parse=True, timeOutInSeconds=None, host=None, additionalHeaders=None):
    sok = _socket(port, timeOutInSeconds)
    try:
        requestString = path
        if arguments:
            requestString = path + '?' + urlencode(arguments, doseq=True)

        request = 'GET %(requestString)s HTTP/1.0\r\n' % locals()
        if host != None:
            request = 'GET %(requestString)s HTTP/1.1\r\nHost: %(host)s\r\n' % locals()
        if additionalHeaders != None:
            for header in additionalHeaders.items():
                request += '%s: %s\r\n' % header
        request += '\r\n'
        sok.send(request)
        header, body = splitHttpHeaderBody(receiveFromSocket(sok))
        return createReturnValue(header, body, parse)
    finally:
        sok.close()

def receiveFromSocket(sok):
    response = ''
    part = sok.recv(1024)
    response += part
    while part != None:
        part = sok.recv(1024)
        if not part:
            break
        response += part
    return response

def splitHttpHeaderBody(response):
    try:
        header, body = response.split('\r\n\r\n', 1)
    except ValueError, e:
        raise ValueError("%s can not be split into a header and body" % repr(response))
    else:
        return header, body

def headerToDict(header):
   return dict(
       tuple(s.strip() for s in line.split(':'))
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

