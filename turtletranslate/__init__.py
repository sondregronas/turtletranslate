import os
import re
from dataclasses import dataclass

import ollama

from turtletranslate import file_handler
from turtletranslate.file_handler import parse, load_translations_from_file
from turtletranslate.logger import logger
from turtletranslate.tokens import NO_TRANSLATE_TOKEN
from turtletranslate.translate import translate, generate_checksum
from turtletranslate.validator import validate

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
    target_filename: str = None  # Target filename for translation output and reuse
    write_file: bool = None  # Whether to write the output to a file (defaults to True if target_filename is provided)
    add_stats: bool = True  # Whether to add translation statistics to the frontmatter
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
    _existing_sections: dict = None  # Dictionary to store existing translated sections by checksum

    def __post_init__(self):
        self._original_frontmatter, self._sections = file_handler.parse(self.document, prepend_md=self.prepend_md)
        self.frontmatter = self._original_frontmatter

    def _load_existing_translations(self):
        """Load existing translations from target file and map them by checksum."""
        if self.target_filename and os.path.exists(self.target_filename):
            self._existing_sections = load_translations_from_file(self.target_filename)
            logger.info(f"Loaded {len(self._existing_sections)} existing translations from {self.target_filename}")
        else:
            logger.warning("Target file does not exist or is not specified.")

    def reconstruct_translated_document(self, extra_frontmatter: dict = None) -> str:
        extra_frontmatter = extra_frontmatter or dict()
        return file_handler.reconstruct(
            {**self.translated_frontmatter, **extra_frontmatter},
            self._translated_sections,
            wrap_in_span=self.wrap_in_span,
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
        # Set write_file default if not explicitly set
        if self.write_file is None:
            self.write_file = self.target_filename is not None

        # Load existing translations if target file exists
        self._existing_sections = dict()
        if self.target_filename and os.path.exists(self.target_filename):
            self._load_existing_translations()

        return translate(self)

    def get_translation_tuples(self) -> dict:
        """
        Extract translations from the target file and return a dictionary of translations.

        Requires target_filename to be set and the file to exist.

        Returns:
            dict: A dictionary where the key is the checksum, and the value is a tuple of
                  (original_section_content, translated_section_content, section_type).
        """
        translations = dict()
        if not self.target_filename or not os.path.exists(self.target_filename):
            logger.warning("Target file does not exist or is not specified.")
            return translations

        try:
            # Parse the original document to get sections and their checksums
            _, source_sections = parse(self.document)

            # Load translations from the target file
            loaded_translations = load_translations_from_file(self.target_filename)

            # Map translations by checksum
            for checksum, translated_content in loaded_translations.items():
                section_type = None  # Default to None if not found
                original_content = ""

                # Find the original content and section type using the checksum
                for section in source_sections:
                    for key, value in section.items():
                        if generate_checksum(value) == checksum:
                            original_content = value
                            section_type = key
                            break
                    if original_content:
                        break

                translations[checksum] = (original_content, translated_content, section_type)

            logger.info(f"Extracted {len(translations)} translations from {self.target_filename}")
        except Exception as e:
            logger.error(f"Failed to extract translations: {e}")

        # Filter out sections of type None and NO_TRANSLATE_TOKEN
        translations = {
            checksum: value for checksum, value in translations.items() if value[2] not in (None, NO_TRANSLATE_TOKEN)
        }

        return translations

    def remove_failed_translation_checksums(self, failed_checksums: list[str]) -> None:
        """
        Remove checksum attributes from failed translations in the target file.

        Args:
            failed_checksums: List of checksums to remove from the target file
        """
        if not failed_checksums:
            return

        try:
            with open(self.target_filename, "r", encoding="utf-8") as f:
                content = f.read()

            for checksum in failed_checksums:
                pattern = rf'\sdata-turtletranslate-checksum="{checksum}"'
                content = re.sub(pattern, "", content)

            with open(self.target_filename, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"Removed {len(failed_checksums)} failed checksums from {self.target_filename}")
        except Exception as e:
            logger.error(f"Failed to remove checksums: {e}")

    def validate_translations(self, invalidate_checksums=True) -> dict[str, list]:
        """Iterate through all translation pairs, run validation, and return a summary of results."""
        results = {
            "passed": [],
            "failed": [],
        }
        for checksum, tuples in self.get_translation_tuples().items():
            org, translated, section_type = tuples
            if validate(self, org, translated, section_type):
                results["passed"].append(checksum)
            else:
                results["failed"].append(checksum)

        if invalidate_checksums and results["failed"]:
            self.remove_failed_translation_checksums(results["failed"])

        # TODO: more validation behavior (e.g., re-translation attempts) can be added here
        # Ideally we should use protocols or strategies to manage different validation failure behaviors, but for now this spaghetti code will do.

        return results

    def write_translated_document(self, extra_frontmatter: dict = None) -> str:
        """Write the translated document to the target file if write_file is True."""
        translated_content = self.reconstruct_translated_document(extra_frontmatter=extra_frontmatter)

        if self.write_file and self.target_filename:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(self.target_filename)), exist_ok=True)
                with open(self.target_filename, "w", encoding="utf-8") as f:
                    f.write(translated_content)
                logger.info(f"Translated document written to {self.target_filename}")
            except Exception as e:
                logger.error(f"Failed to write translated document: {e}")

        return translated_content


def _retroactively_update_checksums(source_document: str, target_document: str, output_file: str = None) -> str:
    """
    Update existing translated document with checksums from source document.

    Args:
        source_document: Path to the original source document
        target_document: Path to the translated document that needs checksums
        output_file: Path to write updated document (defaults to target_document)

    Returns:
        Updated document content with checksums
    """
    # Read source and target documents
    with open(source_document, "r", encoding="utf-8") as f:
        source_content = f.read()
    with open(target_document, "r", encoding="utf-8") as f:
        target_content = f.read()

    # Parse source document to generate checksums
    source_frontmatter, source_sections = parse(source_content)

    # Find opening span tags in target document (without checksum attribute)
    pattern = r'(<span class="turtletranslate-section"[^>]*?data-turtletranslate-type="([^"]+)"[^>]*?data-turtletranslate-index="(\d+)"[^>]*?)>'

    # For each match, calculate and insert the checksum attribute
    def replace_match(match):
        opening_tag = match.group(1)
        section_type = match.group(2)
        index = int(match.group(3)) - 1

        # Skip prepend section as it's not in the original document
        if section_type == "prepend":
            return match.group(0)

        # Only add checksum if it's not already present
        if "data-turtletranslate-checksum" not in opening_tag:
            # Find corresponding source section by index and type
            try:
                print(index, section_type, source_sections[index], source_sections)
                if index < len(source_sections) and section_type in source_sections[index]:
                    original_content = source_sections[index][section_type]
                    checksum = generate_checksum(original_content)
                    # Insert checksum attribute before closing bracket
                    return f'{opening_tag} data-turtletranslate-checksum="{checksum}">'
            except (IndexError, KeyError):
                logger.warning(f"Could not find matching source section for {section_type} at index {index}")

        # If no matching section or already has checksum, return unchanged
        return match.group(0)

    # Apply replacements
    updated_content = re.sub(pattern, replace_match, target_content)

    # Write to output file if specified
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(updated_content)
    elif output_file is None and target_document:  # Default to overwriting target
        with open(target_document, "w+", encoding="utf-8") as f:
            f.write(updated_content)

    logger.info(f"Added checksums to translated document from {source_document}")
    return updated_content
