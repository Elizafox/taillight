# taillight

[![CI](https://github.com/Elizafox/taillight/actions/workflows/ci.yml/badge.svg)](https://github.com/Elizafox/taillight/actions/workflows/ci.yml)
[![Downloads per month](https://img.shields.io/pypi/dm/taillight.svg)](https://pypi.org/project/taillight/)
[![Python versions](https://img.shields.io/pypi/pyversions/taillight.svg)](https://pypi.org/project/taillight/)
[![PyPI version](https://img.shields.io/pypi/v/taillight.svg)](https://pypi.org/project/taillight/)

Taillight is a signal/slots system similar in concept to
[Blinker](https://github.com/jek/blinker), but supporting priorities and is
designed to be lightweight and easy to understand.

Thread-safety is a priority and therefore everything is carefully designed to
use mutexes. It should be safe to use Signal instances across threads.

## Support

Questions, bug reports, and feature requests are welcome in the
[issue tracker](https://github.com/Elizafox/taillight/issues).

Pull requests and patches are always welcomed. Features can be requested via
the bug tracker.

## License and copyright

Copyright © 2013-2026 A. Wilcox and Elizabeth Myers. All rights reserved.

This work is licensed either under the WTFPL or LPRAB, at your option (the two
licenses are equivalent). Terms and conditions can be found at:

        https://www.wtfpl.net/about/
        https://sam.zoy.org/lprab/
