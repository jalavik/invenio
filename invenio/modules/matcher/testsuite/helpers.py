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

    Helper functions used in the test suite.
"""

from random import randint

from ..utils import LogQueue

# ============================ test_utils helpers ============================

CELERY_TEST_CONF = {
    'CELERY_MAX_QUEUE_LENGTH': 10,
    'CELERY_SLEEP_TIME': 1
}


class MockTaskResult(object):
    """ Mock testing class of Celery AsyncResult """
    def __init__(self, rec):
        self.readycount = randint(1, 5)
        # TODO: Replace with MatcherTaskResult
        self.rec = rec
        self.result = None
        self.status = 'STARTED'
        self.traceback = "Traceback goes here"
        self.log = LogQueue()
        self.log.info("Logging info")
        self.log.error("Logging error")
        try:
            self.perform_match()
        except Exception:
            self.status = 'FAILURE'

    def perform_match(self):
        if 'EXCEPTION-TIME' in self.rec:
            raise ValueError
        # Act as though we perform matching
        self.status = 'SUCCESS'

    def ready(self):
        """Emulates Celery AsyncResult.ready()"""
        self.readycount -= 1
        if self.readycount <= 0:
            self.result = (('new', self.rec), self.log.message_queue)
            return True
        else:
            return False

    def successful(self):
        """Emulates Celery AsyncResult.successful()"""
        return True if self.status == 'SUCCESS' else False

    def failed(self):
        """Emulates Celery AsyncResult.failed()"""
        return True if self.status == 'FAILURE' else False


def mock_celery_func(record, config, site_url, username, password, index):
    """Mock celery-decorated matching function.

    Uses Mock() to emulate celery.delay decorator. This function represents
    :func:`celery_match` from ``tasks``

    :return: :class:`MockTaskResult` to represent :class:`AsyncResult` object
    """
    assert config == CELERY_TEST_CONF
    assert site_url is 'site'
    assert username is 'user'
    assert password is 'pass'
    assert isinstance(index, int)
    return MockTaskResult("%s%s" % (record, '--CELERY_PROCESSED'))


def check_internal_values(feeder):
    """Status checker, checks the values inside feeder are ok"""
    assert len(feeder.results) <= CELERY_TEST_CONF['CELERY_MAX_QUEUE_LENGTH']
