#!/usr/bin/python2.5
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