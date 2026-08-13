#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(name="taillight",
      version="0.6.0",
      description="An implementation of signals and slots, with priorities.",
      author="Elizabeth Ashford",
      author_email="elizabeth.jennifer.myers+taillight@gmail.com",
      url="https://github.com/Elizafox/taillight",
      python_requires=">=3.10",
      packages=find_packages(exclude=["build", "contrib", "doc", "tests*"]),
      classifiers=[
          "Development Status :: 4 - Beta",
          "Intended Audience :: Developers",
          "Topic :: Software Development",
          "Topic :: Software Development :: Libraries :: Python Modules",
          "Programming Language :: Python :: 3 :: Only",
          "Programming Language :: Python :: 3.10",
          "Programming Language :: Python :: 3.11",
          "Programming Language :: Python :: 3.12",
          "Programming Language :: Python :: 3.13",
          "Programming Language :: Python :: 3.14",
          "Operating System :: OS Independent",
      ])
