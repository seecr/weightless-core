#!/bin/bash


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
