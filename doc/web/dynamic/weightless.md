
import banner, page

def main(**kwargs):
    yield page.header(**kwargs)
    yield banner.banner(**kwargs)

    yield '''
<h1> Weightless </h1>

<h2> Introduction  </h2>

<p>Weightless supports implementing complete Python programs as co-routines, including protocol stacks, such as the HTTP protocol. Weightless consists of three major parts:</p>
<ol>
  <li><a href="/compose">compose</a>: program decomposition with coroutines (a la PEP380).</li>
  <li><a href="/observer">observable</a>: component configuration with the observer pattern (DNA)</li>
  <li><a href="/gio">gio</a>: connecting file descriptors to a coroutine</li>
</ol>

<p>Weightless is quite well refactored and small (<1000 loc), fully unit-tested and fast.</p>

<p>This <a href="/example">example</a> shows how to use Weightless to create a simple server.</p>

<p>There is a bit more <a href="/background">background information</a> motivating many design decisions.</p>

<p>Weightless is in use by <a href="http://meres.co">Meresco</a>.  Meresco uses its own version for which free <a href="http://repository.seecr.nl">Debian and Redhat packages</a> are provided.</p>

<h2> Sources, Download and Install </h2>

<p>(Currently being split into weightless-core and weightless-http)</p>

<p>* <a href="https://github.com/seecr/weightless-core/">Browse Sources</a>
   * <a href="/weightlessrss">RSS commit log</a></p>

<p>Check out, run the tests, install and run the <a href="/example">example</a>:</p>

<p>(Under construction while at EuroPython 2011)</p>

<pre>
    $ svn co http://weightless.svn.sourceforge.net/svnroot/weightless/weightless-core/tags/version_0.6.0.1 weightless-0.6.0.1
    $ cd weightless-0.6.0.1
    $ (cd test; ./alltests.sh)
    $ python setup.py install
    $ cd weightless/examples
    $ python httpserver.py
    $ wget "http://localhost:8080/" -O - --quiet
    Hello!
    $
</pre>


<h2> Weightless at Conferences </h2>

<h4>EuroPython 2011</h4>
<p><a href="http://ep2011.europython.eu/conference/talks/beyond-python-enhanched-generators">Beyond Python Enhanced Generators</a> introduces the notion of backtraces, flow control, push-back and local on top of PEP 342 and 280, as implemented in compose().
</p>

<h4> EuroPython 2010 </h4>

<p><a href="http://ep2010.europython.eu/talks/talk_abstracts/#talk19">A Pythons DNA</a> introduces the configuration part of Weightless: the DNA.  It introduces a little bit of compose() and program decomposition with generators.</p>

<h4> Software Practice Advancement Conference (SPA) 2008 </h4>

<p><i>Program Decomposition with Python Generators</i> based on Weightless' compose() has been presented and explored on the <a href="http://www.spaconference.org/spa2008/sessions/session130.html">Software Practice Advancement 2008</a> conference. For the results, look <a href="http://www.spaconference.org/cgi-bin/wiki.pl/?ProgramDecompositionWithPython">here</a>.</p>

<h4> Agile Open conference </h4>

<p>On <a href="http://www.agileopen.net/en/agile-open-europe-2008">Agile Open 2008</a> the notion on decomposition with generalized generators was introduced in an Open Space session.</p>


<h4> Dutch Linux Users Group (NLLGG) 2008 </h4>

<p> Many parts of Weightless are presented on <a href="http://www.nllgg.nl/bijeenkomst_20081004_agenda">Nederlandse Linux Gebruikersgroep 2008 in Utrecht</a>.  Most notably, coroutines and the way you can use them to escape from call-back hell are discussed.  See the <a href="https://github.com/seecr/weightless-core/tree/master/weightless/examples">callbackvsgenerator stuff on github</a>. (UPDATE July 2010: This resembles a more general example of 'taming callbacks with generators', as presented by Raymond Hettinger on EuroPython: <a href="http://www.europython.eu/talks/talk_abstracts/index.html#talk61">Taming Twisted with Generators</a>.)</p>


<h4> Python Users Netherlands (PUN) </h4>

<p>During the <a href="http://wiki.python.org/moin/PUN/">november 2008 meeting of the PUN in Rotterdam</a>, the demonstration of co-routines is continued.  Especially, the way you can do program decomposition using <a href="/compose">compose</a> is demonstrated using this <a href="https://github.com/seecr/weightless-core/blob/master/weightless/examples/decomposition.py">example code</a>.</p>



<h2>Related Work</h2>

<p>Below are some other alternatives, initiatives and approaches, with a few short comments on them.</p>

<ol>
<li>Spasmoidal - a very abstract task-dispatcher based on Python 2.5 generators which features a Pollster (Reactor) and a Socket Acceptor.  It clearly suffers lack of program decomposition with generators, as the Spasmodoidal Tasks are very long single generators.  Doug's approach is very generalized (it's more than only I/O) and I think that Doug Fort and I can learn a lot from each other!</li>

<li>Twisted - a popular asynchronous networking library that contains many useful ideas.  I have had the most experience with this library, and learned how not to solve common problems.  It probably is the most popular one in the Python scene, but, as often happens with software once accepted by broader public, it suffers from an old and insufficient architecture, which hinders development.  As an example, the Twisted folks seem to talk about but never implement sendfile funtionality.  Pitty we had to abandon this one.</li>

<li>Asynchio created by Vladimir Sukhoy contains some very interesting idea's.  It implements the Asynchronous Completion Token pattern (Proactor) and it is truely asynchronous.  It is a library that focusses on I/O and not on generators, and it is clear that the interface is a bit complicated to create networking programs every day.  It might be more appropriate to (re)use parts of it under the Weightless cover.</li>

<li><a href="http://viral.media.mit.edu/peers/doc/info.html">Peers</a> seems to be gone.  I can't find it anymore at viral.media.mit.edu. <a href="http://aphex.media.mit.edu/cgi-bin/cvsweb/peers/">Peers sources</a> seem to be dead.</li>

<li><a href="http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/365292">Active Objects</a> Only a pattern, not a real implementation.  Interesting though.</li>

<li><a href="http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/365640">Thread Safe MultiQueue</a></li>

<li><a href="http://pyds.muensterland.org/wiki/continuationbasedserver.html">Continuations</a> Continuations! Yes! Though this is very interesting, the main reason why Weightless explores generators, is the fact that generators can make event drivven programming as easy (in fact: easier, if you take the problems of threading that appear later into account) as writing a sequential piece of code in a threaded environment. Continuations, I believe - unless properly embedded in langauges such as Smalltalk - will not likely make it because it is too abstract for many human beings (at least me) to understand. But I can't deny George Bauer's work is cool! UPDATE: This seems to be gone.  I can't find it anymore. ;-(</li>

<li><a href="http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/498141">Generator Coroutine Access to Its Own Handle</a> (from Doug Fort's Spasmoidal) describes a solution to a common problem you'll hit when diving into this subject: a 'self' or 'this' for generators. Only a pattern description, the implementation is in Spadmoidal. And there is a much better way to do it, btw: use reflection to get 'this' from the callstack with a short and efficient this() method.</li>

<li><a href="http://code.google.com/p/python-multitask/">MultiTask</a> - This is the only other initiative I have found that really solves the decomposition problem and it combines generators with I/O; two problems Weightless addresses as well. Very neat solution and good implementation!</li>

<li><a href="http://code.google.com/p/cogen/">Cogen</a></li>

<li><a href="http://www.goldb.org/goldblog/2007/02/14/TrampoliningWithGeneratorsRollYourOwnScheduler.aspx">Trampolining</a> Seems to be gone.</li>

<li><a href="http://wiki.secondlife.com/wiki/Eventlet">Eventlets</a> Looks promising, still have to look closer.</li>

<li><a href="http://blog.gevent.org/">gEvent</a> A very thoughtful piece of work by Denis Bilenko. He presented it at EuroPython and he really knows a lot about this topic.  gEvent will probably become widely adopted.</li>

<li><a href="http://github.com/saucelabs/monocle">Monocle</a> is a little framework for taming callbacks with generators. It seems compatible with multiple asynchrounous I/O frameworks.  It does not do program decomposition though</li>

</ol>
'''
    yield page.footer(**kwargs)
