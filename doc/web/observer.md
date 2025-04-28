
import page, banner

def main(**kwargs):
    yield page.header(title="Observer", **kwargs)
    yield banner.banner(**kwargs)
    yield '''
<h1>Component Configuration with DNA</h1>

<p>Configuration consists of DNA describing a graph of observables in a Pythonic way.</p>

'''
    yield '''
<h2>Observable</h2>

<p>Weightless uses the Observable Pattern to connect components.</p>

<h3>Pythonic Implementation</h3>

<p>Usually, in the traditional Observer Pattern, observables dispatch messages by calling:</p>

<pre>
            self.notify_observers('message', arg0, arg1, ...)
</pre>

<p>The observer receives this message by implementing:</p>

<pre>
            def notify(self, message, arg0, arg1, ...):
                #do something
</pre>

<p>A message with arguments is very similar to a method with arguments, and in Python we can implement the Observable pattern in a neat Pythonic way.</p>

<p>For an observer receiving message 'message0' with arguments 'arg0' and 'arg1', we would implement:</p>

<pre>
            def message0(arg0, arg1):
                # do something
</pre>

<p>An observable would dispatch this message by calling this method.  However, since this method is implemented elsewhere and has to be dispatched by the Observable machinery, the observable calls it on 'self.do':</p>

<pre>
            self.do.message0('arg0', 'arg1')
</pre>

<p>The Observable machinery is behind 'do'.  It will find the corresponding methods on the observers and call them.</p>


<h3>Beyond Observable</h3>

<p>Let's stretch up things a bit.</p>


<h4>Return Values</h4>
<p>When dispatching messages via 'self.all' instead of 'self.do', we get back a generator with the responses of the observers. For example:</p>
<pre>
            for response in self.all.message0('arg0', 'arg1'):
                print response
</pre>


<h4>Streaming Data</h4>
<p>The generator returned by 'self.all' can contain other generators in a recursive way.  This tree of generators is flattened by <a href="/compose">compose</a> in order to support program decomposition.  Each observer is able to stream data back to the observable (as in the previous code sample), but each observable can also stream data to the observers using send():</p>
<pre>
            pipeline = self.all.message0('arg0', 'arg1'):
            for data in mysource:
                pipeline.send(data)
</pre>

<p>The tree of generators (coroutines) set up by the observers (and their observers recursively) is a pipeline that consumes data and yields a response.</p>


<h4>Call Interfaces</h4>
<p>In Weightless, an interface consists of a method name. Calling a single method 'doSomething' an getting a single response is done by using 'self.any': </p>
<pre>
            response = self.any.doSomething(arg)
</pre>
<p>This will return the response of the first observer that understande 'doSomething'.</p>

<h4>
  Do, Any and All
</h4>

<p>'All' is the generic form on which 'do' and 'any' are based. 'Any' is equivalent to:</p> 
<pre>
            response = self.all.message0(arg0, arg1).next()
</pre>

<p>And 'do' is equivalent to:</p>
<pre>
            for ignore in self.all.message0(arg0, arg1):
                pass
</pre>


<h4> Dynamic Messages: 'unknown' </h4>
<p> Sending or receiving notifications without knowing the messages in advance is possible with 'unknown'.  An Observable can send messages using:</p>
<pre>
            self.all.unknown(message, arg0, arg1)
</pre>

<p>This will transparently call the method 'message' with the given arguments on all the observers.</p>

<p>Similarly, an observer can implement 'unknown' to receive messages dynamically:</p>
<pre>
            def unknown(self, message, *args, **kwargs):
                # do something
</pre>
<p>'Unknown' will only be called when no method with the name 'message' is available. This brings us back to the original notify/notify_observers, but with different names.</p>




<h4>Labeled Messages</h4>
<p>te be determined</p>


'''
    yield '''
<h2>
  Connecting Observables: DNA and be()
</h2>

The Observable Pattern defines the communication between components. The DNA and be() define the relations between the components.

<h3>DNA</h3>

<p>Like nature defines structure with DNA, so does Weightless define the structure of an application with its own DNA.</p>

<h4>Graph of Observables</h4>
<p>Weightless DNA defines a graph of Observables. For example:</p>

<pre>
            dna = (Component1(),
                      (Component2(),
                        (Component3(),)
                      ),
                      (Component4(),)
                  )
</pre>
<p>Component 2 and 4 observe component 1 and component 3 observes component 2.  Formally, DNA is defined recursively as:</p>
<pre>
            dna<sub>0</sub> = (component<sub>0</sub>, dna<sub>1</sub>, ..., dna<sub>n</sub>)
</pre>
<p>The components from dna<sub>1</sub> to dna<sub>n</sub> become observers of the component<sub>0</sub>.  The recursive definition allows copy-pasting DNA strands easily, so refactoring is possible.</p>

<p>Graps can be created by extracting a single component or a complete (sub) strand of DNA and assigning that to a variable.  This variable can then be used in different places.</p>

<p>Since DNA is normal tuples, and the whole thing is normal Python, you can do anything you like.</p>


<h4>Configuration Data</h4>
<p>The prefered way of feeding configuration data to components is by passing it to their constructors.  Take this simple configuration with two components sharing path information:</p>
<pre>
            path = '/starthere'
            dna = (Component1('myhost.org', 80, path),
                      (Component2(),
                          (Component3(path),)
                      ),
                  )
</pre>
<p>Note that sharing configuration data is straight forward, and that Component2, although in the path to Component3, does not need to know path.</p>

<p>Avoid passing through configuration data, and avoid using the environment for it.</p>


<h4>Context: transactions, logging and security</h4>
<p>Crosscutting concerns like logging, transactions and security all come down to sharing context information between components. Context information is scoped in one thread of control which, in Weightless, coincides with a (tree of) generators.</p>

<p>Observables can set context information by setting attributes on self.ctx. An log component, for example, could look like:</p>
<pre>
            class Logger(Observable):
                def unknown(self, message, *args, **kwargs):
                    self.ctx.log = []
                    yield self.all.unknown(message, *args, **kwargs)
                    for line in self.ctx.log:
                        print line
</pre>
<p>It forwards any message transparently using 'unknown', but creates a generator-local log object.  This log object collects log messages from all observers as follows:</p>
<pre>
            class Storage(Observable):
                def store(self):
                    self.ctx.log.append('store')
                    # do work here
</pre>
<p>Please be aware that self.ctx has per-generator scope much like thread-local variables have.</p>

<p>Meresco-core has a nice <a href="https://github.com/seecr/meresco-core/blob/master/meresco/core/transactionscope.py">transaction implementation</a>, although it uses the now deprecated __callstack_var_ instead of self.ctx.>/p>

<h4>Be!</h4>

The observables in the tuples are connected by calling 'be'.  This will call addObserver to create the appropriate relations:
<pre>
            appl = be(dna)
</pre>
<p>The return value 'appl' refers to the root component of the graph. Applications are often started by calling appl.main() or something like that.  See also the <a href="/example">example</a>.</p> 


<h4>Component Initialisation</h4>
<p>Components may require initialisation after all observers are registered.  This can be done by using 'once' or, for example:</p>
<pre>
            dna = ...
            appl = be(dna)
            appl.once.init()
</pre>
<p>Unlike 'all', 'any' and 'do', 'once' dispatches the message to all observers and to their observers recursively. It ensures that each component receives the message once and only once.</p>
'''
    yield page.footer(**kwargs)
