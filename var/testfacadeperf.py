#!/usr/bin/python2.5
from hotshot import Profile
from wlservice import WlService
from os import system

NUMBER_OF_FILES_TO_READ = 100
NUMBER_OF_TESTS_TO_RUN = 100

service = WlService()

def loop():
	results = [[]] * NUMBER_OF_FILES_TO_READ
	def buffer(buf):
		data = yield None
		buf.append(data)
	for i in range(NUMBER_OF_FILES_TO_READ):
		wlf = service.open('file:idea.py')
		status = wlf.sink(buffer(results[i]))

	status.wait()

	def _assert(expr):
		assert(expr)
	map(lambda x: _assert(len(x[0]) == 1062), results)

def main():
	for i in range(NUMBER_OF_TESTS_TO_RUN):
		loop()

#prof = Profile("main.prof")
#try:
#	prof.runcall(main)
#finally:
#	prof.close()
main()
#system('python hotshot2kcachegrind.py -o main.out main.prof; kcachegrind main.out')
#os.system('python hotshot2kcachegrind.py -o thread.out thread.prof; kcachegrind thread.out')
