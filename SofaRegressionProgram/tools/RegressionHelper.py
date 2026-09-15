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


def writeError(message, verbose, prefix='', stream: TextIO = sys.stdout):
    if(verbose >= 0):
        print(f"{prefix}{TermColor.RED}[Regression-Error] {TermColor.RESET}{message}", file=stream, flush=True)

def writeWarning(message, verbose, prefix='', stream: TextIO = sys.stdout):
    if(verbose >= 1):
        print(f"{prefix}{TermColor.YELLOW}[Regression-Warning] {TermColor.RESET}{message}", file=stream, flush=True)

def writeSuccess(message, verbose, prefix='', stream: TextIO = sys.stdout):
    if(verbose >= 0):
        print(f"{prefix}{TermColor.GREEN}[Regression-Success] {TermColor.RESET}{message}", file=stream, flush=True)

def writeLog(message, verbose, prefix='', stream: TextIO = sys.stdout):
    if(verbose >= 2):
        print(f"{prefix}{TermColor.CYAN}[Regression-Log] {TermColor.ITALIC}{message}{TermColor.RESET}", file=stream, flush=True)
