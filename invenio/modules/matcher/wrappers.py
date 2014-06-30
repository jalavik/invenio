# -*- coding: utf-8 -*-
## This file is part of Invenio.
## Copyright (C) 2014 CERN.
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

    Wrappers for functions called by the API.
"""

from .engine import match_records
from .utils import (CeleryFeeder, ResultType, generate_config,
                    generate_logger, generate_connector)
from .validator import validate_match, get_validation_ruleset


class MatcherResultSet(object):
    """Acts as a template. Should be replaced by a model later"""
    def __init__(self, results, config, site_url, username, using_password):
        """
        :param results: Returned from initiate_record_match.
        :param config: Final config used for matching.
        :param site_url: Invenio instance matched against.
        :param username: Username used for the matching instance.
        :param using_password: Boolean, was a password used?
        """
        # Create five lists to contain all results
        for result_type in ResultType.ALL:
            self.__setattr__(result_type, [])
        self.all = results

        for result in results:
            self.__getattribute__(result[0]).append(result)

        self.site_url = site_url
        self.username = username
        self.using_password = using_password


def legacy_bibmatch(record, config, connector, logger, index):
    """Wrapper for the soon-to-be depreciated engine.match_records

    :param record: Single record to match.
    :param config: Dictionary containing *final* configuration.
    :param connector: InvenioConnector instance.
    :param logger: logger object.
    :param index: Record index of the current set.

    :return: Tuple of result type and result"""
    try:
        logger.info(" --- Matching record #%d ---", index)
        result_sets = match_records(
            [record], config, connector, search_mode=None, operator="and",
            verbose=1, modify=0, clean=False, fuzzy=True, ascii_mode=False)
        for restype, reslist in zip(ResultType.SUCCESSES, result_sets):
            if reslist:
                return (restype, reslist[0])
    except Exception as err:
        logger.error(str(err))
        return (ResultType.ERROR, record)
    raise TypeError("No result returned from Engine!")


def initiate_record_match(record, config, connector, logger, index):
    """Wrapper, to be replaced with a class MatcherJob"""
    return legacy_bibmatch(record, config, connector, logger, index)


class MatcherTask(object):
    """Represents an instance of Matcher used to match multiple records.

    This class is created at the API level and given sufficient configuration
    to complete matching and return a result set.

    The :meth:`get_results` method is used to get a result set, either as a
    :class:`ResultSet` if not lazy matching or an iterable containing
    individual Matcher results.
    """
    def __init__(self, records, config, site_url, username, password,
                 log_handlers, lazy, celery):
        """
        :param records: An iterable that gives out records.
        :param config: Dictionary containing *user* configuration.
        :param site_url: URL of the Invenio instance to match against. Default
            is ``localhost``.
        :param username: Username for the Invenio instance. Only needed if
            searching private collections.
        :param password: Password for the user if required for the ``username``
            parameter.
        :param log_handlers: List of instances of additional logging.handlers.
        :param lazy: Toggle lazy output.
        :param celery: Toggle Celery for distributed tasks.
        """
        self.records = records
        self.site_url = site_url
        self.username = username
        self.using_password = bool(password)
        self.lazy = lazy
        self.celery = celery

        self.conf = generate_config(config)
        self.log = generate_logger(log_handlers)

        if celery:
            self.feeder = CeleryFeeder(records, self.conf, site_url,
                                       username, password, self.log)
            self.feeder.begin_feeding()
        else:
            self.connector = generate_connector(site_url, username, password)

    def _perform_matching(self):
        """Private method, performs matching task without celery"""
        for index, record in self.records:
            result = initiate_record_match(record, self.conf, self.connector,
                                           self.log, index)
            yield result

    def get_results(self):
        """Get results back from the Matcher.

        :return: If lazy-matching, returns an iterable that returns Matcher
            Results. If non-lazy matching returns a :class:``MatcherResultSet``
        """
        if self.celery:
            if self.lazy:
                return self.feeder.__iter__()
            else:
                return MatcherResultSet(self.feeder, self.conf, self.site_url,
                                        self.username, self.using_password)
        else:
            if self.lazy:
                return self._perform_matching()
            else:
                return MatcherResultSet(
                    self._perform_matching(), self.conf, self.site_url,
                    self.username, self.using_password)


def validate_records(rec1, rec2, config, log_handlers):
    """Takes two records, uses the validator to compare the records.

    :param rec1: Acts as original record.
    :param rec2: Foreign record to match.
    :param config: Config may contain validation rules. TODO
    :param log_handlers: Validator may log information. TODO

    :return: Similarity represented as a float where 1.0 is an exact match and
        0.0 is no match.
    """
    ruleset = get_validation_ruleset(rec1)
    if not ruleset:
        raise ValueError("Ruleset is blank!")
    return validate_match(rec1, rec2, ruleset)
