#include <Python.h>

#ifndef __observable_h__
#define __observable_h__

#include "core.h"

int PyAllGenerator_Check(PyObject* obj);
int init_observable_c(PyObject* module);

#endif

