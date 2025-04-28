
import page, banner

def main(**kwargs):
    yield page.header(title="Background", **kwargs)
    yield banner.banner(**kwargs)
    yield '''
<h1>
  Background Information
</h1>

<h4>
  Why threads are unwanted
</h4>

<p>
  <a href="http://www.eecs.berkeley.edu/Pubs/TechRpts/2006/EECS-2006-1.pdf">The Problem With Threads</a> (PDF) - About why threads seem attractive at first sight (ignorant sequential programming) and why and how it bites you hard sooner or later (pre-emptive concurrent threads, locking, ...) and how must overhead there actually is involved in switching threads and do the bookkeeping, and about deadlock and.... so on.  It just explains very well why Weightless is about avoiding threads.

<h4>
  Why call-backs are unwanted
</h4>

<p>
  The problems with call-backs are well-known I suppose.  In short, call-backs obfuscate the flow of a program which makes it very hard to write correct code. Also, the code is often hard to maintain and extend.  This is the very reason why threads are often used as a alternative: they linearize the code flow again, but also bring their own problems.  Call-backs and threads are two different ways to deal with potentially blocking I/O operations, each with their own problems.
</p>

<h4>
  Why buffers are unwanted
</h4>

<p>
  Avoiding buffering is also referred to as <a href="http://en.wikipedia.org/wiki/Zero-copy">zero-copy</a>. The problems with buffering (or queuing) are subtle.  They are often seen as a solution for many problems, however, they come with problems too.  For one thing, queues present arbitrary shifts in time, which makes any assertion about the state a program should be in almost impossible.  As a result, queues are the things system administrators are inspecting all the time when something is not as expected.  Secondly, shifts in time caused by queues often break feedback loops which makes programs more complicated and error prone.  Imagine a help-desk where the clerck helps you out while on the phone, or a help-desk where your problem is registered and put into a workflow (queuing) system.  Imagine the complexity of the work-flow system which is completely unnecessary if you can deal with request immediately. Thirdly, queuing takes up resources (remember the work-flow system) and indeed, when performance engineers have removed the main performance bottlenecks of a system, what remains is a system that is busy copying data back and forth.  This data copying is often too intertwined with the code to remove it afterwards. There are classes of problems for which queuing cannot be avoided, but in many cases it is possible to avoid them, or at least contain them and limit them in both time and length.
</p>

<h4>
  How coroutines are implemented in Python
</h4>

<p>
  <a href="http://www.python.org/dev/peps/pep-0342/">PEP-342</a> and <a href="http://www.python.org/dev/peps/pep-0380/">PEP-380</a> describe how Python >=2.5 supports coroutines and how Python >=2.7 supports composition with coroutines respectively.  PEP-380 is a formalization of what Weightless' compose() does for Python <= 2.5.</a>
</p>

<h4>
  How to structure data-processing programs using Jackson Structured Programming (JSP)
</h4>

<p>
  <a href="http://www.ferg.org/papers/jackson--jsp_in_perspective.pdf">JSP in perspective</a> (PDF) - A short and well readable 1975 paper by Jackson himself about structuring programs according to the data structures they process.  It's relevance lies in the way it avoids intermediate buffering (tapes at that time, memory nowadays) by control flow inversion.  This is exactly what Weightless does.
</p>
'''
    yield page.footer(**kwargs)

