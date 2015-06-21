# taillight
Taillight is a signal/slots system similar in concept to
[Blinker](https://github.com/jek/blinker), but supporting priorities and is
designed to be lightweight and easy to understand.

Thread-safety is a priority and therefore everything is carefully designed to
use mutexes. It should be safe to use Signal instances across threads.

Licensed under the WTFPL. Enjoy.
