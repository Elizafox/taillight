Release notes
=============

0.7.0
-----

Taillight 0.7 modernises the supported Python versions, packaging, typing,
asynchronous callbacks, and named-signal construction.

Deferral migration
~~~~~~~~~~~~~~~~~~

``Signal.call()`` and ``Signal.call_async()`` now always begin a new
invocation. Use ``Signal.resume()`` or ``Signal.resume_async()`` to continue
the most recently deferred invocation::

   result = signal.call(sender, value)
   if result.status is SignalStatus.STATUS_DEFER:
       result = signal.resume(sender)

More than one invocation may be deferred. Pending invocations form a stack
and are resumed in last-in, first-out order. ``reset_defer()`` discards only
the next invocation; use ``reset_defers()`` to discard the entire stack.

Call results
~~~~~~~~~~~~

Calls now return immutable ``CallResult`` sequences with ``values`` and
``status`` attributes. They compare equal to equivalent lists and tuples for
straightforward migration. ``SignalResult`` remains as a deprecated alias.
Prefer per-call status to ``Signal.last_status`` when calls may run
concurrently::

   result = await signal.call_async(sender)
   if result.status is SignalStatus.STATUS_STOP:
       ...

Typing
~~~~~~

``Signal`` and ``Slot`` are generic in their callback result type. The wheel
includes a ``py.typed`` marker, so installed-package annotations are visible
to type checkers::

   signal: Signal[int] = Signal()
   values = await signal.call_async(sender)  # CallResult[int]

Priority naming
~~~~~~~~~~~~~~~

Use ``priority_order=PriorityOrder.ASCENDING`` (the default) or
``PriorityOrder.DESCENDING``. The historical ``prio_descend`` spelling is
retained for compatibility, but its inverted meaning makes new code harder to
read.
