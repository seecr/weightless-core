## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    See http://weightless.io
#    Copyright (C) 2006-2009 Seek You Too (CQ2) http://www.cq2.nl
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


class BufferedHandler(object):

    def __init__(self, nextInChain):
        self.nextInChain = nextInChain
        self.allData = []
        self.sentHeaders = False

    def next(self):
        return self.nextInChain.next()

    def send(self, data):
        if not self.sentHeaders:
            self.sentHeaders = True
            self.nextInChain.send(data)
        else:
            self.allData.append(data)

    def throw(self, ex):
        self.nextInChain.send("".join(self.allData))
        return self.nextInChain.throw(ex)
