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
    version='0.5.2.3-seecr-1',
    packages=[
        'weightless', 
        'weightless.core', 
        'weightless.core.compose', 
        'weightless.core.utils',
        'weightless.http', 
        'weightless.httpng', 
        'weightless.io',
		'weightless.examples',
    ],
    url='http://www.weightless.io',
    author='Erik J. Groeneveld',
    author_email='erik@seecr.nl',
    description='Weightless data-processing with coroutines',
    long_description="""
Weightless presents a way to implement data-processing programs, such as web-servers, with coroutines in Python. The results are lightweight, efficient and readable programs without call-backs, threads and buffering. Weightless supports:
1. decomposing programs into coroutines using compose
2. creating pipelines using the observer pattern
3. connecting file descriptors (sockets etc) to pipelines using gio
""",
    license='GNU Public License',
    platforms=['cpython'],
    ext_modules=[
        Extension("weightless.core.compose._compose_c", [
            "weightless/core/compose/_compose.c"
            ],
        )
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Topic :: Communications',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Internet :: WWW/HTTP :: HTTP Servers',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Text Processing'
        ],

)

