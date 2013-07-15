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
#include "_core.h"
#include "_observable.h"

int debug = 0;

////////// Python Object and Type declarations //////////

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

PyObject* Exc_DeclineMessage;

PyObject* _get_next_value(int* i, PyObject* methods, PyObject* args, PyObject* kwargs) {
    while(methods && ((*i)++ < PyTuple_GET_SIZE(methods) -1)) {
        PyObject* m = PyTuple_GET_ITEM(methods, *i);  // borrowed ref
        PyObject* r = PyObject_Call(m, args, kwargs);  // new ref
        //(*i)++;
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
    //if(r && !is_generator(r)) {
    //    Py_DECREF(r);
    //    return MyErr_Format(PyExc_AssertionError, "%s should have resulted in a generator",
    //            PyTuple_GET_ITEM(self->_methods, self->_i-1));
    //}
    return r;
}

static PyObject* allgenerator_call(PyObject* self, PyObject* args, PyObject* kwargs) {
    return allgenerator_iternext(self);
}

static PyObject* allgenerator_send(PyAllGeneratorObject* self, PyObject* arg) {
    if(arg != Py_None) {
        if(self->_i == -1)
            return PyErr_Format(PyExc_TypeError, "can't send non-None value to a just-started generator");
        PyObject* pa = PyObject_Str(PyTuple_GET_ITEM(self->_methods, self->_i));
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
    PyObject* exc_type = NULL, *exc_value = NULL, *exc_tb = NULL;

    if(!PyArg_ParseTuple(arg, "O|OO", &exc_type, &exc_value, &exc_tb)) //borrowed refs
        return NULL;

    if(PyExceptionInstance_Check(exc_type)) { // e.g. throw(Exception())
        exc_value = exc_type;
        exc_type = PyExceptionInstance_Class(exc_type); // borrowed ref
    }

    if (PyErr_GivenExceptionMatches(exc_type, Exc_DeclineMessage)) {
        return allgenerator_iternext((PyObject*) self);
    }
    if(exc_tb) {
        Py_INCREF(exc_type);
        Py_INCREF(exc_value);
        Py_INCREF(exc_tb);
        PyErr_Restore(exc_type, exc_value, exc_tb); // steals object refs
    } else
        PyErr_SetObject(exc_type, exc_value);
    return NULL;
}

static PyObject* allgenerator_close(PyAllGeneratorObject* self) {
    allgenerator_clear((PyObject*)self);
    self->_i = -1;
    Py_RETURN_NONE;
}

static PyObject* _allgenerator_new(PyObject* methods, PyObject* args, PyObject* kwargs) {
    PyAllGeneratorObject* all = PyObject_GC_New(PyAllGeneratorObject, &PyAllGenerator_Type);

    if(all == NULL)
        return NULL;

    all->_methods = methods; Py_INCREF(all->_methods);
    all->_args = args; Py_INCREF(all->_args);
    all->_kwargs = kwargs; Py_INCREF(all->_kwargs);
    all->_i = -1;

    PyObject_GC_Track(all);
    return (PyObject*) all;
}

static PyObject* allgenerator_new(PyObject* type, PyObject* args, PyObject* kwargs) {
    static char* argnames[] = {"methods", "args", "kwargs", NULL};
    PyObject* methods = NULL;
    PyObject* all_args = NULL;
    PyObject* all_kwargs = NULL;

    if(!PyArg_ParseTupleAndKeywords(                            // borrowed refs
                args, kwargs, "O!O!O!:__new__", argnames,
                &PyTuple_Type, &methods,
                &PyTuple_Type, &all_args,
                &PyDict_Type, &all_kwargs)) return NULL;

    return _allgenerator_new(methods, all_args, all_kwargs);
}

////////// Python Types //////////

/// AllGenerator ///

static PyMethodDef allgenerator_methods[] = {
    {"send", (PyCFunction) allgenerator_send,  METH_O, "generator send" },
    {"throw", (PyCFunction) allgenerator_throw,  METH_VARARGS, "generator throw" },
    {"close", (PyCFunction) allgenerator_close,  METH_NOARGS, "generator close" },
    {NULL}
};

PyTypeObject PyAllGenerator_Type = {
    PyObject_HEAD_INIT(&PyType_Type)
    0,                                  /*ob_size*/
    "AllGenerator",                    /*tp_name*/
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
    allgenerator_call,                  /*tp_call*/
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
    0,                                      /* tp_members */
    0,                                      /* tp_getset */
    0,                                      /* tp_base */
    0,                                      /* tp_dict */
    0,                                      /* tp_descr_get */
    0,                                      /* tp_descr_set */
    0,                                      /* tp_dictoffset */
    0,                                      /* tp_init */
    0,                                      /* tp_alloc */
    (newfunc)allgenerator_new,                   /* tp_new */
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
    
int init_observable(PyObject* module) {

    Exc_DeclineMessage = PyErr_NewException("weightless.core.DeclineMessage", NULL, NULL);
    if(!Exc_DeclineMessage) {
        PyErr_Print();
        return 1;
    }

    if(module_add_object(module, "DeclineMessage", Exc_DeclineMessage))
        return 1;

    if(PyType_Ready(&PyAllGenerator_Type) < 0) {
        PyErr_Print();
        return 1;
    }

    if(module_add_object(module, "AllGenerator", (PyObject*) &PyAllGenerator_Type) < 0)
        return 1;

    return 0;
}

