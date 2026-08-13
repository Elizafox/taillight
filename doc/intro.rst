Introduction
============

Taillight is a signals and slots framework similar in concept to Blinker_. The
main difference is instead of ``connect`` and ``disconnect`` methods, there
are ``add`` and ``delete`` methods. There is also the ability to prioritise
the order in which slots are called.

.. _Blinker: https://blinker.readthedocs.io/

A simple example
----------------

.. code-block:: python

  from taillight import Signal
  
  s = Signal("test")
   
  def method(sender):
      print("I was called from: {!r}".format(sender))
  
  s.add(method)
  s.call("testcall")

Which would call method and show that it was called from ``"testcall"``.


Priorities
----------

Signals support adding slots in priority order:

.. code-block:: python
  
  from taillight import Signal
  
  s = Signal("test")
  
  def first(sender):
      print("Called first!")
  
  def second(sender):
      print("Called second!")
  
  def third(sender):
      print("Called third")
  
  s.add(second, priority=2)
  s.add(first, priority=1)
  s.add(third, priority=2)
  s.call("test")

As illustrated by this example, priorities, by default, are run lowest first.
At first this may seem counterintuitive; but consider that counting usually
starts from 0 or 1. This is how the lists are ordered by default. Pass
``priority_order=PriorityOrder.DESCENDING`` to
:class:`~taillight.signal.Signal` to run higher numeric priorities first. The
historical ``prio_descend`` argument remains as a compatibility alias.

Also note in the example that second and third have the same priority; when
two items have the same priority, the one added later is called second. This
is because each slot has its own unique ID (uid), a number that is
monotonically increasing with each added slot. This makes all slots run in a
predictable order, regardless of whether or not a priority was specified.

Listeners
---------

The object passed to ``call()`` or ``emit()`` is the *sender*. A slot's
``listener`` is its optional sender filter. The default listener is the
special sentinel ``ANY``, which accepts every sender. A more specific listener
accepts calls where the sender is ``ANY`` or matches that listener.

Invocation snapshots
--------------------

Each invocation takes a snapshot of its matching slots before calling them.
Connecting or disconnecting slots while an invocation is active affects later
invocations, not the one already in progress.

Typed signals
-------------

Signals are generic in their resolved callback result type::

  from taillight import Signal

  changed: Signal[int] = Signal("changed")
  changed.connect(lambda sender: 42)
  result = changed.emit("example")

Example:

.. code-block:: python

  from taillight import ANY, Signal
  
  s = Signal("test")
  
  def listener(sender):
      print("listener got: {!r}".format(sender))
  
  s.add(listener, listener="x")
  s.add(listener, listener="y")
  s.add(listener)  # Listening on ANY
  
  s.call("x")  # This calls the x and any listeners
  s.call("y")  # This calls the y and any listeners
  s.call(ANY)  # This calls all three listeners

Searching
---------

Taillight supports searching for slots by uid, function, or listener:

.. code-block:: python
  
  from taillight import ANY, Signal
  
  s = Signal("test")
  
  def function(sender):
      print("called")
  
  slot_1 = s.add(function, listener="x")
  slot_2 = s.add(function)
    
  print("Find by UID:", s.find_uid(slot_1.uid), s.find_uid(slot_2.uid))
  print("Find by function:", s.find_function(function))
  print("Find by listener x:", s.find_listener("x"))
  print("Find by listener ANY:", s.find_listener(ANY))

Performance
-----------

Taillight is primarily optimised for fast execution of slots, as execution is
assumed to take place far more often than insertions. Speed of insertion is
decent, but is somewhat suboptimal compared to Blinker, since the order of a
priority list must be maintained. Execution of slots is always O(n), where n
is the number of slots on the signal.

Slot insertion and deletion are more complicated. Taillight uses bisection to
find an insertion point in O(log n) time and stores slots in a deque. The
insertion itself may still require moving elements, so insertion and deletion
costs become noticeable mainly when a signal contains many slots.
