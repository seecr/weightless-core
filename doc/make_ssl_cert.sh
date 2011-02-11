#!/bin/bash
## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    See http://weightless.io
#    Copyright (C) 2009-2011 Seek You Too (CQ2) http://www.cq2.nl
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

if [ "$1" != "" ];
then
	COMMON_NAME=$1
else
	echo -n "common name: "
	read COMMON_NAME
fi

if [ "${COMMON_NAME}" == "" ];
then
	echo "INVALID CN"
	exit 1
fi

mkdir --parents ${COMMON_NAME}


cat << EOF > ${COMMON_NAME}/openssl.cnf
distinguished_name      = req_distinguished_name
[ req_distinguished_name ]
commonName                      = CN
commonName_default              = ${COMMON_NAME}
EOF

openssl genrsa -out ${COMMON_NAME}/server.pem 2096
openssl req -new -key ${COMMON_NAME}/server.pem -out ${COMMON_NAME}/server.csr -config ${COMMON_NAME}/openssl.cnf -batch
openssl x509 -req -days 3650 -in ${COMMON_NAME}/server.csr -signkey ${COMMON_NAME}/server.pem -out ${COMMON_NAME}/server.crt
