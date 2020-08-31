## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2015, 2018-2020 Seecr (Seek You Too B.V.) http://seecr.nl
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

from .httpspec import parseHeaders, parseHeader, parseHeaderFieldvalue, HTTP, REGEXP, FORMAT

from ._httpreader import HttpReader
from ._httpserver import HttpServer, SUPPORTED_COMPRESSION_CONTENT_ENCODINGS, parseContentEncoding
from ._acceptor import Acceptor
from ._socketpool import SocketPool, EmptySocketPool
from ._httprequest import httprequest, httpget, httppost, httpsget, httpspost, httpput, httpdelete, httpsput, httpsdelete, HttpRequest
from ._httprequest1_1 import HttpRequest1_1, HttpRequestAdapter
