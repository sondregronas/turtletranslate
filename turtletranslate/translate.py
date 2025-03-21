import ast
import hashlib
import json
import re
import timeit
from functools import lru_cache

import ollama

from turtletranslate.exceptions import TurtleTranslateException
from turtletranslate.logger import logger
from turtletranslate.models import (
    SUMMARIZER_CRITIC_SYSTEM,
    SUMMARIZER_CRITIC_PROMPT,
    SUMMARIZER_WORKER_SYSTEM,
    SUMMARIZER_WORKER_PROMPT,
    TRANSLATION_CRITIC_BLOCKQUOTE_SYSTEM,
    TRANSLATION_CRITIC_BLOCKQUOTE_PROMPT,
    TRANSLATION_CRITIC_ARTICLE_SYSTEM,
    TRANSLATION_CRITIC_ARTICLE_PROMPT,
    TRANSLATION_CRITIC_CODEFENCE_SYSTEM,
    TRANSLATION_CRITIC_CODEFENCE_PROMPT,
    TRANSLATION_CRITIC_WILDCARD_SYSTEM,
    TRANSLATION_CRITIC_WILDCARD_PROMPT,
    TRANSLATION_WORKER_BLOCKQUOTE_SYSTEM,
    TRANSLATION_WORKER_BLOCKQUOTE_PROMPT,
    TRANSLATION_WORKER_ARTICLE_SYSTEM,
    TRANSLATION_WORKER_ARTICLE_PROMPT,
    TRANSLATION_WORKER_CODEFENCE_SYSTEM,
    TRANSLATION_WORKER_CODEFENCE_PROMPT,
    TRANSLATION_WORKER_WILDCARD_SYSTEM,
    TRANSLATION_WORKER_WILDCARD_PROMPT,
    FRONTMATTER_WORKER_SYSTEM,
    FRONTMATTER_WORKER_PROMPT,
    PREPEND_TRANSLATION_WORKER_SYSTEM,
    PREPEND_TRANSLATION_WORKER_PROMPT,
    PREPEND_TRANSLATION_CRITIC_SYSTEM,
    PREPEND_TRANSLATION_CRITIC_PROMPT,
)
from turtletranslate.parameters import DEFAULT_OPTIONS, STRICT, LENIENT, CREATIVE  # noqa: F401

TRANSLATE_TYPES = {
    # Critics
    "translation_critic_wildcard": (
        TRANSLATION_CRITIC_WILDCARD_SYSTEM,
        TRANSLATION_CRITIC_WILDCARD_PROMPT,
        LENIENT,
    ),
    "translation_critic_codefence": (
        TRANSLATION_CRITIC_CODEFENCE_SYSTEM,
        TRANSLATION_CRITIC_CODEFENCE_PROMPT,
        LENIENT,
    ),
    "translation_critic_article": (
        TRANSLATION_CRITIC_ARTICLE_SYSTEM,
        TRANSLATION_CRITIC_ARTICLE_PROMPT,
        LENIENT,
    ),
    "translation_critic_blockquote": (
        TRANSLATION_CRITIC_BLOCKQUOTE_SYSTEM,
        TRANSLATION_CRITIC_BLOCKQUOTE_PROMPT,
        LENIENT,
    ),
    "summary_critic": (
        SUMMARIZER_CRITIC_SYSTEM,
        SUMMARIZER_CRITIC_PROMPT,
        CREATIVE,
    ),
    # Generic workers
    "summary_worker": (
        SUMMARIZER_WORKER_SYSTEM,
        SUMMARIZER_WORKER_PROMPT,
        STRICT,
    ),
    "frontmatter_worker": (
        FRONTMATTER_WORKER_SYSTEM,
        FRONTMATTER_WORKER_PROMPT,
        STRICT,
    ),
    # Token specific workers
    "translation_worker_wildcard": (
        TRANSLATION_WORKER_WILDCARD_SYSTEM,
        TRANSLATION_WORKER_WILDCARD_PROMPT,
        STRICT,
    ),
    "translation_worker_codefence": (
        TRANSLATION_WORKER_CODEFENCE_SYSTEM,
        TRANSLATION_WORKER_CODEFENCE_PROMPT,
        STRICT,
    ),
    "translation_worker_article": (
        TRANSLATION_WORKER_ARTICLE_SYSTEM,
        TRANSLATION_WORKER_ARTICLE_PROMPT,
        STRICT,
    ),
    "translation_worker_blockquote": (
        TRANSLATION_WORKER_BLOCKQUOTE_SYSTEM,
        TRANSLATION_WORKER_BLOCKQUOTE_PROMPT,
        STRICT,
    ),
    "translation_critic_prepend": (
        PREPEND_TRANSLATION_CRITIC_SYSTEM,
        PREPEND_TRANSLATION_CRITIC_PROMPT,
        CREATIVE,
    ),
    "translation_worker_prepend": (
        PREPEND_TRANSLATION_WORKER_SYSTEM,
        PREPEND_TRANSLATION_WORKER_PROMPT,
        STRICT,
    ),
}


SUMMARY_CACHE = dict()  # Cache for summaries, to avoid re-generating them


@lru_cache
def _download_model_if_not_exists(client: ollama.Client, model: str):
    """Issues a pull command to the Ollama API if the model does not exist."""
    logger.info(f"Checking if model {model} is installed")
    try:
        client.show(model)
        logger.info(f"{model} is installed! Proceeding")
    except ollama.ResponseError:
        logger.info(f"{model} was not installed. Downloading...")
        client.pull(model)
        logger.info(f"Downloaded {model}")


def _prompt(data, type: str, review: str = "") -> ollama.GenerateResponse:
    """Prompt the Ollama API with the correct system and prompt for the given type (ENUM)."""
    system = TRANSLATE_TYPES[type][0].format(**data.format())
    prompt = TRANSLATE_TYPES[type][1].format(**data.format())
    opts = TRANSLATE_TYPES[type][2]
    _download_model_if_not_exists(data.client, data.model)

    logger.debug("Prompt: " + prompt.replace("\n", "\\n").replace("\t", "\\t"))
    logger.debug("System: " + system.replace("\n", "\\n").replace("\t", "\\t"))

    logger.debug("Querying Ollama")
    time = timeit.default_timer()
    options = {
        "num_ctx": data.num_ctx,
        **opts,
    }
    response = data.client.generate(model=data.model, prompt=prompt, system=system, options=options)
    logger.debug(f"Responded in {timeit.default_timer() - time:.2f}s")
    logger.debug(f"Response: {response.response}")
    return response


@lru_cache
def hash_document(document: str, num_ctx: int) -> str:
    """A simple hash function to hash the document and the number of context tokens, for caching purposes."""
    return hashlib.sha256(f"{document}-{num_ctx}".encode()).hexdigest()


def _approve_summary(data) -> bool:
    """Approve the summary, or retry if it does not meet the criteria."""
    if not data.review:
        return True
    logger.info("Reviewing summary")
    text = _prompt(data, "summary_critic").response

    if text.lower().strip().startswith("yes"):
        data._critique = ""
        return True
    data._critique = text
    logger.error(f"Summary did not meet the criteria. Reason: {text}")


def _generate_summary(data, _attempts: int = 0) -> str:
    """Internal function to generate a summary, with a maximum number of attempts."""
    if _attempts >= data._max_attempts:
        logger.error(f"Could not generate summary after {_attempts} attempts.")
        raise TurtleTranslateException(f"Could not generate summary after {_attempts} attempts.")

    attempt_txt = f"\033[34m(Attempt {_attempts + 1}/{data._max_attempts})\033[0m"
    logger.info(f"Generating summary. {attempt_txt}")

    data._summary = _prompt(data, "summary_worker").response.rstrip()

    if not _approve_summary(data):
        return _generate_summary(data, _attempts + 1)
    logger.info("Summary generated successfully!")
    return data._summary


def generate_summary(data) -> str:
    """Generate a summary of the document in order to give some context to the translator, then cache it."""
    if hash_document(data.document, data.num_ctx) in SUMMARY_CACHE:
        logger.debug("Using cached summary")
        return SUMMARY_CACHE[hash_document(data.document, data.num_ctx)]
    summary = _generate_summary(data)
    SUMMARY_CACHE[hash_document(data.document, data.num_ctx)] = summary
    return summary


def _approve_translation(data, token) -> bool:
    """Approve the translation, or retry if it does not meet the criteria."""
    if not data.review:
        return True
    logger.debug("Reviewing translation")
    text = _prompt(data, f"translation_critic_{token}").response

    if text.lower().strip().startswith("yes") or "no" not in text.lower().split():
        data._critique = ""
        return True
    data._critique = text
    logger.error(f"Translation did not meet the criteria. Reason: {text}")


def _translate_section(data, _attempts: int = 0, _current_section: int = 1) -> dict[str, str]:
    """Internal function to translate a section, with a maximum number of attempts."""
    if _attempts >= data._max_attempts:
        logger.error(f"Could not translate section after {_attempts} attempts.")
        raise TurtleTranslateException(f"Could not translate section after {_attempts} attempts.")
    # Extract the token and section for the prompt only
    original_section = data._section.copy()
    token, section = list(data._section.items())[0]

    section_txt = f"\033[33m(Section {_current_section}/{len(data._sections)})\033[0m"
    attempt_txt = f"\033[34m(Attempt {_attempts + 1}/{data._max_attempts})\033[0m"
    type_txt = f"\033[35m(Type: {token})\033[0m"
    logger.info(f"Translating... {section_txt} {attempt_txt} {type_txt}")

    data._section = section
    translated_section = _prompt(data, f"translation_worker_{token}").response.rstrip()
    data._translated_section = translated_section

    if not _approve_translation(data, token):
        data._section = original_section
        return _translate_section(data, _attempts + 1, _current_section=_current_section)

    logger.debug("Section translated successfully!")
    data._translated_section = {token: translated_section}
    return data._translated_section


def translate_sections(data) -> list[dict[str, str]]:
    """Translate all sections in the document, one by one"""
    data._translated_sections = []
    for i, section in enumerate(data._sections):
        data._section = section
        data._translated_sections.append(_translate_section(data, _current_section=i + 1))

    return data._translated_sections


def extrapolate_json(text: str) -> dict:
    """Extract the JSON from a string with some leniency."""
    text = text.encode("unicode_escape").decode("utf-8").replace("\\r", "\r").replace("\\n", "\n").replace("\\t", "\t")
    text = "{" + text.split("{", 1)[1].rsplit("}", 1)[0] + "}"
    # For every line, check if it has more than 4 double quotes, if yes, replace every the 3 to -1 double quotes with a \"
    new_text = ""
    for line in text.split("\n"):
        if not line.strip().startswith('"') or (not line.strip().endswith('"') and not line.strip().endswith('",')):
            new_text += f"{line}\n"
            continue
        if line.count('"') == 4:
            new_text += f"{line}\n"
            continue
        try:
            leading, key, value, trailing = re.search(r'^(\s*)(".*?"):\s*"(.*)"(.*)', line).groups()
        except AttributeError:
            logger.error(f"Couldn't parse JSON from {text}")
            raise SyntaxError(f"Couldn't parse JSON from {text}")
        value = value.replace('"', '\\"')
        new_text += f'{leading}{key}: "{value}"{trailing}\n'
    return ast.literal_eval(new_text)


def translate_frontmatter(data, _attempts: int = 0) -> dict:
    """Translate the relevant frontmatter keys (TRANSLATABLE_FRONTMATTER_KEYS) in the frontmatter."""
    if not data.frontmatter:
        logger.debug("No frontmatter to translate")
        return dict()
    if _attempts >= data._max_attempts:
        logger.error(f"Could not translate frontmatter after {_attempts} attempts.")
        raise TurtleTranslateException(f"Could not translate frontmatter after {_attempts} attempts.")
    attempt_txt = f"\033[34m(Attempt {_attempts + 1}/{data._max_attempts})\033[0m"
    logger.info(f"Translating frontmatter. {attempt_txt}")
    try:
        new_fm = extrapolate_json(_prompt(data, "frontmatter_worker").response)
        data.translated_frontmatter = new_fm
        for key in new_fm.keys():
            if key not in data.frontmatter.keys():
                logger.error(
                    f"Translated frontmatter key {key} does not exist in original frontmatter (AI Hallucination)"
                )
                return translate_frontmatter(data, _attempts + 1)
    except (json.JSONDecodeError, SyntaxError):
        logger.error("Failed to decode JSON response")
        return translate_frontmatter(data, _attempts + 1)

    # TODO: Reviewing the frontmatter translation, might not be necessary
    return data.translated_frontmatter


def translate(data) -> str:
    """The only function you need to call to translate a document, with a TurtleTranslateData object as input."""
    logger.info(f"Translating document from {data.source_language} to {data.target_language}")
    _download_model_if_not_exists(data.client, data.model)
    time = timeit.default_timer()
    # generate_summary(data)
    translate_frontmatter(data)
    translate_sections(data)
    logger.info("Successfully translated document!")
    logger.debug(f"Translation took {timeit.default_timer() - time:.2f}s")
    return data.reconstruct_translated_document()
