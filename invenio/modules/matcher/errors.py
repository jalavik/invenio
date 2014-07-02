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

    Exception classes for Matcher.
"""


class MARCXMLError(Exception):
    """Exception caused when parsing malformed MARCXML"""

    ERROR_TYPES = ['collection-start', 'collection-end',
                   'record-start', 'record-end']

    def __init__(self, error_type, message):
        super(MARCXMLError, self).__init__(message)
        if error_type not in MARCXMLError.ERROR_TYPES:
            raise ValueError("%s is not a valid error_type" % (error_type,))
        else:
            self.error_type = error_type

    def __str__(self):
        return "[%s] %s" % (self.error_type, self.message)


class InvalidConfigError(Exception):
    """Exception thrown for impropper config use"""
    pass


class CeleryFeederError(Exception):
    """Exception thrown if either part of the CeleryFeeder breaks"""
    pass


class BibMatchValidationError(Exception):
    """Legacy exception, to be removed"""
    pass
