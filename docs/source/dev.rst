=================
Development Notes
=================

Testing
=======

To run the tests::

    % python setup.py test

This should automatically install the additional dependencies required for
testing if you don't have them.


Documentation
=============

Documentation is located in ``docs/`` and requires `Sphinx
<http://sphinx-doc.org/>`_ to build.

To get the requirements::

    % pip install Sphinx

To build the docs::

    % cd docs/
    % make html

Documentation committed and pushed to the main repository is available
on ReadTheDocs at `<http://pyelasticsearch.readthedocs.org/>`_.


Philosophy
==========

pyelasticsearch is intended as a low-level, lossless API to elasticsearch. That
is, it generally refrains from adding abstractions that limit flexibility or
power. For example, it handles JSON conversion because there is a strict
one-to-one mapping between JSON and Python dictionaries: nothing is lost. It
converts bad HTTP status codes to exceptions, but you can still access the raw
codes and responses by drilling into the exceptions.

Therefore, pyelasticsearch is a good choice for building higher-level APIs
upon—ones which make common cases easier but where certain edge cases feel like
"coloring outside the lines". One such library is `elasticutils
<https://pypi.python.org/pypi/elasticutils/>`_. However, pyelasticsearch is
also meant to be directly usable by humans: a great deal of care has been taken
to keep calls brief, understandable, consistent, and error-resistant and to
deal in data structures which are easy to manipulate with Python's built-in
routines.

Patches along these lines are always welcome. Thank you for trying
pyelasticsearch!
