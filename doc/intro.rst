Introduction
============

Taillight is a signal and slots framework similar in concept to blinker_. The
main difference is instead of ``connect`` and ``disconnect`` methods, there
are ``add`` and ``delete`` methods. There is also the ability to prioritise
the order in which slots are called.

.. _blinker: https://pythonhosted.org/blinker/

A simple example
----------------

.. code:: python

  from taillight import signal
  
  s = signal.Signal("test")
   
  def method(caller):
      print("I was called from: {!r}".format(caller))
  
  s.add(method)
  s.call("testcall")

Which would call method and show that it was called from ``"testcall"``.


Priorities
----------

Signals support adding slots in priority order:

.. code:: python
  
  from taillight import signal
  
  s = signal.Signal("test")
  
  def first(caller):
      print("Called first!")
  
  def second(caller):
      print("Called second!")
  
  def third(caller):
      print("Called third")
  
  s.add(second, priority=2)
  s.add(first, priority=1)
  s.add(third, priority=2)
  s.call("test")

As illustrated by this example, priorities, by default, are run lowest first.
At first this may seem counterintuitive; but consider that counting usually
starts from 0 or 1. This is how the lists are ordered by default. By passing a
parameter to signal, the behaviour can be altered to go in reverse.

Also note in the example that second and third have the same priority; when
two items have the same priority, the one added later is called second. This
is because each slot has its own unique ID (uid), a number that is
monotonically increasing with each added slot. This makes all slots run in a
predictable order, regardless of whether or not a priority was specified.

Listeners
---------

Signals support listening for specific events. The default listener is the
special sentinel ANY, which means they will be called on all events, no matter
what. Conversely, if they have a more specific listener, they will not be
called unless the sender is set to ANY, or the sender matches the listener.

Example:

.. code:: python

  from taillight import signal, ANY
  
  s = signal.Signal("test")
  
  def listener(caller):
      print("listener got: {!r}".format(caller))
  
  s.add(listener, listener="x")
  s.add(listener, listener="y")
  s.add(listener)  # Listening on ANY
  
  s.call("x")  # This calls the x and any listeners
  s.call("y")  # This calls the y and any listeners
  s.call(ANY)  # This calls all three listeners

Searching
---------

Taillight supports searching for slots by uid, function, or listener:

.. code:: python
  
  from taillight import signal, ANY
  
  s = signal.Signal("test")
  
  def function(caller):
      print("called")
  
  slot_1 = s.add(function, listener="x")
  slot_2 = s.add(function)
    
  print("Find by UID:", s.find_uid(slot_1.uid), s.find_uid(slot_2.uid))
  print("Find by function:", s.find_function(function))
  print("Find by listener x:", s.find_listener("x"))
  print("Find by listener ANY:", s.find_listener(ANY))

Performance
-----------

Taillight is primarily optimised for fast execution of slots, at the cost of
insertion (since priority must be maintained). Execution of slots is O(n),
where n is the number of slots on the signal. Later optimisations may be added
to limit the cost of specific listeners to only the number of slots listening
on that listener.

Slot insertion and deletion are more complicated. The worst case O(n) insert
on the list only happens if an insertion happens at the head (lower priority
items in the default Signal priority mode), but incurs very little penalty
from the bisection algorithim. On the other hand, if insertion happens at the
tail (higher priority in the default Signal priority mode), the O(log n)
bisection algorithim penalty dominates; insertions at the tail are O(1). When
the list is unprioritised, most insertions will be O(log n).

At some point in the future we may transition to a deque (which will improve
performance at the head at the expense of insertion performance at the middle
of the list), but presently the standard deque container does not support an
insert method.

In the meantime, the performance penalty should only be important if you are
making use of thousands of slots.


