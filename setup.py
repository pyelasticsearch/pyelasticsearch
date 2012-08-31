import codecs
import os
import re
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def read(*parts):
    return codecs.open(os.path.join(os.path.dirname(__file__), *parts)).read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


setup(
    name="pyelasticsearch",
    version=find_version("pyelasticsearch.py"),
    description="Lightweight python wrapper for elasticsearch.",
    long_description=read('README.rst'),
    author='Robert Eanes',
    author_email='python@robsinbox.com',
    py_modules=['pyelasticsearch'],
    classifiers=[
        'Development Status :: 3 - Alpha',
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
    tests_require=['mock'],
    test_suite='tests',
    url='http://github.com/rhec/pyelasticsearch'
)
