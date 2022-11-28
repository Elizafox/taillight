#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(name="taillight",
      version="0.5.1",
      description="An implementation of signals and slots, with priorities.",
      author="Elizabeth Myers",
      author_email="elizabeth@interlinked.me",
      url="http://github.com/Elizafox/taillight",
      packages=find_packages(exclude=["build", "contrib", "doc", "tests*"]),
      classifiers=[
          "Development Status :: 4 - Beta",
          "Intended Audience :: Developers",
          "Topic :: Software Development",
          "Topic :: Software Development :: Libraries :: Python Modules",
          "Programming Language :: Python :: 3 :: Only",
          "Programming Language :: Python :: 3.5",
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: 3.7",
          "Programming Language :: Python :: 3.8",
          "Programming Language :: Python :: 3.9",
          "Programming Language :: Python :: 3.10",
          "Programming Language :: Python :: 3.11",
          "Operating System :: OS Independent",
          "License :: DFSG approved",
      ])
