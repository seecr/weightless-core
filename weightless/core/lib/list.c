#include "list.h"

static void List_init(MyList* self, int size) {
    self->_base = (PyObject**) calloc(size, sizeof(PyObject*));
    self->_begin = self->_base;
    self->_end = self->_base;
    self->_size = size;
}

static int List_size(MyList* self) {
    // only reliable if and when the queue is NOT full !!
    int size = self->_end - self->_begin;
    return size < 0 ? size + self->_size : size;
}

static int List_empty(MyList* self) {
    return self->_begin == self->_end;
}

static PyObject* List_next(MyList* self) {
    if(List_empty(self)) {
        PyErr_SetString(PyExc_RuntimeError, "internal error: empty messages queue (compose)");
        return NULL;
    }

    PyObject* result = *self->_begin;
    *self->_begin++ = NULL;

    if(self->_begin == self->_base + self->_size)
        self->_begin = self->_base;

    return result;
}


static int List_append(MyList* self, PyObject* message) {
    if(List_size(self) >= self->_size - 1) {   // keep on entry free at all times
        PyErr_SetString(PyExc_RuntimeError, "maximum return values exceeded (compose)");
        return 0;
    }

    *self->_end++ = message;
    Py_INCREF(message);

    if(self->_end == self->_base + self->_size)
        self->_end = self->_base;

    return 1;
}


static int List_insert(MyList* self, PyObject* message) {
    if(List_size(self) >= self->_size - 1) {
        PyErr_SetString(PyExc_RuntimeError, "maximum return values exceeded (compose)");
        return 0;
    }

    if(self->_begin == self->_base)
        self->_begin = self->_base + self->_size;

    *--self->_begin = message;
    Py_INCREF(message);
    return 1;
}

#define MAX_STACK_SIZE 1000

static int List_push(MyList* self, PyObject* generator) {
    long current_stack_use = self->_end - self->_base;

    if(current_stack_use >= self->_size) {
        if(self->_size >= MAX_STACK_SIZE) {
            PyErr_SetString(PyExc_RuntimeError, "maximum recursion depth exceeded (compose)");
            return 0;
        }

        self->_size *= 2;

        if(self->_size > MAX_STACK_SIZE)
            self->_size = MAX_STACK_SIZE;

        int offset_begin = self->_begin - self->_base;
        PyObject** newstack = realloc(self->_base, self->_size * sizeof(PyObject*));
        self->_base = newstack;
        self->_begin = newstack + offset_begin;
        self->_end = newstack + current_stack_use;
    }

    *self->_end++ = generator;
    Py_INCREF(generator);
    return 1;
}


static PyObject* List_top(MyList* self) {
    PyObject* result = *(self->_end - 1);
    Py_INCREF(result);
    return result;
}


static PyObject* List_pop(MyList* self) {
    PyObject* result = *(--self->_end);
    *self->_end = NULL;
    return result;
}


static int List_gc_visit(MyList* self, visitproc visit, void* arg) {
    PyObject** p;
    if(self->_end >= self->_begin) // buffer is circular
        for(p = self->_begin; p < self->_end; p++)
            Py_VISIT(*p);
    else {
        for(p = self->_begin; p < self->_base + self->_size; p++)
            Py_VISIT(*p);
        for(p = self->_base; p < self->_end; p++)
            Py_VISIT(*p);
    }
    return 0;
}

static int List_gc_clear(MyList* self) {
    PyObject** p;
    if(self->_end >= self->_begin) // buffer is circular
        for(p = self->_begin; p < self->_end; p++)
            Py_DECREF(*p);
    else {
        for(p = self->_begin; p < self->_base + self->_size; p++)
            Py_DECREF(*p);
        for(p = self->_base; p < self->_end; p++)
            Py_DECREF(*p);
    }
    free(self->_base);
    self->_base = NULL;
    return 0;
}

_ListType List = { 
    List_init,
    List_size,
    List_empty, 
    List_next,
    List_append,
    List_insert,
    List_push,
    List_top,
    List_pop,
    List_gc_visit,
    List_gc_clear,
};  

