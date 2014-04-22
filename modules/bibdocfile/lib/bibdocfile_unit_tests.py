# -*- coding: utf-8 -*-
##
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
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Invenio; if not, write to the Free Software Foundation, Inc.,
## 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""BibDocFile Unit Test Suite."""

import unittest
from invenio.testutils import make_test_suite, run_test_suite
from invenio.bibdocfile import file_strip_ext


class BibDocFileTest(unittest.TestCase):
    """Unit tests about"""

    def test_strip_ext(self):
        """bibdocfile - test file_strip_ext """
        self.assertEqual(file_strip_ext("foo.tar.gz"), 'foo')
        self.assertEqual(file_strip_ext("foo.buz.gz"), 'foo.buz')
        self.assertEqual(file_strip_ext("foo.buz"), 'foo')
        self.assertEqual(file_strip_ext("foo.buz",
                                        only_known_extensions=True), 'foo.buz')
        self.assertEqual(file_strip_ext("foo.buz;1",
                                        skip_version=False,
                                        only_known_extensions=True,
                                        allow_subformat=False), 'foo.buz;1')
        self.assertEqual(file_strip_ext("foo.gif;icon"), 'foo')
        self.assertEqual(file_strip_ext("foo.gif:icon",
                                        only_known_extensions=True), 'foo.gif:icon')
        self.assertEqual(file_strip_ext("foo.pdf.pdf",
                                        only_known_extensions=True), 'foo.pdf')


TEST_SUITE = make_test_suite(BibDocFileTest)
if __name__ == "__main__":
    run_test_suite(TEST_SUITE, warn_user=False)
