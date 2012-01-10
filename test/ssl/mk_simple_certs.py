#!/usr/bin/env python2.5
## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    See http://weightless.io
#    Copyright (C) 2009-2010 Seek You Too (CQ2) http://www.cq2.nl
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

from OpenSSL import crypto
from certgen import createKeyPair, createCertRequest, createCertificate, TYPE_RSA

from sys import stdin, argv
from os.path import join


def generateIn(directory):
    cakey = createKeyPair(TYPE_RSA, 1024)
    careq = createCertRequest(cakey, CN='Certificate Authority')
    cacert = createCertificate(careq, (careq, cakey), 0, (0, 60*60*24*365*5)) # five years
    #open(join(directory, 'CA.pkey'), 'w').write(crypto.dump_privatekey(crypto.FILETYPE_PEM, cakey))
    #open(join(directory, 'CA.cert'), 'w').write(crypto.dump_certificate(crypto.FILETYPE_PEM, cacert))


    CN = raw_input("CN: ").strip()
    O = raw_input("O: ").strip()
    pkey = createKeyPair(TYPE_RSA, 1024)
    req = createCertRequest(pkey, CN=CN, O=O)
    cert = createCertificate(req, (cacert, cakey), 1, (0, 60*60*24*365*5)) # five years
    open(join(directory, 'server.pkey'), 'w').write(crypto.dump_privatekey(crypto.FILETYPE_PEM, pkey))
    open(join(directory, 'server.cert'), 'w').write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))


if __name__ == '__main__':
    args = argv[1:]
    if args == []:
        print "Specify output directory"
    else:
        generateIn(args[0])
