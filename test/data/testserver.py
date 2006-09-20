import platform
assert platform.python_version() >= "2.5", "Python 2.5 required"

import wlthread
import wlselect
import wlsocket
import socket
import sys
import sendfile
import os

s = wlselect.WlSelect()

def accept(sokket):
	fd_a = sokket.fileno()
	while True:
		yield wlselect.READ, fd_a
		sok, host = sokket.accept()
		#fd.setsockopt(socket.SOL_TCP, socket.TCP_CORK, 1)
		s.runWlThread(wlthread.create(handle(wlsocket.WlSocket(sok))))

def handle(wlsokket):
	fd = wlsokket._fd
	yield wlsokket.read('(.*)\r?\n\r?\n')
	r = wlsokket.next()
	wlsokket.send("HTTP/1.1 200 Ok\nContent-Type: text/plain\nTransfer-Encoding: identity\n\n")

	for i in range(1,10):
		fdin = os.open('testdata', os.O_RDONLY | os.O_NONBLOCK)
		try:
			sendfile.sendfile(fd, fdin , 0, 99999999)
		finally:
			os.close(fdin)

	wlsokket.send('\n\n')
	wlsokket.shutdown(socket.SHUT_RDWR)
	wlsokket.close()


sokket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#sokket.setsockopt(socket.SOL_SO, socket.SO_NOLINGER, 1)
sokket.bind(('', int(sys.argv[1])))
sokket.listen(5)

s.runWlThread(wlthread.create(accept(sokket)))

def main():
	while True:
		s.schedule()

def prof():
	import hotshot, hotshot.stats, test.pystone
	prof = hotshot.Profile("stones.prof")
	try:
		prof.runcall(main)
	except:
		pass
	prof.close()
	stats = hotshot.stats.load("stones.prof")
	stats.strip_dirs()
	stats.sort_stats('time', 'calls')
	stats.print_stats(20)
	stats.sort_stats('cumulative', 'calls')
	stats.print_stats(20)
	stats.sort_stats('calls', 'calls')
	stats.print_stats(20)

try:
	main()
except Exception, e:
	print s._concurrencyFactor
	raise e
#prof()

