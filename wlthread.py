#!/usr/bin/env python
## begin license ##
#
#    "Weightless" is a package with a wide range of valuable tools.
#    Copyright (C) 2005, 2006 Seek You Too B.V. (CQ2) http://www.cq2.nl
#
#    This file is part of "Weightless".
#
#    "Weightless" is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    "Weightless" is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with "Weightless"; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

import platform
assert platform.python_version() >= "2.5", "Python 2.5 required"

from types import GeneratorType

def WlThread(generator):
	"""
	A Weightless Thread is a list of generators.  It begins with just one generator.  If it 'yield's another generator, this generator is added to the list.  This may go on recursively.  If one of the generators 'yield's something else, execution stops and the value is used as return value for run(). Calling run() repeatedly will cause the thread to run from yield to yield.  NOTE: yield should be read as "yielding a CPU".   Values passed with yield are ment to support communication between the scheduler and the thread. This type of thread is meant for highly efficient networking based on select().  To reach >1000 requests/second, every instruction counts.
	"""
	runlist = [generator]												# Init stack of threads with just one
	response = generator.next()									# Initialize (run until first yield)
	while runlist:															# As long as there are generators
		try:
			if type(response) == GeneratorType:			# If yield yielded another generator
				runlist.append(response)							# Add it to the runlist
				response = response.next()						# and initialize it.
			else:																		# Else yield yielded a value
				response = yield response							# propagate up (allow interception)
				response = runlist[-1].send(response)	#	pass it as return value from yield
		except StopIteration:
			runlist.pop()														# When generator finische pop it
	raise StopIteration('Nothing left to run')	# All done


