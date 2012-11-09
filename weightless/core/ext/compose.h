#include <Python.h>
#include "list.h"

#ifndef __compose_h__
#define __compose_h__

/* initialize Python types */
int init_compose_c(PyObject* module);

/* self test for this module */
PyObject* compose_selftest(PyObject* self, PyObject* null);

/* exported functions */
PyObject* local(PyObject* self, PyObject* name);
PyObject* tostring(PyObject* self, PyObject* gen);
int PyCompose_Check(PyObject* o);

#endif
