## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2018 Seecr (Seek You Too B.V.) http://seecr.nl
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

from weightless.core import be
from weightless.http import HttpRequest1_1, EmptySocketPool
from weightless.io.utils import asProcess
from functools import partial


def makeRequest(host, port, request, body=None, timeout=30, **kwargs):
    httprequest1_1 = be((HttpRequest1_1(),
            (EmptySocketPool(),),
        )).httprequest1_1
    return asProcess(httprequest1_1(host=host, port=port, request=request, body=body, timeout=timeout, **kwargs))

getRequest=makeRequest
postRequest=partial(makeRequest, method='POST')
