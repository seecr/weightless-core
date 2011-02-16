#!/usr/bin/env python
## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    See http://weightless.io
#    Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
#
#    This file is part of Weightless
#
#    Weightless is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    Weightless is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Weightless; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##
from distutils.core import setup
from distutils.extension import Extension

setup(
    name='weightless-core',
    version='%VERSION%',
    packages=[
        'weightless', 
        'weightless.core', 
        'weightless.core.compose', 
        'weightless.core.utils',
        'weightless.http', 
        'weightless.io',
    ],
    url='http://www.weightless.io',
    author='Seek You Too',
    author_email='info@cq2.nl',
    description='Weightless is a High Performance Asynchronous Networking Library.',
    long_description='Weightless is a High Performance Asynchronous Networking Library.',
    license='GNU Public License',
    platforms=['linux'],
    ext_modules=[
        Extension("weightless.core.compose._compose_c", [
            "weightless/core/compose/_compose.c"
            ],
        extra_compile_args = ['-O0'],
        extra_link_args = ['-O0']
        )
    ]
)

