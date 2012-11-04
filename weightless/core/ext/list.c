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

static PyObject* List_get(MyList* self, int i) {
    //printf("   %d %d %d %d\n", i, self->_begin - self->_base, self->_end - self->_base, self->_size);
    if(self->_begin + i >= self->_base + self->_size)
        return self->_base[i - (self->_base + self->_size - self->_begin)];
    return self->_begin[i];
}

#define MAX_STACK_SIZE 1001 // from maxrecursiondepth
static void _List_grow(MyList* self) {
    int new_size = self->_size * 2;
    if(new_size > MAX_STACK_SIZE)
        new_size = MAX_STACK_SIZE;

    //printf("   %d %d\n", self->_begin - self->_base, self->_end - self->_base);
    if(self->_begin <= self->_end) {
        //printf("   growing linear to %d\n", new_size);
        int offset_begin = self->_begin - self->_base;
        int offset_end = self->_end - self->_base;
        PyObject** newstack = realloc(self->_base, new_size * sizeof(PyObject*));
        self->_base = newstack;
        self->_begin = newstack + offset_begin;
        self->_end = newstack + offset_end;
    } else {
        //printf("   growing circular to %d\n", new_size);
        int offset_end = self->_base - self->_end;
        int offset_begin = self->_size - (self->_begin -self->_base);
        PyObject** newstack = realloc(self->_base, new_size * sizeof(PyObject*));
        memmove(newstack + new_size - offset_begin, newstack + (self->_begin - self->_base), offset_begin * sizeof(PyObject*));
        self->_base = newstack;
        self->_begin = newstack + new_size - offset_begin;
        self->_end = newstack + offset_end;
    }
    //printf("   %d %d\n", self->_begin - self->_base, self->_end - self->_base);
    self->_size = new_size;
}


static int List_insert(MyList* self, PyObject* message) {
    if(List_size(self) >= self->_size - 1) {
        if(self->_size >= MAX_STACK_SIZE) {
            PyErr_SetString(PyExc_RuntimeError, "maximum return values exceeded (compose)");
            return 0;
        }
        _List_grow(self);
    }

    if(self->_begin == self->_base)
        self->_begin = self->_base + self->_size;

    *--self->_begin = message;
    Py_INCREF(message);
    return 1;
}


static int List_append(MyList* self, PyObject* o) {
    int old_size = List_size(self);

    if(old_size >= self->_size - 1) {
        if(self->_size >= MAX_STACK_SIZE) {
            PyErr_SetString(PyExc_RuntimeError, "maximum recursion depth exceeded (compose)");
            return 0;
        }
        _List_grow(self);
    }

    *self->_end++ = o;
    Py_INCREF(o);
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
    List_get,
    List_insert,
    List_append,
    List_top,
    List_pop,
    List_gc_visit,
    List_gc_clear,
};  


////////// Testing support //////////

static void assertTrue(const int condition, const char* msg) {
    if(!condition) {
        printf("(%s) FAIL: ", __FILE__);
        printf("%s\n", msg);
    }
}




PyObject* List_selftest(PyObject* self, PyObject* null) {
    MyList l;
    List.init(&l, 1);
    assertTrue(0 == List.size(&l), "10. initial size must be 0");
    int rc = Py_None->ob_refcnt;
    List.append(&l, Py_None);
    assertTrue(rc+1 == Py_None->ob_refcnt, "15. ref count must be increased");
    assertTrue(1 == List.size(&l), "20. now size must be 1");
    assertTrue(Py_None == List.get(&l, 0), "21. get back same object");
    List.append(&l, PyInt_FromLong(5));
    assertTrue(2 == List.size(&l), "30. now size must be 2");
    assertTrue(Py_None == List.get(&l, 0), "21. get back same object at 0");
    assertTrue(5L == PyInt_AsLong(List.get(&l, 1)), "31. get back same object at 1");
    List.append(&l, PyInt_FromLong(87));
    List.append(&l, PyInt_FromLong(45));
    assertTrue(4 == List.size(&l), "40. now size must be 4");
    assertTrue(87L == PyInt_AsLong(List.get(&l, 2)), "41. get back same object at 2");
    assertTrue(45L == PyInt_AsLong(List.get(&l, 3)), "42. get back same object at 3");
    int i;
    for(i = 5; i <= 1000; i++)
        List.append(&l, PyInt_FromLong(i));
    assertTrue(1000 == List.size(&l), "50. cap on size: 1000");
    assertTrue(1000L == PyInt_AsLong(List.get(&l, 999)), "52. get back same object at 999");

    List.init(&l, 1);
    assertTrue(0 == List.size(&l), "60. reinit");
    PyObject* o =  PyInt_FromLong(76);
    rc = o->ob_refcnt;
    List.insert(&l, o);
    assertTrue(rc+1 == o->ob_refcnt, "70. ref count must be increased");
    assertTrue(1 == List.size(&l), "80. now size must be 1");
    assertTrue(o == List.get(&l, 0), "82. get back object at 0");
    List.insert(&l,  PyInt_FromLong(42));
    assertTrue(2 == List.size(&l), "90. now size must be 2");
    assertTrue(42L == PyInt_AsLong(List.get(&l, 0)), "91. get back same object at 0");
    assertTrue(76L == PyInt_AsLong(List.get(&l, 1)), "92. get back same object at 1");
    List.insert(&l, PyInt_FromLong(34));
    assertTrue(3 == List.size(&l), "100. now size must be 3");
    assertTrue(34L == PyInt_AsLong(List.get(&l, 0)), "93. get back same object at 0");
    assertTrue(42L == PyInt_AsLong(List.get(&l, 1)), "94. get back same object at 1");
    assertTrue(76L == PyInt_AsLong(List.get(&l, 2)), "95. get back same object at 2");
    List.append(&l, PyInt_FromLong(53));
    assertTrue(4 == List.size(&l), "110. now size must be 4");
    assertTrue(53L == PyInt_AsLong(List.get(&l, 3)), "111. get back same object at 3");
    List.append(&l, PyInt_FromLong(99));
    assertTrue(5 == List.size(&l), "120. now size must be 5");
    assertTrue(34L == PyInt_AsLong(List.get(&l, 0)), "121. get back same object at 0");
    assertTrue(42L == PyInt_AsLong(List.get(&l, 1)), "122. get back same object at 1");
    assertTrue(76L == PyInt_AsLong(List.get(&l, 2)), "123. get back same object at 2");
    assertTrue(53L == PyInt_AsLong(List.get(&l, 3)), "124. get back same object at 3");
    assertTrue(99L == PyInt_AsLong(List.get(&l, 4)), "125. get back same object at 4");
    Py_RETURN_NONE;
}
