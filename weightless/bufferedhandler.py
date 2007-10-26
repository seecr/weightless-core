

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