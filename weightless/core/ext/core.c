#include <Python.h>

#include "lib/list.h"
#include "compose/_compose.h"
#include "observable/_observable.h"

PyObject* is_generator(PyObject* _, PyObject* o) {
    if(PyCompose_Check(o) || PyGen_Check(o) /* || PyAllMessage_Check(o)*/)
        Py_RETURN_TRUE;
    Py_RETURN_FALSE;
};

static PyMethodDef core_functionslist[] = {
    {"local",       local, METH_O,
            "Finds a local variable on the call stack including compose'd generators."},
    {"tostring",    tostring, METH_O,
            "Returns a string representation of a genarator."},
    {"is_generator", is_generator, METH_O,
            "True if o is generator, compose or all."},
    {"Compose_selftest",   compose_selftest, METH_NOARGS,
            "Runs self test"},
    {"List_selftest", List_selftest, METH_NOARGS,
            "Runs self test for List"},
    {NULL} 
};

PyMODINIT_FUNC initcore_c(void) {

    PyObject* module = Py_InitModule3(
            "weightless.core.core_c",
            core_functionslist,
            "fast observable and compose implementations");

    if(!module) {
        PyErr_Print();
        return;
    }

    if(init_compose_c(module))
        return;

    if(init_observable_c(module))
        return;
}
