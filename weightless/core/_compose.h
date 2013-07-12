#include <Python.h>

#ifndef __compose_h__
#define __compose_h__

int init_compose(PyObject* module);

PyObject* compose_selftest(PyObject* self, PyObject* null);

PyObject* local(PyObject* self, PyObject* name);
PyObject* tostring(PyObject* self, PyObject* gen);
int PyCompose_Check(PyObject* o);

#endif
