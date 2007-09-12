#!/usr/bin/python2.5
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
from os import system
from sys import stdout, setcheckinterval, maxint
from time import sleep

setcheckinterval(maxint) # i.e. cooperative scheduling

NUMBER_OF_FILES_TO_READ = 100
NUMBER_OF_TESTS_TO_RUN = 100
results = [[]] * (NUMBER_OF_FILES_TO_READ * NUMBER_OF_TESTS_TO_RUN)
service = WlService()

def buffer(buf):
	data = yield None
	buf.append(data)

def loop(j):
	for i in range(NUMBER_OF_FILES_TO_READ):
		service.open('file:idea.py', buffer(results[i+j]))
	sleep(0.01)

def do_test():
	print 'Reading files'
	for i in range(NUMBER_OF_TESTS_TO_RUN):
		loop(i*NUMBER_OF_FILES_TO_READ)
	print 'Waiting for completion'
	while not results[-1]: sleep(0.001)

def do_assert():
	print 'Checking results'
	for r in results: assert(len(r[0]) == 1062)

from cq2utils.profile import profile
profile(do_test, runKCacheGrind=True)
#do_test()
#do_assert()
