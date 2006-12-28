#!/usr/bin/env python2.5

from server import main

def sinkFactory():
  """endlessly read and echo back to the client"""
  while 1:
    received = yield None
    yield "ECHO: %s" % received


if __name__ == '__main__':
	main(sinkFactory)