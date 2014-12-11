#include <Python.h>

#ifndef __core_h__
#define __core_h__

#include "_observable.h"

int is_generator(PyObject* o);
PyObject* MyErr_Format(PyObject* exc, const char* f, PyObject* o);

#endif
