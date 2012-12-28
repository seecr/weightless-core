
import page, banner

def main(**kwargs):
    yield page.header(title='Python Generalized Generators or Co-routines', **kwargs)
    yield banner.banner(**kwargs)
    
    yield r'''
<h1>Python Generalized Generators or Co-routines</h1>

<h2>Generators as co-routines</h2>

<p>Starting with Python 2.5, generators in Python can both send or receive data.  While previously a generator - hence its name - would only generate data, it can now also consume data.  It becomes more like a co-routine.  The example below illustrates this:</p>
<pre>
    def f():
        yield 'value'		(1) data production, produces 'value'
        data = yield		(2) new in python 2.5: data consumption consumes 'data'
    g = f()
    value = g.next()		(3) value becomes 'value'
    g.send('data')		(4) sends 'data' for consumption
</pre>
<p>As many others already pointed out, this makes generators ideally suitable for performing asynchronous networking because network connections tend to generate and consume data as well.  Despite the fact that this idea may look straightforward, it turns out to be horribly complicated to actually do so.  For instance, it is not possible to decompose a program into subgenerators, rendering the idea as purely academic (though still interesting), since not being able to do program decomposition makes building real applications completely impossible.</p>

<h2>Jackson Structured Programming</h2>

<p>Michael A. Jackson's work on structured programming, dated 1975 and documented in <i>Principles of Program Design</i>, strongly relates to co-routines.  JSP offers a method to structure programs, using simple flow control features such as <i>if</i> and <i>while</i> to create programs to convert input into output data streams.  Co-routines come to the rescue when input and output structures do not match.  There are some classical example problems that are easily solved using co-routines.  One such problem is regrouping a sequence of grouped data.  In this problem, a boundary clash is present.</p>

<h2>Regrouping data</h2>
Data regrouping is a practical problem that appears for example in the HTTP protocol.  Message streams may be chunked or compressed or both, and more towards the application, the stream might contain a stream of XML tags which must be processed one by one.  The problem is that the boundaries between HTTP chunks do not coalesc with the boundaries between, for example, XML records present in the stream.  This is called a bindary clash in JSP.  One approach to solving this problem is to buffer the whole message, unchunk it, decompress it and parse it in separate steps.  However, buffering and copying data are two obstacles for high performance servers.  Rather we would like to process the stream while it flows in, avoiding buffering an copying as much as possible.  So we would like to have separate co-routines for distinct tasks, such as:</p>
<pre>
    def dechunk(next): pass
    def decompress(next): pass
    def groupbytag(tag, next): pass
</pre>
<p>Then we could combine them into a pipeline, so that data flows from one into the other and so on.  This pipeline can simply be created by:</p>
<pre>
    pipeline = dechunk(decompress(groupbytag('record', ...)))
</pre>
<p>or, if you prefer a pull pipeline rather than a push pipeline:</p>
<pre>
    pipeline = groupbytag('record', decompress(dechunk(...)))
</pre>
<p>Although creating such pipelines could be parameterized and made highly flexible, it is not a substitute for program decomposition.  Program decomposition is about method extraction and recombine the extracted methods to create larger methods or programs.  If, after extraction, the only way to recombine them is to create pipelines as shown above, method extraction becomes cumbersome.  We will seek another solution.</p>

<h2>Co-routine (Method) Extraction</h2>

<h3>One big co-routine</h3>
<p>While implementing the co-routines above we would like to extract shared pieces of code.  Below follows an implementation of dechunk() in which a few lines are marked as a candidate for extraction.  Their reuse in groupbytag(), for example, can be easily imagined:</p>
<pre>
CRLF='\r\n'
def dechunk(next):
    message = yield
    while True:
        match = matchRe('(?P&lt;ChunkSize&gt;[0-9a-fA-F]+)'+CRLF, message)    (1)
        while not match:                                                (2) extract these lines as
            message += yield                                            (3) readWhileRe(regularExpression)
            match = CHUNK_SIZE_LINE.match(message)                      (4)
        chunkSize = int("0x" + message[:match.end()], 16)
        while not len(message) >= match.end() + chunkSize + len(CRLF):  (5) extract thes lines as
            message += yield                                            (6) readBytes(nrOfBytes)
        chunk = message[match.end(): match.end() + chunkSize]           (7)
        next.send(chunk)
        message = message[match.end() + chunkSize + len(CRLF):]
</pre>
<p>As you can see, the fiddling with offsets in line (5) and (7) is based on the match as made in line (4).  The problem is dat line (3) might read more data than what is needed for the match.  This extra data is part of the chunk, which is furhter read on line (5).</p>

<h3>Take 1</h3>
<p>Ideally, we would like to be able to have a co-routine that handles the regular expression matching, yielding a match object and correctly forwarding superfluous data onto the stream. Suppose we have such a co-routine and it is called findRe(). Then the lines (1) - (4) would disappear:</p>
<pre>
CRLF='\r\n'
def dechunk(next):
    match = yield
    chunkSize = int("0x" + match.groupdict()['ChunkSize'], 16)
    message =''
    while len(message) &lt; chunkSize:
        message += yield
    next.send(chunk[:chunkSize])  # this is not correct, but for now it is good enough
</pre>
 <p>and in order to use it, we must modify the pipeline:</p>
<pre>
    pipeline = findRe('...re...', dechunk(decompress(groupbytag('record', ...)))
</pre>
<p>But what have we done here from a coding perspective?  We have extracted a piece of code into a separate co-routine but the main co-routine has lost its structure.  It is no longer a sequential list of statements, it is now only a fragment that can only be understood when seen it the context of a pipeline that recombines the fragments.  Let find something else.</p>

<h3>Take 2</h3>
<p>Suppose we could extract a little co-routine readWhileRe() that consumes a stream up to where a regular expression has matched (just like findRe() above) but then yield the match instead of feeding it further down the pipeline.  We could then invoke this coroutine ourselves as follows:</p>
<pre>
        readWhileReCoRoutine = readWhileRe('(?P&lt;ChunkSize&gt;[0-9a-fA-F]+)\r\n')
        match = None
        while not match:
            data = yield
            match = readWhileReCoRoutine.send(data)
</pre>
<p>This would at least leave the main co-routine in charge, but as can be seen quickly, this requires quite some plumbing.  If calling an extracted method would be that difficult, would you extract small snippets of code?  There is more trouble however: it provides no way for readWhileRe() to transparantly deal with superflous data it has been fed, for example by pushing it back into the data stream. Can we do better?</p>

<h3>Take 3</h3>
<p>Image everything is possible.  The code below shows what we would like as in interface to extracted co-routines.  It looks much like a function call, but with yield in from of it:</p>
<pre>
def dechunk(next):
    while True:
        match = yield readWhileRe('(?P&lt;ChunkSize&gt;[0-9a-fA-F]+)\r\n')       # reads until chunk header
        chunkSize = int("0x" + match.groupdict()['ChunkSize'], 16)
        chunk = yield readBytes(chunkSize)                                 # reads the whole chunk
        next.send(chunk)
        yield readBytes(len(CRLF))                                         # reads the terminator
</pre>
<p>As you can see, this way of writing the code makes it also straightforward to reuse the extracted co-routine readBytes() twice.  It keeps the structure intact.  The main co-routine is in control.  In fact, it mimics function calling quite closely.</p>
<p>However, this does not work. Dechunk() simply yields another generator, that's it.  And you won't get return values from co-routines either.</p>
<p>So what to do?  Let's analyse it further.</p>

<h3>Take 4</h3>
<p>The dechunk co-routine is eating a stream, and wants to 'insert' into the stream another subco-routine that does a short one-time job and then returns control to dechunk.  Secondly, it expects some sort of 'return' value from the subco-routine.  That could be done by the one who is feeding the data to dechunk.  It could check every response of dechunk to see it is an co-routine, and if so, insert it into the pipeline.  Once the subco-routine is exhausted, it is removed from the pipeline, and the last value yielded by it could be used as the 'return' value which is then fed to dechunk.  Also, the subco-routine could yield superfluous data, wich is then fed into dechunk after the return value has been send to it.</p>

<p>Does this work? Is it possible? Isn't it a weird counter intuitive thing?  Yes, Yes, No.  As part of the Weightless project, a Python VM extension called 'compose' is been created.  It does some sort of generator method-dispacthing to achive what is outlined above recursively.  It in fact inverts the control flow of the program, and thanks to the new throw() method on generators in Python 2.5, it is possible to make invert exception handling as well.  More on it is on a separate page for <a href="/compose">compose</a>, including unittests and working code.</p>
'''
    yield page.footer(**kwargs)
