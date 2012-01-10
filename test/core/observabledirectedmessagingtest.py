## begin license ##
# 
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io 
# 
# Copyright (C) 2011-2012 Seecr (Seek You Too B.V.) http://seecr.nl
# 
# This file is part of "Weightless"
# 
# "Weightless" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# "Weightless" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with "Weightless"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# 
## end license ##

from unittest import TestCase

from weightless.core import Observable

class ObservableDirectedMessagingTest(TestCase):

    def testDirectedObserverMessagingDoesNotBreakUndirectedCall(self):
        observable = Observable()
        called = []
        class A(Observable):
            def method(this):
                called.append("A")
        observable.addObserver(A("name"))

        list(observable.all["name"].method())
        
        self.assertEquals(["A"], called)

    def testDirectedObserverMessagingIgnoresNonObservableObservers(self):
        observable = Observable()
        called = []
        class Z(object):
            def method(this):
                called.append("Z")
        observable.addObserver(Z())

        list(observable.all["name"].method())
        
        self.assertEquals([], called)

        list(observable.all.method())

        self.assertEquals(["Z"], called)

    def testDirectedMessagesCanAlsoBeAcceptedByObjects(self):
        observable = Observable()
        called = []
        class Y(object):
            def method(this):
                called.append("Y")
            def observable_name(this):
                return 'name'
        class Z(object):
            def method(this):
                called.append("Z")
        observable.addObserver(Y())
        observable.addObserver(Z())

        list(observable.all["name"].method())
        
        self.assertEquals(['Y'], called)

        del called[:]

        list(observable.all.method())

        self.assertEquals(['Y', "Z"], called)

        del called[:]

        list(observable.all["other"].method())

        self.assertEquals([], called)


    def testUndirectedObserverMessagingIsUnaffectedByObserverName(self):
        observable = Observable()
        called = []
        class A(Observable):
            def method(this):
                called.append(("A", this.observable_name()))
        
        class B(Observable):
            def method(this):
                called.append(("B", this.observable_name()))

        observable.addObserver(A("name"))
        observable.addObserver(A().observable_setName("anothername"))
        observable.addObserver(B("anothername"))
        observable.addObserver(B())

        list(observable.all.method())
        
        self.assertEquals([("A", "name"), 
            ("A", "anothername"), 
            ("B", "anothername"), 
            ("B", None)], called)
        del called[:]

        list(observable.all["name"].method())
        self.assertEquals([("A", "name")], called)

    def testSetName(self):
        observable = Observable().observable_setName('name')
        self.assertEquals('name', observable.observable_name())

