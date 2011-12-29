/* begin license *
 *
 *     Weightless is a High Performance Asynchronous Networking Library
 *     See http://weightless.io
 *     Copyright (C) 2009-2011 Seek You Too (CQ2) http://www.cq2.nl
 *
 *     This file is part of Weightless
 *
 *     Weightless is free software; you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation; either version 2 of the License, or
 *     (at your option) any later version.
 *
 *     Weightless is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with Weightless; if not, write to the Free Software
 *     Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
 *
 * end license */

/* This code is formatted with:
 * astyle --style=java --indent-namespaces --break-blocks=all --pad-oper --unpad-paren --delete-empty-lines --align-pointer=type
 */

#include <Python.h>
#include <frameobject.h>
#include <structmember.h>



////////// Python Object and Type structures //////////

typedef struct {
    PyObject_HEAD
    int        expect_data;
    PyObject** generators_base;
    PyObject** generators_top;
    int        generators_allocated;
    PyObject** messages_base;
    PyObject** messages_start;
    PyObject** messages_end;
    PyObject*  sidekick;
    PyFrameObject* frame;
    PyObject*  weakreflist;
} PyComposeObject;

PyAPI_DATA(PyTypeObject) PyCompose_Type;



////////// Generator Stack //////////

#define INITIAL_STACK_SIZE 10
#define MAX_STACK_SIZE 1000

static int generators_push(PyComposeObject* self, PyObject* generator) {
    int current_stack_use = self->generators_top - self->generators_base;

    if(current_stack_use >= self->generators_allocated) {
        if(self->generators_allocated >= MAX_STACK_SIZE) {
            PyErr_SetString(PyExc_RuntimeError, "maximum recursion depth exceeded (compose)");
            return 0;
        }

        self->generators_allocated *= 2;

        if(self->generators_allocated > MAX_STACK_SIZE)
            self->generators_allocated = MAX_STACK_SIZE;

        PyObject** newstack = realloc(self->generators_base, self->generators_allocated * sizeof(PyObject*));
        self->generators_base = newstack;
        self->generators_top = newstack + current_stack_use;
    }

    *self->generators_top++ = generator;
    Py_INCREF(generator);
    return 1;
}



////////// Messages Queue //////////

#define QUEUE_SIZE 10

static int messages_empty(PyComposeObject* self) {
    return self->messages_start == self->messages_end;
}


static int _messages_size(PyComposeObject* self) {
    // only reliable if and when the queue is NOT full !!
    int size = self->messages_end - self->messages_start;
    return size < 0 ? size + QUEUE_SIZE : size;
}


static PyObject* messages_next(PyComposeObject* self) {
    if(messages_empty(self)) {
        PyErr_SetString(PyExc_RuntimeError, "internal error: empty messages queue (compose)");
        return NULL;
    }

    PyObject* result = *self->messages_start;
    *self->messages_start++ = NULL;

    if(self->messages_start == self->messages_base + QUEUE_SIZE)
        self->messages_start = self->messages_base;

    return result;
}


static int messages_append(PyComposeObject* self, PyObject* message) {
    if(_messages_size(self) >= QUEUE_SIZE - 1) {   // keep on entry free at all times
        PyErr_SetString(PyExc_RuntimeError, "maximum return values exceeded (compose)");
        return 0;
    }

    *self->messages_end++ = message;
    Py_INCREF(message);

    if(self->messages_end == self->messages_base + QUEUE_SIZE)
        self->messages_end = self->messages_base;

    return 1;
}


static int messages_insert(PyComposeObject* self, PyObject* message) {
    if(_messages_size(self) >= QUEUE_SIZE - 1) {
        PyErr_SetString(PyExc_RuntimeError, "maximum return values exceeded (compose)");
        return 0;
    }

    if(self->messages_start == self->messages_base)
        self->messages_start = self->messages_base + QUEUE_SIZE;

    *--self->messages_start = message;
    Py_INCREF(message);
    return 1;
}



////////// Garbage Collector Support //////////

static int compose_traverse(PyComposeObject* self, visitproc visit, void* arg) {
    PyObject** p;

    for(p = self->generators_base; p < self->generators_top; p++)
        Py_VISIT(*p);

    for(p = self->messages_base; p < self->messages_base + QUEUE_SIZE; p++)
        Py_VISIT(*p);

    Py_VISIT(self->sidekick);
    Py_VISIT(self->frame);
    return 0;
}


static int compose_clear(PyComposeObject* self) {
    while(self->generators_base && --self->generators_top >= self->generators_base)
        Py_CLEAR(*self->generators_top);

    free(self->generators_base);
    self->generators_base = NULL;

    while(self->messages_base && !messages_empty(self)) {
        PyObject* p = messages_next(self);
        Py_DECREF(p);
    }

    free(self->messages_base);
    self->messages_base = NULL;
    Py_CLEAR(self->sidekick);
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

static int PyCompose_Check(PyObject* obj) {
    return PyObject_Type(obj) == (PyObject*) &PyCompose_Type;
}


static PyCodeObject* py_code;

static void _compose_initialize(PyComposeObject* cmps) {
    cmps->expect_data = 0;
    cmps->generators_allocated = INITIAL_STACK_SIZE;
    cmps->generators_base = (PyObject**) malloc(cmps->generators_allocated * sizeof(PyObject*));
    cmps->generators_top = cmps->generators_base;
    cmps->messages_base = (PyObject**) calloc(QUEUE_SIZE, sizeof(PyObject*));
    cmps->messages_start = cmps->messages_base;
    cmps->messages_end = cmps->messages_base;
    cmps->sidekick = NULL;
    cmps->weakreflist = NULL;
    cmps->frame = PyFrame_New(PyThreadState_GET(), py_code, PyEval_GetGlobals(), NULL);
    Py_CLEAR(cmps->frame->f_back);
}


static PyObject* compose_new(PyObject* type, PyObject* args, PyObject* kwargs) {
    static char* argnames[] = {"initial", "sidekick"};
    PyObject* initial = NULL;
    PyObject* sidekick = NULL;

    if(!PyArg_ParseTupleAndKeywords(                            // borrowed refs
                args, kwargs, "O|O:compose", argnames,
                &initial, &sidekick)) return NULL;

    if(!PyGen_Check(initial) && !PyCompose_Check(initial)) {
        PyErr_SetString(PyExc_TypeError, "compose() argument 1 must be generator");
        return NULL;
    }

    PyComposeObject* cmps = PyObject_GC_New(PyComposeObject, &PyCompose_Type);

    if(cmps == NULL)
        return NULL;

    _compose_initialize((PyComposeObject*) cmps);

    if(!generators_push(cmps, initial)) return NULL;

    if(sidekick) {
        Py_INCREF(sidekick);
        cmps->sidekick = sidekick;
    }

    PyObject_GC_Track(cmps);
    return (PyObject*) cmps;
}


static int _compose_handle_stopiteration(PyComposeObject* self, PyObject* exc_value) {
    PyObject* args = exc_value
                     ? PyObject_GetAttrString(exc_value, "args") // new ref
                     : NULL;

    if(args && PyTuple_CheckExact(args) && PyObject_IsTrue(args)) {
        int i;

        for(i = PyTuple_Size(args) - 1; i >= 0; i--)
            if(!messages_insert(self, PyTuple_GET_ITEM(args, i))) {
                Py_CLEAR(args);
                return 0;
            }

        Py_CLEAR(args);

    } else
        messages_insert(self, Py_None);

    return 1;
}


static int generator_invalid(PyObject* gen) {
    PyFrameObject* frame = ((PyGenObject*)gen)->gi_frame;

    if(!frame) {
        PyErr_SetString(PyExc_AssertionError, "Generator is exhausted.");
        return 1;
    }

    if(frame->f_lasti != -1) {  // fresh generator, see genobject.c
        PyErr_SetString(PyExc_AssertionError, "Generator already used.");
        return 1;
    }

    return 0;
}


static PyObject* _compose_go(PyComposeObject* self, PyObject* exc_type, PyObject* exc_value, PyObject* exc_tb) {
    Py_XINCREF(exc_type);
    Py_XINCREF(exc_value);
    Py_XINCREF(exc_tb);

    while(self->generators_top > self->generators_base) {
        PyObject* generator = *(self->generators_top - 1); // take over ownership from stack
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
            message = messages_next(self); // new ref
            response = PyObject_CallMethod(generator, "send", "O", message); // new ref
            Py_CLEAR(message);
        }

        if(response) { // normal response
            if(PyGen_Check(response) || PyCompose_Check(response)) {
                if(!generators_push(self, response)) {
                    Py_CLEAR(response);
                    return NULL;
                }

                if(PyGen_Check(response) && generator_invalid(response)) {
                    Py_CLEAR(response);
                    return NULL;
                }

                messages_insert(self, Py_None);

            } else if(self->sidekick && self->sidekick != Py_None && PyCallable_Check(response)) {
                messages_insert(self, Py_None);
                PyObject* r = PyObject_CallFunctionObjArgs(response, self->sidekick, NULL);

                if(!r)
                    PyErr_Fetch(&exc_type, &exc_value, &exc_tb); // new refs

                Py_CLEAR(r);

            } else if(response != Py_None || messages_empty(self)) {
                self->expect_data = response == Py_None;
                return response;
            }

            Py_CLEAR(response);

        } else { // exception thrown
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
            *self->generators_top-- = NULL;
        }
    }

    if(exc_type) {
        PyErr_Restore(exc_type, exc_value, exc_tb); // steals refs
        exc_type = exc_value = exc_tb = NULL;
        return NULL;
    }

    // if any messages are left, 'return' them by StopIteration
    int n = _messages_size(self);
    if (n) {
        PyObject* args = PyTuple_New(n); // new ref
        int i;
        for (i = 0; i < n; i++) {
            PyTuple_SetItem(args, i, messages_next(self)); // steals ref
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
    PyObject* response = _compose_go(self, exc_type, exc_value, exc_tb);
    self->frame->f_stacktop--;
    Py_CLEAR(self->frame->f_back);
    tstate->frame = tstate_frame;
    return response;
}


static PyObject* compose_send(PyComposeObject* self, PyObject* message) {
    if(!self->expect_data && message != Py_None) {
        PyErr_SetString(PyExc_AssertionError, "Cannot accept data. First send None.");
        return NULL;
    }

    messages_insert(self, message);

    return _compose_go_with_frame(self, NULL, NULL, NULL);
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
    PyObject** generator = cmps->generators_top;

    while(--generator >= cmps->generators_base) {
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
        PyObject** generator = cmps->generators_base;

        while(generator < cmps->generators_top) {
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

static PyObject* _selftest(PyObject* self, PyObject* null);


static PyMethodDef compose_functionslist[] = {
    {"local", local, METH_O, "Finds a local variable on the call stack including compose'd generators."},
    {"tostring", tostring, METH_O, "Returns a string representation of a genarator."},
    {"_selftest", _selftest, METH_NOARGS, "runs self test"},
    {NULL} /* Sentinel */
};


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
    0,                                      /* tp_base */
    0,                                      /* tp_dict */
    0,                                      /* tp_descr_get */
    0,                                      /* tp_descr_set */
    0,                                      /* tp_dictoffset */
    0,                                      /* tp_init */
    0,                                      /* tp_alloc */
    (newfunc)compose_new,                   /* tp_new */
    0,                                      /* tp_free */
    0,                                      /* tp_is_gc */
    0,                                      /* tp_bases */
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

PyMODINIT_FUNC init_compose_c(void) {
    PyObject* linecache = PyImport_ImportModule("linecache"); // new ref

    if(!linecache) {
        PyErr_Print();
        return;
    }

    PyObject* dict = PyModule_GetDict(linecache); // borrowed ref

    if(!dict) {
        Py_CLEAR(linecache);
        PyErr_Print();
        return;
    }

    py_getline = PyMapping_GetItemString(dict, "getline"); // new ref

    if(!py_getline) {
        Py_CLEAR(linecache);
        PyErr_Print();
        return;
    }

    py_code = create_empty_code();

    if(!py_code) {
        Py_CLEAR(linecache);
        Py_CLEAR(py_getline);
        PyErr_Print();
        return;
    }

    if(PyType_Ready(&PyCompose_Type) < 0) {
        Py_CLEAR(linecache);
        Py_CLEAR(py_getline);
        Py_CLEAR(py_code);
        PyErr_Print();
        return;
    }

    PyObject* module = Py_InitModule3("_compose_c", compose_functionslist, "fast compose");

    if(!module) {
        Py_CLEAR(linecache);
        Py_CLEAR(py_getline);
        Py_CLEAR(py_code);
        PyErr_Print();
        return;
    }

    Py_INCREF(&PyCompose_Type);
    PyModule_AddObject(module, "compose", (PyObject*) &PyCompose_Type);
}



////////// Testing support //////////

void assertTrue(const int condition, const char* msg) {
    if(!condition) {
        printf("Self-test (%s) FAIL: ", __FILE__);
        printf(msg);
        printf("\n");
    }
}


static PyObject* _selftest(PyObject* self, PyObject* null) {
    PyComposeObject c;
    _compose_initialize(&c);
    // test initial state of generator stack
    assertTrue(c.generators_base != NULL, "generator stack not allocated");
    assertTrue(c.generators_top == c.generators_base, "generator top of stack invalid");
    assertTrue(c.generators_allocated == INITIAL_STACK_SIZE, "invalid allocated stack size");
    // test pushing to generator stack
    Py_ssize_t refcount = Py_None->ob_refcnt;
    assertTrue(generators_push(&c, Py_None) == 1, "generators_push must return 1");
    assertTrue(Py_None->ob_refcnt == refcount + 1, "refcount not increased");
    assertTrue(c.generators_top == c.generators_base + 1, "stack top not increased");
    assertTrue(c.generators_base[0] == Py_None, "top of stack must be Py_None");
    int i;

    for(i = 0; i < INITIAL_STACK_SIZE * 3; i++)
        generators_push(&c, Py_None);

    assertTrue(c.generators_top - c.generators_base == 3 * INITIAL_STACK_SIZE + 1, "extending stack failed");
    assertTrue(c.generators_allocated == 2 * 2 * INITIAL_STACK_SIZE, "stack allocation failed");
    // test messages queue initial state
    assertTrue(messages_empty(&c), "messages not empty");
    assertTrue(0 == _messages_size(&c), "initial queue size must be 0");
    // test append to messages queue
    refcount = Py_None->ob_refcnt;
    messages_append(&c, Py_None);
    assertTrue(1 == _messages_size(&c), "now queue size must be 1");
    assertTrue(Py_None->ob_refcnt == refcount + 1, "messages_append did not increase ref count");
    assertTrue(!messages_empty(&c), "messages must not be empty");
    assertTrue(Py_None == messages_next(&c), "incorrect value from queue");
    // test next on messages queue
    assertTrue(0 == _messages_size(&c), "now queue size must be 0 again");
    assertTrue(messages_empty(&c), "messages must be empty again");
    messages_append(&c, PyInt_FromLong(5));
    messages_append(&c, PyInt_FromLong(6));
    assertTrue(2 == _messages_size(&c), "now queue size must be 2");
    assertTrue(PyInt_AsLong(messages_next(&c)) == 5, "incorrect value from queue");
    assertTrue(PyInt_AsLong(messages_next(&c)) == 6, "incorrect value from queue");
    // test wrap around on append
    compose_clear(&c);
    _compose_initialize(&c);

    for(i = 0; i < QUEUE_SIZE - 2; i++)                                     // 8
        messages_append(&c, PyInt_FromLong(i));

    assertTrue(i == _messages_size(&c), "queue must be equals to i");
    int status = messages_append(&c, PyInt_FromLong(i));                    // 9
    assertTrue(i + 1 == _messages_size(&c), "queue must be equals to i+1");
    assertTrue(status == 1, "status must be ok");
    status = messages_append(&c, PyInt_FromLong(i));                        // full!
    assertTrue(status == 0, "status of append must 0 (no room)");
    assertTrue(PyExc_RuntimeError == PyErr_Occurred(), "runtime exception must be set");
    PyErr_Clear();
    status = messages_insert(&c, PyInt_FromLong(99));
    assertTrue(status == 0, "status of insert must 0 (no room)");
    assertTrue(PyExc_RuntimeError == PyErr_Occurred(), "runtime exception must be set");
    PyErr_Clear();
    // test wrap around on insert
    compose_clear(&c);
    _compose_initialize(&c);
    status = messages_insert(&c, PyInt_FromLong(42));
    assertTrue(1 == _messages_size(&c), "after insert queue must be equals to 1");
    assertTrue(status == 1, "status after first insert must be ok");
    status = messages_insert(&c, PyInt_FromLong(42));
    assertTrue(2 == _messages_size(&c), "after insert queue must be equals to 2");
    assertTrue(status == 1, "status after second insert must be ok");

    for(i = 0; i < QUEUE_SIZE - 3; i++)
        status = messages_insert(&c, PyInt_FromLong(i));

    assertTrue(9 == _messages_size(&c), "after insert queue must be equals to 9");
    assertTrue(status == 1, "status after 9 inserts must be ok");
    status = messages_insert(&c, PyInt_FromLong(4242));
    assertTrue(status == 0, "status after 10 inserts must be error");
    assertTrue(PyExc_RuntimeError == PyErr_Occurred(), "runtime exception must be set here too");
    PyErr_Clear();
    // test wrap around on next
    compose_clear(&c);
    _compose_initialize(&c);
    messages_insert(&c, PyInt_FromLong(1000)); // wrap backward
    messages_append(&c, PyInt_FromLong(1001)); // wrap forward
    PyObject* o = messages_next(&c);           // end
    assertTrue(1000 == PyInt_AsLong(o), "expected 1000");
    assertTrue(2 == o->ob_refcnt, "refcount on next must be 2");
    o = messages_next(&c);                     // wrap
    assertTrue(1001 == PyInt_AsLong(o), "expected 1001");
    assertTrue(2 == o->ob_refcnt, "refcount on next must be 2");
    o = messages_next(&c);
    assertTrue(NULL == o, "error condition on next: empty");
    assertTrue(PyExc_RuntimeError == PyErr_Occurred(), "no runtime exception no next on empty queue");
    PyErr_Clear();
    compose_clear(&c);
    Py_RETURN_NONE;
}

