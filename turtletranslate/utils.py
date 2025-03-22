import re


def remove_backslashes(s):
    # Remove backslashes that precede word boundaries
    return re.sub(r"(\\)(?=\\|\b)", "", s)
