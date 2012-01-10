#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "./weightless-trunk")
from os import environ, system
from traceback import print_exc
from inspect import isfunction
#environ['WEIGHTLESS_COMPOSE_TEST'] = 'PYTHON'
from weightless.core import compose, local
ok = lambda *args, **kwargs: True















#1







def Beyond_Python_Enhanced_Generators():
    conference  = "EuroPython"
    date        = 2011-06-23
    location    = "Florence, Italy"
    presenter   = "Erik J. Groeneveld"
    affiliation = "Seecr"
    email       = "erik@seecr.nl"
    moreinfo    = "weightless.io/compose"

    while True:
        listen()
        speak()






#2

def pep342():
    """Enhanced Generator"""
    msg = yield "response"
    print msg
    yield


def demo_driver():
    """the most profound change ever"""
    g = pep342()
    response = g.next()   #1
    g.send("msg")         #2












#3

def pep380():
    """Delegating to Subgenerator"""
    def f():
        yield "response"
    def g():
        yield from_f()
    for r in g():
        print r


def demo_ala_compose():
    """Delegation with Compose"""
    def f():
        yield "Hello"
        msg = yield None
    def g():
        yield f()         #1
    for r in compose(g()):#2
        print r





#4

def demo_compose_decorator():
    """Compose as decorator"""
    def f():
        yield "Hello"
        msg = yield
    @compose              #1
    def g():
        yield f()         #2
    for r in g():         #3
        print r














#5

def demo_propagation():
    """Compose at top level only"""
    def f():
        yield "I am f"
    def g():
        yield f()
    def h():
        yield g()
    for m in compose(h()):
        print m





"""
    yielded generator
        replaces it parent
"""





#6

def demo_two_way():
    """Communicate both ways"""
    def f():              #2
        msg = yield       #4
        yield msg
    def g():
        yield f()
    p = compose(g())
    print p.next()        #1
    print p.send("hello") #3




"""
    At #3 the message returns 
    immediately, as if #4 were:

    def f(msg):
        return msg
"""        



#7

def demo_alternative():
    """Use of None"""
    def f():
        msg = None
        while True:
           msg = yield msg #1
    def g():
        yield f()
    p = compose(g())
    print p.send(None)     #2
    print p.send("Hello")













#8

def demo_handle_exceptions():
    """Exceptions in subgenerators"""
    def f():
        raise Exception("8-;")
        yield
    @compose
    def g():
        try:                    
            yield f()           #1
        except Exception, e:    #2
            yield e
    print g().next()












#9

def demo_tb():
    """Show generators on Trace"""
    def f():
        raise Exception(";-(")
        yield
    def g():
        yield f()
    @compose
    def h():
        yield g()
    try: h().next()
    except: print_exc()
"""
Traceback (most recent call last):
  File "./ep.py", line 246, in demo_tb
    try: h().next()
  File "./ep.py", line 245, in h
    yield g()
  File "./ep.py", line 242, in g
    yield f()
  File "./ep.py", line 239, in f
    raise Exception(";-(")
Exception: ;-(
"""
#10

def demo_return_value():
    """'call' a generator"""
    def f():
        raise StopIteration("val") #1
        #return "retval"           #2 
        yield
    @compose
    def g():
        v = yield f()
        yield v
    print g().next()


#Jackson Structured Programming
#Program structure = Data structure
#Interleaving clashes
#Ordering clashes
#Boundary clashes
#Recognition difficulties
#Program inversion
#Avoid buffering
#Web-servers


#11

def demo_coroutine():
    """coroutine a la COBOL"""
    def coroutine_a(n = 0):
        while n < 10:
            n = yield b, n + 1
            print ">", n
    def coroutine_b(n = 0):
        while n < 10:
            n = yield a, n + 1
            print "<", n
    a = coroutine_a()
    b = coroutine_b()
    a.next(); b.next()
    g = (a, 0)
    while True: # trampoline
       try: g = g[0].send(g[1])
       except: break







#12

def demo_coroutine_with_inversion():
    """Limited scope/lifetime"""
    def coroutine_a(n = 0):
        yield                       #1
        print ">", n
        raise StopIteration(n + 1)
    def coroutine_b(n = 0):
        while n < 10:
            n = yield coroutine_a(n + 1)
            print "<", n
    g = compose(coroutine_b())
    list(g)












#13

def socket_driver1(sok, gen):
    """Naive Socket Driver"""
    msg = None
    while True:
        res = gen.send(msg)
        sok.send(resp)
        msg = sok.recv()

















#14

def socket_driver(sok, prot):
    """Protocol controls flow"""
    res = prot.next()               #1
    while True:
        if res:                     #2
            sok.send(res)
            res = prot.next()
        else:
            msg = sok.recv()        #3
            res = prot.send(msg)














#15

def http_protocol():
    """naive protocol"""
    request = yield
    yield "HTTP/1.1 200 Ok\r\n\r\n"
    yield "<table><tr>"
    for i in range(3):
        yield "<td>%d></td>" % i
    yield "</tr></table"


def demo_http_protocol():
    """Test naive http implementation"""
    p = http_protocol()
    p.next()
    p.send("HTTP/1.0 GET /\r\n\r\n")
    for l in p:
        print l







#16

@compose
def http_protocol2(handler):
    """Separation of concerns"""
    req, hdrs = yield readRequest() #1
    yield handler(req, hdrs)        #2


def readRequest():
    """More refactoring (parsing)"""
    reql = yield read_req_line()
    hdrs = yield read_headers()
    raise StopIteration([reql, hdrs])












#17

def read_req_line():
    """Push back superfluous data"""
    msg = ''
    while not '\r\n' in msg:
        msg += yield
    req, tail = msg.split('\r\n',1)    #1
    raise StopIteration(req, tail)     #2


def demo_read_request_line():
    """Demo Boundary Clash"""
    r = compose(read_req_line())
    try:
      r.next()
      print r.send("GET /docs HT")
      print r.send("TP/1.0\r\nHost: pyt")
      print r.send("hon.org\r\n\r\n")
    except StopIteration, e:
      print e.args





#18

"""
    Boundary Clashes
    TCP packets 
        != HTTP chunks
            != XML tags

    What happens with 'tail'?

    General case:
    raise StopIteration(
        retval, token0, ..., tokenn)
"""












#19

def read_headers():
    msg = ''
    while not '\r\n\r\n' in msg:
        msg += yield
    result = msg.split('\r\n\r\n')
    raise StopIteration(*result)


def demo_read_request():
    """a real world example"""
    r = compose(readRequest())
    r.next()
    try:
        r.send("GET /docs HT")
        r.send("TP/1.0\r\nHost: pytho")
        r.send("n.org\r\n\r\nFORM data")
    except StopIteration, e:
        print e.args # nested tuple






#20

def handleRequest(req, headers):
    msg = ''
    try:
        while True:
            msg += yield
    except StopIteration:
        print "BODY:", msg
        yield 'HTTP/1.0 200 Ok\r\n\r\n'


def demo_complete_protocol():
    """three levels of delegation"""
    p = http_protocol2(handleRequest)
    p.next()
    p.send("GET /docs HT")
    p.send("TP/1.0\r\nHost: pytho")
    p.send("n.org\r\n\r\nFORM data")
    print p.throw(StopIteration)






#21

"""
    It would be highly unpractical
    to have to deal with push backs
    at every delegation.

    ==> let compose do it
"""

















#22

def handler_rev(req, headers):
    """Flow control"""
    yield 'HTTP/1.0 200 Ok\r\n\r\n'    #1
    msg = ''
    try:
        while True:
            msg += yield               #2
    except StopIteration:
        print "BODY:", msg

def demo_complete_protocol_2():
    """A handler with different flow"""
    p = http_protocol2(handler_rev)
    print 1, p.send(None)
    print 2, p.send("GET /docs HT")
    print 3, p.send("TP/1.0\r\nHost: pyt")
    print 4, p.send("hon.org\r\n\r\nFORM")
    print 5, p.next()
    print 6, p.send("data")
    try: print 7, p.throw(StopIteration)
    except StopIteration: pass



#23

def Fragment_from_compose():
    if response or not messages:
      message = yield response
      assert not (message and response),\
            'Cannot accept data.' + \
            'First send None.'
      messages.insert(0,message)
    #...
    try:
      pass # ...
    except StopIteration, retval:
      generators.pop()
      if retval.args:
        messages = list(retval.args) \
                 + messages
      else:
        messages.insert(0, None)







#24

def a_template():
    yield """
        <html><body>
            <table><tr>"""
    for i in range(3):
        yield """
                <td>%d></td>""" % i
    yield """
            </tr></table>
        <html><body>"""


def demo_flow_control():
    """a driver with flow control"""
    msgs = iter(['GET /','GET /en'])
    template = a_template()
    m = None
    try:
        while True:
            r = template.send(m)
            m = None if r else msgs.next()
            print r,
    except StopIteration: pass

#25

def a_template_2():
    print (yield """
        <html><body>
          <table><tr>""")
    for i in range(3):
        print (yield """
            <td>%d></td>""" % i)
    print (yield """
          </tr></table>
        <html><body>
        """)


def demo_flow_control_2():
    """driver without flow control"""
    msgs = iter([None,'GET /','GET /en'])
    template = a_template()
    while True:
        print template.send(msgs.next())





#26

def demo_what_about_thread_local():
    """Cross cutting concerns:
        Transactions, security, logging"""
    def f():
        tx_id = "ID:392123"     #1
        yield g()
    def g():
        yield h()
    def h():
        tx_id = local("tx_id")  #2
        print tx_id
    list(compose(f()))












#27

"""
    Topics for discussion:
    1. back traces?
    2. flow control?
    3. look ahead, push back?
    4. generator locals
"""

















#28

funcs = (f for f in locals().values() if 
        isfunction(f) and f.__code__.co_name.startswith("demo"))

if len(sys.argv) > 1:
    funcs = (f for f in funcs if f.__code__.co_name in sys.argv)

system('clear')

for f in sorted(funcs, key=lambda k: k.__code__.co_firstlineno):
    print "\n* %s()\n* %s" % (f.__code__.co_name, f.func_doc)
    try: f() # run def demo_*():
    except: print_exc()









#end
