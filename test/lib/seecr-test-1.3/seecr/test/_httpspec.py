## begin license ##
#
# "Seecr Test" provides test tools.
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012 Seecr (Seek You Too B.V.) http://seecr.nl
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

#
# Attention dear reader:
#
# This file is copied from Weightless v0.7.8 (http://weightless.io)
# instead of imported to reduce non-standard dependencies of seecr-test.
#

from re import compile
VERSION=b'0.7.8'  # hacky :-)

"""
    HTTP specifications.
    http://www.w3.org/Protocols/rfc2616/rfc2616.html
"""

def parseHeaders(headerBytes):
    headers = {}
    for (groupname, fieldname, fieldvalue) in REGEXP.HEADER.findall(headerBytes):
        # fieldvalue can be a "superset of US-ASCII" - so coerce to unicode (since mostly OK, and more backwards compatible & conveniant - and leave it as bytes otherwise).
        headers[fieldname.decode('ascii').title()] = _maybeDecodeIfAscii(fieldvalue).strip()
    return headers

def parseHeader(headerBytesOrStr):
    # fieldvalue can be a "superset of US-ASCII" - since guessing is dangerous, assume only "safe"-ascii if not already represented as bytes.
    headerBytes = headerBytesOrStr.encode('ascii') if type(headerBytesOrStr) == str else headerBytesOrStr
    parts = headerBytes.split(b';')
    cType = parts[0]
    pDict = {}
    if len(parts) != 1:
        pDict = dict(map(_maybeDecodeIfAscii, part.strip().split(b'=', 1)) for part in (part for part in parts[1:]))

    return cType, pDict

def _maybeDecodeIfAscii(inBytes):
    return inBytes.decode('ascii') if inBytes.isascii() else inBytes


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
    token =  rb"([!#$%&'*+\-.0-9A-Z^_`a-z|~]+){1}"
    field_name = token
    field_value = b'.*'
    named_field_name = b'(?P<fieldname>' + field_name + b')'
    named_field_value = b'(?P<fieldvalue>' + field_value + b")"

    message_header = field_name + b":" + field_value + CRLF
    named_message_header = named_field_name + b':' + named_field_value + CRLF

    Headers = b"(?P<_headers>(" + message_header + b')*)'

    Method = rb'(?P<Method>' + token + b')'
    Request_URI = rb'(?P<RequestURI>.+)'
    HTTP_Version = rb'HTTP/(?P<HTTPVersion>\d\.\d)'
    ignoredCRLFs = b'(' + CRLF + b')*'
    Request_Line = ignoredCRLFs + Method + SP + Request_URI + SP + HTTP_Version + CRLF

    Chunk_Size = b'(?P<ChunkSize>[0-9a-fA-F]+)'
    Chunk_Size_Line = Chunk_Size + CRLF  # FIXME: TS: incomplete, missing chunk-extensions (at least match & ignore).

    Status_Code = rb'(?P<StatusCode>[0-9]{3})'
    Reason_Phrase = rb'(?P<ReasonPhrase>[^\r\n].+)'
    Status_Line = HTTP_Version + SP + Status_Code + SP + Reason_Phrase + CRLF

    Request = Request_Line + Headers + CRLF
    Response = Status_Line + Headers + CRLF


class REGEXP:
    RESPONSE = compile(HTTP.Response)
    REQUEST = compile(HTTP.Request)
    REQUESTLINE = compile(HTTP.Request_Line)
    HEADER = compile(HTTP.named_message_header)
    CHUNK_SIZE_LINE = compile(HTTP.Chunk_Size_Line)
    CRLF = compile(HTTP.CRLF)

class FORMAT:
    RequestLine = b'%(Method)s %(Request_URI)s HTTP/%(HTTPVersion)s' + HTTP.CRLF
    HostHeader = b'Host: %(Host)s' + HTTP.CRLF
    Header = b'%s: %s' + HTTP.CRLF
    UserAgentHeader = b'User-Agent: Weightless/v' + VERSION + HTTP.CRLF
    StatusLine = b'HTTP/%(version)s %(status)s %(reason)s' + HTTP.CRLF
