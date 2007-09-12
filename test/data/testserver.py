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

