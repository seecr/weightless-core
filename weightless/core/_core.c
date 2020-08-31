#include <Python.h>

#include <assert.h>

#include "_core.h"
#include "_compose.h"
#include "_observable.h"

int is_generator(PyObject* o) {
    return PyCompose_Check(o) || PyGen_Check(o) || PyAllGenerator_Check(o);
}

PyObject* py_is_generator(PyObject* _, PyObject* o) {
    assert(_ == NULL);
    if(is_generator(o))
        Py_RETURN_TRUE;
    Py_RETURN_FALSE;
}

PyObject* MyErr_Format(PyObject* exc, const char* f, PyObject* o) {
    PyObject* str = PyObject_Str(o);
    PyErr_Format(exc, f, PyBytes_AsString(str));
    Py_DECREF(str);
    return NULL;
}

static PyMethodDef core_functionslist[] = {
    {"local",       local, METH_O,
            "Finds a local variable on the call stack including compose'd generators."},
    {"tostring",    tostring, METH_O,
            "Returns a string representation of a genarator."},
    {"is_generator", py_is_generator, METH_O,
            "True if o is generator, compose or all."},
    {"Compose_selftest",   compose_selftest, METH_NOARGS,
            "Runs self test"},
    {NULL} 
};

PyMODINIT_FUNC PyInit_ext(void) {
    static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "ext",     /* m_name */
        "c compose and observable",  /* m_doc */
        -1,                  /* m_size */
        core_functionslist,  /* m_methods */
        NULL,                /* m_reload */
        NULL,                /* m_traverse */
        NULL,                /* m_clear */
        NULL,                /* m_free */
    };


    PyObject* module = PyModule_Create(&moduledef);

    if(!module) {
        PyErr_Print();
        return NULL;
    }

    if(init_compose(module))
        return NULL;

    if(init_observable(module))
        return NULL;

    return module;
}
