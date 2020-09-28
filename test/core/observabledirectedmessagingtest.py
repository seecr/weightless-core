## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2011-2013 Seecr (Seek You Too B.V.) http://seecr.nl
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

from weightless.core import Observable, compose


class ObservableDirectedMessagingTest(TestCase):
    def testDirectedObserverMessagingDoesNotBreakUndirectedCall(self):
        observable = Observable()
        called = []
        class A(Observable):
            def method(this):
                called.append("A")
                return
                yield
        observable.addObserver(A("name"))

        list(compose(observable.all["name"].method()))
        list(compose(observable.all["name"].method()))

        self.assertEqual(["A", "A"], called)

    def testDeferredObjectsAreCached(self):
        observable = Observable()
        class A(Observable):
            pass
        observable.addObserver(A("name"))
        d1 = observable.all["name"]
        d2 = observable.all["name"]
        self.assertEqual(d1, d2)

    def testDirectedObserverMessagingIgnoresNonObservableObservers(self):
        observable = Observable()
        called = []
        class Z(object):
            def method(this):
                called.append("Z")
                return
                yield
        observable.addObserver(Z())

        list(compose(observable.all["name"].method()))

        self.assertEqual([], called)

        list(compose(observable.all.method()))

        self.assertEqual(["Z"], called)

    def testDirectedMessagesCanAlsoBeAcceptedByObjects(self):
        observable = Observable()
        called = []
        class Y(object):
            def method(this):
                called.append("Y")
                return
                yield
            def observable_name(this):
                return 'name'
        class Z(object):
            def method(this):
                called.append("Z")
                return
                yield
        observable.addObserver(Y())
        observable.addObserver(Z())

        list(compose(observable.all["name"].method()))

        self.assertEqual(['Y'], called)

        del called[:]

        list(compose(observable.all.method()))

        self.assertEqual(['Y', "Z"], called)

        del called[:]

        list(compose(observable.all["other"].method()))

        self.assertEqual([], called)


    def testUndirectedObserverMessagingIsUnaffectedByObserverName(self):
        observable = Observable()
        called = []
        class A(Observable):
            def method(this):
                called.append(("A", this.observable_name()))
                return
                yield

        class B(Observable):
            def method(this):
                called.append(("B", this.observable_name()))
                return
                yield

        observable.addObserver(A("name"))
        observable.addObserver(A().observable_setName("anothername"))
        observable.addObserver(B("anothername"))
        observable.addObserver(B())

        list(compose(observable.all.method()))

        self.assertEqual([("A", "name"),
            ("A", "anothername"),
            ("B", "anothername"),
            ("B", None)], called)
        del called[:]

        list(compose(observable.all["name"].method()))
        self.assertEqual([("A", "name")], called)

    def testSetName(self):
        observable = Observable().observable_setName('name')
        self.assertEqual('name', observable.observable_name())

