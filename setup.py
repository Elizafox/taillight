#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(name="taillight",
      version="0.1a1",
      description="An implementation of signals and slots, with priorities.",
      author="Elizabeth Myers",
      author_email="elizabeth@interlinked.me",
      url="<none yet>",
      packages=find_packages(exclude=["build", "contrib", "docs", "tests*"]),
      classifiers=[
          "Development Status :: 3 - Alpha",
          "Intended Audience :: Developers",
          "Topic :: Software Development",
          "Topic :: Software Development :: Libraries :: Python Modules",
          "Programming Language :: Python :: 3 :: Only",
          "Programming Language :: Python :: 3.4",
          "Operating System :: OS Independent",
          "License :: DFSG approved",
      ]
)
