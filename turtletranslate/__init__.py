from dataclasses import dataclass

import ollama

from turtletranslate import file_handler


class TurtleTranslateException(BaseException): ...


TRANSLATABLE_FRONTMATTER_KEYS = [
    "title",
    "description",
    "summary",
]


@dataclass
class TurtleTranslateData:
    client: ollama.Client
    document: str
    model: str = "llama3.1"
    source_language: str = "English"
    target_language: str = "Spanish"
    _max_attempts: int = 100
    _sections: list[str] = None
    _translated_sections: list[str] = None
    _section: str = ""
    _summary: str = ""
    _frontmatter: dict = None

    def __post_init__(self):
        self.frontmatter, self._sections = file_handler.parse(self.document)

    def format(self) -> dict:
        return {
            "source_language": self.source_language,
            "target_language": self.target_language,
            "section": self._section,
            "document": self.document,
            "summary": self._summary,
            "frontmatter": self.frontmatter,
        }

    @property
    def frontmatter(self) -> dict:
        return self._frontmatter

    @frontmatter.setter
    def frontmatter(self, value: dict):
        self._frontmatter = {k: v for k, v in value.items() if k in TRANSLATABLE_FRONTMATTER_KEYS}
