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
from sys import stderr, exc_info
from traceback import print_tb

RETURN = 1

class Scope: pass
global_vars = Scope()
globals()['__builtins__']['g'] = global_vars

def compose(initial):
	"""
	A Weightless Thread is a chain of generators.  It begins with just one generator.  If it 'yield's another generator, this generator is executed.  This may go on recursively.  If one of the generators 'yield's something else, execution stops and the value is yielded. Generators can return values to parents by yielding RETURN value, ...
	"""
	generators = [initial]
	#if __debug__: generator_names = [initial.gi_frame.f_code.co_name]
	messages = [None]
	responses = []
	while generators:
		try:
			generator = generators[-1]
			if messages:
				message = messages.pop(0)
				if isinstance(message, Exception):
					response = generator.throw(message)
				else:
					response = generator.send(message)
				if type(response) == GeneratorType:
					generators.append(response)
					#if __debug__:
					#	generator_names.append(response.gi_frame.f_code.co_name)
					#	print ' ' * len(generator_names), 'Starting', generator_names[-1]
					messages.insert(0, None)
				elif type(response) == tuple:
					messages = list(response) + messages
				else:
					responses.append(response)
			if responses:
				try:
					message = yield responses.pop(0)
				except GeneratorExit:
					raise
				except Exception, exception:
					message = exception
				messages.append(message)
		except (StopIteration, GeneratorExit):
			g = generators.pop()
			#if __debug__: print ' ' * len(generator_names), 'Stopping:', generator_names.pop()
			g.close()
			if not messages:
				messages.append(None)