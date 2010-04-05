from distutils.core import setup
import setuptools

setup(
    name = "pyelasticsearch",
    version = "0.0.3",
    description = "Lightweight python wrapper for elastic search.",
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
    url = 'http://github.com/rhec/pyelasticsearch'
)