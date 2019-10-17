## begin license ##
#
# "Seecr Test" provides test tools.
#
# Copyright (C) 2012, 2016 Seecr (Seek You Too B.V.) http://seecr.nl
#
# This file is part of "Seecr Test"
#
# "Seecr Test" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# "Seecr Test" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with "Seecr Test"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

import socket as socketModule
import sys
from contextlib import closing
from copy import copy
from socket import socket, getaddrinfo, error as socket_error, has_ipv6, SOL_SOCKET, SO_LINGER, SO_REUSEADDR, SOCK_STREAM, SOCK_DGRAM, IPPROTO_TCP, IPPROTO_UDP, AF_INET
from struct import pack


class PortNumberGenerator(object):
    _ephemeralPortLow, _ephemeralPortHigh = [int(p) for p in open('/proc/sys/net/ipv4/ip_local_port_range', 'r').read().strip().split('\t', 1)]  # low\thigh
    _maxTries = (_ephemeralPortHigh - _ephemeralPortLow) // 2
    _usedPorts = set([])
    _bound = {}

    @classmethod
    def next(cls, blockSize=1, bind=False):
        blockSize = verifyAndCoerseBlockSize(blockSize)
        for i in range(cls._maxTries):
            port = cls._bindAttempt(0, blockSize, bind, cls._usedPorts)
            if port:
                return port

        raise RuntimeError('Not been able to get an new uniqe free port within a reasonable amount (%s) of tries.' % cls._maxTries)

    @classmethod
    def unbind(cls, port, blockSize=1):
        blockSize = verifyAndCoerseBlockSize(blockSize)
        for p in range(port, port + blockSize):
            close = cls._bound.pop(p, None)
            if close is not None:
                close()

    @classmethod
    def bind(cls, port, blockSize=1):
        blockSize = verifyAndCoerseBlockSize(blockSize)
        portsToBind = set(range(port, port + blockSize))
        if set(cls._bound.keys()).intersection(portsToBind):
            raise RuntimeError('Port(s) already bound')

        usedPortsMinusToBind = cls._usedPorts.difference(portsToBind)
        port = cls._bindAttempt(port, blockSize, True, usedPortsMinusToBind)
        if not port:
            raise RuntimeError('Port(s) are not free!')

        return port

    @classmethod
    def clear(cls):
        for close in list(cls._bound.values()):
            close()
        cls._bound.clear()
        cls._usedPorts.clear()

    @classmethod
    def _bindAttempt(cls, port, blockSize, bind, blacklistedPorts):
        port, bound = attemptEphemeralBindings(
            bindPort=port,
            blockSize=blockSize,
            bind=bind,
            blacklistedPorts=blacklistedPorts)
        if port:
            cls._usedPorts.update(set(range(port, port + blockSize)))
            cls._bound.update(bound)
            return port

def attemptEphemeralBindings(bindPort, blockSize, bind, blacklistedPorts=None):
    """
    Returns port and bound if succesful; otherwise all None's.
    If bindPort is 0; does ephemeral binding (first port) and the remaining ports explicitly.

    port:
        First port (of consequative ports iff blockSize > 1).
    bound:
        Dictionary of port-numbers to a close function; representing the bond socket objects .close() - if bind is False, empty.
    """
    blacklistedPorts = set() if blacklistedPorts is None else blacklistedPorts

    port = None
    portNumberToBind = bindPort
    togo = blockSize
    bound = {}
    # togo > 0; but called quite often, so a quicker check.
    while togo is not 0:
        # portNumberToBind > 0; but called quite often, so a quicker check.
        if portNumberToBind is not 0 and portNumberToBind in blacklistedPorts:
            return None, None

        aPort, close = attemptBinding(bindPort=portNumberToBind)

        if aPort is None:
            return None, None
        elif aPort in blacklistedPorts:
            close()
            return None, None

        if bind is True:
            bound[aPort] = close
        else:
            close()

        if port is None:
            portNumberToBind = port = aPort
        portNumberToBind += 1
        togo -= 1

    return port, bound

def verifyAndCoerseBlockSize(blockSize):
    blockSize = int(blockSize)
    if blockSize < 1:
        raise ValueError('blockSize smaller than 1')
    return blockSize


#
# Implementation for Dual-Stack or IPv4 below here.
#

def has_dual_stack():
    """
    Return True if kernel allows creating a socket which is able to
    listen for both IPv4 and IPv6 connections.
    """
    # From: http://bugs.python.org/issue17561 - see also: http://code.activestate.com/recipes/578504-server-supporting-ipv4-and-ipv6/
    if not has_ipv6 \
            or not hasattr(socketModule, 'AF_INET6') \
            or not hasattr(socketModule, 'IPV6_V6ONLY'):
        return False
    try:
        with closing(socket(socketModule.AF_INET6, SOCK_STREAM)) as sock:
            if not sock.getsockopt(socketModule.IPPROTO_IPV6, socketModule.IPV6_V6ONLY):
                return True
            else:
                sock.setsockopt(socketModule.IPPROTO_IPV6, socketModule.IPV6_V6ONLY, False)
                return True
    except socket_error:
        return False

if has_dual_stack():
    # Imports that could fail without IPv6 / Dual-Stack support.
    from socket import AI_PASSIVE, AF_UNSPEC, AF_INET6, IPPROTO_IPV6, IPV6_V6ONLY

    def attemptBinding(bindPort):
        # Prepare TCP and UDP socket
        sokT = socket(AF_INET6, SOCK_STREAM, IPPROTO_TCP)
        setIPv6Options(sokT)
        sokU = socket(AF_INET6, SOCK_DGRAM, IPPROTO_UDP)
        setIPv6Options(sokU)

        try:
            sokT.bind(ipv6SocketAddr(bindPort))
            _host, tcpPort, _flowInfo, _scopeId = sokT.getsockname()
            sokU.bind(ipv6SocketAddr(tcpPort))  # Identical to bindPort iff port != 0; otherwise same as ephemeral tcpPort
        except (IOError, OverflowError):  # OverflowError can occur when port > 65535
            return None, None

        def close():
            sokT.close()
            sokU.close()

        return tcpPort, close

    def setIPv6Options(sok):
        sok.setsockopt(IPPROTO_IPV6, IPV6_V6ONLY, 0) # Dual-Stack please.
        sok.setsockopt(SOL_SOCKET, SO_LINGER, pack('ii', 0, 0))
        sok.setsockopt(SOL_SOCKET, SO_REUSEADDR, 0) # *No* re-use (it's usually the default, but anyways)!

    def ipv6SocketAddr(port):
        return (IPv6_WILDCARD_SOCKADDR[0], port, IPv6_WILDCARD_SOCKADDR[2], IPv6_WILDCARD_SOCKADDR[3])

    def _determineIPv6WildcardSockAddr():
        host = None
        port = 0  # Ephemeral port by default
        family = AF_UNSPEC
        socktype = SOCK_STREAM  # SOCK_DGRAM would be fine too.
        proto = 0               # Could probably be IPPROTO_TCP (or _UDP too).
        flags = AI_PASSIVE
        # getaddrinfo(...) could theoretically fail (with socker.(gai)error); but should never for wildcard lookup.
        # It gives: 2 results, 1 for IPv4 and one for IPv6 (both wildcards)
        info = getaddrinfo(host, port, family, socktype, proto, flags)
         # sockaddr for IPv6 consists of: (host, port, flow-information, scope-id)  -- The last 2 are quite impossible to guess (though possibly not that important); so using getaddrinfo result instead of hard-coded values.
        family, socktype, proto, canonname, sockaddr = [i for i in info if i[0] == AF_INET6][0]
        if not ((family, socktype, proto) == (AF_INET6, SOCK_STREAM, IPPROTO_TCP) and \
                ('::', 0) == sockaddr[0:2] and \
                type(sockaddr) == type(tuple())):
            raise RuntimeError('Assumption failure.')
        return sockaddr

    # Format IPv6 Wildcard: ('::', <port-number>, <flow-information>, <scope-id>) - usually being: ('::', 0, 0, 0)
    IPv6_WILDCARD_SOCKADDR = _determineIPv6WildcardSockAddr()

else:
    sys.stderr.write("\nSeecr-Test's PortNumberGenerator: Dual-Stack IP (IPv4 and IPv6 configurable on one socket) is not found!\n")
    sys.stderr.write("  Falling back to IPv4 wildcard :-(\n")
    sys.stderr.flush()

    def attemptBinding(bindPort):
        # Prepare TCP and UDP socket
        sokT = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)
        setIPv4Options(sokT)
        sokU = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        setIPv4Options(sokU)

        try:
            sokT.bind((IPv4_WILDCARD, bindPort))
            _host, tcpPort = sokT.getsockname()
            sokU.bind((IPv4_WILDCARD, tcpPort))  # Identical to bindPort iff port != 0; otherwise same as ephemeral tcpPort
        except (IOError, OverflowError):  # OverflowError can occur when port > 65535
            return None, None

        def close():
            sokT.close()
            sokU.close()

        return tcpPort, close

    def setIPv4Options(sok):
        sok.setsockopt(SOL_SOCKET, SO_LINGER, pack('ii', 0, 0))
        sok.setsockopt(SOL_SOCKET, SO_REUSEADDR, 0) # *No* re-use (it's usually the default, but anyways)!

    IPv4_WILDCARD = '0.0.0.0'
