## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2009 Seek You Too (CQ2) http://www.cq2.nl
#
#    This file is part of Weightless
#
#    Weightless is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    Weightless is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Weightless; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

VERSION='0.4.x' # in makeDeb.sh this is replaced by a real version number.

from platform import python_version
import sys
from os import system
from os.path import dirname, abspath, isdir, join

from python2_5._compose_py import compose

from _acceptor import Acceptor
from _reactor import Reactor, reactor
from _httpreader import HttpReader, Connector
from _httpserver import HttpServer, HttpsServer
from _local import local
from _suspend import Suspend

from _gutils import tostring, identify, autostart
from _local import local

from _httpget import httpget
