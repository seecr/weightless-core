
<h1>
  Example
</h1>

<h2>
  Hello World
</h2>

<p>
  Below is a simple HTTP server that answers a request from a browser with "Hello!":
</p>

<pre>
  from weightless import Reactor, Server, HttpProtocol, http, be

  class HelloWorld(object):
      def processRequest(self, *args, **kwargs):
          yield http.ok()
          yield http.headers('Content-Length', 6)
          yield 'Hello!'

  reactor = Reactor()

  dna = \\
      (Server(reactor, 8080),
          (HttpProtocol(),
              (HelloWorld(),)
          )
      )

  server = be(dna)
  reactor.loop()
</pre>

<p>Simply start this server with:</p>

<pre>
  $ python httpserver.py
</pre>

<p>
  Next, use your browser to go to <a href="http://localhost:8080/">http://localhost:8080</a>.
</p>

<p>
  In practice, you would have the class HelloWorld in a separate file.  We call the remaining things in httpserver.py the <i>server configuration</i>.  
</p>


<h2>
  Real-world server configurations
</h2>

<p>
  If you like to see large real-world server configurations, take a look at the example in Meresco: <a href="https://github.com/seecr/meresco-examples/blob/master/meresco/examples/dna/server.py">server.py</a>.
</p>
