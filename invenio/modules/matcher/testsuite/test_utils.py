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
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Invenio; if not, write to the Free Software Foundation, Inc.,
## 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

# pylint: disable=R0904

"""
    Matcher - a tool that attempts to match a record, or a batch of records,
    against existing records within Invenio; either a local instance or remote.

    Test cases for invenio/modules/matcher/utils.py
"""

import os
import logging

from mock import Mock
from random import seed
from tempfile import NamedTemporaryFile
from cStringIO import StringIO

from invenio.base.wrappers import lazy_import
from invenio.testsuite import make_test_suite, run_test_suite, InvenioTestCase

LazyMarcXMLReader = lazy_import(
    'invenio.modules.matcher.utils:LazyMarcXMLReader')
CeleryFeeder = lazy_import('invenio.modules.matcher.utils:CeleryFeeder')
LogQueue = lazy_import('invenio.modules.matcher.utils:LogQueue')

generate_logger = lazy_import('invenio.modules.matcher.utils:generate_logger')

REGEX_COLLECTION_START = lazy_import(
    'invenio.modules.matcher.utils:REGEX_COLLECTION_START')
REGEX_COLLECTION_END = lazy_import(
    'invenio.modules.matcher.utils:REGEX_COLLECTION_END')
REGEX_RECORD = lazy_import('invenio.modules.matcher.utils:REGEX_RECORD')
REGEX_RECORD_START = lazy_import(
    'invenio.modules.matcher.utils:REGEX_RECORD_START')
REGEX_RECORD_END = lazy_import(
    'invenio.modules.matcher.utils:REGEX_RECORD_END')


class LazyReaderTest(InvenioTestCase):
    """ Tests LazyMarcXMLReader """

    def test_regex_patterns(self):
        """Test the compiled regex patterns used for record matching"""
        test_string_1 = """
        <collection>
            <record>
                <controlfield tag="001">999</controlfield>
                <datafield tag="900" ind1=" " ind2=" ">
                    <subfield code="a>TestValues</subfield>
                </datafield>
            </record>
        </collection>"""

        self.assertEqual(len(REGEX_COLLECTION_START.findall(test_string_1)), 1)
        self.assertEqual(len(REGEX_COLLECTION_END.findall(test_string_1)), 1)
        self.assertEqual(len(REGEX_RECORD.findall(test_string_1)), 1)
        self.assertEqual(len(REGEX_RECORD_START.findall(test_string_1)), 1)
        self.assertEqual(len(REGEX_RECORD_END.findall(test_string_1)), 1)

        test_string_2 = """<marc:collection>
        <marc:record>dataValue</marc:record>
        </marc:collection>"""

        self.assertEqual(REGEX_COLLECTION_START.findall(test_string_2)[0],
                         '<marc:collection>')
        self.assertEqual(REGEX_COLLECTION_END.findall(test_string_2)[0],
                         '</marc:collection>')
        self.assertEqual(REGEX_RECORD.findall(test_string_2)[0],
                         '<marc:record>dataValue</marc:record>')
        self.assertEqual(REGEX_RECORD_START.findall(test_string_2)[0],
                         '<marc:record>')
        self.assertEqual(REGEX_RECORD_END.findall(test_string_2)[0],
                         '</marc:record>')

        test_string_3 = """<collection>
            <record>dataValue1</record>
            <record>dataValue2</record>
            <record>dataValue3</record>
        </collection>"""

        self.assertEqual(len(REGEX_COLLECTION_START.findall(test_string_3)), 1)
        self.assertEqual(len(REGEX_COLLECTION_END.findall(test_string_3)), 1)
        self.assertEqual(len(REGEX_RECORD.findall(test_string_3)), 3)
        self.assertEqual(len(REGEX_RECORD_START.findall(test_string_3)), 3)
        self.assertEqual(len(REGEX_RECORD_END.findall(test_string_3)), 3)

    def test_valid_output(self):
        """Puts valid MARCXML in, expects records """

        valid_marcxml = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
<record>
  <controlfield tag="001">101</controlfield>
  <datafield tag="035" ind1=" " ind2=" ">
    <subfield code="9">BOOP</subfield>
    <subfield code="a">33333</subfield>
  </datafield>
</record>
<record>
  <controlfield tag="001">202</controlfield>
  <datafield tag="035" ind1=" " ind2=" ">
    <subfield code="9">BOOP</subfield>
    <subfield code="a">44444</subfield>
  </datafield>
</record>
<record>
  <controlfield tag="001">303</controlfield>
  <datafield tag="035" ind1=" " ind2=" ">
    <subfield code="9">BOOP</subfield>
    <subfield code="a">55555</subfield>
  </datafield>
</record>
</collection>
"""
        expected = [
            {'001': [([], ' ', ' ', '101', 1)],
             '035': [([('9', 'BOOP'), ('a', '33333')], ' ', ' ', '', 2)]},
            {'001': [([], ' ', ' ', '202', 1)],
             '035': [([('9', 'BOOP'), ('a', '44444')], ' ', ' ', '', 2)]},
            {'001': [([], ' ', ' ', '303', 1)],
             '035': [([('9', 'BOOP'), ('a', '55555')], ' ', ' ', '', 2)]}
        ]

        results = []
        with NamedTemporaryFile('w', prefix='invenio_matcher_tests',
                                delete=False) as handle:
            handle.write(valid_marcxml)
            filepath = handle.name
        try:
            reader = LazyMarcXMLReader(filepath)
            for val in reader:
                results.append(val)
        finally:
            os.remove(filepath)
        self.assertListEqual(expected, results)

    def test_faulty_data(self):
        """Tests that errors are raised on invalid data"""
        from invenio.modules.matcher.errors import MARCXMLError

        filepath_fake = "/this_file_does_not/exist.txt"
        self.assertRaises(IOError, LazyMarcXMLReader, filepath_fake)

        test_xml_1 = """<?xml version="1.0" encoding="UTF-8"?>
<record>
  <controlfield tag="001">101</controlfield>
  <datafield tag="035" ind1=" " ind2=" ">
    <subfield code="9">TEST-1A</subfield>
    <subfield code="a">33333</subfield>
  </datafield>
</record>
<record>
  <controlfield tag="001">202</controlfield>
  <datafield tag="035" ind1=" " ind2=" ">
    <subfield code="9">TEST-1B</subfield>
    <subfield code="a">44444</subfield>
  </datafield>
</record>
</collection>
"""
        with NamedTemporaryFile('w', prefix='invenio_matcher_tests',
                                delete=False) as handle:
            handle.write(test_xml_1)
            filepath = handle.name
        try:
            self.assertRaises(MARCXMLError, LazyMarcXMLReader, filepath)
        finally:
            os.remove(filepath)

        test_xml_2 = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
<record>
  <controlfield tag="001">101</controlfield>
  <datafield tag="035" ind1=" " ind2=" ">
    <subfield code="9">TEST-2A</subfield>
    <subfield code="a">33333</subfield>
  </datafield>
</record>
<record>
  <controlfield tag="001">202</controlfield>
  <datafield tag="035" ind1=" " ind2=" ">
    <subfield code="9">TEST-2B</subfield>
    <subfield code="a">44444</subfield>
  </datafield>
</record>
"""
        with NamedTemporaryFile('w', prefix='invenio_matcher_tests',
                                delete=False) as handle:
            handle.write(test_xml_2)
            filepath = handle.name
        try:
            reader = LazyMarcXMLReader(filepath)
            with self.assertRaises(MARCXMLError):
                for val in reader:
                    pass
        finally:
            os.remove(filepath)

        test_xml_3 = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
<record>
  <controlfield tag="001">101</controlfield>
  <datafield tag="035" ind1=" " ind2=" ">
    <subfield code="9">TEST 3A</subfield>
    <subfield code="a">33333</subfield>
  </datafield>
<record>
  <controlfield tag="001">202</controlfield>
  <datafield tag="035" ind1=" " ind2=" ">
    <subfield code="9">TEST 3B</subfield>
    <subfield code="a">44444</subfield>
  </datafield>
</record>
</collection>
"""
        with NamedTemporaryFile('w', prefix='invenio_matcher_tests',
                                delete=False) as handle:
            handle.write(test_xml_3)
            filepath = handle.name
        try:
            reader = LazyMarcXMLReader(filepath)
            with self.assertRaises(MARCXMLError):
                for val in reader:
                    pass
        finally:
            os.remove(filepath)

    def test_open_and_close(self):
        """Puts valid MARCXML in, expects records back"""

        valid_marcxml = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
<record>
  <controlfield tag="001">101</controlfield>
  <datafield tag="035" ind1=" " ind2=" ">
    <subfield code="9">BOOP</subfield>
    <subfield code="a">33333</subfield>
  </datafield>
</record>
<record>
  <controlfield tag="001">202</controlfield>
  <datafield tag="035" ind1=" " ind2=" ">
    <subfield code="9">BOOP</subfield>
    <subfield code="a">44444</subfield>
  </datafield>
</record>
</collection>
"""
        expected = [
            {'001': [([], ' ', ' ', '101', 1)],
             '035': [([('9', 'BOOP'), ('a', '33333')], ' ', ' ', '', 2)]},
            {'001': [([], ' ', ' ', '202', 1)],
             '035': [([('9', 'BOOP'), ('a', '44444')], ' ', ' ', '', 2)]}
        ]
        results = []
        with NamedTemporaryFile('w', prefix='invenio_matcher_tests',
                                delete=False) as handle:
            handle.write(valid_marcxml)
            filepath = handle.name
        try:
            reader = LazyMarcXMLReader(filepath)
            iterator = reader.__iter__()
            results.append(iterator.next())
            position = reader.close()
            del reader
            self.assertEqual(position, 281)
            reader = LazyMarcXMLReader(filepath, position=position)
            for remaining in reader:
                results.append(remaining)
        finally:
            os.remove(filepath)
        self.assertListEqual(expected, results)


class CeleryFeederTest(InvenioTestCase):
    """Tests the CeleryFeeder class using Mock objects to mimic Celery"""

    def test_init(self):
        """ Test that initating the CeleryFeeder object works """
        from .helpers import CELERY_TEST_CONF
        cfo = CeleryFeeder([1, 2, 3], CELERY_TEST_CONF, '', '', '', None)
        self.assertIsNotNone(cfo)

    def test_feeding_valid(self):
        """ Test that feeding basic data through the feeder works """
        from .helpers import (CELERY_TEST_CONF, mock_celery_func,
                              check_internal_values)

        seed()
        str_list = ['Iterable #%d' % idx for idx in xrange(1, 21)]
        mock_celery_func.delay = Mock(wraps=mock_celery_func)
        log = generate_logger([])

        celery_feed = CeleryFeeder(str_list, CELERY_TEST_CONF, 'site',
                                   'user', 'pass', log)
        celery_feed.celery_func = mock_celery_func
        celery_feed.begin_feeding()
        check_internal_values(celery_feed)

        results = []
        for result_type, result in celery_feed:
            check_internal_values(celery_feed)
            original, celery = result.split('--')
            self.assertIn(original, str_list)
            self.assertEqual(celery, 'CELERY_PROCESSED')
            results.append((result_type, result))

        self.assertEqual(mock_celery_func.delay.call_count, 20)
        self.assertEqual(len(str_list), len(results))

    def test_feeding_invalid(self):
        """ Test that feeding dodgy data doesn't break the entire feeder """
        from .helpers import CELERY_TEST_CONF, mock_celery_func
        seed()
        # The substring 'EXCEPTION-TIME' should cause an exception
        test_strings = ['Part1', 'Part2 EXCEPTION-TIME', 'Part3',
                        'Part4', 'Part5 EXCEPTION-TIME']

        mock_celery_func.delay = Mock(wraps=mock_celery_func)
        log = generate_logger([])

        celery_feed = CeleryFeeder(test_strings, CELERY_TEST_CONF, 'site',
                                   'user', 'pass', log)
        celery_feed.celery_func = mock_celery_func
        celery_feed.begin_feeding()

        results_success = 0
        results_failure = 0

        # TODO: Replace with MatcherTaskResult
        for result_type, result in celery_feed:
            if result_type == 'error':
                results_failure += 1
            elif result_type == 'new':
                results_success += 1

        self.assertEqual(mock_celery_func.delay.call_count, len(test_strings))
        self.assertEqual(results_success, 3)
        self.assertEqual(results_failure, 2)


class LogQueueTest(InvenioTestCase):

    def test_log_queue(self):
        """Test log_queue.message_queue structure"""
        log_queue = LogQueue()
        log_queue.debug("Debugging message #%d", 1, 2, 3)
        log_queue.info("Information message %s", "are good.")
        log_queue.warning("Warning messages aren't so great")
        log_queue.error("No... not an error...", exc_info="Some")
        log_queue.critical("NOOOOOOOOOOOOOOOOOO!")

        expected = [
            ('debug', "Debugging message #%d", (1, 2, 3), {}),
            ('info', "Information message %s", ("are good.",), {}),
            ('warning', "Warning messages aren't so great", (), {}),
            ('error', "No... not an error...", (), {'exc_info': "Some"}),
            ('critical', "NOOOOOOOOOOOOOOOOOO!", (), {})
        ]

        self.assertListEqual(expected, log_queue.message_queue)

    def test_exception_logging(self):
        """Test log_queue.exception method"""
        log_queue = LogQueue()
        test_msg = "Hey kids! It's exception time!"
        err_msg = "potatos are not a fruit"
        try:
            raise ValueError(err_msg)
        except ValueError:
            pass
        log_queue.exception(test_msg)
        msg = log_queue.message_queue[0][1]
        message, partition, tb_msg = msg.partition('\n')
        self.assertEqual(test_msg, message)
        self.assertIn(err_msg, tb_msg)

    def test_deposit_message(self):
        """Test that depositing messages into a logger works"""
        from invenio.modules.matcher.utils import deposit_messages

        logger = logging.getLogger()
        stream = StringIO()
        logger.addHandler(logging.StreamHandler(stream))

        mock_log = LogQueue()
        mock_log.error("#%d test of %s", 9, 'logging')

        deposit_messages(logger, mock_log.message_queue)
        stream.reset()
        self.assertEqual(stream.read(), "#9 test of logging\n")


TEST_SUITE = make_test_suite(LazyReaderTest,
                             CeleryFeederTest)


if __name__ == "__main__":
    run_test_suite(TEST_SUITE, warn_user=False)
