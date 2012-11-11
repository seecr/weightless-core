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
#include <limits.h>
#include "observable.h"

int debug = 0;

////////// Python Object and Type declarations //////////

/// MessageBase ///
typedef struct {
    PyObject_HEAD
    PyObject*   _methods;
    PyObject*   _message;
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
    self->ob_type->tp_free((PyObject*) self);
}

/// AllGenerator ///

static int allgenerator_traverse(PyObject* self, visitproc visit, void* arg) {
    Py_VISIT(((PyAllGeneratorObject*)self)->_methods);
    Py_VISIT(((PyAllGeneratorObject*)self)->_args);
    if(((PyAllGeneratorObject*)self)->_kwargs) Py_VISIT(((PyAllGeneratorObject*)self)->_kwargs);
    return 0;
}

static int allgenerator_clear(PyObject* _self) {
    PyAllGeneratorObject* self = (PyAllGeneratorObject*) _self;
    Py_CLEAR(self->_methods);
    Py_CLEAR(self->_args);
    Py_CLEAR(self->_kwargs);
    return 0;
}

static void allgenerator_dealloc(PyObject* self) {
    PyObject_GC_UnTrack(self);
    allgenerator_clear(self);
    PyObject_GC_Del(self);
}


////////// Methods //////////

/// MessageBase methods ///

static PyObject* messagebasec_new(PyTypeObject* type, PyObject* args, PyObject* kwargs) {
    PyMessageBaseCObject* obj = (PyMessageBaseCObject*) type->tp_alloc(type, 0);
    if(obj == NULL)
        return NULL;
    obj->_methods = NULL;
    obj->_message = NULL;
    return (PyObject*) obj;
}


static int messagebasec_init(PyObject* _self, PyObject* args, PyObject* kwargs) {
    static char* argnames[] = {"methods", "message", NULL};
    PyMessageBaseCObject* self = (PyMessageBaseCObject*) _self;
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "O!S:_MessageBaseC.__init__",
                argnames, &PyTuple_Type, &self->_methods, &self->_message))
        return -1;
    Py_INCREF(self->_methods);
    Py_INCREF(self->_message);
    return 0;
}

PyObject* messagebasec_candidates(PyMessageBaseCObject* self, PyObject* _) {
    Py_INCREF(self->_methods);
    return self->_methods;
}

PyObject* messagebasec_all(PyMessageBaseCObject* self, PyObject* args, PyObject* kwargs) {
    PyAllGeneratorObject* iter = PyObject_GC_New(PyAllGeneratorObject, &PyAllGenerator_Type);
    if (!iter) return NULL;
    if(!PyObject_Init((PyObject*) iter, &PyAllGenerator_Type)) return NULL;
    iter->_methods = self->_methods;
    iter->_args = args;
    iter->_kwargs = kwargs;
    iter->_i = 0;
    Py_INCREF(iter->_methods);
    Py_INCREF(iter->_args);
    if(kwargs)
        Py_INCREF(iter->_kwargs);
    PyObject_GC_Track(iter);
    return (PyObject*) iter;
}

PyObject* Exc_DeclineMessage;
PyObject* Exc_NoneOfTheObserversRespond;

PyObject* _get_next_value(int* i, PyObject* methods, PyObject* args, PyObject* kwargs) {
    while(methods && (*i < PyTuple_GET_SIZE(methods))) {
        PyObject* m = PyTuple_GET_ITEM(methods, *i);  // borrowed ref
        PyObject* r = PyObject_Call(m, args, kwargs);  // new ref
        (*i)++;
        if(r)
            return r;
        if(PyErr_ExceptionMatches(Exc_DeclineMessage))
            PyErr_Clear();
        else
            return NULL;
    }
    PyErr_SetNone(PyExc_StopIteration);
    return NULL;
}

PyObject* messagebasec_any(PyMessageBaseCObject* self, PyObject* args, PyObject* kwargs) {
    int i = 0;
    PyObject* g = _get_next_value(&i, self->_methods, args, kwargs);
    PyObject* r = PyObject_CallMethod(g, "next", ""); // new ref
    Py_DECREF(g);
    if(PyErr_ExceptionMatches(PyExc_StopIteration))
        return NULL;
    PyObject *exctype, *excvalue, *exctb;
    PyErr_Fetch(&exctype, &excvalue, &exctb);
    if(r)
        PyErr_SetObject(PyExc_StopIteration, r);
    else if(PyErr_ExceptionMatches(PyExc_StopIteration)) {
        PyErr_Clear();
        PyErr_SetString(Exc_NoneOfTheObserversRespond, "no one?");
    }
    return NULL;
}


/// AllGenerator Methods ///

int PyAllGenerator_Check(PyObject* obj) {
    return PyObject_Type(obj) == (PyObject*) &PyAllGenerator_Type;
}

static PyObject* allgenerator_iter(PyObject *self) {
    Py_INCREF(self);
    return self;
}

static PyObject* allgenerator_iternext(PyObject* _self) {
    PyAllGeneratorObject* self = (PyAllGeneratorObject*) _self;
    PyObject* r = _get_next_value(&self->_i, self->_methods, self->_args, self->_kwargs);
    if(r && !is_generator(r)) {
        Py_DECREF(r);
        return MyErr_Format(PyExc_AssertionError, "%s should have resulted in a generator",
                PyTuple_GET_ITEM(self->_methods, self->_i-1));
    }
    return r;
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
    return allgenerator_iternext((PyObject*)self);
}

static PyObject* allgenerator_throw(PyAllGeneratorObject* self, PyObject* arg) {
    if(self->_i == 0) {
        PyErr_SetNone(arg);
        return NULL;
    }
    return allgenerator_iternext((PyObject*) self);
}

static PyObject* allgenerator_close(PyAllGeneratorObject* self) {
    //allgenerator_clear(self);
    //self->_i = 0;
    Py_RETURN_NONE;
}


////////// Python Types //////////

/// MessageBaseC_Type ///

static PyMethodDef messagebasec_methods[] = {
    {"candidates", (PyCFunction) messagebasec_candidates,  METH_NOARGS,
        "Returns filtered methods." },
    {"all", (PyCFunction) messagebasec_all,  METH_VARARGS | METH_KEYWORDS,
        "Return generator with call to all observers" },
    {"any", (PyCFunction) messagebasec_any, METH_VARARGS | METH_KEYWORDS,
        "Return one result from on of the observers" },
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
    0,                                      /* tp_weaklistoffset */
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
    messagebasec_init,            /* tp_init */
    0, /*PyType_GenericAlloc,*/                      /* tp_alloc */
    (newfunc)messagebasec_new,                /* tp_new */
};


/// AllGenerator ///

static PyMethodDef allgenerator_methods[] = {
    {"send", (PyCFunction) allgenerator_send,  METH_O, "generator send" },
    {"throw", (PyCFunction) allgenerator_throw,  METH_O, "generator throw" },
    {"close", (PyCFunction) allgenerator_close,  METH_NOARGS, "generator close" },
    {NULL}
};

PyTypeObject PyAllGenerator_Type = {
    PyObject_HEAD_INIT(&PyType_Type)
    0,                                  /*ob_size*/
    "_AllGenerator",                    /*tp_name*/
    sizeof(PyAllGeneratorObject),       /*tp_basicsize*/
    0,                                  /*tp_itemsize*/
    (destructor)allgenerator_dealloc,   /*tp_dealloc*/
    0,                                  /*tp_print*/
    0,                                  /*tp_getattr*/
    0,                                  /*tp_setattr*/
    0,                                  /*tp_compare*/
    0,                                  /*tp_repr*/
    0,                                  /*tp_as_number*/
    0,                                  /*tp_as_sequence*/
    0,                                  /*tp_as_mapping*/
    0,                                  /*tp_hash */
    0,                                  /*tp_call*/
    0,                                  /*tp_str*/
    0,                                  /*tp_getattro*/
    0,                                  /*tp_setattro*/
    0,                                  /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC | Py_TPFLAGS_HAVE_ITER,
    "Internal all-iterator object.",    /*tp_doc */
    allgenerator_traverse,/*tp_traverse */
    (inquiry)allgenerator_clear,        /*tp_clear */
    0,                                  /* tp_richcompare */
    0,                                  /* tp_weaklistoffset */
    allgenerator_iter,                  /* tp_iter: __iter__() method */
    allgenerator_iternext,              /* tp_iternext: next() method */
    allgenerator_methods,               /* tp_methods */
};


////////// Module initialization //////////

int module_add_object(PyObject* module, const char* name, PyObject* obj) {
    Py_INCREF(obj);
    if(PyModule_AddObject(module, name, obj)) {
        PyErr_Print();
        return 1;
    }
    return 0;
}
    
int init_observable_c(PyObject* module) {

    Exc_DeclineMessage = PyErr_NewException("weightless.core.core_c._DeclineMessage", NULL, NULL);
    if(!Exc_DeclineMessage) {
        PyErr_Print();
        return 1;
    }

    if(module_add_object(module, "DeclineMessage", Exc_DeclineMessage))
        return 1;

    Exc_NoneOfTheObserversRespond = PyErr_NewException("weightless.core.core_c._NoneOfTheObserversRespond", NULL, NULL);
    if(!Exc_NoneOfTheObserversRespond) {
        PyErr_Print();
        return 1;
    }

    if(module_add_object(module, "NoneOfTheObserversRespond", Exc_NoneOfTheObserversRespond))
        return 1;

    if(PyType_Ready(&PyMessageBaseC_Type) < 0) {
        PyErr_Print();
        return 1;
    }

    if(module_add_object(module, "MessageBaseC", (PyObject*) &PyMessageBaseC_Type) < 0)
        return 1;

    if(PyType_Ready(&PyAllGenerator_Type) < 0) {
        PyErr_Print();
        return 1;
    }

    if(module_add_object(module, "AllGenerator", (PyObject*) &PyAllGenerator_Type) < 0)
        return 1;

    return 0;
}

