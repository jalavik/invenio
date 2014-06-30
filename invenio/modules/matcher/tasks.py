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

    Decleration of tasks for Celery.
"""

from invenio.celery import celery


@celery.task
def celery_match(record, config, site_url, username, password, index):
    """Celery task wrapper.

    :param record: The record to try matching.
    :param config: Configuration of the matching session
    :param site_url: URL of the Invenio instance to match against.
    :param username: Username for the instance.
    :param password: Password for the instance.
    :param logger: A MockLogger instance.
    :param index: Record number being matched.

    :return: tuple of Matcher result, and ``message_queue`` list from the
        :class:`LogQueue` instance.
    """
    from .utils import generate_connector, LogQueue
    from .wrappers import initiate_record_match

    connector = generate_connector(site_url, username, password)
    logger = LogQueue()
    logger.info("Celery matching record #%d", index)

    result = initiate_record_match(record, config, connector, logger, index)
    return result, logger.message_queue
