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

    Matcher Manager - Provides the Command Line Interface (CLI) to Matcher
    using Flask-Script.
"""

from __future__ import print_function

import os
import sys
import re
import logging
import cPickle as pickle

from time import sleep
from json import load as json_load
from getpass import getpass
from time import strftime
from datetime import datetime
from urllib2 import urlopen, URLError


from invenio.ext.script import Manager, change_command_name
from invenio.base.globals import cfg

manager = Manager(description="Command Line Interface for Matcher")

REGEX_DATE = re.compile("_([0-9]{4})-([01][0-9])-([0-3][0-9])_"
                        + "([0-2][0-9])-([0-6][0-9])-([0-6][0-9])")
REGEX_BIBMATCH_RESULTS = re.compile(
    r"<!-- BibMatch-Matching-Found: (http[s]{0,1}:\/\/.*\/record\/[0-9]*)")
REGEX_BIBMATCH_MODE = re.compile(
    r"<!-- BibMatch-Matching-Mode: ([a-z \-]+?) -->")

MARCXML_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
"""
MARCXML_FOOTER = "</collection>\n"

BIBMATCH_RESULT_MODES = {
    "no match": "new",
    "exact-matched": "matched",
    "ambiguous-matched": "ambiguous",
    "fuzzy-matched": "fuzzy"
}

OUTPUT_SUFFIX_NEW = '.manual.new.xml'
OUTPUT_SUFFIX_MATCHED = '.manual.matched.xml'
OUTPUT_COMMENT_NEW = """<!-- Output of Matcher CLI Manual Matching

Records have been looked at and compared manually, they have been confirmed
as NEW RECORDS (No match).
-->"""
OUTPUT_COMMENT_MATCHED = """<!-- Output of Matcher CLI Manual Matching

Records have been looked at and compared manually, they have been confirmed
as MATCHED RECORDS; the matching record IDs have been appended in 001.
-->"""


# ============================| Matcher Commands |============================

@manager.option('-v', '--verbose', action='store_true', dest='verbose',
                help="Give verbose output")
@change_command_name
def list_validation_rules(verbose):
    """Show available validation rulesets"""
    from invenio.modules.matcher.registry import validation_rules
    print("Available Validation Rules:")
    for key, value in validation_rules.iteritems():
        print(key)
        if verbose:
            print(" %s" % (str(value),))


@manager.option('-i', '--input', dest='xml_filepath', metavar="INPUT_PATH",
                help="Records to match (if undefined, reads from StdIn)")
@manager.option('-o', '--output', dest='output', metavar="OUTPUT_PREFIX",
                help="Location to write results to, including file prefix.")
@manager.option('-c', '--config', dest='config_path', metavar="CONFIG_PATH")
@manager.option('-r', '--remote', dest='remote', metavar="INSTANCE_URL",
                help="Remote server to search for matches")
@manager.option('-u', '--username', dest='username',
                help="Username for the instance")
@manager.option(
    '-q', '--querystrings', dest='querystrings', action='append',
    help="Querystrings to use for matching")
@manager.option('-x', '--collections', dest='collections',
                help="Specify collections to work in.")
@manager.option('-v', '--verbose', action='store_true', dest='verbose',
                help="Give verbose output")
@manager.option('-s', '--save-result', action='store_true', dest='save_result',
                help="Save results in Invenio")
@manager.option('-l', '--lazy', action='store_true', dest='lazy',
                help="Lazy loading of records (for large files)")
@manager.option('-d', '--distribute', action='store_true', dest='distribute',
                help="Use Celery to distribute tasks (for large jobs)")
@change_command_name
def match_records(
        xml_filepath, output, config_path, remote, username, use_pass,
        querystrings, collections, verbose, save_result, lazy, distribute):
    """Initiate a matching session, attempt to match a set of records."""
    from invenio.modules.matcher.errors import (MARCXMLError,
                                                InvalidConfigError)
    from invenio.modules.matcher.api import match_records, match_records_file
    from invenio.modules.matcher.utils import RESULT_TYPES
    from invenio.legacy.bibrecord import create_records, record_xml_output

    print("Initialising Matcher...")

    password = ''
    config = {}

    if not (output or save_result or cfg['MATCHER_CLI_RESULTS_AUTO_SAVE']):
        print("Error: No output method specified, use either '--output' "
              + "argument or the '--save-result' flag.")
        sys.exit(0)

    if username:
        if remote:
            request_string = "Enter password for %s@%s: " % (username, remote)
        else:
            request_string = "Enter password for %s@localhost: " % (username,)
        password = getpass(request_string)

    if config_path:
        try:
            with open(config_path) as handle:
                conf_json = json_load(handle)
                config.update(conf_json)
        except IOError as error:
            print("FATAL ERROR: Could not access config file "
                  + "'%s'. Is the filepath correct?" % (config_path,))
            if verbose:
                raise error
            sys.exit(1)

    if querystrings:
        if 'SEARCH_QUERY_STRINGS' in config:
            config['SEARCH_QUERY_STRINGS'] = (querystrings +
                                              config['SEARCH_QUERY_STRINGS'])
        else:
            config['SEARCH_QUERY_STRINGS'] = querystrings

    if collections:
        cols = collections.split(',')
        if 'SEARCH_COLLECTIONS' in config:
            config['SEARCH_COLLECTIONS'].extend(cols)
        else:
            config['SEARCH_COLLECTIONS'] = cols

    if not xml_filepath:
        print("Reading MARCXML from command line... (Ctrl+D to finish input)")
        try:
            record_xml = sys.stdin.read()
            records_in = [rec[0] for rec in create_records(record_xml)]
        except KeyboardInterrupt:
            print("\nKeyboardInterrupt: Matcher is exiting.")
            sys.exit(1)
    else:
        try:
            with open(xml_filepath):
                pass
        except IOError as error:
            print("FATAL ERROR: Could not access records file "
                  + "'%s'. Is the filepath correct?" % (xml_filepath,))
            sys.exit(1)

    # logging
    cli_handle = logging.StreamHandler(stream=sys.stdout)
    if verbose:
        cli_handle.setLevel(logging.DEBUG)
    else:
        cli_handle.setLevel(logging.ERROR)
    log_handlers = [cli_handle]

    # API call
    try:
        if xml_filepath:
            results = match_records_file(
                xml_filepath, config=config, site_url=remote,
                username=username, password=password,
                log_handlers=log_handlers, lazy=lazy, celery=distribute)
        else:
            results = match_records_file(
                records_in, config=config, site_url=remote,
                username=username, password=password,
                log_handlers=log_handlers, lazy=lazy, celery=distribute)
        results = list(results)
    except (MARCXMLError, InvalidConfigError) as error:
        print(str(error))
        if verbose:
            raise error
        sys.exit(0)

    # Pickle result and store.
    strdatetime = strftime('%Y-%m-%d_%H-%M-%S')
    if save_result or cfg['MATCHER_CLI_RESULTS_AUTO_SAVE']:
        test_results_dir()
        results_dir = get_results_dir()
        filename = "%s_%s.pickled" % (cfg['MATCHER_CLI_RESULTS_PREFIX'],
                                      strdatetime)
        pickle_path = os.path.join(results_dir, filename)

        with open(pickle_path, 'w') as pickle_handle:
            pickle.dump(results, pickle_handle)
        print("Results recorded, use list-result-sets to see them.")
        if verbose:
            print("Result set: %s" % (pickle_path,))

    if output:
        output_files = set()
        for result, (record, matching_info) in results:
            path = "%s_%s.%s.xml" % (output, strdatetime, result)
            output_files.add(path)
            xml_record = record_xml_output(record)
            with file(path, 'a') as handle:
                handle.write("%s\n" % (matching_info,))
                handle.write("%s\n\n" % (xml_record,))
        print("Matcher results here:")
        for filepath in output_files:
            print(" %s" % (filepath,))

    # Summary information
    counters = dict((rty, 0) for rty in RESULT_TYPES)
    for result, data in results:
        counters[result] += 1

    print("\n Matcher Results Summary")
    print("=" * 30)
    print("         New records : %d" % counters['new'])
    print("     Matched records : %d" % counters['matched'])
    print("   Ambiguous records : %d" % counters['ambiguous'])
    print("       Fuzzy records : %d" % counters['fuzzy'])
    print("=" * 30)
    print("       Total records : %d\n" % (len(results),))


@manager.option('-v', '--verbose', action='store_true', dest='verbose',
                help="Give verbose output")
@change_command_name
def list_result_sets(verbose):
    """List all preserved previous results."""
    results_dir = get_results_dir()
    contents = get_contents()
    if not contents:
        print("No stored results")
        sys.exit(0)
    print("Result set:")
    for index, result_file in enumerate(contents, 1):
        date_parts = REGEX_DATE.findall(result_file)[-1]
        date_ints = tuple([int(x) for x in date_parts])
        date = datetime(*date_ints)
        filepath = os.path.join(results_dir, result_file)
        print(" %d) %s" % (index, date.strftime("%a %d %B %Y, %X")))
        if verbose:
            print("    File: %s" % (filepath,))


@manager.option(dest='result_index', type=int,
                help='Number of the result set to fetch')
@manager.option('-o', '--output', dest='output', metavar="OUTPUT_PATH",
                help="File path to write to, prints out if not defined.")
@manager.option(
    '-f', '--filter', dest='filter_types', metavar="FILTER_RESULT_TYPE",
    help="Result types to preserve, seperated by commas (eg '-f new,matched')")
@manager.option('-m', '--marc', action='store_true', dest='marcformat',
                help="Format as human-readable MARC rather than MARCXML")
@change_command_name
def get_result_set(result_index, output, filter_types, marcformat):
    """View saved results from a previous Matcher session."""
    from invenio.legacy.bibrecord import record_xml_output
    from invenio.modules.matcher.utils import transform_record_to_marc

    all_recs = fetch_results_list(result_index)
    result_set = filter_records(all_recs, filter_types)

    if not result_set:
        print("No records in this result set.")
        sys.exit(0)

    def output_results(stream, end_char=''):
        if not marcformat:
            stream(MARCXML_HEADER)
            formatter = record_xml_output
        else:
            formatter = transform_record_to_marc

        for result, (record, matching_info) in result_set:
            stream(matching_info + end_char)
            stream(formatter(record) + end_char)

        if not marcformat:
            stream(MARCXML_FOOTER)

    if output:
        with open(output, 'w') as handle:
            output_results(handle.write, '\n')
        print("Wrote %d records to %s" % (len(result_set), output))
    else:
        output_results(print)


@manager.option(dest='result_index', type=int,
                help='Index of the result set to delete')
@change_command_name
def delete_result_set(result_index):
    """Remove a stored result set."""
    contents = get_contents()
    try:
        path = os.path.join(get_results_dir(), contents[result_index - 1])
        print("Deleting results file: %s" % (path,))
        os.remove(path)
    except (IndexError, OSError):
        print("Error: Index '%d' is not a valid result." % result_index)


@manager.option('--yes-i-know', action='store_true', dest='yes_i_know',
                help="Give verbose output")
@change_command_name
def delete_all_results(yes_i_know):
    """Clear all current result sets in store."""
    results_dir = get_results_dir()
    contents = get_contents()

    if not contents:
        print("No results in result directory.")
        sys.exit(0)

    if not yes_i_know:
        action = raw_input("Delete all %d current results? [y/N] "
                           % len(contents))
        if action.upper() != 'Y':
            print("Abort!")
            sys.exit(0)

    for filename in contents:
        path = os.path.join(results_dir, filename)
        os.remove(path)
    print("Results directory clear; removed %d results" % len(contents))


@manager.option(dest='results_source', metavar="INDEX_or_PATH",
                help='Result index, or path to BibMatch MARCXML file')
@manager.option('-o', '--output', dest='output', metavar="OUTPUT_PATH_PREFIX",
                help="Records to match (if undefined, reads from StdIn)")
@manager.option(
    '-f', '--filter', default='ambiguous',
    dest='filter_types', metavar="FILTER_RESULT_TYPE",
    help="Result types to lookup, seperated by commas. Default: ambiguous")
@manager.option('-l', '--no-lookup', action='store_true', dest='no_lookup',
                help="Give verbose output")
@change_command_name
def match_ambiguous(results_source, output, filter_types, no_lookup):
    """Manually match ambiguous results"""

    from invenio.legacy.bibrecord import (create_record, create_records,
                                          record_add_field,
                                          record_get_field_instances)

    def ask_question(rec_urls):
        """ Ask user """
        recognised_ids = {}
        options = 'Possible options:'
        for code, record_url in zip(generate_alpha_code(len(rec_urls)),
                                    rec_urls):
            recid = record_url.split('/record/')[-1]
            recognised_ids[code] = recid
            options += " %s: %s  " % (code, record_url)
        print(options)
        print("Select an option from above, enter a new record ID to append;"
              + " or leave blank to confirm as new.")

        while True:
            try:
                answer = raw_input('Answer> ')
            except KeyboardInterrupt:
                print("\nAbort!")
                sys.exit(0)
            if not answer:
                return None
            elif answer.upper() in recognised_ids.keys():
                return recognised_ids[answer.upper()]
            elif answer.strip().isdigit():
                return answer.strip()
            else:
                print("Input Error: '%s' is not a valid option." % (answer,))

    def parse_bibmatch_xml(marcxml):
        """ Parses XML taken from BibMatch results, gets a list of
        records and possible recIDs

        Returns a list of tuples in the form (record, matches) where
        record is the BibRecord representation and matches is a list
        of possible Record IDs"""
        results = []
        try:
            records = marcxml.split("<!-- BibMatch-Matching-Results: -->")[1:]
            records[-1] = records[-1].replace('</collection>', '')
        except IndexError:
            print("Index error while parsing (are these BibMatch results?)")

        for xml in records:
            record = create_record(xml)[0]
            xml_comments = xml.partition('<record>')[0]
            try:
                xml_mode = REGEX_BIBMATCH_MODE.findall(xml_comments)[0]
                mode = BIBMATCH_RESULT_MODES[xml_mode]
            except (IndexError, KeyError) as exception:
                print("Error parsing BibMatch results. %s" % str(exception))
                sys.exit(1)
            # This tuple matches the output format for legacy BibMatch
            tup = (mode, (record, xml_comments))
            results.append(tup)
        return results

    def format_field_vals(vals):
        """ Makes the pretty line """
        string_vals = ''
        for field in vals:
            string_vals += ' ['
            for idx, (code, value) in enumerate(field, 1):
                string_vals += '(%s: %s)' % (code, value)
                if idx < len(field):
                    string_vals += ' '
            string_vals += ']'
        return string_vals

    def get_fields_vals(fields, sub_codes):
        """ Extracts appropriate subfields from list of fields """
        field_vals = []
        if sub_codes:
            # We need only print the subfields mentioned in subs from tag_list
            for field in fields:
                fld = []
                for tup in field[0]:
                    if tup[0] in sub_codes:
                        fld.append(tup)
                if fld:
                    field_vals.append(fld)
        else:
            # If subs is not defined, we get the values of all subfields
            for field in fields:
                field_vals.append(field[0])
        return field_vals

    def print_essentials(record, tag_list):
        """ Neatly prints all subfield values """
        # Print control values first
        for control in tag_list['control']:
            for field in record_get_field_instances(record, tag=control):
                print(" %s: %s" % (control, field[3]))

        # Then values of datafields
        for tag, ind1, ind2, subs in tag_list['datafld']:
            fields = record_get_field_instances(record, tag, ind1, ind2)
            fields_values = get_fields_vals(fields, subs)
            field_line = format_field_vals(fields_values)
            try:
                print(" %s:%s" % (tag, field_line))
            except UnicodeDecodeError:
                print(" %s:%s" % (tag, unicode(field_line, 'utf-8')))

        print('\n')

    def fetch_remote_record(remote_url):
        """ Gets MARCXML from a server instance of Invenio and returns
        a single BibRecord structure.
        Raises ValueError if returned data is not MARCXML and URLError if
        there's an issue accessing the page after DOWNLOAD_ATTEMPTS times
        """
        url = "%s/export/xm" % (remote_url)
        for cnt in range(cfg['MATCHER_CLI_LOOKUP_ATTEMPTS']):
            try:
                handle = urlopen(url)
                xml = handle.read()
                handle.close()
                record, code, error = create_records(xml)[0]
                if code == 0:
                    print("Error: Could not parse record %s" % (url,))
                    raise ValueError(str(error))
                return record
            except URLError as exc:
                if cnt < cfg['MATCHER_CLI_LOOKUP_ATTEMPTS'] - 1:
                    print("Timeout #%d: waiting %d seconds..." %
                          (cnt, cfg['MATCHER_CLI_TIMEOUT_WAIT']))
                    sleep(cfg['MATCHER_CLI_TIMEOUT_WAIT'])
                else:
                    print("ERROR: Could not download %s (tried %d times)" %
                          (url, cfg['MATCHER_CLI_LOOKUP_ATTEMPTS']))
                    raise exc

    def lookup_remote_record(possible_matches):
        """
        Given a list of sources and record IDs, attempts to download
        the record from the source, then calls print_essentials() to display
        record information.

        Parameter
        :param possible_matches: List of tuples in the formal ('host', 'recid')
            for example [('http://cds.cern.ch', '1596995')]
        """
        print("Displaying possible matches information...")
        for code, record_url in zip(generate_alpha_code(len(possible_matches)),
                                    possible_matches):
            print("Possible match (%s): %s" % (code, record_url))
            try:
                record = fetch_remote_record(record_url)
                print_essentials(record, cfg['MATCHER_CLI_TAG_LIST'])
            except (ValueError, URLError) as exc:
                print(exc)
                continue

    def add_record_fields(record, possible_matches):
        """ Appends the inputted values to the records. If provided a
        record id, appends that, else asks for user input """
        new_recid = ask_question(possible_matches)

        if new_recid:
            try:
                del record['001']
            except KeyError:
                pass
            record_add_field(record, '001', controlfield_value=str(new_recid))
            print("RESULT: Matched to record #%s" % (new_recid,))
            return True
        else:
            print("RESULT: Confirmed as new")
            return False
        # This bit can be extended

    if not output:
        print("Error: No output prefix specified")
        sys.exit(0)

    if results_source.isdigit():
        results = fetch_results_list(int(results_source))
    else:
        with open(results_source) as handle:
            results = parse_bibmatch_xml(handle.read())

    results = filter_records(results, filter_types)

    matched_records = []
    new_records = []
    for idx, (result, (record, match_results)) in enumerate(results, 1):
        possible_matches = REGEX_BIBMATCH_RESULTS.findall(match_results)
        print(" === RECORD #%d " % idx + "=" * 60)
        print("\nOriginal Record:")
        print_essentials(record, cfg['MATCHER_CLI_TAG_LIST'])
        if not no_lookup:
            lookup_remote_record(possible_matches)

        recid_appended = add_record_fields(record, possible_matches)
        if recid_appended:
            matched_records.append(record)
        else:
            new_records.append(record)

    output_records(output + OUTPUT_SUFFIX_MATCHED,
                   matched_records, OUTPUT_COMMENT_MATCHED)
    output_records(output + OUTPUT_SUFFIX_NEW,
                   new_records, OUTPUT_COMMENT_NEW)


# ============================| Helper Functions |============================

def test_results_dir():
    """Test that the results directory exists and is writeable."""
    results_dir = get_results_dir()
    if not os.path.isdir(results_dir):
        os.mkdir(results_dir)

    filepath = "%s/testing_access" % (results_dir,)
    with open(filepath, 'w') as test_handle:
        test_handle.write("Matcher Testing File Access")
    os.remove(filepath)


def get_contents():
    """Get a list of files from the results directory."""
    test_results_dir()
    results_dir = get_results_dir()
    contents = [f for f in os.listdir(results_dir) if
                os.path.isfile(os.path.join(results_dir, f)) and
                f.startswith(cfg['MATCHER_CLI_RESULTS_PREFIX'])]
    return sorted(contents)


def fetch_results_list(result_index):
    """Returns a list of unpickled objects."""
    if result_index < 1:
        print("Error: Requested index cannot be negative.")
        sys.exit(0)

    contents = get_contents()
    results_dir = get_results_dir()
    try:
        pickle_path = os.path.join(results_dir, contents[result_index - 1])
    except IndexError:
        print("Error: Index '%d' is not a valid result." % (result_index,))
        sys.exit(0)

    with open(pickle_path, 'r') as handle:
        records = [rec for rec in pickle.load(handle)]
    return records


def filter_records(result_set, filter_types):
    """Filters a result set.

    Expects a list of results to filter, and a comma sperated list of result
    types to filter against.

    :param result_set: List of results in tuple format (result, data)
    :param filter_types: Comma seperated string of filter types
    """
    from invenio.modules.matcher.utils import RESULT_TYPES

    if filter_types:
        filter_types = [x.lower() for x in filter_types.split(',')]
        if not RESULT_TYPES.issuperset(filter_types):
            print("Error: Invalid filter types, valid choices are "
                  + "%s, %s, %s, and %s." % tuple(RESULT_TYPES))
            sys.exit(0)
    else:
        return result_set

    return [rec for rec in result_set if rec[0] in filter_types]


def generate_alpha_code(length, start='A'):
    """Generator function, creates incrementing Alphabetic codes
    (example, length=18278 gives A -> ZZZ)"""
    def increment_alpha(code, pos=-1):
        """ Increments alphabetic code, AB -> AC """
        try:
            if ord(code[pos]) >= 90:
                code[pos] = 'A'
                code = increment_alpha(code, pos - 1)
            else:
                code[pos] = chr(ord(code[pos]) + 1)
        except IndexError:
            code = ['A'] + code
        return code

    alpha_code = [x for x in start.upper()]
    while length > 0:
        yield ''.join(alpha_code)
        alpha_code = increment_alpha(alpha_code)
        length -= 1


def output_records(output_file, records, comment=''):
    """Write the records to file."""
    if len(records) == 0:
        print("Nothing to write to %s" % (output_file,))
        return

    from invenio.legacy.bibrecord import record_xml_output

    print("Writing %d records to %s" % (len(records), output_file))
    with open(output_file, 'w') as handle:
        handle.write('<?xml version="1.0" encoding="UTF-8"?>\n' + comment +
                     '\n<collection xmlns="http://www.loc.gov/MARC21/slim">\n')
        for record in records:
            xml = record_xml_output(record)
            handle.write(xml + '\n')
        handle.write('</collection>\n')


def get_results_dir():
    """Get path of the results directory"""
    return os.path.join(cfg['CFG_TMPSHAREDDIR'],
                        cfg['MATCHER_CLI_RESULTS_DIRECTORY'])


def main():
    """Flask-Script Entry Point"""
    from invenio.base.factory import create_app
    app = create_app()
    manager.app = app
    manager.run()


if __name__ == '__main__':
    main()
