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

def compose(initial):
	"""
	The method compose() allows program (de)composition with generators.  It enables calls like:
		retvat = yield otherGenerator(args)
	The otherGenerator may return values by:
		yield RETURN, retvat, remaining data
	Remaining data might be present if the otherGenerator consumes less than it get gets.  It must
	make this remaining data available to the calling generator by yielding it as shown.
	"""
	generators = [initial]
	messages = [None]
	responses = []
	while generators:
		generator = generators[-1]
		if messages:
			message = messages.pop(0)
			#print '>' * len(generators), 'sending', repr(message), 'to', generator.gi_frame.f_code.co_name, 'at line', generator.gi_frame.f_lineno, 'in', generator.gi_frame.f_code.co_filename
			send = generator.send if not isinstance(message, Exception) else generator.throw
			try:
				response = send(message)
				if type(response) == GeneratorType:
					generators.append(response)
					messages.insert(0, None)
				elif type(response) == tuple:
					messages = list(response) + messages
				elif response or not messages:
					responses.append(response)
			except StopIteration:
				generators.pop()
				if not messages:
					messages.append(None)
			except Exception, exception:
				generators.pop()
				messages.insert(0, exception)
		if responses:
			try:
				message = yield responses.pop(0)
			except Exception, exception:
				message = exception
			messages.append(message)
	if messages and isinstance(messages[0], Exception):
		raise messages[0]
