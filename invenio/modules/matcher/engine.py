# -*- coding: utf-8 -*-
## This file is part of Invenio.
## Copyright (C) 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014 CERN.
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

    The engine code sits in here, if you want to interact with matcher, use
    the API instead.
"""

__revision__ = "$Id$"

import sys
import string
import os
import getopt
import re
from time import sleep

from invenio.base.globals import cfg
from invenio.legacy.bibconvert import api as bibconvert
from invenio.legacy.bibrecord import (create_records, record_get_field_values,
                                      record_xml_output,
                                      record_modify_controlfield,
                                      record_has_field,
                                      record_add_field)
from invenio.legacy.search_engine import (get_fieldcodes,
                                          re_pattern_single_quotes,
                                          re_pattern_double_quotes,
                                          re_pattern_regexp_quotes,
                                          re_pattern_spaces_after_colon)
from invenio.legacy.search_engine.query_parser import SearchQueryParenthesisedParser
from invenio.legacy.dbquery import run_sql
from invenio.legacy.bibrecord.scripts.textmarc2xmlmarc import transform_file
from invenio.utils.connector import (InvenioConnector,
                                     InvenioConnectorAuthError)
from invenio.utils.text import translate_to_ascii, xml_entities_to_utf8

from .config import (MATCHER_FUZZY_WORDLIMITS,
                     MATCHER_QUERY_TEMPLATES,
                     MATCHER_FUZZY_EMPTY_RESULT_LIMIT,
                     MATCHER_LOCAL_SLEEPTIME,
                     MATCHER_REMOTE_SLEEPTIME,
                     MATCHER_SEARCH_RESULT_MATCH_LIMIT)
from .validator import (validate_matches,
                        validate_tag, BibMatchValidationError)


re_querystring = re.compile("\s?([^\s$]*)\[(.+?)\]([^\s$]*).*?", re.DOTALL)


class Querystring:
    """
    Holds the information about a querystring.
    The object contains lists of fields, formats and queries which generates search queries.

    self.fields    is a dict of found field-data {"tag": [list of found record data]}
    self.formats   is a dict of found BibConvert formats {"tag": [list of found format-values]}
    self.pattern   contains the original search string
    self.query     contains the generated query
    self.operator  holds the current active operator, upper-case (OR/AND)

    To populate the Querystring instance with values and search string structure,
    call create_query(..) with BibRecord structure and a query-string to populate with retrieved values.

    Example: The template "title:[245__a]" will retrieve the value from subfield 245__a in
             given record. If any BibConvert formats are specified for this field, these will
             be applied.
    """
    def __init__(self, operator="OR", clean=False, ascii_mode=False):
        """
        Creates Querystring instance.

        @param operator: operator used to concatenate several queries
        @type operator: str

        @param clean: indicates if queries should be sanitized
        @type clean: bool
        """
        self.fields = {}
        self.operator = operator.upper()
        self.pattern = ""
        self.query = ""
        self.clean = clean
        self.ascii_mode = ascii_mode
        self.formats = {}

    def create_query(self, record, qrystr="[title]"):
        """
        Main method that parses and generates a search query from
        given query-string structure and record data. Returns the
        resulting query-string and completeness determination as a tuple.

        A query is 'complete' when all found field references has a value
        in the passed record. Should a value be missing, the query is
        incomplete.

        @param record: bibrecord to retrive field-values from
        @type record: dict

        @param qrystr: proper query string template. (i.e. title:[245__a])
                       defaults to: [title]
        @type qrystr: str

        @return: (query-string, complete flag)
        @rtype: tuple
        """
        if qrystr == "":
            qrystr = "[title]"
        if "||" in qrystr or not "[" in qrystr:
            # Assume old style query-strings
            qrystr = self._convert_qrystr(qrystr)

        # FIXME: Convert to lower case, since fuzzy_parser
        # which treats everything lower-case, and will cause problems when
        # retrieving data from the self.fields dict.
        # Also BibConvert formats are currently case sensitive, so we cannot
        # force lower-case yet.
        self.pattern = qrystr.lower()
        self.fields = {}
        # Extract referenced field-values from given record
        complete, fieldtags_found = self._extract_fieldvalues(record, qrystr)

        # If no field references are found, we exit as empty query.
        if len(self.fields) == 0:
            self.query = ""
            return self.query, False
        # Now we assemble the found values into a proper search query
        all_queries = []
        operator_delimiter = " %s " % (self.operator,)
        if self.operator == "AND":
            # We gather all the values from the self.fields and put them
            # in a list together with any prefix/suffix associated with the field.
            new_query = self.pattern
            for (field_prefix, field_reference, field_suffix), value_list in self.fields.items():
                new_values = []
                for value in value_list:
                    new_values.append("%s%s%s" % (field_prefix, value, field_suffix))
                new_query = new_query.replace("%s[%s]%s" % (field_prefix,
                                                            field_reference,
                                                            field_suffix),
                                              operator_delimiter.join(set(new_values)))
            all_queries = [new_query]
        else:
            # operator is OR, which means a more elaborate approach to multi-value fields
            field_tuples = []
            for key, values in self.fields.items():
                field_list = []
                for value in values:
                    # We add key here to be able to associate the value later
                    field_list.append((key, value))
                field_tuples.append(field_list)
            # Grab all combinations of queries
            query_tuples = cproduct(field_tuples)
            for query in query_tuples:
                new_query = self.pattern
                for (field_prefix, field_reference, field_suffix), value in query:
                    new_query = new_query.replace("%s[%s]%s" % (field_prefix,
                                                                field_reference,
                                                                field_suffix),
                                                  "%s%s%s" % (field_prefix,
                                                              value,
                                                              field_suffix))
                all_queries.append(new_query)
        # Finally we concatenate all unique queries into one, delimited by chosen operator
        self.query = operator_delimiter.join(set(all_queries))
        if not complete:
            # Clean away any leftover field-name references from query
            for fieldtag in fieldtags_found:
                self.query = self.query.replace("%s" % (fieldtag,), "")
        # Clean query?
        if self.clean:
            self._clean_query()
        return self.query, complete

    def fuzzy_queries(self):
        """
        Returns a list of queries that are built more 'fuzzily' using the main query as base.
        The list returned also contains the current operator in context, so each query is a tuple
        of (operator, query).

        @return: list of tuples [(operator, query), ..]
        @rtype: list [(str, str), ..]
        """
        fuzzy_query_list = []
        operator_delimiter = " %s " % (self.operator,)
        parser = SearchQueryParenthesisedParser()
        query_parts = parser.parse_query(self.pattern)
        author_query = []
        author_operator = None
        # Go through every expression in the query and generate fuzzy searches
        for i in range(0, len(query_parts) - 1, 2):
            current_operator = query_parts[i]
            current_pattern = query_parts[i + 1]
            fieldname_list = re_querystring.findall(current_pattern)
            if fieldname_list == []:
                # No reference to record value, add query 'as is'
                fuzzy_query_list.append((current_operator, current_pattern))
            else:
                # Each reference will be split into prefix, field-ref and suffix.
                # Example:
                # 773__p:"[773__p]" 100__a:/.*[100__a].*/ =>
                # [('773__p:"', '773__p', '"'), ('100__a:/.*', '100__a', '.*/')]
                for field_prefix, field_reference, field_suffix in fieldname_list:
                    if field_reference == '245__a':
                        new_query = []
                        for value in self.fields.get((field_prefix, field_reference, field_suffix), []):
                            # Grab the x+1 longest words in the string and perform boolean OR
                            # for all combinations of x words (boolean AND)
                            # x is determined by the configuration dict and is tag-based. Defaults to 3 words
                            word_list = get_longest_words(value, limit=MATCHER_FUZZY_WORDLIMITS.get(field_reference, 3)+1)
                            for i in range(len(word_list)):
                                words = list(word_list)
                                words.pop(i)
                                new_query.append("(" + current_pattern.replace("[%s]" % (field_reference,), " ".join(words)) + ")")
                            fuzzy_query_list.append((current_operator, " OR ".join(new_query)))
                    elif field_reference == '100__a':
                        for value in self.fields.get((field_prefix, field_reference, field_suffix), []):
                            author_query.append(current_pattern.replace("[%s]" % (field_reference,), value))
                            author_operator = current_operator
                    elif field_reference == '700__a':
                        for value in self.fields.get((field_prefix, field_reference, field_suffix), []):
                            # take only the first 2nd author
                            author_query.append(current_pattern.replace("[%s]" % (field_reference,), value))
                            if not author_operator:
                                author_operator = current_operator
                            break
                    # for unique idenifier (DOI, repno) fuzzy search makes no sense
                    elif field_reference == '037__a':
                        continue
                    elif field_reference == '0247_a':
                        continue
                    else:
                        new_query = []
                        for value in self.fields.get((field_prefix, field_reference, field_suffix), []):
                            # Grab the x longest words in the string and perform boolean AND for each word
                            # x is determined by the configuration dict and is tag-based. Defaults to 3 words
                            # AND can be overwritten by command line argument -o o
                            word_list = get_longest_words(value, limit=MATCHER_FUZZY_WORDLIMITS.get(field_reference, 3))
                            for word in word_list:
                                # Create fuzzy query with key + word, including any surrounding elements like quotes, regexp etc.
                                new_query.append(current_pattern.replace("[%s]" % (field_reference,), word))
                            fuzzy_query_list.append((current_operator, operator_delimiter.join(new_query)))
        if author_query:
            fuzzy_query_list.append((author_operator, " OR ".join(author_query)))
        # Return a list of unique queries
        return list(set(fuzzy_query_list))

    def _clean_query(self):
        """
        This function will remove erroneous characters and combinations from
        a the generated search query that might cause problems when searching.

        @return: cleaned query
        @rtype: str
        """
        #FIXME: Extend cleaning to account for encodings and LaTeX symbols
        query = self.query.replace("''", "")
        query = query.replace('""', "")
        return query

    def _convert_qrystr(self, qrystr):
        """
        Converts old-style query-strings into new-style.
        """
        fields = qrystr.split("||")
        converted_query = []
        for field in fields:
            converted_query.append("[%s]" % (field,))
        return self.operator.join(converted_query)

    def _extract_fieldvalues(self, record, qrystr):
        """
        Extract all the values in the given record referenced in the given query-string
        and attach them to self.fields as a list. Return boolean indicating if a query
        is complete, and a list of all field references found.

        Field references is checked to be valid MARC tag references and all values
        found are added to self.fields as a list, hashed by the full reference including
        prefix and suffix.

        If ascii_mode is enabled, the record values will be translated to its ascii
        representation.

        e.g. for the query-string: 700__a:"[700__a]"
        { ('700__a:"', '700__a', '"') : ["Ellis, J.", "Olive, K. A."]}

        Should no values be found for a field references, the query will be flagged
        as incomplete.

        @param record: bibrecord to retrive field-values from
        @type record: dict

        @param qrystr: proper query string template. (i.e. title:[245__a])
                       defaults to: [title]
        @type qrystr: str

        @return: complete flag, [field references found]
        @rtype: tuple
        """
        complete = True
        fieldtags_found = []
        # Find all potential references to record tag values and
        # add to fields-dict as a list of values using field-name tuple as key.
        #
        # Each reference will be split into prefix, field-ref and suffix.
        # Example:
        # 773__p:"[773__p]" 100__a:/.*[100__a].*/ =>
        # [('773__p:"', '773__p', '"'), ('100__a:/.*', '100__a', '.*/')]
        for field_prefix, field_reference, field_suffix in re_querystring.findall(qrystr):
            # First we see if there is any special formats for this field_reference
            # The returned value from _extract_formats is the field-name stripped from formats.
            # e.g. 245__a::SUP(NUM) => 245__a
            fieldname = self._extract_formats(field_reference)
            # We need everything in lower-case
            field_prefix = field_prefix.lower()
            field_suffix = field_suffix.lower()
            # Find proper MARC tag(s) for the stripped field-name, if fieldname is used.
            # e.g. author -> [100__a, 700__a]
            # FIXME: Local instance only!
            tag_list = get_field_tags_from_fieldname(fieldname)
            if len(tag_list) == 0:
                tag_list = [fieldname]
            for field in tag_list:
                # Check if it is really a reference to a tag to not confuse with e.g. regex syntax
                tag_structure = validate_tag(field)
                if tag_structure is not None:
                    tag, ind1, ind2, code = tag_structure
                    value_list = record_get_field_values(record, tag, ind1, ind2, code)
                    if len(value_list) > 0:
                        # Apply any BibConvert formatting functions to each value
                        updated_value_list = self._apply_formats(fieldname, value_list)
                        # Also remove any errornous XML entities. I.e. &amp; -> &
                        updated_value_list = [xml_entities_to_utf8(v, skip=[])
                                              for v in updated_value_list]
                        if self.ascii_mode:
                            updated_value_list = translate_to_ascii(updated_value_list)
                        # Store found values linked to full field reference tuple including
                        # (prefix, field, suffix)
                        self.fields[(field_prefix,
                                     fieldname,
                                     field_suffix)] = updated_value_list
                    else:
                        # No values found. The query is deemed incomplete
                        complete = False
                    fieldtags_found.append("%s[%s]%s" % (field_prefix, fieldname, field_suffix))
        return complete, fieldtags_found

    def _extract_formats(self, field_reference):
        """
        Looks for BibConvert formats within query-strings and adds to
        the instance. Formats are defined by one or more '::' followed
        by a format keyword which is defined in BibConvert FormatField()
        method.

        The function also removes the references to formatting functions
        in the query (self.pattern)

        Returns the field_reference reference, with formats stripped.
        """
        field_parts = field_reference.split("::")
        if len(field_parts) > 1:
            # Remove any references to BibConvert functions in pattern. e.g. 245__a::SUP(PUNCT, ) -> 245__a
            # self.pattern is lower cased. Returned value is field-name stripped from formats.
            for aformat in field_parts[1:]:
                self.formats.setdefault(field_parts[0], []).append(aformat)
            self.pattern = self.pattern.replace("[%s]" % (field_reference.lower(),), "[%s]" % (field_parts[0],))
        return field_parts[0]

    def _apply_formats(self, fieldname, value_list):
        """
        Apply the current stored BibConvert formating operations for a
        field-name to the given list of strings. The list is then returned.

        @param fieldname: name of field - used as key in the formats dict
        @type fieldname: string

        @param value_list: list of strings to apply formats to
        @type value_list: list

        @return: list of values with formatting functions applied
        @rtype: list
        """
        if fieldname in self.formats:
            new_list = []
            for value in value_list:
                if value.strip() != "":
                    # Apply BibConvert formats if applicable
                    for aformat in self.formats[fieldname]:
                        value = bibconvert.FormatField(value, aformat)
                new_list.append(value)
            return new_list
        else:
            return value_list


def get_field_tags_from_fieldname(field):
    """
    Gets list of field 'field' for the record with 'sysno' system number from the database.
    """
    query = ("select tag.value from tag left join field_tag on tag.id=field_tag.id_tag "
             + "left join field on field_tag.id_field=field.id where field.code='%s'" % (field,))
    out = []
    res = run_sql(query)
    for row in res:
        out.append(row[0])
    return out


def cproduct(args):
    """
    Returns the Cartesian product of passed arguments as a list of tuples.
    '12','34' -> ('1', '3'), ('1', '4'), ('2', '3'), ('2', '4')

    @param args: iterable with elements to compute
    @type args: iterable

    @return list containing tuples for each computed combination
    @rtype list of tuples

    Based on http://docs.python.org/library/itertools.html#itertools.product
    """
    values = list(map(tuple, args))
    result = [[]]
    for value in values:
        result = [x + [y] for x in result for y in value]
    return [tuple(res) for res in result]


def bylen(word1, word2):
    """ Sort comparison method that compares by length """
    return len(word1) - len(word2)


def get_longest_words(wstr, limit=5):
    """
    Select the longest words for matching. It selects the longest words from
    the string, according to a given limit of words. By default the 5 longest word are selected

    @param wstr: string to extract the longest words from
    @type wstr: str

    @param limit: maximum number of words extracted
    @type limit: int

    @return: list of long words
    @rtype: list
    """
    words = []
    if wstr:
        # Protect spaces within quotes
        wstr = re_pattern_single_quotes.sub(
            lambda x: "'" + string.replace(x.group(1), ' ', '__SPACE__') + "'",
            wstr)
        wstr = re_pattern_double_quotes.sub(
            lambda x: "\"" + string.replace(x.group(1), ' ', '__SPACE__') + "\"",
            wstr)
        wstr = re_pattern_regexp_quotes.sub(
            lambda x: "/" + string.replace(x.group(1), ' ', '__SPACE__') + "/",
            wstr)
        # and spaces after colon as well:
        wstr = re_pattern_spaces_after_colon.sub(
            lambda x: string.replace(x.group(1), ' ', '__SPACE__'),
            wstr)
        words = wstr.split()
        for i in range(len(words)):
            words[i] = words[i].replace('__SPACE__', ' ')
        words.sort(cmp=bylen)
        words.reverse()
        words = words[:limit]
    return words


def add_recid(record, recid):
    """
    Add a given record-id to the record as $$001 controlfield. If an 001 field already
    exists it will be replaced.

    @param record: the record to retrive field-values from
    @type record: a bibrecord instance

    @param recid: record-id to be added
    @type recid: int
    """
    if record_has_field(record, '001'):
        record_modify_controlfield(record, '001',
                                   controlfield_value=str(recid),
                                   field_position_global=1)
    else:
        record_add_field(record, '001', controlfield_value=str(recid))


def match_result_output(bibmatch_recid, recID_list, server_url, query, matchmode="no match"):
    """
    Generates result as XML comments from passed record and matching parameters.

    @param bibmatch_recid: BibMatch record identifier
    @type bibmatch_recid: int

    @param recID_list: record matched with record
    @type recID_list: list

    @param server_url: url to the server the matching has been performed
    @type server_url: str

    @param query: matching query
    @type query: str

    @param matchmode: matching type
    @type matchmode: str

    @rtype str
    @return XML result string
    """
    result = ["<!-- BibMatch-Matching-Results: -->",
              "<!-- BibMatch-Matching-Record-Identifier: %s -->" % (bibmatch_recid,)]
    for recID in recID_list:
        result.append("<!-- BibMatch-Matching-Found: %s/%s/%s -->"
                      % (server_url, cfg['CFG_SITE_RECORD'], recID))
    result.append("<!-- BibMatch-Matching-Mode: %s -->" % (matchmode,))
    result.append("<!-- BibMatch-Matching-Criteria: %s -->" % (query,))
    return "\n".join(result)


def match_records(record, config, connector,
                  search_mode=None,
                  operator="and",
                  verbose=1, modify=0,
                  clean=False,
                  fuzzy=True, ascii_mode=False):
    """
    Match passed records with existing records on a local or remote Invenio
    installation. Returns which records are new (no match), which are matched,
    which are ambiguous and which are fuzzy-matched. A formatted result of each
    records matching are appended to each record tuple:
    (record, status_code, list_of_errors, result)

    @param records: records to analyze
    @type records: list of records

    @param qrystrs: list of tuples (field, querystring)
    @type qrystrs: list

    @param search_mode: if mode is given, the search will perform an advanced
                        query using the desired mode. Otherwise 'simple search'
                        is used.
    @type search_mode: str

    @param operator: operator used to concatenate values of fields occurring more then once.
                     Valid types are: AND, OR. Defaults to AND.
    @type operator: str

    @param verbose: be loud
    @type verbose: int

    @param server_url: which server to search on. Local installation by default
    @type server_url: str

    @param modify: output modified records of matches
    @type modify: int

    @param sleeptime: amount of time to wait between each query
    @type sleeptime: float

    @param clean: should the search queries be cleaned before passed them along?
    @type clean: bool

    @param collections: list of collections to search, if specified
    @type collections: list

    @param user: username in case of authenticated search requests
    @type user: string

    @param password: password in case of authenticated search requests
    @type password: string

    @param fuzzy: True to activate fuzzy query matching step
    @type fuzzy: bool

    @param validate: True to activate match validation
    @type validate: bool

    @param ascii_mode: True to transform values to its ascii representation
    @type ascii_mode: bool

    @rtype: list of lists
    @return an array of arrays of records, like this [newrecs,matchedrecs,
                                                      ambiguousrecs,fuzzyrecs]
    """
    # Legacy setup
    server_url = connector.server_url
    sleeptime = config["LOCAL_SLEEPTIME"]
    validate = config["VALIDATION"]
    collections = config["SEARCH_COLLECTIONS"]
    qrystrs = config["SEARCH_QUERY_STRINGS"]

    newrecs = []
    matchedrecs = []
    ambiguousrecs = []
    fuzzyrecs = []
    MATCHER_LOGGER.info("-- BibMatch starting match of %d records --" % (len(records),))

    ## Go through each record and try to find matches using defined querystrings
    record_counter = 0
    for record in records:
        record_counter += 1
        if (verbose > 1):
            sys.stderr.write("\n Processing record: #%d .." % (record_counter,))

        # At least one (field, querystring) tuple is needed for default search query
        if not qrystrs:
            qrystrs = [("", "")]
        MATCHER_LOGGER.info("Matching of record %d: Started" % (record_counter,))
        [matched_results, ambiguous_results, fuzzy_results] = match_record(bibmatch_recid=record_counter,
                                                                           record=record[0],
                                                                           server=connector,
                                                                           qrystrs=qrystrs,
                                                                           search_mode=search_mode,
                                                                           operator=operator,
                                                                           verbose=verbose,
                                                                           sleeptime=sleeptime,
                                                                           clean=clean,
                                                                           collections=collections,
                                                                           fuzzy=fuzzy,
                                                                           validate=validate,
                                                                           ascii_mode=ascii_mode)

        ## Evaluate final results for record
        # Add matched record iff number found is equal to one, otherwise return fuzzy,
        # ambiguous or no match
        if len(matched_results) == 1:
            results, query = matched_results[0]
            # If one match, add it as exact match, otherwise ambiguous
            if len(results) == 1:
                if modify:
                    add_recid(record[0], results[0])
                matchedrecs.append((record[0],
                                    match_result_output(record_counter,
                                                        results, server_url,
                                                        query, "exact-matched")))
                if (verbose > 1):
                    sys.stderr.write("Final result: match - %s/record/%s\n" % (server_url, str(results[0])))
                MATCHER_LOGGER.info("Matching of record %d: Completed as 'match'" % (record_counter,))
            else:
                ambiguousrecs.append((record[0],
                                      match_result_output(record_counter,
                                                          results, server_url,
                                                          query, "ambiguous-matched")))
                if (verbose > 1):
                    sys.stderr.write("Final result: ambiguous\n")
                MATCHER_LOGGER.info("Matching of record %d: Completed as 'ambiguous'" % (record_counter,))
        else:
            if len(fuzzy_results) > 0:
                # Find common record-id for all fuzzy results and grab first query
                # as "representative" query
                query = fuzzy_results[0][1]
                result_lists = []
                for res, dummy in fuzzy_results:
                    result_lists.extend(res)
                results = set([res for res in result_lists])
                if len(results) == 1:
                    fuzzyrecs.append((record[0],
                                      match_result_output(record_counter,
                                                          results, server_url,
                                                          query, "fuzzy-matched")))
                    if (verbose > 1):
                        sys.stderr.write("Final result: fuzzy\n")
                    MATCHER_LOGGER.info("Matching of record %d: Completed as 'fuzzy'" % (record_counter,))
                else:
                    ambiguousrecs.append((record[0],
                                          match_result_output(record_counter,
                                                              results, server_url,
                                                              query, "ambiguous-matched")))
                    if (verbose > 1):
                        sys.stderr.write("Final result: ambiguous\n")
                    MATCHER_LOGGER.info("Matching of record %d: Completed as 'ambiguous'" % (record_counter,))
            elif len(ambiguous_results) > 0:
                # Find common record-id for all ambiguous results and grab first query
                # as "representative" query
                query = ambiguous_results[0][1]
                result_lists = []
                for res, dummy in ambiguous_results:
                    result_lists.extend(res)
                results = set([res for res in result_lists])
                ambiguousrecs.append((record[0],
                                      match_result_output(record_counter,
                                                          results, server_url,
                                                          query, "ambiguous-matched")))
                if (verbose > 1):
                    sys.stderr.write("Final result: ambiguous\n")
                MATCHER_LOGGER.info("Matching of record %d: Completed as 'ambiguous'" % (record_counter,))
            else:
                newrecs.append((record[0], match_result_output(record_counter, [], server_url, str(qrystrs))))
                if (verbose > 1):
                    sys.stderr.write("Final result: new\n")
                MATCHER_LOGGER.info("Matching of record %d: Completed as 'new'" % (record_counter,))
    MATCHER_LOGGER.info("-- BibMatch ending match: New(%d), Matched(%d), Ambiguous(%d), Fuzzy(%d) --" %
                             (len(newrecs), len(matchedrecs), len(ambiguousrecs), len(fuzzyrecs)))
    return [newrecs, matchedrecs, ambiguousrecs, fuzzyrecs]


def match_record(bibmatch_recid, record, server, qrystrs=None, search_mode=None, operator="and",
                 verbose=1, sleeptime=MATCHER_LOCAL_SLEEPTIME,
                 clean=False, collections=[], fuzzy=True, validate=True,
                 ascii_mode=False):
    """
    Matches a single record.

    @param bibmatch_recid: Current record number. Used for logging.
    @type bibmatch_recid: int

    @param record: record to match in BibRecord structure
    @type record: dict

    @param server: InvenioConnector server object
    @type server: object

    @param qrystrs: list of tuples (field, querystring)
    @type qrystrs: list

    @param search_mode: if mode is given, the search will perform an advanced
                        query using the desired mode. Otherwise 'simple search'
                        is used.
    @type search_mode: str

    @param operator: operator used to concatenate values of fields occurring more then once.
                     Valid types are: AND, OR. Defaults to AND.
    @type operator: str

    @param verbose: be loud
    @type verbose: int

    @param server_url: which server to search on. Local installation by default
    @type server_url: str

    @param sleeptime: amount of time to wait between each query
    @type sleeptime: float

    @param clean: should the search queries be cleaned before passed them along?
    @type clean: bool

    @param collections: list of collections to search, if specified
    @type collections: list

    @param fuzzy: True to activate fuzzy query matching step
    @type fuzzy: bool

    @param validate: True to activate match validation
    @type validate: bool

    @param ascii_mode: True to transform values to its ascii representation
    @type ascii_mode: bool
    """
    matched_results = []
    ambiguous_results = []
    fuzzy_results = []
    # Keep a list of generated querystring objects for later use in fuzzy match
    query_list = []
    # Go through each querystring, trying to find a matching record
    # Stops on first valid match, if no exact-match we continue with fuzzy match
    for field, qrystr in qrystrs:
        querystring = Querystring(operator, clean=clean, ascii_mode=ascii_mode)
        query, complete = querystring.create_query(record, qrystr)
        if query == "":
            if (verbose > 1):
                sys.stderr.write("\nEmpty query. Skipping...\n")
            # Empty query, no point searching database
            continue
        query_list.append((querystring, complete, field))
        if not complete:
            if (verbose > 1):
                sys.stderr.write("\nQuery not complete. Flagged as uncertain/ambiguous...\n")

        # Determine proper search parameters
        if search_mode is not None:
            search_params = dict(p1=query, f1=field, m1=search_mode, of='id', c=collections)
        else:
            search_params = dict(p=query, f=field, of='id', c=collections)
        if (verbose > 8):
            sys.stderr.write("\nSearching with values %s\n" %
                             (search_params,))
        MATCHER_LOGGER.info("Searching with values %s" % (search_params,))
        ## Perform the search with retries
        try:
            result_recids = server.search_with_retry(**search_params)
        except InvenioConnectorAuthError as error:
            if verbose > 0:
                sys.stderr.write("Authentication error when searching: %s"
                                 % (str(error),))
            break

        sleep(sleeptime)

        ## Check results:
        if len(result_recids) > 0:
            # Matches detected
            MATCHER_LOGGER.info("Results: %s" % (result_recids[:15],))

            if len(result_recids) > MATCHER_SEARCH_RESULT_MATCH_LIMIT:
                # Too many matches, treat as non-match
                if (verbose > 8):
                    sys.stderr.write("result=More then %d results...\n" %
                                    (MATCHER_SEARCH_RESULT_MATCH_LIMIT,))
                continue

            if (verbose > 8):
                sys.stderr.write("result=%s\n" % (result_recids,))

            if validate:
                # Validation can be run
                MATCHER_LOGGER.info("Matching of record %d: Query (%s) found %d records: %s" %
                                         (bibmatch_recid,
                                          query,
                                          len(result_recids),
                                          str(result_recids)))

                exact_matches = []
                fuzzy_matches = []
                try:
                    exact_matches, fuzzy_matches = validate_matches(bibmatch_recid=bibmatch_recid,
                                                                    record=record,
                                                                    server=server,
                                                                    result_recids=result_recids,
                                                                    collections=collections,
                                                                    verbose=verbose,
                                                                    ascii_mode=ascii_mode)
                except BibMatchValidationError as e:
                    sys.stderr.write("ERROR: %s\n" % (str(e),))

                if len(exact_matches) > 0:
                    if (verbose > 8):
                        sys.stderr.write("Match validated\n")
                    matched_results.append((exact_matches, query))
                    break
                elif len(fuzzy_matches) > 0:
                    if (verbose > 8):
                        sys.stderr.write("Match validated fuzzily\n")
                    fuzzy_results.append((fuzzy_matches, query))
                    continue
                else:
                    if (verbose > 8):
                        sys.stderr.write("Match could not be validated\n")

            else:
                # No validation
                # Ambiguous match
                if len(result_recids) > 1:
                    ambiguous_results.append((result_recids, query))
                    if (verbose > 8):
                        sys.stderr.write("Ambiguous\n")
                    continue
                # Match
                elif len(result_recids) == 1:
                    if complete:
                        matched_results.append((result_recids, query))
                        if (verbose > 8):
                            sys.stderr.write("Match\n")
                        # This was a complete match, so let's break out to avoid more searching
                        break
                    else:
                        # We treat the result as ambiguous (uncertain) when query is not complete
                        # and we are not validating it.
                        ambiguous_results.append((result_recids, query))
                        if (verbose > 8):
                            sys.stderr.write("Ambiguous\n")
                        continue
        # No match
        if (verbose > 8):
            sys.stderr.write("result=No matches\n")
    # No complete matches, lets try fuzzy matching of all the queries
    else:
        if fuzzy:
            if (verbose > 8):
                sys.stderr.write("\nFuzzy query mode...\n")
            ## Fuzzy matching: Analyze all queries and perform individual searches, then intersect results.
            for querystring, complete, field in query_list:
                result_hitset = None
                if (verbose > 8):
                    sys.stderr.write("\n Start new search ------------ \n")
                fuzzy_query_list = querystring.fuzzy_queries()
                empty_results = 0
                # Go through every expression in the query and generate fuzzy searches
                for current_operator, qry in fuzzy_query_list:
                    current_resultset = None
                    if qry == "":
                        if (verbose > 1):
                            sys.stderr.write("\nEmpty query. Skipping...\n")
                            # Empty query, no point searching database
                            continue
                    search_params = dict(p=qry, f=field, of='id', c=collections)
                    MATCHER_LOGGER.info("Fuzzy searching with values %s" % (search_params,))
                    try:
                        current_resultset = server.search_with_retry(**search_params)
                    except InvenioConnectorAuthError as error:
                        if (verbose > 0):
                            sys.stderr.write("Authentication error when searching: %s"
                                             % (str(error),))
                        break
                    MATCHER_LOGGER.info("Results: %s" % (current_resultset[:15],))
                    if (verbose > 8):
                        if len(current_resultset) > MATCHER_SEARCH_RESULT_MATCH_LIMIT:
                            sys.stderr.write("\nSearching with values %s result=%s\n" %
                                             (search_params, "More then %d results..." %
                                              (MATCHER_SEARCH_RESULT_MATCH_LIMIT,)))
                        else:
                            sys.stderr.write("\nSearching with values %s result=%s\n"
                                             % (search_params, current_resultset))
                    sleep(sleeptime)
                    if current_resultset is None:
                        continue
                    if current_resultset == [] and empty_results < MATCHER_FUZZY_EMPTY_RESULT_LIMIT:
                        # Allows some empty results
                        empty_results += 1
                    else:
                        # Intersect results with previous results depending on current operator
                        if result_hitset is None:
                            result_hitset = current_resultset
                        if current_operator == '+':
                            result_hitset = list(set(result_hitset) & set(current_resultset))
                        elif current_operator == '-':
                            result_hitset = list(set(result_hitset) - set(current_resultset))
                        elif current_operator == '|':
                            result_hitset = list(set(result_hitset) | set(current_resultset))
                else:
                    # We did not hit a break in the for-loop: we were allowed to search.
                    if result_hitset and len(result_hitset) > MATCHER_SEARCH_RESULT_MATCH_LIMIT:
                        if (verbose > 1):
                            sys.stderr.write("\nToo many results... %d  " % (len(result_hitset)))
                    elif result_hitset:
                        # This was a fuzzy match
                        query_out = " ".join(["%s %s" % (op, qu) for op, qu in fuzzy_query_list])
                        if validate:
                            # We can run validation
                            MATCHER_LOGGER.info("Matching of record %d: Fuzzy query (%s) found %d records: %s" %
                                                     (bibmatch_recid,
                                                      query_out,
                                                      len(result_hitset),
                                                      str(result_hitset)))
                            exact_matches = []
                            fuzzy_matches = []
                            try:
                                exact_matches, fuzzy_matches = validate_matches(bibmatch_recid=bibmatch_recid,
                                                                                record=record,
                                                                                server=server,
                                                                                result_recids=result_hitset,
                                                                                collections=collections,
                                                                                verbose=verbose,
                                                                                ascii_mode=ascii_mode)
                            except BibMatchValidationError as e:
                                sys.stderr.write("ERROR: %s\n" % (str(e),))

                            if len(exact_matches) > 0:
                                if (verbose > 8):
                                    sys.stderr.write("Match validated\n")
                                matched_results.append((exact_matches, query_out))
                                break
                            elif len(fuzzy_matches) > 0:
                                if (verbose > 8):
                                    sys.stderr.write("Match validated fuzzily\n")
                                fuzzy_results.append((fuzzy_matches, query_out))
                            else:
                                if (verbose > 8):
                                    sys.stderr.write("Match could not be validated\n")
                        else:
                            # No validation
                            if len(result_hitset) == 1 and complete:
                                fuzzy_results.append((result_hitset, query_out))
                                if (verbose > 8):
                                    sys.stderr.write("Fuzzy: %s\n" % (result_hitset,))
                            else:
                                # We treat the result as ambiguous (uncertain) when:
                                # - query is not complete
                                # - more then one result
                                ambiguous_results.append((result_hitset, query_out))
                                if (verbose > 8):
                                    sys.stderr.write("Ambiguous\n")
    return [matched_results, ambiguous_results, fuzzy_results]
