class TransparentSocket(object):
    def __init__(self, originalObject, logFile = None):
        self._originalObject = originalObject
        self._logFile = logFile
        self._lastMethod = None

    def __getattr__(self, attrname):
        return getattr(self._originalObject, attrname)

    def __hasattr__(self, attrname):
        return hasattr(self._originalObject, attrname)

    def _logString(self, method, data):
        if self._logFile:
            f = open(self._logFile, 'a')
            try:
                if method != self._lastMethod:
                    f.write("\n%s:\n" % method)
                    self._lastMethod = method
                f.write(data)
            finally:
                f.close()

    def recv(self, bytes, *args, **kwargs):
        result = self._originalObject.recv(bytes, *args, **kwargs)
        self._logString('recv', result)
        return result

    def send(self, data, *args, **kwargs):
        bytesSent = self._originalObject.send(data, *args, **kwargs)
        self._logString("send", data[:bytesSent])
        return bytesSent

    def sendall(self, data, *args, **kwargs):
        self._logString("send", data)
        return self._originalObject.sendall(data, *args, **kwargs)
