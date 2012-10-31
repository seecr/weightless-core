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
    PyObject*   _methods;
    PyObject*   _message;
    PyObject*   _weakreflist;
} PyMessageBaseCObject;

PyAPI_DATA(PyTypeObject) PyMessageBaseC_Type;

////////// Garbage Collector Support //////////

static int messagebasec_traverse(PyMessageBaseCObject* self, visitproc visit, void* arg) {
    Py_VISIT(self->_methods);
    Py_VISIT(self->_message);
    return 0;
}

static int messagebasec_clear(PyMessageBaseCObject* self) {
    Py_CLEAR(self->_methods);
    Py_CLEAR(self->_message);
    return 0;
}

static void messagebasec_dealloc(PyMessageBaseCObject* self) {
    messagebasec_clear(self);
    if(self->_weakreflist != NULL)
        PyObject_ClearWeakRefs((PyObject*) self);
    self->ob_type->tp_free((PyObject*) self);
}


////////// MessageBaseC Methods //////////

static int PyMessageBaseC_Check(PyObject* obj) {
    return PyObject_Type(obj) == (PyObject*) &PyMessageBaseC_Type;
}


static PyObject* messagebasec_new(PyTypeObject* type, PyObject* args, PyObject* kwargs) {
    PyMessageBaseCObject* obj = (PyMessageBaseCObject*) type->tp_alloc(type, 0);
    obj->_methods = PyTuple_New(0); // new ref
    obj->_message = NULL;
    obj->_weakreflist = NULL;
    return (PyObject*) obj;
}


static int messagebasec_init(PyMessageBaseCObject* self, PyObject* args, PyObject* kwargs) {
    static char* argnames[] = {"methods", "message", NULL};
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "OS:_MessageBaseC.__new__",
                argnames, &self->_methods, &self->_message)) return 1;
    Py_INCREF(self->_methods);
    Py_INCREF(self->_message);
    return 0;
}

PyObject* messagebasec_candidates(PyMessageBaseCObject* self, PyObject* _) {
    Py_INCREF(self->_methods);
    return self->_methods;
}


PyObject* messagebasec_all(PyMessageBaseCObject* self, PyObject* args, PyObject* kwargs) {
    return NULL;
}


static void messagebasec_del(PyObject* self) {
}


////////// MessageBaseC Python Type //////////

static PyMethodDef messagebasec_functionslist[] = {
    {NULL} /* Sentinel */
};

static PyMethodDef messagebasec_methods[] = {
    {"candidates", (PyCFunction) messagebasec_candidates,  METH_NOARGS, "Returns filtered methods." },
    {"all", (PyCFunction) messagebasec_all,  METH_VARARGS | METH_KEYWORDS, "Return generator with call to all observers" },
    {NULL}	/* Sentinel */
};


PyTypeObject PyMessageBaseC_Type = {
    PyObject_HEAD_INIT(&PyType_Type)
    0,                                      /* ob_size */
    "_MessageBaseC",                           /* tp_name */
    sizeof(PyMessageBaseCObject),             /* tp_basicsize */
    0,                                      /* tp_itemsize */
    /* methods */
    (destructor)messagebasec_dealloc,         /* tp_dealloc */
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
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC | Py_TPFLAGS_BASETYPE,  /* tp_flags */
    0,                                      /* tp_doc */
    (traverseproc)messagebasec_traverse,      /* tp_traverse */
    (inquiry)messagebasec_clear,              /* tp_clear */
    0,                                      /* tp_richcompare */
    offsetof(PyMessageBaseCObject, _weakreflist), /* tp_weaklistoffset */
    0,                                      /* tp_iter */
    0,                                      /* tp_iternext */
    messagebasec_methods,                     /* tp_methods */
    0,                                      /* tp_members */
    0,                                      /* tp_getset */
    0,                                      /* tp_base */
    0,                                      /* tp_dict */
    0,                                      /* tp_descr_get */
    0,                                      /* tp_descr_set */
    0,                                      /* tp_dictoffset */
    (initproc)messagebasec_init,            /* tp_init */
    0, /*PyType_GenericAlloc,*/                      /* tp_alloc */
    (newfunc)messagebasec_new,                /* tp_new */
    0,                                      /* tp_free */
    0,                                      /* tp_is_gc */
    0,                                      /* tp_bases */
    0,                                      /* tp_mro */
    0,                                      /* tp_cache */
    0,                                      /* tp_subclasses */
    0,                                      /* tp_weaklist */
    messagebasec_del,                         /* tp_del */
};



////////// Module initialization //////////

PyMODINIT_FUNC init_observable_c(void) {

    if(PyType_Ready(&PyMessageBaseC_Type) < 0) {
        PyErr_Print();
        return;
    }

    PyObject* module = Py_InitModule3("_observable_c", messagebasec_functionslist, "fast MessageBaseC");

    if(!module) {
        PyErr_Print();
        return;
    }

    Py_INCREF(&PyMessageBaseC_Type);
    PyModule_AddObject(module, "_MessageBaseC", (PyObject*) &PyMessageBaseC_Type);
}

