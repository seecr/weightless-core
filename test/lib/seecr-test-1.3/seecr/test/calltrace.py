## begin license ##
#
# "Seecr Test" provides test tools.
#
# Copyright (C) 2005-2009 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2012 Seecr (Seek You Too B.V.) http://seecr.nl
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

from re import compile

def emptyGenerator():
    return
    yield

class CallTrace:
    def __init__(self, name="CallTrace", verbose=False, returnValues=None, ignoredAttributes=[], methods=None, onlySpecifiedMethods=False, emptyGeneratorMethods=[]):
        self.calledMethods = CalledMethods()
        self.returnValues = returnValues or {}
        self.methods = methods or {}
        self.exceptions = {}
        self._verbose = verbose
        self._name = name
        self.ignoredAttributes = ignoredAttributes or []
        self.onlySpecifiedMethods = onlySpecifiedMethods
        self.emptyGeneratorMethods = emptyGeneratorMethods

    def calledMethodNames(self):
        return [m.name for m in self.calledMethods]

    def __getattr__(self, attrname):
        if attrname.startswith('__') and attrname.endswith('__') and not attrname in self.returnValues:
            return object.__getattr__(self, attrname)
        if attrname in self.ignoredAttributes:
            raise AttributeError("'CallTrace' is instructed to not have an attribute called '%s'" % attrname)
        if self.onlySpecifiedMethods and not attrname in (list(self.returnValues.keys()) + list(self.methods.keys()) + self.emptyGeneratorMethods):
            raise AttributeError("'CallTrace' does not support '%s' as it is instructed to only allow specified methods." % attrname)
        return CallTraceMethod(attrname, self)

    def __calltrace__(self):
        return list(map(str, self.calledMethods))

    def __bool__(self):
        return True

    def __repr__(self):
        #TODO: __repr__ ook terug laten komen in calltrace
        return "<CallTrace: %s>" % self._name

    def __str__(self):
        #TODO: __str__ ook terug laten komen in calltrace
        return self.__repr__()


class CallTraceMethod:
    def __init__(self, methodName, callTrace):
        self.name = methodName
        self._callTrace = callTrace

    def __call__(self, *args, **kwargs):
        return TracedCall(self.name, self._callTrace)(*args, **kwargs)

    def __repr__(self):
        return "<bound method %s of %s>" % (self.name, self._callTrace)


class TracedCall:
    def __init__(self, methodName, callTrace):
        self.name = methodName
        self._callTrace = callTrace
        #inits are necessary to make __repr__ calls before __call__ calls possible
        self.args = ()
        self.kwargs = {}

    def __call__(self, *args, **kwargs):
        self._callTrace.calledMethods.append(self)
        self.args = args
        self.arguments = list(args) # For backwards compatibility only
        self.kwargs = kwargs
        if self._callTrace._verbose:
            print('%s.%s -> %s' % (
                self._callTrace._name,
                self.__repr__(),
                self.represent(self._callTrace.returnValues.get(self.name, None))))
        if self.name in self._callTrace.exceptions:
            raise self._callTrace.exceptions[self.name]

        returnValue = None
        if self.name in self._callTrace.returnValues:
            returnValue = self._callTrace.returnValues.get(self.name)
        elif self.name in self._callTrace.methods:
            returnValue = self._callTrace.methods.get(self.name)(*args, **kwargs)
        elif self.name in self._callTrace.emptyGeneratorMethods:
            returnValue = emptyGenerator()

        return returnValue

    def asDict(self):
        return {
            'name': self.name,
            'args': self.args,
            'kwargs': self.kwargs
        }

    def represent(self, something):
        """
        <calltracetest.NonObject instance at 0x2b02ba1075a8>
        <calltracetest.IsObject object at 0x2b02ba0f3510>
        <class 'calltracetest.IsObject'>
        calltracetest.NonObject
        """
        objectOnlyRe = r'((?:\w+\.)*\w+)'
        instanceRe = r'<%s instance at .*>' % objectOnlyRe
        objectRe = r'<%s object at .*>' % objectOnlyRe
        classRe = r"<class '%s'>" % objectOnlyRe
        objectsRe = compile(r'|'.join([instanceRe, objectRe]))
        classesRe = compile(r'|'.join([classRe, objectOnlyRe]))

        strSomething = str(something)

        if something == None:
            return 'None'
        elif isinstance(something, str):
            return "'%s'" % something
        elif isinstance(something, (int, float)):
            return strSomething
        elif isinstance(something, (bytes, bytearray)):
            return strSomething
        elif isinstance(something, type): # a Class
            return "<class %s>" % getattr(something, ("__qualname__" if self._callTrace._verbose else "__name__"))
        elif isinstance(type(something), type) and (" object " in strSomething or
                                                    " instance " in strSomething): # object (instance) of some class
            return "<%s>" % getattr(type(something), ("__qualname__" if self._callTrace._verbose else "__name__"))
        else:
            return strSomething

    def __repr__(self):
        return '%s(%s)' % (self.name, ", ".join(list(map(self.represent, self.args))+['%s=%s' % (key, self.represent(value)) for key, value in list(self.kwargs.items())]))


class CalledMethods(list):
    def reset(self):
        del self[:]
        return self
