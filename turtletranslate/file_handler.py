import re

import yaml


def _prep_codefences(markdown: str) -> str:
    """We need to replace newlines in codefences with a placeholder to avoid splitting them into sections."""
    codefences = re.findall(r"```.*?```", markdown, re.DOTALL)
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


def _get_sections(markdown: str) -> list[str]:
    """Get the sections from a markdown string as a list."""
    if markdown.startswith("---\n"):
        markdown = "".join(markdown.split("---\n")[2:])
    markdown = _prep_codefences(markdown)

    sections = re.split(r"\n(#{1,6})\s(?!\n#{1,6}\s)", markdown)
    sections = [s.strip() for s in sections if s.strip()]
    sections = [f"{sections[i]} {sections[i + 1]}" for i in range(0, len(sections), 2)]
    return [_unprep_codefences(s) for s in sections]


def parse(markdown: str) -> tuple[dict, list[str]]:
    """
    Parse a markdown string into frontmatter and sections.
    :param markdown: The markdown string.
    :return: A tuple containing the frontmatter and sections.
    """
    frontmatter = _get_frontmatter(markdown)
    sections = _get_sections(markdown)
    return frontmatter, sections
