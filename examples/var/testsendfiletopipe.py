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
import sendfile
import os
import socket
import threading
import select
import time
import sys
import hotshot, hotshot.stats, test.pystone
from Queue import Queue


sok, sok2 = socket.socketpair()
rfd = sok.fileno()
wfd = sok2.fileno()

#command_pipe_r, command_pipe_w = os.pipe()
command_queue = Queue(1)

def prof_sendloop():
	prof = hotshot.Profile("thread.prof")
	try:
		prof.runcall(sendloop)
	finally:
		prof.close()

def parse_command(command):
	#if command == 'stop': return 0, None
	#return ord(command[0]), command[1:]
	return wfd, '/home/erik/development/weightless/trunk/wlthread.py'

def read_command():
	#print 'wait for command'
	#cmd =
	#return os.read(command_pipe_r, 4096)
	return command_queue.get()
	#return parse_command(cmd)
	#return wfd,

def open_file(name):
	return open(name)

def send_file(tofd, fromfd):
	sendfile.sendfile(tofd, fromfd, 0, 9999999)

def sendloop():
	while True:
		#fd, file =
		if read_command() == 'stop': return
		#if not fd: return
		#print fd, file
		f = open_file('wlthread.py')
		send_file(wfd, f.fileno())
		#sok2.close()

t = threading.Thread(None, sendloop)
t.start()

def send_command(fd, filename):
	#print 'send command'
	#os.write(command_pipe_w, chr(fd)+filename)
	command_queue.put(chr(fd)+filename)

def read_from(sok):
	while True:
		r, w, e = select.select([sok],[],[],0.00001)
		if not r: break
		#sys.stdout.write(sok.recv(16))
		data = sok.recv(4096)
		assert(len(data) == 2033)

def f():
	for i in range(10000):
		send_command(sok2.fileno(), '/home/erik/development/weightless/trunk/wlthread.py')

		read_from(sok)

	#os.write(command_pipe_w, 'stop')
	command_queue.put('stop')

#prof = hotshot.Profile("main.prof", lineevents = 1, linetimings = 1)
#try:
#	prof.runcall(f)
#finally:
#	prof.close()
f()
#stats = hotshot.stats.load("main.prof")
#stats.strip_dirs()
#stats.sort_stats('time', 'calls')
#stats.print_stats(20)

#os.system('python hotshot2kcachegrind.py -o main.out main.prof; kcachegrind main.out')
#os.system('python hotshot2kcachegrind.py -o thread.out thread.prof; kcachegrind thread.out')
