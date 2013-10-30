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

BibMatch CLI, Command Line Interface. This provides the functions for the
command line interface used by the bibmatch interface in the '/bin' directory
"""

# Necessary?
__revision__ = "$Id$"


import os
import sys
import getopt
import getpass
from tempfile import mkstemp
from six import StringIO

from invenio.base.globals import cfg
from invenio.base.factory import with_app_context
from invenio.legacy.bibconvert import api as bibconvert
from invenio.legacy.bibrecord.scripts.textmarc2xmlmarc import transform_file
from invenio.legacy.bibrecord import (create_records, record_xml_output)
from invenio.legacy.search_engine import get_fieldcodes
from invenio.utils.text import xml_entities_to_utf8
from invenio.utils.connector import InvenioConnector

from .config import (MATCHER_LOCAL_SLEEPTIME,
                     MATCHER_REMOTE_SLEEPTIME,
                     MATCHER_QUERY_TEMPLATES)

from .engine import legacy_bibmatch_matching
from .validator import transform_record_to_marc


def usage():
    """Print help"""

    print(""" BibMatch - match bibliographic data against database, either locally or remotely
 Usage: %s [options] [QUERY]

 Options:

 Output:

 -0 --print-new (default) print unmatched in stdout
 -1 --print-match print matched records in stdout
 -2 --print-ambiguous print records that match more than 1 existing records
 -3 --print-fuzzy print records that match the longest words in existing records

 -b --batch-output=(filename). filename.new will be new records, filename.matched will be matched,
      filename.ambiguous will be ambiguous, filename.fuzzy will be fuzzy match
 -t --text-marc-output transform the output to text-marc format instead of the default MARCXML

 Simple query:

 -q --query-string=(search-query/predefined-query) See "Querystring"-section below.
 -f --field=(field)

 General options:

 -n   --noprocess          Do not print records in stdout.
 -i,  --input              use a named file instead of stdin for input
 -v,  --verbose=LEVEL      verbose level (from 0 to 9, default 1)
 -r,  --remote=URL         match against a remote Invenio installation (Full URL, no trailing '/')
                           Beware: Only searches public records attached to home collection
 -a,  --alter-recid        The recid (controlfield 001) of matched or fuzzy matched records in
                           output will be replaced by the 001 value of the matched record.
                           Note: Useful if you want to replace matched records using BibUpload.
 -z,  --clean              clean queries before searching
 --no-validation           do not perform post-match validation
 -h,  --help               print this help and exit
 -V,  --version            print version information and exit

 Advanced options:

 -m --mode=(a|e|o|p|r)     perform an advanced search using special search mode.
                             Where mode is:
                               "a" all of the words,
                               "o" any of the words,
                               "e" exact phrase,
                               "p" partial phrase,
                               "r" regular expression.

 -o --operator(a|o)        used to concatenate identical fields in search query (i.e. several report-numbers)
                             Where operator is:
                               "a" boolean AND (default)
                               "o" boolean OR

 -c --config=filename      load querystrings from a config file. Each line starting with QRYSTR will
                           be added as a query. i.e. QRYSTR --- [title] [author]

 -x --collection           only perform queries in certain collection(s).
                           Note: matching against restricted collections requires authentication.

 --user=USERNAME           username to use when connecting to Invenio instance. Useful when searching
                           restricted collections. You will be prompted for password.

 QUERYSTRINGS
   Querystrings determine which type of query/strategy to use when searching for the
   matching records in the database.

   Predefined querystrings:

     There are some predefined querystrings available:

     title             - standard title search. (i.e. "this is a title") (default)
     title-author      - title and author search (i.e. "this is a title AND Lastname, F")
     reportnumber      - reportnumber search (i.e. reportnumber:REP-NO-123).

     You can also add your own predefined querystrings inside invenio.conf file.

     You can structure your query in different ways:

     * Old-style: fieldnames separated by '||' (conforms with earlier BibMatch versions):
       -q "773__p||100__a"

     * New-style: Invenio query syntax with "bracket syntax":
       -q "773__p:\"[773__p]\" 100__a:[100__a]"

     Depending on the structure of the query, it will fetch associated values from each record and put it into
     the final search query. i.e in the above example it will put journal-title from 773__p.

     When more then one value/datafield is found, i.e. when looking for 700__a (additional authors),
     several queries will be put together to make sure all combinations of values are accounted for.
     The queries are separated with given operator (-o, --operator) value.

     Note: You can add more then one query to a search, just give more (-q, --query-string) arguments.
     The results of all queries will be combined when matching.

   BibConvert formats:

     Another option to further improve your matching strategy is to use BibConvert formats. By using the formats
     available by BibConvert you can change the values from the retrieved record-fields.

     i.e. using WORDS(1,R) will only return the first (1) word from the right (R). This can be very useful when
     adjusting your matching parameters to better match the content. For example only getting authors last-name
     instead of full-name.

     You can use these formats directly in the querystrings (indicated by '::'):

     * Old-style: -q "100__a::WORDS(1,R)::DOWN()"
       This query will take first word from the right from 100__a and also convert it to lower-case.

     * New-style: -q "100__a:[100__a::WORDS(1,R)::DOWN()]"

     See BibConvert documentation for a more detailed explanation of formats.

   Predefined fields:

     In addition to specifying distinct MARC fields in the querystrings you can use predefined
     fields as configured in the LOCAL(!) Invenio system. These fields will then be mapped to one
     or more fieldtags to be retrieved from input records.

     Common predefined fields used in querystrings: (for Invenio demo site, your fields may vary!)

     'abstract', 'affiliation', 'anyfield', 'author', 'coden', 'collaboration',
     'collection', 'datecreated', 'datemodified', 'division', 'exactauthor', 'exactfirstauthor',
     'experiment', 'fulltext', 'isbn', 'issn', 'journal', 'keyword', 'recid',
     'reference', 'reportnumber', 'subject', 'title', 'year'

 Examples:

 $ bibmatch [options] < input.xml > unmatched.xml
 $ bibmatch -b out -n < input.xml
 $ bibmatch -a -1 < input.xml > modified_match.xml

 $ bibmatch --field=title < input.xml
 $ bibmatch --field=245__a --mode=a < input.xml

 $ bibmatch --print-ambiguous -q title-author < input.xml > ambigmatched.xml
 $ bibmatch -q "980:Thesis 773__p:\"[773__p]\" 100__a:[100__a]" -r "http://inspirebeta.net" < input.xml

 $ bibmatch --collection 'Books,Articles' < input.xml
 $ bibmatch --collection 'Theses' --user admin < input.xml
    """ % (sys.argv[0],))
    sys.exit(1)
    return


@with_app_context()
def main():
    """
    Record matches database content when defined search gives
    exactly one record in the result set. By default the match is
    done on the title field.
    """
    try:
        opts, args = getopt.getopt(sys.argv[1:], "0123hVm:fq:c:nv:o:b:i:r:tazx:",
                                   ["print-new",
                                    "print-match",
                                    "print-ambiguous",
                                    "print-fuzzy",
                                    "help",
                                    "version",
                                    "mode=",
                                    "field=",
                                    "query-string=",
                                    "config=",
                                    "no-process",
                                    "verbose=",
                                    "operator=",
                                    "batch-output=",
                                    "input=",
                                    "remote=",
                                    "text-marc-output",
                                    "alter-recid",
                                    "clean",
                                    "collection=",
                                    "user=",
                                    "no-fuzzy",
                                    "no-validation",
                                    "ascii"])

    except getopt.GetoptError:
        usage()

    match_results = []
    qrystrs = []                              # list of query strings
    print_mode = 0                            # default match mode to print new records
    noprocess = 0                             # dump result in stdout?
    operator = "and"
    verbose = 1                               # 0..be quiet
    records = []
    batch_output = ""                         # print stuff in files
    f_input = ""                              # read from where, if param "i"
    server_url = cfg['CFG_SITE_SECURE_URL']   # url to server performing search, local by default
    modify = 0                                # alter output with matched record identifiers
    textmarc_output = 0                       # output in MARC instead of MARCXML
    field = ""
    search_mode = None                        # activates a mode, uses advanced search instead of simple
    sleeptime = MATCHER_LOCAL_SLEEPTIME  # the amount of time to sleep between queries, changes on remote queries
    clean = False                             # should queries be sanitized?
    collections = []                          # only search certain collections?
    user = ""
    password = ""
    validate = True                           # should matches be validate?
    fuzzy = True                              # Activate fuzzy-mode if no matches found for a record
    ascii_mode = False                        # Should values be turned into ascii mode

    for opt, opt_value in opts:
        if opt in ["-0", "--print-new"]:
            print_mode = 0
        if opt in ["-1", "--print-match"]:
            print_mode = 1
        if opt in ["-2", "--print-ambiguous"]:
            print_mode = 2
        if opt in ["-3", "--print-fuzzy"]:
            print_mode = 3
        if opt in ["-n", "--no-process"]:
            noprocess = 1
        if opt in ["-h", "--help"]:
            usage()
            sys.exit(0)
        if opt in ["-V", "--version"]:
            print(__revision__)
            sys.exit(0)
        if opt in ["-t", "--text-marc-output"]:
            textmarc_output = 1
        if opt in ["-v", "--verbose"]:
            verbose = int(opt_value)
        if opt in ["-f", "--field"]:
            raise NotImplementedError("--field flag not implemented in PU")
            # if opt_value in get_fieldcodes():
            #     field = opt_value
        if opt in ["-q", "--query-string"]:
            try:
                template = MATCHER_QUERY_TEMPLATES[opt_value]
                qrystrs.append((field, template))
            except KeyError:
                qrystrs.append((field, opt_value))
        if opt in ["-m", "--mode"]:
            raise NotImplementedError("--mode flag not implemented in PU")
            # search_mode = opt_value
        if opt in ["-o", "--operator"]:
            raise NotImplementedError("--operator flag not implemented in PU")
            # if opt_value.lower() in ["o", "or", "|"]:
            #     operator = "or"
            # elif opt_value.lower() in ["a", "and", "&"]:
            #     operator = "and"
        if opt in ["-b", "--batch-output"]:
            batch_output = opt_value
        if opt in ["-i", "--input"]:
            f_input = opt_value
        if opt in ["-r", "--remote"]:
            server_url = opt_value
            sleeptime = MATCHER_REMOTE_SLEEPTIME
        if opt in ["-a", "--alter-recid"]:
            raise NotImplementedError("--alter-recid flag not implemented in PU")
            # modify = 1
        if opt in ["-z", "--clean"]:
            raise NotImplementedError("--clean flag not implemented in PU")
            # clean = True
        if opt in ["-c", "--config"]:
            raise NotImplementedError("--config flag not implemented in PU")
            # config_file = opt_value
            # config_file_read = bibconvert.read_file(config_file, 0)
            # for line in config_file_read:
            #     tmp = line.split("---")
            #     if(tmp[0] == "QRYSTR"):
            #         qrystrs.append((field, tmp[1]))
        if opt in ["-x", "--collection"]:
            colls = opt_value.split(',')
            for collection in colls:
                if collection not in collections:
                    collections.append(collection)
        if opt in ["--user"]:
            user = opt_value
            password = getpass.getpass()
        if opt == "--no-fuzzy":
            raise NotImplementedError("--no-fuzzy flag not implemented in PU")
            # fuzzy = False
        if opt == "--no-validation":
            validate = False
        if opt == "--ascii":
            raise NotImplementedError("--ascii flag not implemented in PU")
            # ascii_mode = True

    if verbose:
        print("\nBibMatch: Parsing input file %s..." % (f_input,))

    read_list = []
    if not f_input:
        for line_in in sys.stdin:
            read_list.append(line_in)
    else:
        f = open(f_input)
        for line_in in f:
            read_list.append(line_in)
        f.close()
    file_read = "".join(read_list)

    # Detect input type
    if not file_read.strip().startswith('<'):
        # Not xml, assume type textmarc
        file_read = transform_input_to_marcxml(f_input, file_read)

    records = create_records(file_read)

    if len(records) == 0:
        if verbose:
            print("\nBibMatch: Input file contains no records.\n")
        sys.exit(1)

    # Check for any parsing errors in records
    if bibrecs_has_errors(records):
        # Errors found. Let's try to remove any XML entities
        if verbose > 8:
            print("\nBibMatch: Parsing error. Trying removal of XML entities..\n")

        file_read = xml_entities_to_utf8(file_read)
        records = create_records(file_read)
        if bibrecs_has_errors(records):
            # Still problems.. alert the user and exit
            if verbose:
                errors = "\n".join([str(err_msg) for dummy, err_code, err_msg in records
                                    if err_code == 0])
                print("\nBibMatch: Errors during record parsing:\n%s\n" % (errors,))
            sys.exit(1)

    if verbose:
        print("read %d records" % (len(records),))
        print("\nBibMatch: Matching ...")

    if not validate:
        if verbose:
            print("\nWARNING: Skipping match validation.\n")

    config = {
        "SEARCH_QUERY_STRINGS": qrystrs,
        "SEARCH_COLLECTIONS": collections
    }

    # TODO, some variables here, hardcoded, need changing
    logfile = "/tmp/matcher.log"
    cli_handle = logging.StreamHandler(stream=sys.stdout)
    cli_handle.setLevel(logging.DEBUG)
    handlers = [cli_handle]
    connector = InvenioConnector(server_url, user, password)
    # NOTE: Direct link to engine.py will be removed upon implementation of
    #       the API.
    all_results = legacy_bibmatch_matching(records, config, connector)

    recs_new = []
    recs_matched = []
    recs_ambiguous = []
    recs_fuzzy = []

    for result, record in all_results:
        if result == 'new':
            recs_new.append(record)
        if result == 'matched':
            recs_matched.append(record)
        if result == 'ambiguous':
            recs_ambiguous.append(record)
        if result == 'fuzzy':
            recs_fuzzy.append(record)

    match_results = [recs_new, recs_matched, recs_ambiguous, recs_fuzzy]

    # set the output according to print..
    # 0-newrecs 1-matchedrecs 2-ambiguousrecs 3-fuzzyrecs
    recs_out = match_results[print_mode]

    if verbose:
        print("\n Bibmatch report")
        print("=" * 35)
        print(" New records         : %d" % (len(match_results[0]),))
        print(" Matched records     : %d" % (len(match_results[1]),))
        print(" Ambiguous records   : %d" % (len(match_results[2]),))
        print(" Fuzzy records       : %d" % (len(match_results[3]),))
        print("=" * 35)
        print(" Total records       : %d" % (len(records),))
        print(" See detailed log at %s" % (logfile,))

    if not noprocess and recs_out:
        print '<collection xmlns="http://www.loc.gov/MARC21/slim">'
        for record, results in recs_out:
            if textmarc_output:
                # FIXME: textmarc output does not print matching results
                print transform_record_to_marc(record)
            else:
                print results
                print record_xml_output(record)
        print "</collection>"

    if batch_output:
        i = 0
        outputs = ['new', 'matched', 'ambiguous', 'fuzzy']
        for result in match_results:
            out = []
            out.append('<collection xmlns="http://www.loc.gov/MARC21/slim">')
            for record, results in result:

                if textmarc_output:
                    # FIXME: textmarc output does not print matching results
                    out.append(transform_record_to_marc(record))
                else:
                    out.append(results)
                    out.append(record_xml_output(record))
            out.append("</collection>")
            filename = "%s.%s.xml" % (batch_output, outputs[i])
            file_fd = open(filename, "w")
            file_fd.write("\n".join(out))
            file_fd.close()
            i += 1


def transform_input_to_marcxml(filename=None, file_input=""):
    """
    Takes the filename or input of text-marc and transforms it
    to MARCXML.
    """
    if not filename:
        # Create temporary file to read from
        tmp_fd, filename = mkstemp()
        os.write(tmp_fd, file_input)
        os.close(tmp_fd)
    try:
        # Redirect output, transform, restore old references
        old_stdout = sys.stdout
        new_stdout = StringIO()
        sys.stdout = new_stdout

        transform_file(filename)
    finally:
        sys.stdout = old_stdout
    return new_stdout.getvalue()


def bibrecs_has_errors(bibrecs):
    """
    Utility function to check a list of parsed BibRec objects, directly
    from the output of bibrecord.create_records(), for any
    badly parsed records.

    If an error-code is present in the result the function will return True,
    otherwise False.
    """
    return 0 in [err_code for dummy, err_code, dummy2 in bibrecs]
