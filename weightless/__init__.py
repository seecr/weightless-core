## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2007 Seek You Too B.V. (CQ2) http://www.cq2.nl
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

VERSION='0.1.x'

from platform import python_version
import sys
from os import system
from os.path import dirname, abspath

if python_version() >= "2.5":
    # development support; the simplest thing that could possibly work
    dirName = abspath(dirname(__file__))
    if "trunk/" in dirName:
        x = ":".join(abspath(path) for path in sys.path)
        system("cd %s/..; PYTHONPATH=%s python2.5 setup.py build_ext --inplace" % (dirName,x))
    from python2_5._compose_pyx import compose, RETURN
    import python2_5._gio as gio
    from python2_5.http import sendRequest, recvRegExp, recvBytes, recvBody, sendBody, copyBody, HttpException

from _acceptor import Acceptor
from _reactor import Reactor
from _httpreader import HttpReader
from _httpserver import HttpServer
