import os
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name = "pyelasticsearch",
    version = "0.0.6",
    description = "Lightweight python wrapper for elasticsearch.",
    long_description=open(os.path.join(os.path.dirname(__file__), 'README.rst'), 'r').read(),
    author = 'Robert Eanes',
    author_email = 'python@robsinbox.com',
    py_modules = ['pyelasticsearch'],
    classifiers = [
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search'
    ],
    requires=[
        'requests(>=0.9.0)',
    ],
    install_requires=[
        'requests>=0.9.0',
    ],
    test_suite='tests',
    url = 'http://github.com/rhec/pyelasticsearch'
)
