class TermColor:
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    BOLD = "\033[1m"
    ITALIC = "\033[3m"
    RESET = "\033[0m"


def writeError(message, verbose):
    if(verbose >= 0):
        print(f"{TermColor.RED}[Regression-Error] {TermColor.RESET}{message}")

def writeWarning(message, verbose):
    if(verbose >= 1):
        print(f"{TermColor.YELLOW}[Regression-Warning] {TermColor.RESET}{message}")

def writeSuccess(message, verbose):
    if(verbose >= 0):
        print(f"{TermColor.GREEN}[Regression-Success] {TermColor.RESET}{message}")

def writeLog(message, verbose):
    if(verbose >= 2):
        print(f"{TermColor.CYAN}[Regression-Log] {TermColor.ITALIC}{message}{TermColor.RESET}")
