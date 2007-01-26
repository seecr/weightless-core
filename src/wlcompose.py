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

RETURN = 1

class Scope: pass
global_vars = Scope()
globals()['__builtins__']['g'] = global_vars

def compose(initial):
	"""
	A Weightless Thread is a chain of generators.  It begins with just one generator.  If it 'yield's another generator, this generator is executed.  This may go on recursively.  If one of the generators 'yield's something else, execution stops and the value is yielded. Generators can return values to parents by yielding RETURN value, ...
	"""
	generators = [initial]
	messages = [None]
	while generators:
		try:
			generator = generators[-1]
			message = messages.pop(0)
			if isinstance(message, Exception):
				response = generator.throw(message)
			else:
				response = generator.send(message)
			if type(response) == GeneratorType:
				generators.append(response)
				messages.insert(0, None)
			elif type(response) == tuple:
				messages = list(response) + messages
			else:
				try:
					message = yield response
				except Exception, exception:
					message = exception
				messages.append(message)
		except StopIteration:
			generators.pop()
			#messages.pop()
			if not messages:
				messages.append(None)