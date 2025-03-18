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


def parse(markdown: str, prepend_md: str = "") -> tuple[dict, list[str]]:
    """
    Parse a markdown string into frontmatter and sections.
    :param markdown: The markdown string.
    :param prepend_md: Text to prepend at the beginning of the text, i.e. "> NOTE: This is a machine generated translation."
    :return: A tuple containing the frontmatter and sections.
    """
    frontmatter = _get_frontmatter(markdown)
    sections = _get_sections(markdown)
    if prepend_md:
        sections.insert(0, prepend_md.strip())
    return frontmatter, sections


def reconstruct(frontmatter: dict, sections: list[str]) -> str:
    """
    Reconstruct a markdown string from frontmatter and sections.
    :param frontmatter: The frontmatter dictionary.
    :param sections: The sections list.
    :return: The reconstructed markdown string.
    """
    frontmatter_str = yaml.dump(frontmatter, default_flow_style=False)
    sections_str = "\n\n".join(sections)
    return f"---\n{frontmatter_str}---\n\n{sections_str}"
