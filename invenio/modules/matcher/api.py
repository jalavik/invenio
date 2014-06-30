# -*- coding: utf-8 -*-
## This file is part of Invenio.
## Copyright (C) 2013, 2014 CERN.
##
## Invenio is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 2 of the
## License, or (at your option) any later version.
##
## Invenio is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Invenio; if not, write to the Free Software Foundation, Inc.,
## 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""
    Matcher - a tool that attempts to match a record, or a batch of records,
    against existing records within Invenio; either a local instance or remote.

    The API, main entry point to Matcher.
"""

from .utils import LazyMarcXMLReader, get_records_from_file
from .wrappers import MatcherTask, validate_records


def match_records(records, config=None, site_url=None, username='',
                  password='', log_handlers=None, lazy=True, celery=True):
    """Initiate matching of a set of records.

    The main entry point for Matcher. Given an iterable item that provides
    records and suitable configuration, Matcher will attempt to search an
    Invenio instance to find if those records exist there.

    This function can run in a lazy or non-lazy manner. If non-lazy, the
    results are returned as a ``MatcherResultSet`` class which contains all
    ``MatcherResult``s sorted by their result type. If lazy, an iterable is
    returned that provides ``MatcherResult``s.

    :param records: An iterable that gives out records.
    :param config: Dictionary containing user configuration.
    :param site_url: URL of the Invenio instance to match against. Default is
        ``localhost``.
    :param username: Username for the Invenio instance. Only needed if
        searching private collections.
    :param password: Password for the user if required for the ``username``
        parameter.
    :param log_handlers: List of instances of additional logging.handlers.
    :param lazy: Toggle lazy output.
    :param celery: Toggle Celery for distributed tasks.

    :return: :class:``MatcherResultSet`` instance if non-lazy, iterable of
        :class:``MatcherResult``s if lazy.
    """
    task = MatcherTask(records, config, site_url, username, password,
                       log_handlers, lazy, celery)
    return task.get_results()


def match_records_file(filepath, config=None, site_url=None, username='',
                       password='', log_handlers=None, lazy=True, celery=True):
    """Initiate matching of a set of records from a file.

    The main entry point for Matcher. Given an filepath to a file that contains
    MARCXML records and suitable configuration, Matcher will attempt to search
    an Invenio instance to find if those records exist there.

    This function can run in a lazy or non-lazy manner. If non-lazy, the
    results are returned as a :class:``MatcherResultSet`` class which contains
    all :class:``MatcherResult``s sorted by their result type. If lazy, an
    iterable is returned that provides :class:``MatcherResult``s.

    :param records: An iterable that gives out records.
    :param config: Dictionary containing user configuration.
    :param site_url: URL of the Invenio instance to match against. Default is
        ``localhost``.
    :param username: Username for the Invenio instance. Only needed if
        searching private collections.
    :param password: Password for the user if required for the ``username``
        parameter.
    :param log_handlers: List of instances of additional logging.handlers.
    :param lazy: Toggle lazy input and output.
    :param celery: Toggle Celery for distributed tasks.

    :return: :class:``MatcherResultSet`` instance if non-lazy, iterable of
        :class:``MatcherResult``s if lazy.
    """
    if lazy:
        records = LazyMarcXMLReader(filepath, parse_xml=True)
    else:
        records = get_records_from_file(filepath)
    task = MatcherTask(records, config, site_url, username, password,
                       log_handlers, lazy, celery)
    return task.get_results()


def compare_records(record1, record2, config=None, log_handlers=None):
    """Test similarity of two records.

    Given two records, this compares and returns a validation result to show
    the similarity between the records.

    :param record1: First record to match.
    :param record2: Second record to match.
    :param config: Dictionary containing user configuration. TODO
    :param log_handlers: List of instances of additional logging.handlers. TODO

    :return: Similarity as a float where 1.0 is an exact match and 0.0 is no
        match.
    """
    return validate_records(record1, record2, config, log_handlers)
