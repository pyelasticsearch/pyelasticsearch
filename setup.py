import codecs
import re
from os.path import join, dirname

# Prevent spurious errors during `python setup.py test`, a la
# http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html:
try:
    import multiprocessing
except ImportError:
    pass

from setuptools import setup, find_packages


def read(filename):
    return codecs.open(join(dirname(__file__), filename), 'r').read()


def find_version(file_path):
    version_file = read(file_path)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError('Unable to find version string.')


setup(
    name='pyelasticsearch',
    version=find_version(join('pyelasticsearch', '__init__.py')),
    description='Flexible, high-scale API to elasticsearch',
    long_description=read('README.rst') + '\n\n' +
                     '\n'.join(read(join('docs', 'source', 'changelog.rst'))
                                   .splitlines()[2:]),
    author='Robert Eanes',
    author_email='python@robsinbox.com',
    maintainer='Erik Rose',
    maintainer_email='erik@mozilla.com',
    license='BSD',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        # simplejson doesn't support 3.1 or 3.2.
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search'
    ],
    install_requires=[
        'elasticsearch>=1.0.0,<2.0.0',
        'urllib3>=1.8,<2.0',
        'simplejson>=3.0',
        'six>=1.4.0,<2.0'
    ],
    tests_require=['mock', 'nose>=1.2.1'],
    test_suite='nose.collector',
    url='https://github.com/pyelasticsearch/pyelasticsearch'
)
