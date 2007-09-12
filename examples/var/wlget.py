#!/usr/bin/env python2.5
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
from weightless.wlservice import WlService
from weightless.wlhttp import recvResponse, sendRequest, recvBody
from time import sleep
from threading import Event
from sys import argv
from urllib import quote

if len(argv) < 2:
	print 'Usage:', argv[0], '<url> [--verbose]'
	print 'This tool downloads a url without interpreting status codes.'
	exit(1)

verbose = len(argv) > 2 and argv[2] == '--verbose'
url = argv[1]
flag = Event()
service = WlService()

def collect(buff):
	while True:
		data = yield None
		print ' * received', len(data), 'bytes'
		if verbose:	print data
		buff.append(data)

def get(url):
	try:
		if verbose: print ' * Sending GET', url
		yield sendRequest('GET', url)
		response = yield recvResponse()
		print ' * Status and headers'
		print response.__dict__
		buff = []
		yield recvBody(response, collect(buff))
		print ' * Received total of', sum(len(fragment) for fragment in buff), 'bytes.'
	finally:
		flag.set()

from urlparse import urlsplit
addressing_scheme, network_location, path, query, fragment_identifier = urlsplit(url)
s = service.open(addressing_scheme + '://' + network_location, get(url))

flag.wait()

