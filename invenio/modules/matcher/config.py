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

    Matcher Configuration.
"""

MATCHER_DEFAULT_CONFIG = {
    "SEARCH_RESULT_MATCH_LIMIT": 15,
    "MIN_VALIDATION_COMPARISONS": 2,
    "VALIDATION_RESULT_MODES": ["normal", "final", "joker"],
    "QUERY_TEMPLATES": {
        "reportnumber": "reportnumber:[reportnumber]",
        "title-author": "[title] [author]",
        "title": "[title]"
    },
    "REMOTE_SLEEPTIME": 2,
    "VALIDATION_COMPARISON_MODES": [
        "strict",
        "normal",
        "lazy",
        "ignored"
    ],
    "FUZZY_WORDLIMITS": {
        "245__a": 4,
        "100__a": 2
    },
    "LOCAL_SLEEPTIME": 0,
    "MATCH_VALIDATION_RULESETS": {
        "default": {
            "rules": [
                {
                    "threshold": 0.8,
                    "match_mode": "title",
                    "result_mode": "normal",
                    "compare_mode": "lazy",
                    "tags": "245__%,242__%"
                },
                {
                    "threshold": 1,
                    "match_mode": "identifier",
                    "result_mode": "final",
                    "compare_mode": "lazy",
                    "tags": "037__a,088__a"
                },
                {
                    "threshold": 0.8,
                    "match_mode": "author",
                    "result_mode": "normal",
                    "compare_mode": "normal",
                    "tags": "100__a,700__a"
                },
                {
                    "threshold": 1,
                    "match_mode": "title",
                    "result_mode": "normal",
                    "compare_mode": "lazy",
                    "tags": "773__a"
                }
            ]
        },
        "doi": {
            "rules": [
                {
                    "threshold": 1,
                    "match_mode": "identifier",
                    "result_mode": "final",
                    "compare_mode": "lazy",
                    "tags": "0247_a"
                }
            ],
            "pattern": "0247_"
        },
        "isbn": {
            "rules": [
                {
                    "threshold": 1,
                    "match_mode": "identifier",
                    "result_mode": "joker",
                    "compare_mode": "lazy",
                    "tags": "020__a"
                }
            ],
            "pattern": "020__"
        },
        "publication": {
            "rules": [
                {
                    "threshold": 0.8,
                    "match_mode": "date",
                    "result_mode": "normal",
                    "compare_mode": "lazy",
                    "tags": "260__c"
                }
            ],
            "pattern": "260__"
        },
        "thesis": {
            "rules": [
                {
                    "threshold": 0.8,
                    "match_mode": "author",
                    "result_mode": "normal",
                    "compare_mode": "strict",
                    "tags": "100__a"
                },
                {
                    "threshold": 1,
                    "match_mode": "author",
                    "result_mode": "normal",
                    "compare_mode": "lazy",
                    "tags": "700__a,701__a"
                },
                {
                    "threshold": 0.8,
                    "match_mode": "author",
                    "result_mode": "normal",
                    "compare_mode": "ignored",
                    "tags": "100__a,700__a"
                }
            ],
            "pattern": "980__ $$a(THESIS|Thesis)"
        }
    },
    "FUZZY_MATCH_VALIDATION_LIMIT": 0.65,
    "FUZZY_EMPTY_RESULT_LIMIT": 1,
    "VALIDATION_MATCHING_MODES": [
        "title",
        "author",
        "identifier",
        "date",
        "normal"
    ],
    "CELERY_MAX_QUEUE_LENGTH": 25,
    "CELERY_SLEEP_TIME": 3,
    "VALIDATION": True,
    "LOGFILE": "/tmp/bibmatch.log",
    "SEARCH_QUERY_STRINGS": [],
    "SEARCH_COLLECTIONS": []
}


# =============================================================================
#  Legacy Variables, these should be replaced with the cfg_matcher dictionary
# TODO: depreciate everything here
# =============================================================================

## MATCHER_VALIDATION_MATCHING_MODES - list of supported comparison modes
## during record validation.
MATCHER_VALIDATION_MATCHING_MODES = ['title', 'author', 'identifier', 'date', 'normal']

## MATCHER_VALIDATION_RESULT_MODES - list of supported result modes
## during record validation.
MATCHER_VALIDATION_RESULT_MODES = ['normal', 'final', 'joker', 'fuzzy']

## MATCHER_VALIDATION_COMPARISON_MODES - list of supported parsing modes
## during record validation.
MATCHER_VALIDATION_COMPARISON_MODES = ['strict', 'normal', 'lazy', 'ignored']

MATCHER_FUZZY_EMPTY_RESULT_LIMIT = 1
MATCHER_MIN_VALIDATION_COMPARISONS = 2
MATCHER_FUZZY_MATCH_VALIDATION_LIMIT = 0.65
MATCHER_FUZZY_WORDLIMITS = {'100__a': 2, '245__a': 4}
MATCHER_LOCAL_SLEEPTIME = 0.0
MATCHER_MATCH_VALIDATION_RULESETS = [
    ('default',
        [
            {
                'compare_mode': 'lazy',
                'match_mode': 'title',
                'result_mode': 'normal',
                'tags': '245__%,242__%',
                'threshold': 0.8
            },
            {
                'compare_mode': 'lazy',
                'match_mode': 'identifier',
                'result_mode': 'final',
                'tags': '037__a,088__a',
                'threshold': 1.0
            },
            {
                'compare_mode': 'normal',
                'match_mode': 'author',
                'result_mode': 'normal',
                'tags': '100__a,700__a',
                'threshold': 0.8
            },
            {
                'compare_mode': 'lazy',
                'match_mode': 'title',
                'result_mode': 'normal',
                'tags': '773__a',
                'threshold': 1.0
            }
        ]
    ),
    ('980__ \\$\\$a(THESIS|Thesis)',
        [
            {
                'compare_mode': 'strict',
                'match_mode': 'author',
                'result_mode': 'normal',
                'tags': '100__a',
                'threshold': 0.8
            },
            {
                'compare_mode': 'lazy',
                'match_mode': 'author',
                'result_mode': 'normal',
                'tags': '700__a,701__a',
                'threshold': 1.0
            },
            {
                'compare_mode': 'ignored',
                'match_mode': 'author',
                'result_mode': 'normal',
                'tags': '100__a,700__a',
                'threshold': 0.8
            }
        ]
    ),
    ('260__',
        [
            {
                'compare_mode': 'lazy',
                'match_mode': 'date',
                'result_mode': 'fuzzy',
                'tags': '260__c',
                'threshold': 1.0
            }
        ]
    ),
    ('0247_',
        [
            {
                'compare_mode': 'lazy',
                'match_mode': 'identifier',
                'result_mode': 'final',
                'tags': '0247_a',
                'threshold': 1.0
            }
        ]
    ),
    ('020__',
        [
            {
                'compare_mode': 'lazy',
                'match_mode': 'identifier',
                'result_mode': 'joker',
                'tags': '020__a',
                'threshold': 1.0
            }
        ]
    )
]

MATCHER_QUERY_TEMPLATES = {
    'title': '[title]',
    'title-author': '[title] [author]',
    'reportnumber': 'reportnumber:[reportnumber]'
}

MATCHER_REMOTE_SLEEPTIME = 2.0
MATCHER_SEARCH_RESULT_MATCH_LIMIT = 15

# CFG_MATCHER_SEARCH_FIELDS = {
#     'unique-idents': [
#         ('0247_a', '2=DOI')
#     ]
# }
