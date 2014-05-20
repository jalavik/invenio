# -*- coding: utf-8 -*-
## This file is part of Invenio.
## Copyright (C) 2010, 2011, 2013, 2014 CERN.
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

"""
    Matcher - a tool that attempts to match a record, or a batch of records,
    against existing records within Invenio; either a local instance or remote.

    Default configuration for Matcher.

    End-user configuration variables are denoted with the prefix defined by
    the variable `USER_CONFIG_PREFIX` in `utils.py`. Currently this is
    "MATCHER_DEFAULT_". The user configuration can be overriden by the user at
    the API level.

    General Matcher configuration can be changed by the instance administrator
    using `inveniomanage` if needed.
"""

# ============================================================================
# --------------------------- USER CONFIGURATION -----------------------------
# ============================================================================

# General
MATCHER_DEFAULT_LOCAL_SLEEPTIME = 1
MATCHER_DEFAULT_REMOTE_SLEEPTIME = 4

# Searching
MATCHER_DEFAULT_SEARCH_QUERY_STRINGS = []
MATCHER_DEFAULT_SEARCH_RESULT_MATCH_LIMIT = 15
MATCHER_DEFAULT_SEARCH_COLLECTIONS = []
MATCHER_DEFAULT_SEARCH_TIMEOUT_SLEEP_TIME = 30
MATCHER_DEFAULT_SEARCH_TIMEOUT_RETRIES = 3

# Celery
MATCHER_DEFAULT_CELERY_MAX_QUEUE_LENGTH = 25
MATCHER_DEFAULT_CELERY_SLEEP_TIME = 3

# Validation
MATCHER_DEFAULT_VALIDATE_RESULTS = True
MATCHER_DEFAULT_FUZZY_MATCH_VALIDATION_LIMIT = 0.65
MATCHER_DEFAULT_FUZZY_WORDLIMITS = {'245__a': 4, '100__a': 2}
MATCHER_DEFAULT_FUZZY_EMPTY_RESULT_LIMIT = 1
MATCHER_DEFAULT_MIN_VALIDATION_COMPARISONS = 2


# ============================================================================
# -------------------------- MATCHER CONFIGURATION ---------------------------
# ============================================================================

# Command Line Interface Config
MATCHER_CLI_RESULTS_DIRECTORY = 'matcher_cli'
MATCHER_CLI_RESULTS_PREFIX = 'matcher_results'
MATCHER_CLI_RESULTS_AUTO_SAVE = True
MATCHER_CLI_LOOKUP_ATTEMPTS = 3
MATCHER_CLI_TIMEOUT_WAIT = 30
MATCHER_CLI_TAG_LIST = {
    'control': ['001'],
    'datafld': [
        ('035', " ", " ", ''),
        ('037', " ", " ", ''),
        ('100', " ", " ", ''),
        ('245', " ", " ", ''),
        ('269', " ", " ", ''),
        ('300', " ", " ", ''),
        ('773', " ", " ", ''),
        ('980', " ", " ", '')
    ]
}

MATCHER_QUERY_TEMPLATES = {
    'title': '[title]',
    'title-author': '[title] [author]',
    'reportnumber': 'reportnumber:[reportnumber]'
}
