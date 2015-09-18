#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(name="taillight",
      version="0.2b4",
      description="An implementation of sigs and slots, with priorities.",
      author="Elizabeth Myers",
      author_email="elizabeth@interlinked.me",
      url="http://github.com/Elizafox/taillight",
      packages=find_packages(exclude=["build", "contrib", "docs", "tests*"]),
      classifiers=[
          "Development Status :: 4 - Beta",
          "Intended Audience :: Developers",
          "Topic :: Software Development",
          "Topic :: Software Development :: Libraries :: Python Modules",
          "Programming Language :: Python :: 3 :: Only",
          "Programming Language :: Python :: 3.3",
          "Programming Language :: Python :: 3.4",
          "Operating System :: OS Independent",
          "License :: DFSG approved",
      ])
