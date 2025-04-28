
import page, banner

def main(**kwargs):
    yield page.header(title="Gio", **kwargs)
    yield banner.banner(**kwargs)
    yield '''
<h1>
  Gio
</h1>

<p>
  This page describes how Gio connects sockets (file descriptors) to a coroutine created with the observable pattern and compose.  
</p>

<p>
  For details see testGioAsContext(), testAlternate() and testNesting() in <a href="http://weightless.svn.sourceforge.net/viewvc/weightless/trunk/test/giotest.py?view=markup">giotest.py</a>.
</p>

<p>
 Gio works with Python context objest.  Context objects are those objects you can use in a 'with' statement.
</p>
<pre>
    with connection:
        request = yield
        yield 'reponse
</pre>

<p>  The connection is a special object created by Weightless to represent a socket.  The statement 'request = yield' reads data from the socket, and 'yield data' writes data to the socket. </p>

<p>  The idea is to have this plumbing on such a low level that the whole protocol (say HTTP) can be implemented as a generator.  Doing so yield a very simple HTTP server, and also an open server: one that allows the program to do anything it want with the protocol in a simple way.  Most HTTP protocols are to rigid and do lost of things for you that you one day or another want to do yourself.</p>

<p>
Status:  Currently there is a limited HTTP implementation.  For the whole thing to work with pipelines, the is still work to be done.  The problem is that calling generator.send(data) properly requires so much handling that it is unfeasible to do.  In fact, whenever you can send() directly, you will have to do everything that compose()  or yield-from is doing.  Currently I am create a helper method for this. (Summer 2010).
</p>
'''
    yield page.footer(**kwargs)
