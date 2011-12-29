## begin license ##
#
#    "CQ2 Utils" (cq2utils) is a package with a wide range of valuable tools.
#    Copyright (C) 2005-2008 Seek You Too (CQ2) http://www.cq2.nl
#
#    This file is part of "CQ2 Utils".
#
#    "CQ2 Utils" is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    "CQ2 Utils" is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with "CQ2 Utils"; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

from types import InstanceType, ClassType

class CallTrace:
    def __init__(self, name = "CallTrace", verbose = False, returnValues = None, ignoredAttributes=[]):
        self.calledMethods = []
        self.returnValues = returnValues or {}
        self.exceptions = {}
        self._verbose = verbose
        self._name = name
        self.ignoredAttributes = ignoredAttributes or []

    def __getattr__(self, attrname):
        if attrname.startswith('__') and attrname.endswith('__') and not attrname in self.returnValues:
            return object.__getattr__(self, attrname)
        if attrname in self.ignoredAttributes:
            raise AttributeError("'CallTrace' is instructed to not have an attribute called '%s'" % attrname)
        return TracedCall(attrname, self)

    def __calltrace__(self):
        return map(str, self.calledMethods)

    def __nonzero__(self):
        return 1

    def __repr__(self):
        #TODO: __repr__ ook terug laten komen in calltrace
        return "<CallTrace: %s>" % self._name

    def __str__(self):
        #TODO: __str__ ook terug laten komen in calltrace
        return self.__repr__()

class TracedCall:
    def __init__(self, methodName, callTrace):
        self.name = methodName
        self._callTrace = callTrace
        #inits are necessary to make __repr__ calls before __call__ calls possible
        self.arguments = []
        self.kwargs = {}

    def __call__(self, *args, **kwargs):
        self._callTrace.calledMethods.append(self)
        self.arguments = list(args)
        self.args = args #??! is not used?
        self.kwargs = kwargs
        if self._callTrace._verbose:
            print '%s.%s -> %s' % (
                self._callTrace._name,
                self.__repr__(),
                self.represent(self._callTrace.returnValues.get(self.name, None)))
        if self._callTrace.exceptions.has_key(self.name):
            raise self._callTrace.exceptions[self.name]
        return self._callTrace.returnValues.get(self.name, None)

    def represent(self, something):
        """
        <calltracetest.NonObject instance at 0x2b02ba1075a8>
        <calltracetest.IsObject object at 0x2b02ba0f3510>
        <class 'calltracetest.IsObject'>
        calltracetest.NonObject
        """
        from re import compile
        objectOnlyRe = r'((?:\w+\.)*\w+)'
        instanceRe = r'<%s instance at .*>' % objectOnlyRe
        objectRe = r'<%s object at .*>' % objectOnlyRe
        classRe = r"<class '%s'>" % objectOnlyRe
        objectsRe = compile(r'|'.join([instanceRe, objectRe]))
        classesRe = compile(r'|'.join([classRe, objectOnlyRe]))

        if something == None:
            return 'None'

        if type(something) == str:
            return "'%s'" % something
        if type(something) == int or type(something) == float:
            return str(something)

        typeName = str(something)
        match = objectsRe.match(typeName)
        if match:
            return "<%s>" % filter(None, match.groups())[0]

        match = classesRe.match(typeName)
        if match:
            return "<class %s>" % filter(None, match.groups())[0]

        return typeName

    def __repr__(self):
        return '%s(%s)' % (self.name, ", ".join(map(self.represent, self.arguments)+['%s=%s' % (key, self.represent(value)) for key, value in self.kwargs.items()]))

