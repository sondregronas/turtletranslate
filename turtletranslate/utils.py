import re
import ast


def remove_backslashes(s):
    # Remove backslashes that precede word boundaries
    return re.sub(r"(\\)(?=\\|\b)", "", s)


def _parse_json_flexibly(s: str):
    """Attempt to parse JSON using progressively lenient heuristics."""
    try:
        return ast.literal_eval(s)
    except Exception:
        repaired = _repair_json_apostrophes(s)
        try:
            return ast.literal_eval(repaired)
        except Exception:
            return _reparse_json_with_commas_fixed(repaired)


def _repair_json_apostrophes(src: str) -> str:
    """Repair unescaped apostrophes inside single-quoted JSON-like strings."""
    out, i = [], 0
    in_single = in_double = escaped = False

    def next_significant_char(idx: int) -> str:
        while idx < len(src) and src[idx].isspace():
            idx += 1
        return src[idx] if idx < len(src) else ""

    while i < len(src):
        ch = src[i]

        if not in_single and not in_double:
            if ch in ("'", '"') and not escaped:
                in_single = ch == "'"
                in_double = ch == '"'
                out.append(ch)
                i += 1
                escaped = False
                continue
            out.append(ch)
            escaped = (ch == "\\") and not escaped
            i += 1
            continue

        if in_double:
            out.append(ch)
            if ch == '"' and not escaped:
                in_double = False
            escaped = (ch == "\\") and not escaped
            i += 1
            continue

        if ch == "'" and not escaped:
            nxt = next_significant_char(i + 1)
            if nxt not in {",", "}", "]", ":", ""}:
                out.append("\\'")
            else:
                out.append(ch)
                in_single = False
            i += 1
            escaped = False
            continue

        out.append(ch)
        escaped = (ch == "\\") and not escaped
        i += 1

    return "".join(out)


def _reparse_json_with_commas_fixed(s: str):
    """Final fallback: reformat top-level commas and retry JSON parsing."""
    inner = s[1:-1]
    out = []
    in_str = False
    quote = ""
    depth = 0
    esc = False

    for ch in inner:
        if in_str:
            out.append(ch)
            if not esc and ch == quote:
                in_str = False
                quote = ""
            esc = (ch == "\\") and not esc
            continue
        if ch in ("'", '"'):
            in_str = True
            quote = ch
            out.append(ch)
            esc = False
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "," and depth == 0:
            out.append(",\n")
            continue
        out.append(ch)

    s2 = "{" + "".join(out) + "}"
    return ast.literal_eval(s2)
