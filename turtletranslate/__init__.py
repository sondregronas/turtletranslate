from dataclasses import dataclass

import ollama

from turtletranslate import file_handler
from turtletranslate.translate import translate

TRANSLATABLE_FRONTMATTER_KEYS = [
    "title",
    "description",
    "summary",
]


@dataclass
class TurtleTranslator:
    client: ollama.Client
    document: str
    model: str = "gemma3:27b-it-q4_K_M"
    num_ctx: int = 6 * 1024
    source_language: str = "English"
    target_language: str = "Spanish"
    prepend_md: str = (
        ""  # Markdown to prepend to the translated document (i.e. "> NOTE: This is a machine generated translation.")
    )
    review: bool = True  # Whether to enable the review process (critique and revision)
    wrap_in_span: bool = True  # Whether to wrap each section in a span tag with data attributes for type and index
    _max_attempts: int = 100  # Maximum number of attempts to make before giving up on a translation
    _sections: list[dict[str, str]] = list
    _section: dict[str, str] = dict
    _translated_sections: list[str] = list
    _translated_section: str = ""
    _summary: str = ""
    _frontmatter: dict = dict
    _original_frontmatter: dict = dict
    _translated_frontmatter: dict = dict
    _critique: str = ""  # The last critique given by the reviewer worker

    def __post_init__(self):
        self._original_frontmatter, self._sections = file_handler.parse(self.document, prepend_md=self.prepend_md)
        self.frontmatter = self._original_frontmatter

    def reconstruct_translated_document(self) -> str:
        return file_handler.reconstruct(
            self.translated_frontmatter, self._translated_sections, wrap_in_span=self.wrap_in_span
        )

    def format(self) -> dict:
        return {
            "source_language": self.source_language,
            "target_language": self.target_language,
            "section": self._section,
            "translated_section": self._translated_section,
            "document": self.document,
            "summary": self._summary,
            "frontmatter": self.frontmatter,
            "critique": self._critique,
        }

    @property
    def frontmatter(self) -> dict:
        return self._frontmatter

    @frontmatter.setter
    def frontmatter(self, value: dict):
        self._frontmatter = {k: v for k, v in value.items() if k in TRANSLATABLE_FRONTMATTER_KEYS}

    @property
    def translated_frontmatter(self) -> dict:
        return {k: self._translated_frontmatter.get(k, v) for k, v in self._original_frontmatter.items()}

    @translated_frontmatter.setter
    def translated_frontmatter(self, value: dict):
        self._translated_frontmatter = value

    def translate(self):
        return translate(self)
