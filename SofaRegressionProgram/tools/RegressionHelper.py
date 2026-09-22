import sys
from typing import TextIO

class TermColor:
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    BOLD = "\033[1m"
    ITALIC = "\033[3m"
    RESET = "\033[0m"

class TermTypeStrings:
    ERROR = "[Regression-Error]"
    WARNING = "[Regression-Warning]"
    SUCCESS = "[Regression-Success]"
    LOG = "[Regression-Log]"


def writeMessage(message, stream: TextIO = sys.stdout):
    print(f"{message}", file=stream, flush=True)

def writeError(message, verbose, prefix='', err_log_stream = None):
    complete_message = f"{prefix}{TermColor.RED}{TermTypeStrings.ERROR} {TermColor.RESET}{message}"
    if(verbose >= 0):
        writeMessage(complete_message)
    if(err_log_stream is not None):
        writeMessage(complete_message, stream = err_log_stream)

def writeWarning(message, verbose, prefix=''):
    if(verbose >= 1):
        writeMessage(f"{prefix}{TermColor.YELLOW}{TermTypeStrings.WARNING} {TermColor.RESET}{message}")

def writeSuccess(message, verbose, prefix=''):
    if(verbose >= 0):
        writeMessage(f"{prefix}{TermColor.GREEN}{TermTypeStrings.SUCCESS} {TermColor.RESET}{message}")

def writeLog(message, verbose, prefix=''):
    if(verbose >= 2):
        writeMessage(f"{prefix}{TermColor.CYAN}{TermTypeStrings.LOG} {TermColor.ITALIC}{message}{TermColor.RESET}")
