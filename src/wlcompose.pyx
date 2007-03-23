from types import GeneratorType

RETURN = 1
STOP = StopIteration()
EXIT = GeneratorExit()

def strGen(g):
	frame = g.gi_frame
	code = frame.f_code
	return '%s (%s:%s)' % (code.co_name, code.co_filename, frame.f_lineno)

class compose:
	def __init__(self, initial):
		self.generators = [initial]
		self.messages = []
		self.responses = []

	def next(self):
		return self.send(None)

	def send(self, message):
		self.messages.append(message)
		while self.generators:
			generator = self.generators[-1]
			if self.messages:
				message = self.messages.pop(0)
				send = isinstance(message, Exception) and generator.throw or generator.send
				try:
					response = send(message)
					if type(response) == GeneratorType:
						self.generators.append(response)
						self.messages.insert(0, None)
					elif type(response) == tuple:
						self.messages = list(response) + self.messages
					elif response or not self.messages:
						self.responses.append(response)
				except StopIteration:
					self.generators.pop()
					if not self.messages:
						self.messages.append(None)
				except Exception, exception:
					self.generators.pop()
					self.messages.insert(0, exception)
			if self.responses:
				return self.responses.pop(0)
		if self.messages and isinstance(self.messages[0], Exception):
			raise self.messages[0]
		raise STOP

	def throw(self, exception):
		return self.send(exception)

	def close(self):
		try:
			return self.send(EXIT)
		except (GeneratorExit, StopIteration):
			pass	  # mimic genuine GeneratorType.close()

	def __iter__(self):
		return self