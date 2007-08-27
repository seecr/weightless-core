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
	int PyErr_ExceptionMatches(PyObject* exc)
	PyObject* PyObject_CallFunctionObjArgs(PyObject *callable, ...)
	PyObject* PyErr_Occurred(  )
	PyObject* PyExc_Exception
	PyObject* PyExc_StopIteration
	PyObject* PyExc_GeneratorExit
	void PyErr_Clear()
	void PyErr_Fetch(PyObject** ptype, PyObject** pvalue, PyObject** ptrace)
	void __Pyx_Raise(PyObject* exc, PyObject* na1, PyObject* na2)

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
		cdef PyObject* msg
		while self.moreMessages():
			msg = self.messages_next()
			Py_DECREF(msg)
		while self.generatorIndex >= 0:
			self.generators_pop()
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
		self.messages_append(Py_None)
		Py_INCREF(Py_None)
		return self.send_(NULL)

	def send(self, message):
		self.messages_append(<PyObject*>message)
		Py_INCREF(<PyObject*>message)
		return self.send_(NULL)

	cdef send_(self, PyObject* exception):
		cdef PyObject* message
		cdef PyObject* response
		cdef PyObject* na1
		cdef PyObject* na2
		while self.generatorIndex >= 0:
			if exception:
				response = PyObject_CallFunctionObjArgs(<PyObject*>generator_throw, self.generators[self.generatorIndex], exception, NULL)
				Py_DECREF(exception)
				exception = NULL
			else:
				message = self.messages_next()
				response = PyObject_CallFunctionObjArgs(<PyObject*>generator_send, self.generators[self.generatorIndex], message, NULL)
				Py_DECREF(message)
			if response == NULL:
				self.generators_pop()
				if PyErr_ExceptionMatches(PyExc_StopIteration):
					PyErr_Clear()
					if not self.moreMessages(): #  generator didn't provide return value
						Py_INCREF(Py_None)
						self.messages_append(Py_None)
				else:
					PyErr_Fetch(&na1, &exception, &na2) # I own the refs
					Py_DECREF(na1)
					Py_DECREF(na2)
			elif PyGen_Check(response):
				self.generators_push(response)
				Py_INCREF(Py_None)
				self.messages_insert(Py_None)
			elif PyTuple_Check(response):
				self.messages_insert_tuple(response)
			elif response != Py_None or not self.moreMessages():
				Py_DECREF(response)
				return <object>response
		if exception:
			# ugly and slow, but exception must be released, rather use C here
			try:
				raise <object>exception
			finally:
				Py_DECREF(exception)
		raise <object>STOP

	def throw(self, exception):
		Py_INCREF(<PyObject*>exception)
		return self.send_(<PyObject*>exception)

	def close(self):
		try:
			Py_INCREF(<PyObject*>EXIT)
			return self.send_(<PyObject*>EXIT)
		except (<object>PyExc_GeneratorExit, <object>PyExc_StopIteration):
			pass	  # mimic genuine GeneratorType.close()

	def __iter__(self):
		return self