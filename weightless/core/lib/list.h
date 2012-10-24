#include <Python.h>

typedef struct {
     PyObject** _base;
     PyObject** _start;
     PyObject** _end;
     int        _size;
} MyList;

typedef struct {
    void      (*init)    (MyList* self, int size);
    int       (*size)    (MyList* self);
    int       (*empty)   (MyList* self);
    PyObject* (*next)    (MyList* self);
    int       (*append)  (MyList* self, PyObject* o);
    int       (*insert)  (MyList* self, PyObject* o);
    int       (*gc_visit)(MyList* self, visitproc visit, void* arg);
    int       (*gc_clear)(MyList* self);
} _ListType;

extern _ListType List;

