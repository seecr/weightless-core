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
#
from __future__ import with_statement

from Queue import Queue
from cq2utils.cq2thread import CQ2Thread as Thread
from types import GeneratorType
from sys import stderr

__author__ = "Erik Groeneveld"
__email__ = "erik@cq2.org"


class Pool:

	def __init__(self, workers = 10, logger = stderr):
		"""Create a pool of 'workers' threads.  The threads are started immediatly.  The threads are daemons, meaning they will disappear when the main program exits."""
		self._jobs = Queue()
		pool = [Thread(None, self._worker) for i in range(workers)]
		map(lambda thread: thread.setDaemon(True), pool)
		map(Thread.start, pool)
		self._pool = pool

	def _worker(self):
		while True:
			cmd = self._jobs.get()
			if cmd == 'stop': return
			cmd()

	def shutdown(self):
		"""Shutdown the pool.  Issues stop commands and waits until ook threads are terminated.  Current jobs are finische normally, remaining work is discarded."""
		for t in self._pool: self._jobs.put(('stop', None, None))
		map(Thread.join, self._pool)

	def execute(self, function):
		"""Adds a piece of work.  The first available thread wil pick it up.  Returns an WlStatus object that becomes set when on termination of the piece of work."""
		assert callable(function), 'execute() expects a callable'
		status = self._createStatus()
		self._jobs.put(function)
		return status
