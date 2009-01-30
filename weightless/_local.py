from weightless import reactor

class local(object):

    def __init__(self):
        object.__setattr__(self, '_reactor', None)

    def _getReactor(self):
        if self._reactor == None:
            object.__setattr__(self, '_reactor', reactor())
        return self._reactor

    def __getattr__(self, name):
        context = self._getReactor().currentcontext
        return context.locals[name]

    def __setattr__(self, name, attr):
        context = self._getReactor().currentcontext
        context.locals[name] = attr

