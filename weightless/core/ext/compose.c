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
#include <frameobject.h>
#include <structmember.h>

#include "compose.h"
#include "core.h" // for is_generator

////////// Python Object and Type structures //////////

typedef struct {
    PyObject_HEAD
    int        expect_data;
    int        started;
    int        stepping;
    int        paused_on_step;
    MyList     generators;
    MyList     messages;
    PyFrameObject* frame;
    PyObject*  weakreflist;
} PyComposeObject;

PyAPI_DATA(PyTypeObject) PyCompose_Type;


typedef struct {
    PyObject_HEAD
} PyYieldObject;

////////// Yield Python Type //////////
static PyTypeObject PyYield_Type = {
    PyObject_HEAD_INIT(&PyType_Type)
    0,                         /*ob_size*/
    "Yield",                   /*tp_name*/
    sizeof(PyYieldObject),     /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    0,                         /*tp_dealloc*/
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
    Py_TPFLAGS_DEFAULT,        /*tp_flags*/
    "Yield objects",           /* tp_doc */
};


////////// Generator Stack //////////
#define INITIAL_STACK_SIZE 10

////////// Messages Queue //////////
#define QUEUE_SIZE 10

////////// Garbage Collector Support //////////

static int compose_traverse(PyComposeObject* self, visitproc visit, void* arg) {
    List.gc_visit(&self->generators, visit, arg);
    List.gc_visit(&self->messages, visit, arg);
    Py_VISIT(self->frame);
    return 0;
}


static int compose_clear(PyComposeObject* self) {
    List.gc_clear(&self->generators);
    List.gc_clear(&self->messages);
    Py_CLEAR(self->frame);
    return 0;
}


static void compose_dealloc(PyComposeObject* self) {
    PyObject_GC_UnTrack(self);

    if(self->weakreflist != NULL)
        PyObject_ClearWeakRefs((PyObject*)self);

    compose_clear(self);
    PyObject_GC_Del(self);
}



////////// Compose Methods //////////

int PyCompose_Check(PyObject* obj) {
    return PyObject_Type(obj) == (PyObject*) &PyCompose_Type;
}


static PyCodeObject* py_code;

static void _compose_initialize(PyComposeObject* cmps) {
    cmps->expect_data = 0;
    cmps->started = 0;
    cmps->stepping = 0;
    cmps->paused_on_step = 0;
    List.init(&cmps->generators, INITIAL_STACK_SIZE);
    List.init(&cmps->messages, QUEUE_SIZE);
    cmps->weakreflist = NULL;
    cmps->frame = PyFrame_New(PyThreadState_GET(), py_code, PyEval_GetGlobals(), NULL);
    Py_CLEAR(cmps->frame->f_back);
}


static PyObject* compose_new(PyObject* type, PyObject* args, PyObject* kwargs) {
    static char* argnames[] = {"initial", "stepping", NULL};
    PyObject* initial = NULL;
    PyObject* stepping = Py_False;

    if(!PyArg_ParseTupleAndKeywords(                            // borrowed refs
                args, kwargs, "O|O:compose", argnames,
                &initial, &stepping)) return NULL;

    if(!is_generator(initial)) {
        PyErr_SetString(PyExc_TypeError, "compose() argument 1 must be generator");
        return NULL;
    }

    PyComposeObject* cmps = PyObject_GC_New(PyComposeObject, &PyCompose_Type);

    if(cmps == NULL)
        return NULL;

    _compose_initialize((PyComposeObject*) cmps);

    if(stepping)
        cmps->stepping = stepping == Py_True;

    if(!List.append(&cmps->generators, initial)) return NULL;

    PyObject_GC_Track(cmps);
    return (PyObject*) cmps;
}


static int _compose_handle_stopiteration(PyComposeObject* self, PyObject* exc_value) {
    PyObject* args = exc_value
                     ? PyObject_GetAttrString(exc_value, "args") // new ref
                     : NULL;

    if(args && PyTuple_CheckExact(args) && PyObject_IsTrue(args)) {
        long i;

        for(i = PyTuple_Size(args) - 1; i >= 0; i--)
            if(!List.insert(&self->messages, PyTuple_GET_ITEM(args, i))) {
                Py_CLEAR(args);
                return 0;
            }

        Py_CLEAR(args);

    } else if(!List.empty(&self->generators))
        List.insert(&self->messages, Py_None);

    return 1;
}


static int generator_invalid(PyObject* gen) {
    PyFrameObject* frame;
    int started;

    if(PyCompose_Check(gen)) {
        frame = ((PyComposeObject*)gen)->frame;
        started = ((PyComposeObject*)gen)->started;

    } else { // PyGenObject
        frame = ((PyGenObject*)gen)->gi_frame;
        started = frame && frame->f_lasti != -1;
    }

    if(!frame) {
        PyErr_SetString(PyExc_AssertionError, "Generator is exhausted.");
        return 1;
    }

    if(started) {
        PyErr_SetString(PyExc_AssertionError, "Generator already used.");
        return 1;
    }

    return 0;
}


static PyObject* _compose_go(PyComposeObject* self, PyObject* exc_type, PyObject* exc_value, PyObject* exc_tb) {
    Py_XINCREF(exc_type);
    Py_XINCREF(exc_value);
    Py_XINCREF(exc_tb);

    if(!self->started)
        self->started = 1;

    self->paused_on_step = 0;

    while(!List.empty(&self->generators)) {
        PyObject* generator = List.top(&self->generators);
        PyObject* response = NULL;
        PyObject* message = NULL;

        if(exc_type) { // exception
            if(PyErr_GivenExceptionMatches(exc_type, PyExc_GeneratorExit)) {
                PyObject* result = PyObject_CallMethod(generator, "close", NULL); // new ref

                if(result) {
                    Py_CLEAR(result);
                    PyErr_Restore(exc_type, exc_value, exc_tb); //steals refs
                    exc_type = exc_value = exc_tb = NULL;
                }

            } else
                response =
                    PyObject_CallMethod(generator, "throw", "OOO",
                                        exc_type,
                                        exc_value ? exc_value : Py_None,
                                        exc_tb ? exc_tb : Py_None); // new ref

            Py_CLEAR(exc_type);
            Py_CLEAR(exc_value);
            Py_CLEAR(exc_tb);

        } else { // normal message
            message = List.next(&self->messages); // new ref
            response = PyObject_CallMethod(generator, "send", "(O)", message); // new ref
            Py_CLEAR(message);
        }
    
        if(response) { // normal response
            Py_DECREF(generator);
            if(PyGen_Check(response) || PyCompose_Check(response)) {

                if(generator_invalid(response)) {
                    PyErr_Fetch(&exc_type, &exc_value, &exc_tb); // new refs
                    Py_CLEAR(response);
                    continue;
                }

                if(!List.append(&self->generators, response)) {
                    Py_CLEAR(response);
                    return NULL;
                }

                if(self->stepping) {
                    Py_CLEAR(response);
                    self->paused_on_step = 1;
                    Py_INCREF(&PyYield_Type);
                    return (PyObject*) &PyYield_Type;
                }
                List.insert(&self->messages, Py_None);

            } else if(response != Py_None || List.empty(&self->messages)) {
                self->expect_data = response == Py_None;
                return response;
            }

            Py_CLEAR(response);

        } else { // exception thrown
            Py_DECREF(List.pop(&self->generators));
            PyErr_Fetch(&exc_type, &exc_value, &exc_tb); // new refs

            if(PyErr_GivenExceptionMatches(exc_type, PyExc_StopIteration)) {
                Py_CLEAR(exc_tb);
                Py_CLEAR(exc_type);
                int ok = _compose_handle_stopiteration(self, exc_value);
                Py_CLEAR(exc_value);

                if(!ok)
                    PyErr_Fetch(&exc_type, &exc_value, &exc_tb); // new refs
            }

            Py_CLEAR(generator);
        }
    }

    if(exc_type) {
        PyErr_Restore(exc_type, exc_value, exc_tb); // steals refs
        exc_type = exc_value = exc_tb = NULL;
        return NULL;
    }

    // if any messages are left, 'return' them by StopIteration
    long n = List.size(&self->messages);

    if(n) {
        PyObject* args = PyTuple_New(n); // new ref
        int i;

        for(i = 0; i < n; i++) {
            PyTuple_SetItem(args, i, List.next(&self->messages)); // steals ref
        }

        PyObject* sie = PyObject_Call(PyExc_StopIteration, args, NULL); // new ref
        PyErr_SetObject(PyExc_StopIteration, sie);
        Py_DECREF(sie);
        Py_DECREF(args);

    } else
        PyErr_SetNone(PyExc_StopIteration);
    return NULL;
}


static PyObject* _compose_go_with_frame(PyComposeObject* self, PyObject* exc_type, PyObject* exc_value, PyObject* exc_tb) {
    PyThreadState* tstate = PyThreadState_GET();
    PyFrameObject* tstate_frame = tstate->frame;
    self->frame->f_back = tstate_frame;
    Py_INCREF(self->frame->f_back);
    tstate->frame = self->frame;
    *(self->frame->f_stacktop++) = (PyObject*) self;
    Py_INCREF(self);
    PyObject* response = _compose_go(self, exc_type, exc_value, exc_tb);
    self->frame->f_stacktop--;
    Py_DECREF(self);
    Py_CLEAR(self->frame->f_back);
    tstate->frame = tstate_frame;
    return response;
}


static PyObject* compose_send(PyComposeObject* self, PyObject* message) {
    PyObject* exc_type = NULL;
    PyObject* exc_val = NULL;
    if(self->paused_on_step && message != Py_None) {
        exc_val = PyString_FromString("Cannot accept data when stepping. First send None.");
        exc_type = PyExc_AssertionError;
    } else if(!self->expect_data && message != Py_None) {
        exc_val = PyString_FromString("Cannot accept data. First send None.");
        exc_type = PyExc_AssertionError;
    } else
        List.insert(&self->messages, message);
    PyObject* response = _compose_go_with_frame(self, exc_type, exc_val, NULL);
    Py_CLEAR(exc_val);
    return response;
}


static PyObject* compose_throw(PyComposeObject* self, PyObject* arg) {
    PyObject* exc_type = NULL, *exc_value = NULL, *exc_tb = NULL;

    if(!PyArg_ParseTuple(arg, "O|OO", &exc_type, &exc_value, &exc_tb)) //borrowed refs
        return NULL;

    if(PyExceptionInstance_Check(exc_type)) { // e.g. throw(Exception())
        exc_value = exc_type;
        exc_type = PyExceptionInstance_Class(exc_type); // borrowed ref
    }

    return _compose_go_with_frame(self, exc_type, exc_value, exc_tb);
}


static PyObject* compose_close(PyComposeObject* self) {
    _compose_go_with_frame(self, PyExc_GeneratorExit, NULL, NULL);

    if(PyErr_ExceptionMatches(PyExc_StopIteration) || PyErr_ExceptionMatches(PyExc_GeneratorExit)) {
        PyErr_Clear();	/* ignore these errors */
        Py_RETURN_NONE;
    }

    return NULL;
}

static void compose_del(PyObject* self) {
    if(!compose_close((PyComposeObject*) self))
        PyErr_WriteUnraisable(self);
}


static PyObject* compose_iternext(PyComposeObject* self) {
    return compose_send(self, Py_None);
}



////////// local() implementation //////////

PyObject* find_local_in_locals(PyFrameObject* frame, PyObject* name);


PyObject* find_local_in_compose(PyComposeObject* cmps, PyObject* name) {
    PyObject** generator = cmps->generators._end;

    while(--generator >= cmps->generators._base) {
        if(PyGen_Check(*generator)) {
            PyObject* result = find_local_in_locals(((PyGenObject*) * generator)->gi_frame, name);

            if(result != NULL)
                return result;

        } else {
            PyObject* result = find_local_in_compose((PyComposeObject*) * generator, name);

            if(result != NULL)
                return result;
        }
    }

    return NULL;
}


PyObject* find_local_in_locals(PyFrameObject* frame, PyObject* name) {
    int i;

    for(i = 0; i < PyTuple_Size(frame->f_code->co_varnames); i++) {
        PyObject* localVar = frame->f_localsplus[i];

        if(localVar) {
            PyObject* localName = PyTuple_GetItem(frame->f_code->co_varnames, i);

            if(_PyString_Eq(name, localName)) {
                Py_INCREF(localVar);
                return localVar;
            }
        }
    }

    if(frame->f_stacktop > frame->f_valuestack) {
        PyObject* o = frame->f_stacktop[-1];

        if(o->ob_type == &PyCompose_Type) {
            return find_local_in_compose((PyComposeObject*) o, name);
        }
    }

    return NULL;
}


PyObject* find_local_in_frame(PyFrameObject* frame, PyObject* name) {
    if(!frame) return NULL;

    PyObject* result = find_local_in_locals(frame, name);

    if(result)
        return result;

    return find_local_in_frame(frame->f_back, name);
}


PyObject* local(PyObject* self, PyObject* name) {
    PyFrameObject* frame = PyEval_GetFrame();
    PyObject* result = find_local_in_frame(frame, name);

    if(!result) {
        PyErr_SetString(PyExc_AttributeError, PyString_AsString(name));
        return NULL;
    }

    return result;
}



////////// tostring //////////

PyObject* py_getline;

PyObject* tostring(PyObject* self, PyObject* gen) {
    if(PyGen_Check(gen)) {
        PyFrameObject* frame = ((PyGenObject*)gen)->gi_frame;

        if(!frame)
            return PyString_FromString("<no frame>");

        int ilineno = PyCode_Addr2Line(frame->f_code, frame->f_lasti);
        PyObject* lineno = PyInt_FromLong(ilineno); // new ref
        PyObject* codeline = PyObject_CallFunctionObjArgs(py_getline,
                             frame->f_code->co_filename, lineno, NULL); // new ref
        Py_CLEAR(lineno);

        if(!codeline) return NULL;

        PyObject* codeline_stripped = PyObject_CallMethod(codeline, "strip", NULL); // new ref
        Py_CLEAR(codeline);

        if(!codeline_stripped) return NULL;

        PyObject* result =
            PyString_FromFormat("  File \"%s\", line %d, in %s\n    %s",
                                PyString_AsString(frame->f_code->co_filename),
                                ilineno, PyString_AsString(frame->f_code->co_name),
                                PyString_AsString(codeline_stripped)); // new ref
        Py_CLEAR(codeline_stripped);
        return result;

    } else if(gen->ob_type == &PyCompose_Type) {
        PyComposeObject* cmps = (PyComposeObject*) gen;
        PyObject* result = NULL;
        PyObject** generator = cmps->generators._base;

        while(generator < cmps->generators._end) {
            PyObject* s = tostring(NULL, *generator++);

            if(!result)
                result = s;

            else {
                PyString_ConcatAndDel(&result, PyString_FromString("\n"));
                PyString_ConcatAndDel(&result, s);
            }
        }

        return result;
    }

    PyErr_SetString(PyExc_TypeError, "tostring() expects generator");
    return NULL;
}



////////// compose Python Type //////////

static PyMethodDef compose_methods[] = {
    {"send", (PyCFunction) compose_send,  METH_O,       "Send arg into composed generator." },
    {"throw", (PyCFunction) compose_throw, METH_VARARGS, "Raise GeneratorExit in composed generator."},
    {"close", (PyCFunction) compose_close, METH_NOARGS,  "Throws exception in composed generator."},
    {NULL}	/* Sentinel */
};


PyTypeObject PyCompose_Type = {
    PyObject_HEAD_INIT(&PyType_Type)
    0,                                      /* ob_size */
    "compose",                              /* tp_name */
    sizeof(PyComposeObject),                /* tp_basicsize */
    0,                                      /* tp_itemsize */
    /* methods */
    (destructor)compose_dealloc,            /* tp_dealloc */
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
    (traverseproc)compose_traverse,         /* tp_traverse */
    (inquiry)compose_clear,                 /* tp_clear */
    0,                                      /* tp_richcompare */
    offsetof(PyComposeObject, weakreflist), /* tp_weaklistoffset */
    PyObject_SelfIter,                      /* tp_iter */
    (iternextfunc)compose_iternext,         /* tp_iternext */
    compose_methods,                        /* tp_methods */
    0,                                      /* tp_members */
    0,                                      /* tp_getset */
    0,                                      /* tp._base */
    0,                                      /* tp_dict */
    0,                                      /* tp_descr_get */
    0,                                      /* tp_descr_set */
    0,                                      /* tp_dictoffset */
    0,                                      /* tp_init */
    0,                                      /* tp_alloc */
    (newfunc)compose_new,                   /* tp_new */
    0,                                      /* tp_free */
    0,                                      /* tp_is_gc */
    0,                                      /* tp._bases */
    0,                                      /* tp_mro */
    0,                                      /* tp_cache */
    0,                                      /* tp_subclasses */
    0,                                      /* tp_weaklist */
    compose_del,                            /* tp_del */
};



////////// Module initialization //////////

static PyCodeObject* create_empty_code(void) {
    PyObject* py_srcfile = PyString_FromString(__FILE__);
    PyObject* py_funcname = PyString_FromString("compose");
    PyObject* empty_string = PyString_FromString("");
    PyObject* empty_tuple = PyTuple_New(0);
    PyCodeObject* code = PyCode_New(
                             0, 0, 1, 0,  // stacksize is 1
                             empty_string,
                             empty_tuple,
                             empty_tuple,
                             empty_tuple,
                             empty_tuple,
                             empty_tuple,
                             py_srcfile,
                             py_funcname,
                             __LINE__,
                             empty_string);
    return code;
}

int init_compose_c(PyObject* module) {

    PyObject* linecache = PyImport_ImportModule("linecache"); // new ref

    if(!linecache) {
        PyErr_Print();
        return 1;
    }

    PyObject* dict = PyModule_GetDict(linecache); // borrowed ref

    if(!dict) {
        Py_CLEAR(linecache);
        PyErr_Print();
        return 1;
    }

    py_getline = PyMapping_GetItemString(dict, "getline"); // new ref

    if(!py_getline) {
        Py_CLEAR(linecache);
        PyErr_Print();
        return 1;
    }

    py_code = create_empty_code();

    if(!py_code) {
        Py_CLEAR(linecache);
        Py_CLEAR(py_getline);
        PyErr_Print();
        return 1;
    }

    if(PyType_Ready(&PyCompose_Type) < 0) {
        Py_CLEAR(linecache);
        Py_CLEAR(py_getline);
        Py_CLEAR(py_code);
        PyErr_Print();
        return 1;
    }

    Py_INCREF(&PyCompose_Type);
    PyModule_AddObject(module, "compose", (PyObject*) &PyCompose_Type);

    Py_INCREF(&PyYield_Type);
    PyModule_AddObject(module, "Yield", (PyObject*) &PyYield_Type);

    return 0;
}



////////// Testing support //////////

static void assertTrue(const int condition, const char* msg) {
    if(!condition) {
        printf("Self-test (%s) FAIL: ", __FILE__);
        printf("%s\n", msg);
    }
}


PyObject* compose_selftest(PyObject* self, PyObject* null) {
    PyComposeObject c;
    _compose_initialize(&c);
    // test initial state of generator stack
    assertTrue(c.generators._base != NULL, "generator stack not allocated");
    assertTrue(c.generators._end == c.generators._base, "generator top of stack invalid");
    assertTrue(c.generators._size == INITIAL_STACK_SIZE, "invalid allocated stack size");
    // test pushing to generator stack
    Py_ssize_t refcount = Py_None->ob_refcnt;
    assertTrue(List.append(&c.generators, Py_None) == 1, "generators_push must return 1");
    assertTrue(Py_None->ob_refcnt == refcount + 1, "refcount not increased");
    assertTrue(c.generators._end == c.generators._base + 1, "stack top not increased");
    assertTrue(c.generators._base[0] == Py_None, "top of stack must be Py_None");
    int i;

    for(i = 0; i < INITIAL_STACK_SIZE * 3; i++)
        List.append(&c.generators, Py_None);

    assertTrue(c.generators._end - c.generators._base == 3 * INITIAL_STACK_SIZE + 1, "extending stack failed");
    assertTrue(c.generators._size == 2 * 2 * INITIAL_STACK_SIZE, "stack allocation failed");
    // test messages queue initial state
    assertTrue(List.empty(&c.messages), "messages not empty");
    assertTrue(0 == List.size(&c.messages), "initial queue size must be 0");
    // test append to messages queue
    refcount = Py_None->ob_refcnt;
    List.append(&c.messages, Py_None);
    assertTrue(1 == List.size(&c.messages), "now queue size must be 1");
    assertTrue(Py_None->ob_refcnt == refcount + 1, "messages_append did not increase ref count");
    assertTrue(!List.empty(&c.messages), "messages must not be empty");
    assertTrue(Py_None == List.next(&c.messages), "incorrect value from queue");
    // test next on messages queue
    assertTrue(0 == List.size(&c.messages), "now queue size must be 0 again");
    assertTrue(List.empty(&c.messages), "messages must be empty again");
    List.append(&c.messages, PyInt_FromLong(5));
    List.append(&c.messages, PyInt_FromLong(6));
    assertTrue(2 == List.size(&c.messages), "now queue size must be 2");
    assertTrue(PyInt_AsLong(List.next(&c.messages)) == 5, "incorrect value from queue");
    assertTrue(PyInt_AsLong(List.next(&c.messages)) == 6, "incorrect value from queue");
    // test wrap around on append
    compose_clear(&c);
    _compose_initialize(&c);

    for(i = 0; i < 1001 - 2; i++)                                     // 8
        List.append(&c.messages, PyInt_FromLong(i));

    assertTrue(i == List.size(&c.messages), "queue must be equals to i");
    int status = List.append(&c.messages, PyInt_FromLong(i));                    // 9
    assertTrue(i + 1 == List.size(&c.messages), "queue must be equals to i+1");
    assertTrue(status == 1, "0. status must be ok");
    status = List.append(&c.messages, PyInt_FromLong(i));                        // full!
    assertTrue(status == 0, "1. status of append must 0 (no room)");
    assertTrue(PyExc_RuntimeError == PyErr_Occurred(), "runtime exception must be set");
    PyErr_Clear();
    status = List.insert(&c.messages, PyInt_FromLong(99));
    assertTrue(status == 0, "2. status of insert must 0 (no room)");
    assertTrue(PyExc_RuntimeError == PyErr_Occurred(), "runtime exception must be set");
    PyErr_Clear();
    // test wrap around on insert
    compose_clear(&c);
    _compose_initialize(&c);
    status = List.insert(&c.messages, PyInt_FromLong(42));
    assertTrue(1 == List.size(&c.messages), "after insert queue must be equals to 1");
    assertTrue(status == 1, "status after first insert must be ok");
    status = List.insert(&c.messages, PyInt_FromLong(42));
    assertTrue(2 == List.size(&c.messages), "after insert queue must be equals to 2");
    assertTrue(status == 1, "status after second insert must be ok");

    assertTrue(2 == List.size(&c.messages), "start condition for next test");
    for(i = 2; i < 1000; i++) {
        assertTrue(i == List.size(&c.messages), "size must equal inserts");
        status = List.insert(&c.messages, PyInt_FromLong(i));
    }

    assertTrue(1000 == List.size(&c.messages), "after insert queue must be equals to 1001");
    assertTrue(status == 1, "status after 1000 inserts must be ok");
    status = List.insert(&c.messages, PyInt_FromLong(4242));
    assertTrue(status == 0, "status after 10 inserts must be error");
    assertTrue(PyExc_RuntimeError == PyErr_Occurred(), "runtime exception must be set here too");
    PyErr_Clear();
    // test wrap around on next
    compose_clear(&c);
    _compose_initialize(&c);
    List.insert(&c.messages, PyInt_FromLong(1000)); // wrap backward
    List.append(&c.messages, PyInt_FromLong(1001)); // wrap forward
    PyObject* o = List.next(&c.messages);           // end
    assertTrue(1000 == PyInt_AsLong(o), "expected 1000");
    assertTrue(2 == o->ob_refcnt, "refcount on next must be 2");
    o = List.next(&c.messages);                     // wrap
    assertTrue(1001 == PyInt_AsLong(o), "expected 1001");
    assertTrue(2 == o->ob_refcnt, "refcount on next must be 2");
    o = List.next(&c.messages);
    assertTrue(NULL == o, "error condition on next: empty");
    assertTrue(PyExc_RuntimeError == PyErr_Occurred(), "no runtime exception no next on empty queue");
    PyErr_Clear();
    compose_clear(&c);
    Py_RETURN_NONE;
}
