## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012, 2015, 2018-2021 Seecr (Seek You Too B.V.) https://seecr.nl
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

import re
from weightless.core import VERSION

"""
    HTTP specifications.
    http://www.w3.org/Protocols/rfc2616/rfc2616.html
"""

def parseHeadersString(headerString):
    return {k.decode():v.decode() for k,v in parseHeaders(headerString.encode()).items()}

def parseHeaders(headerBytes):
    return {fieldname.title():fieldvalue.strip() for (groupname, fieldname, fieldvalue) in REGEXP.HEADER.findall(headerBytes)}

def unquote(b):
    if b and len(b) > 1 and b[0] == b[-1] == ord('"'):
        return b[1:-1]
    return b

def parseHeaderFieldvalue(fieldvalue):
    parts = fieldvalue.split(b';', 1)
    cType = parts[0]
    pDict = {}
    if len(parts) != 1:
        for each in (match.groupdict() for match in REGEXP.FIELDVALUE.finditer(parts[1])):
            pDict[each['fieldname']] = unquote(each['fieldvalue'])

    return cType, pDict
parseHeader = parseHeaderFieldvalue

class HTTP:
    #class Response:
        #StatusLine = 'HTTP/%(version)s %(status)s %(reason)s' + CRLF
    #class Message:
        #MessageHeader = '%(name)s: %(value)s' + CRLF
        #def _Headers(klas, headers = {}):
            #for name, value in headers.items():
                #yield HTTP.Message.MessageHeader % locals()
            #yield CRLF
        #Headers = classmethod(_Headers)

    SP = b' '
    CRLF = b'\r\n'
    # http://www.w3.org/Protocols/rfc2616/rfc2616-sec2.html#sec2.2
    token =  b"([!#$%&'*+\\-.0-9A-Z^_`a-z|~]+){1}"
    quoted_string = r'".*?(?:(?<!\\)")'.encode()
    field_name = token
    field_value = b'.*'
    named_field_name = b'(?P<fieldname>' + field_name + b')'
    named_field_value = b'(?P<fieldvalue>' + field_value + b")"

    message_header = field_name + b":" + field_value + CRLF
    named_message_header = named_field_name + b':' + named_field_value + CRLF

    Headers = b"(?P<_headers>(" + message_header + b')*)'

    Method = b'(?P<Method>' + token + b')'
    Request_URI = b'(?P<RequestURI>.+)'
    HTTP_Version = b'HTTP/(?P<HTTPVersion>\\d\\.\\d)'
    ignoredCRLFs = b'(' + CRLF + b')*'
    Request_Line = ignoredCRLFs + Method + SP + Request_URI + SP + HTTP_Version + CRLF

    Chunk_Size = b'(?P<ChunkSize>[0-9a-fA-F]+)'
    Chunk_Size_Line = Chunk_Size + CRLF  # FIXME: TS: incomplete, missing chunk-extensions (at least match & ignore).

    Status_Code = b'(?P<StatusCode>[0-9]{3})'
    Reason_Phrase = b'(?P<ReasonPhrase>[^\r\n].+)'
    Status_Line = HTTP_Version + SP + Status_Code + SP + Reason_Phrase + CRLF

    Request = Request_Line + Headers + CRLF
    Response = Status_Line + Headers + CRLF


class REGEXP:
    RESPONSE = re.compile(HTTP.Response)
    REQUEST = re.compile(HTTP.Request)
    REQUESTLINE = re.compile(HTTP.Request_Line)
    HEADER = re.compile(HTTP.named_message_header)
    CHUNK_SIZE_LINE = re.compile(HTTP.Chunk_Size_Line)
    CRLF = re.compile(HTTP.CRLF)
    FIELDVALUE = re.compile(HTTP.named_field_name + b"=" + b"(?P<fieldvalue>(" + HTTP.token + b"|" + HTTP.quoted_string + b"))", re.DOTALL)
    STATUS_LINE = re.compile(HTTP.Status_Line)

class FORMAT:
    RequestLine = b'%(Method)s %(Request_URI)s HTTP/%(HTTPVersion)s' + HTTP.CRLF
    HostHeader = b'Host: %(Host)s' + HTTP.CRLF
    Header = b'%s: %s' + HTTP.CRLF
    UserAgentHeader = b'User-Agent: Weightless/v' + VERSION.encode() + HTTP.CRLF
    StatusLine = b'HTTP/%(version)s %(status)s %(reason)s' + HTTP.CRLF

