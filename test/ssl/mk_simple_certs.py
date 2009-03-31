#!/usr/bin/env python2.5

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