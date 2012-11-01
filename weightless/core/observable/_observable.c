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

////////// Python Object and Type declarations //////////

/// MessageBase ///
typedef struct {
    PyObject_HEAD
    PyObject*   _methods;
    PyObject*   _message;
    PyObject*   _weakreflist;
} PyMessageBaseCObject;

PyAPI_DATA(PyTypeObject) PyMessageBaseC_Type;

/// AllGenerator ///
typedef struct {
    PyObject_HEAD
    PyObject*   _methods;
    PyObject*   _args;
    PyObject*   _kwargs;
    int         _i;
} PyAllGeneratorObject;

PyAPI_DATA(PyTypeObject) PyAllGenerator_Type;


////////// Garbage Collector Support //////////

/// MessageBase ///

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

/// AllGenerator ///

static int allgenerator_traverse(PyAllGeneratorObject* self, visitproc visit, void* arg) {
    Py_VISIT(self->_methods);
    Py_VISIT(self->_args);
    Py_VISIT(self->_kwargs);
    return 0;
}

static int allgenerator_clear(PyAllGeneratorObject* self) {
    Py_CLEAR(self->_methods);
    Py_CLEAR(self->_args);
    Py_CLEAR(self->_kwargs);
    return 0;
}

static void allgenerator_dealloc(PyAllGeneratorObject* self) {
    allgenerator_clear(self);
    PyObject_Del(self);
}


////////// Methods //////////

/// MessageBase methods ///

static PyObject* messagebasec_new(PyTypeObject* type, PyObject* args, PyObject* kwargs) {
    PyMessageBaseCObject* obj = (PyMessageBaseCObject*) type->tp_alloc(type, 0);
    if(obj == NULL) return NULL;
    obj->_methods = NULL;
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
    PyAllGeneratorObject* iter = PyObject_New(PyAllGeneratorObject, &PyAllGenerator_Type);
    if (!iter) return NULL;
    PyObject_Init(iter, &PyAllGenerator_Type);
    iter->_methods = self->_methods;
    iter->_args = args;
    iter->_kwargs = kwargs;
    iter->_i = 0;
    Py_INCREF(iter->_methods);
    Py_INCREF(iter->_args);
    if(kwargs)
        Py_INCREF(iter->_kwargs);
    return (PyObject*) iter;
}


/// AllGenerator Methods ///

static PyObject* allgenerator_new(PyTypeObject* type, PyObject* args, PyObject* kwargs) {
    PyAllGeneratorObject* obj = (PyAllGeneratorObject*) type->tp_alloc(type, 0);
    if(obj == NULL) return NULL;
    obj->_methods = NULL;
    obj->_args = NULL;
    obj->_kwargs = NULL;
    obj->_i       = 0;
    return (PyObject*) obj;
}

static PyObject* allgenerator_iter(PyObject *self) {
    Py_INCREF(self);
    return self;
}

PyObject* Exc_DeclineMessage;

static PyObject* allgenerator_iternext(PyAllGeneratorObject* self) {
    while(self->_i < PyTuple_GET_SIZE(self->_methods)) {
        PyObject* m = PyTuple_GET_ITEM(self->_methods, self->_i);  // borrowed ref
        PyObject* r = PyObject_Call(m, self->_args, self->_kwargs);  // new ref
        self->_i++;
        if(!r && PyErr_ExceptionMatches(Exc_DeclineMessage))
            continue;
        return r;
    }
    PyErr_SetNone(PyExc_StopIteration);
    return NULL;
}

static PyObject* allgenerator_send(PyAllGeneratorObject* self, PyObject* arg) {
    if(arg != Py_None) {
        if(self->_i == 0)
            return PyErr_Format(PyExc_TypeError, "can't send non-None value to a just-started generator");
        PyObject* pa = PyObject_Str(PyTuple_GET_ITEM(self->_methods, self->_i-1));
        PyObject* pb = PyObject_Str(arg);
        PyObject* r = PyErr_Format(PyExc_AssertionError, "%s returned '%s'",
                PyString_AsString(pa), PyString_AsString(pb));
        Py_DECREF(pa);
        Py_DECREF(pb);
        return r;
    }
    return allgenerator_iternext(self);
}

// Send and Throw !!!


////////// Python Types //////////

/// MessageBaseC_Type ///

static PyMethodDef messagebasec_methods[] = {
    {"candidates", (PyCFunction) messagebasec_candidates,  METH_NOARGS,
        "Returns filtered methods." },
    {"all", (PyCFunction) messagebasec_all,  METH_VARARGS | METH_KEYWORDS,
        "Return generator with call to all observers" },
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
    0, /*messagebasec_del,*/                         /* tp_del */
};


/// AllGenerator ///

static PyMethodDef allgenerator_methods[] = {
    {"send", (PyCFunction) allgenerator_send,  METH_O, "generator send" },
    {NULL}
};

PyTypeObject PyAllGenerator_Type = {
    PyObject_HEAD_INIT(&PyType_Type)
    0,                         /*ob_size*/
    "_AllGenerator",            /*tp_name*/
    sizeof(PyAllGeneratorObject),       /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)allgenerator_dealloc,                         /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    0,                         /*tp_repr*/
    0,                         /*tp_as_number*/
    0,                         /*tp_as_sequence*/
    0,                         /*tp_as_mapping*/
    0,                         /*tp_hash */
    0,                         /*tp_call*/
    0,                         /*tp_str*/
    0,                         /*tp_getattro*/
    0,                         /*tp_setattro*/
    0,                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC | Py_TPFLAGS_HAVE_ITER,
    "Internal all-iterator object.",           /* tp_doc */
    (traverseproc)allgenerator_traverse,  /* tp_traverse */
    (inquiry)allgenerator_clear,  /* tp_clear */
    0,  /* tp_richcompare */
    0,  /* tp_weaklistoffset */
    allgenerator_iter,  /* tp_iter: __iter__() method */
    allgenerator_iternext,  /* tp_iternext: next() method */
    allgenerator_methods,                     /* tp_methods */
    0,                                      /* tp_members */
    0,                                      /* tp_getset */
    0,                                      /* tp_base */
    0,                                      /* tp_dict */
    0,                                      /* tp_descr_get */
    0,                                      /* tp_descr_set */
    0,                                      /* tp_dictoffset */
    0,            /* tp_init */
    0, /*PyType_GenericAlloc,*/                      /* tp_alloc */
    (newfunc)allgenerator_new,                /* tp_new */
    0,                                      /* tp_free */
};


////////// Module initialization //////////

PyMODINIT_FUNC init_observable_c(void) {

    PyObject* weightlesscore = PyImport_ImportModule("weightless.core.observable._observable_py"); // new ref

    if(!weightlesscore) {
        PyErr_Print();
        return;
    }

    PyObject* dict = PyModule_GetDict(weightlesscore); // borrowed ref

    if(!dict) {
        Py_CLEAR(weightlesscore);
        PyErr_Print();
        return;
    }

    Exc_DeclineMessage = PyMapping_GetItemString(dict, "_DeclineMessage"); // new ref

    if(!Exc_DeclineMessage) {
        Py_CLEAR(weightlesscore);
        PyErr_Print();
        return;
    }
    
    if(PyType_Ready(&PyMessageBaseC_Type) < 0) {
        PyErr_Print();
        return;
    }

    if(PyType_Ready(&PyAllGenerator_Type) < 0) {
        PyErr_Print();
        return;
    }

    PyObject* module = Py_InitModule3("_observable_c", NULL, "fast MessageBaseC");

    if(!module) {
        PyErr_Print();
        return;
    }

    Py_INCREF(&PyMessageBaseC_Type);
    if(PyModule_AddObject(module, "_MessageBaseC", (PyObject*) &PyMessageBaseC_Type) < 0) {
        PyErr_Print();
        return;
    };
    Py_INCREF(&PyAllGenerator_Type);
    if(PyModule_AddObject(module, "_AllGenerator", (PyObject*) &PyAllGenerator_Type) < 0) {;
        PyErr_Print();
        return;
    };
}

