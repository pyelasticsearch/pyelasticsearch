import codecs
import os
import re

from setuptools import setup, find_packages


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
    version=find_version("pyelasticsearch/__init__.py"),
    description="Lightweight python wrapper for elasticsearch.",
    long_description=read('README.rst') + '\n\n' +
                     '\n'.join(read('docs', 'source', 'versions.rst')
                                   .splitlines()[1:]),
    author='Robert Eanes',
    author_email='python@robsinbox.com',
    packages=find_packages(exclude=['ez_setup']),
    include_package_data=True,
    zip_safe=False,
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
    test_suite='pyelasticsearch.tests',
    url='http://github.com/rhec/pyelasticsearch'
)
