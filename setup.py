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
                     '\n'.join(read('docs', 'source', 'changelog.rst')
                                   .splitlines()[1:]),
    author='Robert Eanes',
    author_email='python@robsinbox.com',
    maintainer='Jannis Leidel',
    maintainer_email='jannis@leidel.info',
    license='BSD',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search'
    ],
    requires=[  # Needed?
        'requests(>=1.0,<2.0)',
        'simplejson(>=2.1.0)'
    ],
    install_requires=[
        'requests>=1.0,<2.0',
        'simplejson>=2.1.0'
    ],
    tests_require=['mock'],
    test_suite='pyelasticsearch.tests',
    url='http://github.com/rhec/pyelasticsearch'
)
