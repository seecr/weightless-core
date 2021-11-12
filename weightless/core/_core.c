/* begin license *
 *
 * "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
 *
 * Copyright (C) 2020-2021 Seecr (Seek You Too B.V.) https://seecr.nl
 *
 * This file is part of "Weightless"
 *
 * "Weightless" is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * "Weightless" is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with "Weightless"; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
 *
 * end license */

#include <Python.h>

#include <assert.h>

#include "_core.h"
#include "_compose.h"
#include "_observable.h"

int is_generator(PyObject* o) {
    return PyCompose_Check(o) || PyGen_Check(o) || PyAllGenerator_Check(o);
}

PyObject* py_is_generator(PyObject* _, PyObject* o) {
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
