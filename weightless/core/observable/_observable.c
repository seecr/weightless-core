/* begin license *
 * 
 * "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io 
 * 
 * Copyright (C) 2009-2011 Seek You Too (CQ2) http://www.cq2.nl
 * Copyright (C) 2011-2012 Seecr (Seek You Too B.V.) http://seecr.nl
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

/* This code is formatted with:
 * astyle --style=java --indent-namespaces --break-blocks=all --pad-oper --unpad-paren --delete-empty-lines --align-pointer=type
 */

#include <Python.h>
#include <structmember.h>

////////// Python Object and Type structures //////////

typedef struct {
    PyObject_HEAD
    PyObject*  weakreflist;
} PyObservableObject;

PyAPI_DATA(PyTypeObject) PyObservable_Type;

////////// Garbage Collector Support //////////

static int observable_traverse(PyObservableObject* self, visitproc visit, void* arg) {
    return 0;
}

static int observable_clear(PyObservableObject* self) {
    return 0;
}

static void observable_dealloc(PyObservableObject* self) {
    PyObject_GC_UnTrack(self);

    if(self->weakreflist != NULL)
        PyObject_ClearWeakRefs((PyObject*)self);

    observable_clear(self);
    PyObject_GC_Del(self);
}


////////// Observable Methods //////////

static int PyObservable_Check(PyObject* obj) {
    return PyObject_Type(obj) == (PyObject*) &PyObservable_Type;
}

static void _observable_initialize(PyObservableObject* obs) {
    obs->weakreflist = NULL;
}

static PyObject* observable_new(PyObject* type, PyObject* args, PyObject* kwargs) {

    PyObservableObject* obs = PyObject_GC_New(PyObservableObject, &PyObservable_Type);

    if(obs == NULL)
        return NULL;

    _observable_initialize((PyObservableObject*) obs);

    PyObject_GC_Track(obs);
    return (PyObject*) obs;
}

PyObject* observable_addObserver(PyObject* args) {
    Py_RETURN_NONE;
}

static void observable_del(PyObject* self) {
}

////////// Observable Python Type //////////

static PyMethodDef observable_functionslist[] = {
    //{"addObserver", observable_addObserver, METH_1, "Add an observer."},
    {NULL} /* Sentinel */
};

static PyMethodDef observable_methods[] = {
    {"addObserver", (PyCFunction) observable_addObserver,  METH_O, "Add one observer." },
    {NULL}	/* Sentinel */
};


PyTypeObject PyObservable_Type = {
    PyObject_HEAD_INIT(&PyType_Type)
    0,                                      /* ob_size */
    "Observable",                           /* tp_name */
    sizeof(PyObservableObject),             /* tp_basicsize */
    0,                                      /* tp_itemsize */
    /* methods */
    (destructor)observable_dealloc,         /* tp_dealloc */
    0,                                      /* tp_print */
    0,                                      /* tp_getattr */
    0,                                      /* tp_setattr */
    0,                                      /* tp_compare */
    0,                                      /* tp_repr */
    0,                                      /* tp_as_number */
    0,                                      /* tp_as_sequence */
    0,                                      /* tp_as_mapping */
    0,                                      /* tp_hash */
    0,                                      /* tp_call */
    0,                                      /* tp_str */
    PyObject_GenericGetAttr,                /* tp_getattro */
    0,                                      /* tp_setattro */
    0,                                      /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,/* tp_flags */
    0,                                      /* tp_doc */
    (traverseproc)observable_traverse,      /* tp_traverse */
    (inquiry)observable_clear,              /* tp_clear */
    0,                                      /* tp_richcompare */
    offsetof(PyObservableObject, weakreflist), /* tp_weaklistoffset */
    0,                                      /* tp_iter */
    0,                                      /* tp_iternext */
    observable_methods,                     /* tp_methods */
    0,                                      /* tp_members */
    0,                                      /* tp_getset */
    0,                                      /* tp_base */
    0,                                      /* tp_dict */
    0,                                      /* tp_descr_get */
    0,                                      /* tp_descr_set */
    0,                                      /* tp_dictoffset */
    0,                                      /* tp_init */
    0,                                      /* tp_alloc */
    (newfunc)observable_new,                /* tp_new */
    0,                                      /* tp_free */
    0,                                      /* tp_is_gc */
    0,                                      /* tp_bases */
    0,                                      /* tp_mro */
    0,                                      /* tp_cache */
    0,                                      /* tp_subclasses */
    0,                                      /* tp_weaklist */
    observable_del,                         /* tp_del */
};



////////// Module initialization //////////

PyMODINIT_FUNC init_observable_c(void) {

    if(PyType_Ready(&PyObservable_Type) < 0) {
        PyErr_Print();
        return;
    }

    PyObject* module = Py_InitModule3("_observable_c", observable_functionslist, "fast Observable");

    if(!module) {
        PyErr_Print();
        return;
    }

    Py_INCREF(&PyObservable_Type);
    PyModule_AddObject(module, "Observable", (PyObject*) &PyObservable_Type);
}

