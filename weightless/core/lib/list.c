#include "list.h"

static void List_init(MyList* self, int size) {
    self->_base = (PyObject**) calloc(size, sizeof(PyObject*));
    self->_start = self->_base;
    self->_end = self->_base;
    self->_size = size;
}

static int List_size(MyList* self) {
    // only reliable if and when the queue is NOT full !!
    int size = self->_end - self->_start;
    return size < 0 ? size + self->_size : size;
}

static int List_empty(MyList* self) {
    return self->_start == self->_end;
}

static PyObject* List_next(MyList* self) {
    if(List_empty(self)) {
        PyErr_SetString(PyExc_RuntimeError, "internal error: empty messages queue (compose)");
        return NULL;
    }

    PyObject* result = *self->_start;
    *self->_start++ = NULL;

    if(self->_start == self->_base + self->_size)
        self->_start = self->_base;

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

    if(self->_start == self->_base)
        self->_start = self->_base + self->_size;

    *--self->_start = message;
    Py_INCREF(message);
    return 1;
}

static int List_gc_visit(MyList* self, visitproc visit, void* arg) {
    PyObject** p;
    for(p = self->_base; p < self->_base + self->_size; p++)
        Py_VISIT(*p);
    return 0;
}

static int List_gc_clear(MyList* self) {
    while(self->_base && !List_empty(self)) {
        PyObject* p = List_next(self);
        Py_DECREF(p); 
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
    List_gc_visit,
    List_gc_clear
};  

