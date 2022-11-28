# taillight

[![Build Status](https://travis-ci.org/Elizafox/taillight.svg?branch=master)](https://travis-ci.org/Elizafox/taillight)
[![Downloads per month](https://img.shields.io/pypi/dm/taillight.svg)](https://pypi.org/project/taillight/)
[![Python versions](https://img.shields.io/pypi/pyversions/taillight.svg)](https://pypi.org/project/taillight/)
[![PyPI version](https://img.shields.io/pypi/v/taillight.svg)](https://pypi.org/project/taillight/)

Taillight is a signal/slots system similar in concept to
[Blinker](https://github.com/jek/blinker), but supporting priorities and is
designed to be lightweight and easy to understand.

Thread-safety is a priority and therefore everything is carefully designed to
use mutexes. It should be safe to use Signal instances across threads.

## Support
We can be reached easily at irc.interlinked.me #foxkit.us to answer any
questions you may have.

Pull requests and patches are always welcomed. Features can be requested via
the bug tracker.

## License and copyright
Copyright © 2013-2022 A. Wilcox and Elizabeth Myers. All rights reserved.

This work is licensed either under the WTFPL or LPRAB, at your option (the two
licenses are equivalent). Terms and conditions can be found at:

        http://www.wtfpl.net/about/
        http://sam.zoy.org/lprab/
