import logging
import re
from functools import lru_cache

import yaml

from turtletranslate.logger import logger
from turtletranslate.tokens import TOKENS, NO_TRANSLATE_TOKEN, DEFAULT_TOKEN, PREPEND_TOKEN, TOKENS_CH_LEN

# The blockquote syntax captures content until there is a newline that is not followed by a blockquote symbol
# Captures both callouts and blockquotes
BLOCKQUOTE_SYNTAX = r"[^\S\r\n]*(?:> ?)([^\n]*(?:\n[ \t>][^\n]*)*)"
DELIMITERS = "|".join(
    [
        r"#{1,6}\s",  # Headers
        r"`{3}(?:\n|.)+?`{3}",  # Code fences
        BLOCKQUOTE_SYNTAX,  # Callouts and blockquotes
        # These are commented out because they can cause extra hallucinations in the translation, omitting them for now
        # r"={3}\s",  # Content blocks  # Not a problem so far, but might give inconsistent spacing
    ]
)

# TODO: Adding sections to a dictionary with the section type as the key, and the section as the value, would
#       allow for separate translation handling for different section types, i.e. admonitions, code blocks, etc.
callout_regex = re.compile(BLOCKQUOTE_SYNTAX)
delimiter_regex = re.compile(rf"(?:\n|^)({DELIMITERS})\n*", re.MULTILINE)


def _prep_codefences(markdown: str) -> str:
    """We need to replace newlines in codefences with a placeholder to avoid splitting them into sections."""
    codefences = re.findall(r"\n```(.*?```)", markdown, re.DOTALL)
    for codefence in codefences:
        markdown = markdown.replace(codefence, codefence.replace("\n", "\n!%CODEFENCE%!"))
    return markdown


def _unprep_codefences(markdown: str) -> str:
    """Replace the placeholder with newlines in codefences."""
    return markdown.replace("\n!%CODEFENCE%!", "\n")


def _get_frontmatter(markdown: str) -> dict:
    """Get the frontmatter from a markdown string as a dictionary."""
    frontmatter = {}
    if markdown.startswith("---\n"):
        frontmatter = yaml.safe_load(markdown.split("---\n")[1])
    return frontmatter


def _cleanup_sections(sections: list[str]) -> list[str]:
    """Merge sections that should be merged, i.e. headers with the following section, and remove duplicate selections."""

    sections = [s.rstrip("\n") for s in sections if s and s.strip()]

    def should_merge(section: str) -> bool:
        mergable_symbols = ["#"]
        s = section.strip()
        if not s:
            return False
        if s[0] not in mergable_symbols:
            return False
        return len(s) == s.count(s[0])

    merged_sections = []
    for i, section in enumerate(sections):
        if i + 1 < len(sections) and should_merge(section):
            merged_sections.append(f"{section}{sections[i + 1]}")
            sections.pop(i + 1)  # Remove the next section, as it has been merged
        # If it matches the callout syntax, we should skip the next section, as it gets captured in the callout itself
        elif callout_regex.match(section):
            merged_sections.append(section)
            logger.debug("Removing section after callout")
            logger.debug("Keeping: " + section.replace("\n", "\\n"))
            logger.debug("Removing: " + sections[i + 1].replace("\n", "\\n"))
            sections.pop(i + 1)  # Remove the next section, as it is already captured in the callout
        else:
            merged_sections.append(section)
    return [_unprep_codefences(s) for s in merged_sections]


def _tokenize_sections(sections: list[str]) -> list[dict[str, str]]:
    """Tokenize the sections into a dictionary with the section type as the key, and the section as the value."""
    tokens = list()
    for section in sections:
        for token, token_type in TOKENS.items():
            if section.startswith(token):
                tokens.append({token_type: section})
                break
            # If no alphanumeric characters are present, we can mark it as a no_translate section
            if not any(c.isalnum() for c in section):
                tokens.append({NO_TRANSLATE_TOKEN: section})
                break
        else:
            tokens.append({DEFAULT_TOKEN: section})
    return tokens


def _get_sections(markdown: str) -> list[dict[str, str]]:
    """Get the sections from a markdown string as a list."""
    if markdown.startswith("---\n"):
        markdown = "".join(markdown.split("---\n")[2:])
    markdown = _prep_codefences(markdown)
    sections = delimiter_regex.split(markdown)
    sections = _cleanup_sections(sections)  # Merge headers with the following section
    sections = _tokenize_sections(sections)
    return sections


@lru_cache
def parse(markdown: str, prepend_md: str = "") -> tuple[dict, list[dict[str, str]]]:
    """
    Parse a markdown string into frontmatter and sections.
    :param markdown: The markdown string.
    :param prepend_md: Text to prepend at the beginning of the text, i.e. "> NOTE: This is a machine generated translation."
    :return: A tuple containing the frontmatter and sections.
    """
    frontmatter = _get_frontmatter(markdown)
    sections = _get_sections(markdown)
    if prepend_md:
        sections.insert(0, {PREPEND_TOKEN: prepend_md.strip()})
    if logger.level == logging.DEBUG:
        for i, s in enumerate(sections):
            k, v = list(s.items())[0]
            c = v.replace("\n", "\\n").replace("\t", "\\t")
            logger.debug(f"\033[33mSection {i}\033[0m \033[35m{k:.<{TOKENS_CH_LEN}}\033[0m: \033[34m{c}\033[0m")
    return frontmatter, sections


def wrap_span_around_sections(sections: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    Wrap a span tag around each section in a list of sections.
    :param sections: The sections list.
    :return: The sections list with the span wrapped around the text.
    """
    new_sections = list()
    for i, section in enumerate(sections):
        k, v = list(section.items())[0]
        new_sections.append(
            {
                k: f'<span class="turtletranslate-section" '
                f'data-turtletranslate-type="{k}" '
                f'data-turtletranslate-index="{i}" '
                f'data-turtletranslate-checksum="{section["checksum"]}"'
                f">\n\n{v}\n\n</span>"
            }
        )
    return new_sections


def reconstruct(frontmatter: dict, sections: list[dict[str, str]], wrap_in_span: bool = True) -> str:
    """
    Reconstruct a markdown string from frontmatter and sections.
    :param frontmatter: The frontmatter dictionary.
    :param sections: The sections list.
    :param wrap_in_span: Whether to wrap a span tag around each section, with data attributes for type and index.
    :return: The reconstructed markdown string.
    """
    frontmatter_str = yaml.dump(frontmatter, default_flow_style=False)
    if frontmatter_str.strip() == "{}":
        frontmatter_str = ""
    if wrap_in_span:
        sections = wrap_span_around_sections(sections)
    sections_str = "\n\n".join([list(s.values())[0] for s in sections])
    return f"---\n{frontmatter_str}---\n\n{sections_str}"
