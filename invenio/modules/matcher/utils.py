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

    Utilities (misc bits'n'bobs) for use with Matcher.
"""

import re
import sys
import codecs

from time import sleep
from six import StringIO, next, iteritems
from threading import Thread, BoundedSemaphore
from traceback import format_exc

from invenio.base.globals import cfg, current_app
from invenio.legacy.bibrecord import create_record, create_records
from invenio.utils.connector import (InvenioConnector,
                                     InvenioConnectorAuthError,
                                     InvenioConnectorServerError)
from invenio.legacy.bibrecord.scripts.xmlmarc2textmarc import (
    get_sysno_from_record, create_marc_record)

from .errors import CeleryFeederError, InvalidConfigError, MARCXMLError
from .tasks import celery_match


REGEX_COLLECTION_START = re.compile('<(?:[a-z]+?:)?collection.*?>',
                                    re.IGNORECASE)
REGEX_COLLECTION_END = re.compile('</(?:[a-z]+?:)?collection.*?>',
                                  re.IGNORECASE)
REGEX_RECORD = re.compile('<(?:[a-z]+?:)?record>.*?</(?:[a-z]+?:)?record>',
                          re.IGNORECASE | re.DOTALL)
REGEX_RECORD_START = re.compile('<(?:[a-z]+?:)?record>', re.IGNORECASE)
REGEX_RECORD_END = re.compile('</(?:[a-z]+?:)?record>', re.IGNORECASE)

LOGGER_FORMAT_LINE = "%(asctime)s -- [%(levelname)s] %(message)s"
LOGGER_FORMAT_DATETIME = "%Y-%m-%d %H:%M:%S"

USER_CONFIG_PREFIX = "MATCHER_DEFAULT_"


class ResultType(object):
    NEW = 'new'
    MATCHED = 'matched'
    AMBIGUOUS = 'ambiguous'
    FUZZY = 'fuzzy'
    ERROR = 'error'
    SUCCESSES = (NEW, MATCHED, AMBIGUOUS, FUZZY)
    ALL = (NEW, MATCHED, AMBIGUOUS, FUZZY, ERROR)


class LazyMarcXMLReader(object):
    """
    Class for lazily reading records from MARCXML files.

    Raises MARCXMLError if end-of-file is reached before
    it's expected (in case of malformed MARCXML)

    Create an instance passing the filepath to the constructor; then
    iterate over the instance to get records.
    """

    def __init__(self, filepath, parse_xml=True, position=None):
        """
        :param filepath: path of file to read in
        :param parse_xml: Parse records into BibRecord structures when
            returning. If false then only the MARCXML is returned
        :param position: file position to start reading from, by default this
            is found automatically by looking up the initial <collection> tag.
        """
        self.handle = codecs.open(filepath, mode='r', encoding='utf-8')
        self.parse_xml = parse_xml
        if not position:
            self.position = 0
            while True:
                try:
                    line = next(self.handle)
                except StopIteration:
                    msg = ("Premature end-of-file, couldn't find beginning "
                           "<collection> tag. "
                           "(Is %s a valid MARCXML file?)" % (filepath,))
                    raise MARCXMLError('collection-start', msg)
                self.position += len(line)
                if REGEX_COLLECTION_START.search(line):
                    break
        else:
            self.position = position
            self.handle.seek(position)

    def __iter__(self):
        """Get records out of the reader.

        :return: records from the file.
        """
        pipe = StringIO()
        for line in self.handle:
            pipe.write(line)
            if 'record>' in line.lower():
                pipe.seek(0)
                pos_rec_xml = pipe.read()
                self.test_valid_record_tags(pos_rec_xml)
                rec_xml = REGEX_RECORD.findall(pos_rec_xml)
                if len(rec_xml) >= 1:
                    for rec in rec_xml:
                        if self.parse_xml:
                            record, status, error_msg = create_record(rec)
                            if status == 0:
                                current_app.logger.error(str(error_msg))
                            yield record
                        else:
                            yield rec
                    del pipe
                    pipe = StringIO()
                    split_line = "%s%s" % line.rpartition('<')[1:]
                    pipe.write(split_line)
                else:
                    pipe.seek(0, 2)
            # Finally, increment our own file pointer
            self.position += len(line)

        # Test that we reached the end of the file succesfully
        pipe.seek(0)
        remainder = pipe.read()
        filepath = self.handle.name
        if (REGEX_RECORD_START.search(remainder) and
                not REGEX_RECORD_END.search(remainder)):
            msg = ("Premature end-of-record, couldn't find "
                   "ending </record> tag in %s" % (filepath,))
            raise MARCXMLError('record-end', msg)
        if not REGEX_COLLECTION_END.search(remainder):
            msg = ("Premature end-of-collection, couldn't find "
                   "ending </collection> tag in %s" % (filepath,))
            raise MARCXMLError('collection-end', msg)

    @staticmethod
    def test_valid_record_tags(xml):
        """Tests that record tags are valid so far"""
        tags_start = len(REGEX_RECORD_START.findall(xml))
        tags_end = len(REGEX_RECORD_END.findall(xml))
        if (tags_start - tags_end) > 1:
            raise MARCXMLError('record-end', 'Missing record end tag')
        elif (tags_start - tags_end) < -1:
            raise MARCXMLError('record-start', 'Missing record start tag')

    def close(self):
        """Closes the contained file object

        :return: returns the position of the file pointer"""
        self.handle.close()
        # Note: can't use tell() because the readahead buffer returns
        # wrong values
        return self.position


class CeleryFeeder(object):
    """
    Feeds Matcher tasks into Celery.

    Helper class for feeding tasks into Celery. Makes use of threading to
    allow simultaneous task input and result collection.

    To use: initiate the object and call the :meth:`begin_feeding` to begin
    the feeder thread. Iterate over the instance to get results back out.
    """

    def __init__(self, records, conf, site_url, username, password, log):
        """
        :param records: Iterable object that outputs records
        :param conf: The generated configuration for passing to tasks
        :param site_url: URL of the Invenio instance to match against.
        :param username: Username for the Invenio instance.
        :param password: Password for the user if required.
        :param log: logger object from logging library
        """
        self.records = records
        self.conf = conf
        self.max_queue_length = conf['CELERY_MAX_QUEUE_LENGTH']
        self.sleep_time = conf['CELERY_SLEEP_TIME']
        self.site_url = site_url
        self.username = username
        self.password = password
        self.log = log
        self.semaphore = BoundedSemaphore()
        self.results = []
        # Need to assign this variable so we can change it during tests
        self.celery_func = celery_match
        self.thread = Thread(target=self.feed_celery_tasks)
        self.feeder_error = False

    def begin_feeding(self):
        """Begin the CeleryFeeder thread."""
        self.thread.start()

    def feed_celery_tasks(self):
        """
        Feeds iterator items into Celery, this is intended to be ran in a
        seperate thread.
        """
        try:
            func = self.celery_func
            for idx, record in enumerate(self.records, 1):
                self.log.info("Feeding into celery record #%d", idx)
                result_wrapper = func.delay(
                    record, self.conf, self.site_url, self.username,
                    self.password, idx)
                with self.semaphore:
                    self.results.append(result_wrapper)
                while len(self.results) >= self.max_queue_length:
                    sleep(self.sleep_time)
                    if self.feeder_error:
                        break
                if self.feeder_error:
                    self.log.critical("CeleryFeeder feeder-thread has been " +
                                      "signaled to stop.")
                    return
        except Exception as err:
            self.log.critical("CeleryFeeder feeder-thread exited prematurely!")
            self.log.critical(str(err))
            self.feeder_error = True
            raise

    def _get_finished_task(self):
        """
        Retrieve a single finished task from results.
        Note, this method is intended to be called from the __iter__ method,
        calling it directly can result in a CPU-blocking infinite loop.
        """
        task_idx = None
        while task_idx is None:
            with self.semaphore:
                for idx, task in enumerate(self.results):
                    if task.ready():
                        task_idx = idx
                        break
                if task_idx is not None:
                    async_result = self.results.pop(task_idx)
                    if async_result.successful():
                        result, message_queue = async_result.result
                        deposit_messages(self.log, message_queue)
                        return result
                    elif async_result.failed():
                        self.log.error(
                            " *** A task has resulted in failure ***")
                        self.log.error(str(async_result.traceback))
                        # TODO: Replace with MatcherTaskResult
                        return ('error', async_result.traceback)
            sleep(self.sleep_time)
            if self.feeder_error:
                raise CeleryFeederError(
                    "CeleryFeeder feeder thread has stopped unexpectedly.")
            if not self.are_records_remaining():
                raise StopIteration

    def __iter__(self):
        """Retrieve results from Celery.

        :return: Matcher result
        """
        try:
            while self.are_records_remaining():
                yield self._get_finished_task()
        except Exception:
            self.feeder_error = True
            raise

    def are_records_remaining(self):
        return self.thread.is_alive() or len(self.results) > 0


class LogQueue(object):
    """Emulates a logger object

    Collects messages during Celery tasks so that they may be placed in the
    log when the task completes.
    """

    def __init__(self):
        self.message_queue = []

    def debug(self, msg, *args, **kwargs):
        """Mock of :func:`logger.debug`"""
        self.message_queue.append(('debug', msg, args, kwargs))

    def info(self, msg, *args, **kwargs):
        """Mock of :func:`logger.info`"""
        self.message_queue.append(('info', msg, args, kwargs))

    def warning(self, msg, *args, **kwargs):
        """Mock of :func:`logger.warning`"""
        self.message_queue.append(('warning', msg, args, kwargs))

    def error(self, msg, *args, **kwargs):
        """Mock of :func:`logger.error`"""
        self.message_queue.append(('error', msg, args, kwargs))

    def exception(self, msg, *args, **kwargs):
        """Mock of :func:`logger.exception`

        Exception traceback text is appended to the message
        """
        msg = msg + '\n' + format_exc(sys.exc_traceback)
        self.message_queue.append(('error', msg, args, kwargs))

    def critical(self, msg, *args, **kwargs):
        """Mock of :func:`logger.critical`"""
        self.message_queue.append(('critical', msg, args, kwargs))


def generate_config(user_conf):
    """Generate final configuration based on user config and default.

    Takes the user provided configuration and combines it with the default
    configuration. If the user configuration is invalid then an exception
    ``InvalidConfigError`` is raised.

    :param user_conf: Dictionary of the user configuration.

    :return: Final user configuration.
    """
    gen_conf = get_default_configuration()
    if not user_conf:
        return gen_conf

    if not isinstance(user_conf, dict):
        raise InvalidConfigError("User config needs to be a dictionary.")

    errors = []
    for key, value in iteritems(user_conf):
        try:
            if not isinstance(value, type(gen_conf[key])):
                msg = ("Config option '%s' should be of type " % (key,) +
                       " %s (found type %s)." % (type(value),
                                                 type(gen_conf[key])))
                errors.append(msg)
        except KeyError:
            errors.append("'%s' is not a valid config option." % (key,))

    if errors:
        raise InvalidConfigError('\n'.join(errors))
    gen_conf.update(user_conf)
    return gen_conf


def generate_logger(handlers):
    """Spawns a Matcher-specific logger from ``current_app.logger``

    :param handlers: Additional handlers to be given to the logger.

    :return: Logger instance for Matcher.
    """
    matcher_logger = current_app.logger.getChild('matcher')
    # name = 'invenio.modules.matcher'
    matcher_logger.name = '.'.join(__name__.split('.')[:-1])
    try:
        for handler in handlers:
            matcher_logger.addHandler(handler)
    except TypeError:
        matcher_logger.info("No additional loggers provided.")
    matcher_logger.info("Matcher logging enabled.")
    return matcher_logger


def generate_connector(site_url, username, password):
    """Create InvenioConnector instance.

    :param site_url: URL of the invenio instance, if ``None`` then the value
        of ``cfg['CFG_SITE_URL']`` is used instead.
    :param username: Username to use for the instance.
    :param password: Password to use for the instance.

    :return: ``InvenioConnector`` instance.
    """
    try:
        if site_url is None:
            site_url = cfg['CFG_SITE_URL']
        connector = InvenioConnector(site_url, user=username,
                                     password=password)
    except (InvenioConnectorAuthError, InvenioConnectorServerError) as error:
        raise error
    return connector


def get_records_from_file(filepath):
    """Take the path to a MARCXML file and generate records from it.

    This function is intended to fail-fast on MARCXML parsing errors, if an
    error occurs when BibRecord creates the record, it throws ValueError.

    :param filepath: path to the MARCXML file to parse.

    :return: List of parsed records.
    """
    with codecs.open(filepath, mode='r', encoding='utf-8') as handle:
        marcxml = handle.read()
    records = []
    for rec, code, errors in create_records(marcxml):
        if code == 0:
            raise ValueError("Error creating record: %s" % (errors,))
        records.append(rec)
    return records


def get_default_configuration():
    """
    Fetches the default Matcher config.

    Retreives all values from invenio.base.globals.cfg and filters
    all those items whose keys begin with USER_CONFIG_PREFIX and gives
    back a dictionary with the prefix removed.

    The value of USER_CONFIG_PREFIX is usually 'MATCHER_DEFAULT_' and
    defined at the top of this file.

    For example...
        {'MATCHER_DEFAULT_SLEEPTIME': 60}
    becomes...
        {'SLEEPTIME': 60}

    :return: default configuration as a dictionary
    """
    default_config = dict((key[len(USER_CONFIG_PREFIX):], value)
                          for key, value in iteritems(cfg)
                          if key.startswith(USER_CONFIG_PREFIX))
    return default_config


def deposit_messages(logger, message_queue):
    """Places all messages into a real logger object

    :param message_queue: list of messages from :class:`LogQueue`
    """
    for key, msg, args, kwargs in message_queue:
        function = logger.__getattribute__(key)
        function(msg, *args, **kwargs)


def transform_record_to_marc(record, options=None):
    """
    This function will transform a given bibrec record into marc
    using methods from xmlmarc2textmarc in invenio.utils.text
    The function returns the record as a MARC string.

    :param record: BibRecord structure of record
    :param options: dictionary describing type of MARC record.
        Defaults to textmarc.

    :return: resulting MARC record as string
    """
    if not options:
        options = {'text-marc': 1, 'aleph-marc': 0}

    sysno = get_sysno_from_record(record, options)
    # Note: Record dict is copied as create_marc_record() perform deletions
    return create_marc_record(record.copy(), sysno, options)
