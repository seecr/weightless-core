
import page, banner

def main(**kwargs):
    yield page.header(title="Compose", **kwargs)
    yield banner.banner(**kwargs)
    yield '''
<h1>Program Decomposition using Co-routines</h1>

<p>
  This chapter explains how <em>compose</em> supports program decomposition using generators. It also clarifies how <em>compose</em> extends <a href="http://www.python.org/dev/peps/pep-0380/">yield-from (PEP 380)</a>.
</p>
'''
    yield '''
<h2>Decomposition</h2>

<p>Consider this simplified generator that reads from and writes to a socket using <em>yield</em>:</p>
<pre>
            def f():
                request = yield                 (1)
                yield 'HTTP/1.0 200 Ok'         (2)
                yield ...                       (3)
</pre>
<p>It reads an HTTP request (1), generates an HTTP response (2) and sends a body (3).  When these steps get more complicated, one would like to extract parts of it into sub-generators and write something like:</p>
<pre>
            def f():
               request = yield readRequest()    (1)
               yield sendResponse(200, 'Ok')    (2)
               yield sendFile(...)              (3)
</pre>
<p>The little program is decomposed into <em>readRequest</em>, <em>sendResponse</em> and <em>sendFile</em> and combined again by 'calling' them using 'yield'. PEP 380 suggests to use 'yield from' here:</p>
<pre>
            def f():
                request = yield from readRequest()   (1)
                yield from sendResponse(200, 'Ok')   (2)
                yield from sendFile(...)             (3)
</pre>

<p>PEP380 will probably not be implemented before Python 3.3, so in the mean time, we use <em>compose</em>. Also, PEP380 is not sufficient for decomposing programs into generators. Two more things are needed, see <em>Additional Functionality</em> below.  These are in <em>compose</em> as well.</p>
'''
    yield '''
<h2>Compose</h2>

<p>Compose is a simple decorator for a generator that does what PEP 380 suggests.  And a little bit more.</p>

<h3>Basic Functionality (<em>yield from</em>)</h3>

<h4>'Calling' a subgenerator</h4>
<p>Consider the following code:</p>
<pre>
            def one():
                yield 'Hello!'
            def two():
                yield one()
</pre>
<p>The intention of <em>two</em> is to delegate part of the work to <em>one</em>, or, to 'call' it.  PEP 380 suggest to write this like:</p>
<pre>
            def two():
                yield from one()
</pre>
<p>Weightless does this as follows:</p>
<pre>
            @compose
            def two():
                yield one()
</pre>
<p>Alternatively, one can also omit the decorator and wrap the generator. Both situation are supported by <em>compose</em>:</p>
<pre>
            g = compose(two())
</pre>


<h4>Returning values</h4>

<p>Suppose we have code which calls <em>readRequest</em> and catch the return value in <em>request</em>:</p>
<pre>
            request = yield readRequest()
</pre>
<p>Normal generators do not support return values, so <em>readRequest</em> uses <em>StopIteration</em> to return data to the caller as follows:</p>
<pre>
            raise StopIteration('return value')
</pre>
<p>PEP 380 discusses this, and also handles the <a href="http://www.python.org/dev/peps/pep-0380/#use-of-stopiteration-to-return-values">debate</a> whether this is a good solution or not.</p>

<h4>Catching exceptions</h4>

<p>Although it looks natural to write, normally the code below does not catch exceptions thrown by <em>readRequest</em>:</p>
<pre>
            try:
                request = yield readRequest()
            except:
                handle error
</pre>
<p>With <em>compose</em> however, exceptions thrown by generators <em>can</em> be catched like this.</p>



<h3>Additional Functionality (beyond <em>yield from</em>)</h3>

<a name="tracebacks"></a><h4>Fixing tracebacks</h4>

<p>Suppose the following decomposition of a program into three generators (see <a href="https://github.com/seecr/weightless-core/tree/master/weightless/examples/">weightless/examples/</a>fixtraceback.py):</p>
<pre>
26          def a():
27              yield b()
28          def b():
29              yield c()
30          def c():
31              yield 'a'
32              raise Exception('b')
33
34          list(compose(a()))
</pre>
<p>When line 34 executes, you would <em>like to see</em> a traceback like:</p>
<pre>
            Traceback (most recent call last):
              File "fixtraceback.py", line 34, in <module>
                list(compose(a()))
              File "fixtraceback.py", line 27, in a
                yield b()
              File "fixtraceback.py", line 29, in b
                yield c()
              File "fixtraceback.py", line 32, in c
                raise Exception('b')
            Exception: b
</pre>
<p>But without special measures, you will only see:</p>
<pre>
            Traceback (most recent call last):
              File "fixtraceback.py", line 34, in <module>
                list(compose(a()))
              File "fixtraceback.py", line 32, in c
                raise Exception('b')
            Exception: b
</pre>
<p>Since this makes programming with generators next to impossible, <em>compose</em> maintains a stack of generators and, during an exception, it adds this stack to the traceback.</p>

<h4> Push-back data </h4>

<p>When using decomposed generators as a pipeline (see <a href="http://weightless.io/background">background on JSP</a>), <em>boundary clashes</em> appear because, for example, TCP network messages do not correspond to HTTP chunks and those do not correspond to, say, your XML records.</p>

<p>JSP describes how to deal with boundary clashes in a structured way using lookahead. A lookahead in Weightless naturally corresponds to performing an additional <em>yield</em> to get the next input token. However, there must be a way to push back (part of) this token when it belongs to the next record.</p>

<p>The co-routine below reads a stream with records. A single record is read by <em>readRecord</em>:</p>
<pre>
            def readAllRecords():
                while ...:
                    record = yield readRecord()               (1)
</pre>
<p>Each record begins with the token STARTRECORD and runs until the next STARTRECORD. Here is what <em>readRecord</em> looks like (note that <em>readRecord</em> will be invoked over and over again):
<pre>
            def readRecord():
                record = yield
                while True:
                    token = yield                             (2)
                    if token == STARTRECORD:
                        raise StopIteration(record, token)    (3)
                    record += token
</pre>
<p>The look ahead takes place at (2).  When the next value is the beginning of the next record, it returns the completed record (3) to (1). At the same it time pushes back <em>token</em> (2) so it will be read by the next <em>yield</em> (1) again. </p>

<p>PEP380 does not provide look-ahead functionality.</p>

<p>Technically (and most interestingly), there is no difference between the return value and push back.  The return value is <em>also</em> just pushed back into the input stream. It will then be read by the next <em>yield</em>, which happens immediately after <em>readRecord</em> returns at (1).  In fact, there can be an arbitrary number of tokens to be pushed back:</p>
<pre>
            raise StopIteration(retval, token<sub>0</sub>, ..., token<sub>n</sub>)
</pre>
<p>This will simply push back all values in reverse order: &lt;<em>token<sub>n</sub>, ..., token<sub>0</sub>, retval</em>&gt;.</p>


<h4>Flow Control</h4>
<p>Suppose we have a simple consumer that reads requests (1) and writes out a response in <em>n</em> parts (2, 3):</p>
<pre>
            def consumer():
                while True:
                    request = yield               (1)
                    for i in range(n):            (2)
                        yield <response part i>   (3)
</pre>
<p>A producer is supposed to first send a request and then read the response until... what? It would have to know <en>n</em>!  Now suppose we allow the producer to send a new request while the consumer is not at (1) yet. We would have to write ugly code like this:</p>
<pre>
            def responder():
                requests = []
                while True:
                    if requests:
                        request = requests.pop()
                    else:
                        request = yield                 (1)
                    for i in range(n):                  (2)
                        msg = yield <response part i>
                        if msg:
                            requests.append(msg)
</pre>
<p>This adds so much checking code that it makes decomposing programs into co-routines unfeasible. Therefor, <em>compose</em> supports flow control by means of <em>The None Protocol</em>.</p>


<h4>The None Protocol</h4>
<p>Recall that whenever we want to <em>accept data</em> and we write:</p>
<pre>
            message = yield
</pre>
<p>the Python VM interprets this as:</p>
<pre>
            message = yield None
</pre>
<p>Similarly, when we <em>want data</em> and call next:</p>
<pre>
            response = generator.next()
</pre>
<p>the Python VM interprets this as:</p>
<pre>
            response = generator.send(None)
</pre>
</p>There seems to be an implicit meaning of None in this case.  Compose makes this explicit and wields the rule: None means 'I want data'.</p>

<p>This means that every co-routine must must obey it, and <em>compose</em> checks it.</p>

<p><em>The None Protocol</em> turned out to be essential to make <em>compose</em> practical, natural, intuitive, easy to understand and consistent.  Compose was just a nice intellectual exercise and until &mdash; after a year of remorse &mdash; I added the None Protocol. </p>
'''
    yield '''
<h2> Generator Local </h2>
<p>Generetor Local is the equivalent of Thread Local variables in generator land. Weightless provides a function local() that gets locals from the stack (or backtrace, if you don't have a stack).</p>
'''
    yield '''
<h2> Side Kick </h2>

<p>This subject goes back to an old discussion about how to use <em>yield</em>. Most people I met (and also most of the competitors mention in 'Related Work') propose this for communicating with a socket:</p>
<pre>
             response = yield &lt;command&gt;          # general form
             message = yield socket.read()
             yield socket.write("response")
</pre>
<p>While I propose this:
<pre>
             message = yield
             yield "response"
</pre>
<p>In the first case, the co-routine is communicating with some sort of scheduler that executes commands, in the second case, the co-routine is communication with nobody in particular.  I prefer the latter because:
<ol>
  <li>It separates protocol from transport.</li>
  <li>It is better testable.</li>
</ol>
In both proposals, is is possible to synchronize the execution of the co-routine to read and write events on sockets.  In the first proposal, it is straightforward to synchronize on other events like timers, or locks:</p>
<pre>
             yield scheduler.sleep(1)
             yield scheduler.wait(lock)
</pre>
<p>But how to do this in the second proposal?  The answer is the Side Kick.</p>
<p>Recall that the co-routine is already communicating with something that produces and consumes data. The side kick enables the co-routine to communicate with a second entity.  An example:</p>
<pre>
             @compose(scheduler)
             def coroutine():
                 messages = yield
                 yield scheduler.wait(1)
                 yield "hello " + message                     
</pre>

<p>to be continued... </p>
'''
    yield '''
<h2> Status </h2>

<p>Compose is finalized and stable. It has a Python implementation and a C extension for better speed.  It is feasible to develop develop large programs with it. See the <a href="/example">examples</a>.</p>

<p> The idea of composing generators is formalized in Python Enhancement Proposal: <a href="http://www.python.org/dev/peps/pep-0380/">PEP-380</a>.  Compose is intended compatible with this PEP, although it extends it as explained above.</p>
'''
    yield page.footer()
