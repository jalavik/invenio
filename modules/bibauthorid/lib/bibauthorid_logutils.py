import invenio.bibauthorid_config as bconfig
import sys
import os
from datetime import datetime
from math import floor

PID = os.getpid

PRINT_OUTPUT = bconfig.DEBUG_OUTPUT
FO = bconfig.DEBUG_LOG_TO_PIDFILE
FILE_TO_WRITE = '/tmp/bibauthorid_log_pid_' + str(PID())
PRINT_TS = bconfig.DEBUG_TIMESTAMPS
PRINT_TS_US = bconfig.DEBUG_TIMESTAMPS_UPDATE_STATUS and PRINT_TS
NEWLINE = bconfig.DEBUG_UPDATE_STATUS_THREAD_SAFE

status_len = 18
comment_len = 40

TERMINATOR = '\r'
if NEWLINE or FO:
    TERMINATOR = '\n'


pidfiles = dict()


def update_status(percent, comment="", print_ts=False):
    if PRINT_OUTPUT:
        set_stdout()
        filled = max(0, int(floor(percent * status_len)))
        bar = "[%s%s] " % ("#" * filled, "-" * (status_len - filled))
        percent = ("%.2f%% done" % (percent * 100))
        progress = padd(bar + percent, status_len + 2)
        comment = padd(comment, comment_len)
        if print_ts or PRINT_TS_US:
            print datetime.now(),
        print 'pid:', PID(),
        print progress, comment, TERMINATOR,
        sys.stdout.flush()


def padd(stry, l):
    return stry[:l].ljust(l)


def update_status_final(comment=""):
    if PRINT_OUTPUT:
        set_stdout()
        update_status(1., comment)
        bibauthorid_print("")


def override_stdout_config(verbose=bconfig.DEBUG_OUTPUT, fileout=False,
                           stdout=True):
    global PRINT_OUTPUT
    global FO
    PRINT_OUTPUT = verbose
    assert fileout ^ stdout
    if fileout:
        FO = True
    if stdout:
        FO = False


def bibauthorid_verbose(verbose):
    global PRINT_OUTPUT
    PRINT_OUTPUT = verbose

def set_file_to_write(file_location):
    global FILE_TO_WRITE
    FILE_TO_WRITE = file_location


def set_stdout():
    if FO:
        try:
            sys.stdout = pidfiles[PID()]
        except KeyError:
            pidfiles[PID()] = open(FILE_TO_WRITE, 'w')
            sys.stdout = pidfiles[PID()]
            print 'WRITING TO', FILE_TO_WRITE


def __print_func(*args):
    set_stdout()
    if PRINT_TS:
        print datetime.now(),
    for arg in args:
        print arg,
    print ""
    sys.stdout.flush()


def bibauthorid_print(file_only=False, *args):
    if file_only and not FO:
        pass
    elif not (FO or PRINT_OUTPUT):
        pass
    else:
        __print_func(*args)
