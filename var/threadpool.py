from Queue import Queue
from threading import Thread
from select import select
from socket import socketpair, SHUT_RDWR
from sendfile import sendfile
from sys import stdout

commands = Queue()

NUMBER_OF_WORKERS = 10
NUMBER_OF_FILES_TO_READ = 100
NUMBER_OF_TESTS_TO_RUN = 100

def send_file_worker():
	while True:
		cmd = commands.get()
		if cmd == 'stop': break
		list(cmd)

pool = [Thread(None, send_file_worker) for i in range(NUMBER_OF_WORKERS)]
map(Thread.start, pool)

def send_file(tofd, name):
	f = open(name)
	try:
		sendfile(tofd.fileno(), f.fileno(), 0, 999999)
	finally:
		f.close()
	tofd.shutdown(SHUT_RDWR)
	tofd.close()
	yield None

def main():
	soks_r = range(NUMBER_OF_FILES_TO_READ)
	for i in soks_r:
		sok_r, sok_w = socketpair()
		soks_r[i] = sok_r
		commands.put(send_file(sok_w, 'wlthread.py'))

	results = {}

	while soks_r:
		readables, w, e = select(soks_r,[],[])
		for r in readables:
			data = r.recv(4096)
			if not data:
				soks_r.remove(r)
				r.shutdown(SHUT_RDWR)
				r.close()
			old_data = results.get(r, '')
			results[r] = old_data + data

	assert(len(results) == NUMBER_OF_FILES_TO_READ)
	def _assert(expr):
		assert(expr)
	map(lambda x: _assert(len(x) == 2033), results.values())

try:
	for i in range(NUMBER_OF_TESTS_TO_RUN):
		main()
finally:
	for t in pool: commands.put('stop')
	map(Thread.join, pool)