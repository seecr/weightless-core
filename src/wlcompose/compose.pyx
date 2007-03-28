from types import GeneratorType

# use default type (Python object) for import in programs
RETURN = 1

# import types and functions for direct usage to speed up
cdef extern from "Python.h":
	ctypedef extern struct PyObject
	#ctypedef extern struct PyBaseExceptionObject
	PyObject* Py_None
	void Py_INCREF(PyObject* o)
	void Py_DECREF(PyObject* o)
	void   PyMem_Free(void *p)
	void*  PyMem_Malloc(int n) except NULL
	int PyGen_Check(PyObject* o)
	int PyTuple_Check(PyObject* o)
	PyObject* PyTuple_GET_ITEM(PyObject* o, int index)
	int PyTuple_Size(PyObject* o)
	int PyErr_GivenExceptionMatches(PyObject* given, PyObject* exc)
	int PyErr_ExceptionMatches(PyObject* exc)
	PyObject* PyObject_CallFunctionObjArgs(PyObject *callable, ...)
	PyObject* __Pyx_GetExcValue()
	PyObject* PyExc_Exception
	PyObject* PyExc_StopIteration
	PyObject* PyExc_GeneratorExit

# Speeds up significantly because it avoids reference counting etc.
cdef enum:
	STACKSIZE = 500
	EMPTYSTACK = -1
	QUEUESIZE = 100

# precreate exceptions to speed up
cdef STOP
STOP = StopIteration()
cdef EXIT
EXIT = GeneratorExit()
cdef MEMERROR
MEMERROR = MemoryError('stack over/underflow')

# prefectch class methods instead of looking up on the object all the time
cdef object generator_send
generator_send = GeneratorType.send
cdef object generator_throw
generator_throw = GeneratorType.throw

# use extension type to enable cdef for private attributes
cdef class compose:

	# private C attributes
	cdef int generatorIndex
	cdef PyObject **generators
	cdef int messagesHead
	cdef int messagesTail
	cdef PyObject **messages

	def __new__(self, generator):
		self.generatorIndex = EMPTYSTACK
		cdef PyObject** buf
		buf = <PyObject**> PyMem_Malloc((STACKSIZE + QUEUESIZE) * sizeof(PyObject*))
		self.generators = buf
		self.messagesHead = self.messagesTail = 0
		self.messages = buf + STACKSIZE
		self.generators_push(<PyObject*>generator)
		Py_INCREF(<PyObject*>generator)

	def __dealloc__(self):
		PyMem_Free(self.generators)

	cdef void generators_push(self, PyObject* generator):
		if self.generatorIndex >= STACKSIZE:
			raise MEMERROR
		self.generatorIndex = self.generatorIndex + 1
		self.generators[self.generatorIndex] = generator

	cdef void generators_pop(self):
		if self.generatorIndex <= EMPTYSTACK:
			raise MEMERROR
		Py_DECREF(self.generators[self.generatorIndex])
		self.generatorIndex = self.generatorIndex - 1

	cdef void messages_append(self, PyObject* message):
		self.messagesHead = (self.messagesHead + 1) % QUEUESIZE
		if self.messagesHead == self.messagesTail:
			raise MEMERROR
		self.messages[self.messagesHead] = message

	cdef PyObject* messages_next(self):
		self.messagesTail = (self.messagesTail + 1) % QUEUESIZE
		Py_DECREF(self.messages[self.messagesTail])
		return self.messages[self.messagesTail]

	cdef void messages_insert(self, PyObject* message):
		self.messages[self.messagesTail] = message
		# avoid negative modulo (failing in C) by adding QUEUESIZE first
		self.messagesTail = (self.messagesTail - 1 + QUEUESIZE) % QUEUESIZE

	cdef void messages_insert_tuple(self, PyObject* aTuple):
		cdef int i
		for i from PyTuple_Size(aTuple) > i >= 0:
			self.messages[self.messagesTail] =  PyTuple_GET_ITEM(aTuple, i) # returns borrowed ref
			Py_INCREF(self.messages[self.messagesTail])
			self.messagesTail = (self.messagesTail - 1 + QUEUESIZE) % QUEUESIZE
		Py_DECREF(aTuple)

	cdef int moreMessages(self):
		return self.messagesHead != self.messagesTail

	def __next__(self):
		return self.send_(Py_None)

	def send(self, message):
		return self.send_(<PyObject*>message)

	cdef send_(self, PyObject* message):
		cdef PyObject* response
		Py_INCREF(message) # because messages_next releases it
		self.messages_append(message)
		while self.generatorIndex >= 0:
			message = self.messages_next()
			if PyErr_GivenExceptionMatches(<PyObject*>message, <PyObject*>PyExc_Exception):
				response = PyObject_CallFunctionObjArgs(<PyObject*>generator_throw, self.generators[self.generatorIndex], message, NULL)
			else:
				response = PyObject_CallFunctionObjArgs(<PyObject*>generator_send, self.generators[self.generatorIndex], message, NULL)
			if response == NULL:
				self.generators_pop()
				if PyErr_ExceptionMatches(PyExc_StopIteration):
					if not self.moreMessages():
						Py_INCREF(Py_None)
						self.messages_append(Py_None)
				else:
					self.messages_insert(__Pyx_GetExcValue())
			elif PyGen_Check(response):
				self.generators_push(response)
				Py_INCREF(Py_None)
				self.messages_insert(Py_None)
			elif PyTuple_Check(response):
				self.messages_insert_tuple(response)
			elif response != Py_None or not self.moreMessages():
				Py_DECREF(response)
				return <object>response
		if self.moreMessages():
			message =  self.messages_next()
			if PyErr_GivenExceptionMatches(message, <PyObject*>PyExc_Exception):
				raise <object>message
		raise <object>STOP

	def throw(self, exception):
		return self.send_(<PyObject*>exception)

	def close(self):
		try:
			return self.send_(<PyObject*>EXIT)
		except (<object>PyExc_GeneratorExit, <object>PyExc_StopIteration):
			pass	  # mimic genuine GeneratorType.close()

	def __iter__(self):
		return self