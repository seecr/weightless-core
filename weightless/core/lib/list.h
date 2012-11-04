#include <Python.h>

typedef struct {
     PyObject** _base;
     PyObject** _begin;
     PyObject** _end;
     int        _size;
} MyList;

typedef struct {
    void      (*init)    (MyList* self, int size);
    int       (*size)    (MyList* self);
    int       (*empty)   (MyList* self);
    PyObject* (*next)    (MyList* self);
    PyObject* (*get)     (MyList* self, int index);
    int       (*insert)  (MyList* self, PyObject* o);
    int       (*append)  (MyList* self, PyObject* o);
    PyObject* (*top)     (MyList* self);
    PyObject* (*pop)     (MyList* self);
    int       (*gc_visit)(MyList* self, visitproc visit, void* arg);
    int       (*gc_clear)(MyList* self);
} _ListType;

extern _ListType List;

PyObject* List_selftest(PyObject* self, PyObject* null);
