/* begin license *
 *
 * "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
 *
 * Copyright (C) 2013 Seecr (Seek You Too B.V.) http://seecr.nl
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

#include <Python.h>

#ifndef __compose_h__
#define __compose_h__

int init_compose(PyObject* module);

PyObject* compose_selftest(PyObject* self, PyObject* null);

PyObject* local(PyObject* self, PyObject* name);
PyObject* tostring(PyObject* self, PyObject* gen);
int PyCompose_Check(PyObject* o);

#endif
