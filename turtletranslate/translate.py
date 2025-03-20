import ast
import hashlib
import json
import timeit
from functools import lru_cache

import ollama

from turtletranslate.exceptions import TurtleTranslateException
from turtletranslate.logger import logger
from turtletranslate.models import (
    SUMMARIZER_CRITIC_PROMPT,
    SUMMARIZER_CRITIC_SYSTEM,
    SUMMARIZER_WORKER_PROMPT,
    SUMMARIZER_WORKER_SYSTEM,
    TRANSLATION_CRITIC_SYSTEM_BLOCKQUOTE,
    TRANSLATION_CRITIC_PROMPT_BLOCKQUOTE,
    TRANSLATION_CRITIC_SYSTEM_ARTICLE,
    TRANSLATION_CRITIC_PROMPT_ARTICLE,
    TRANSLATION_CRITIC_SYSTEM_CODEFENCE,
    TRANSLATION_CRITIC_PROMPT_CODEFENCE,
    TRANSLATION_CRITIC_SYSTEM_WILDCARD,
    TRANSLATION_CRITIC_PROMPT_WILDCARD,
    TRANSLATION_WORKER_SYSTEM_BLOCKQUOTE,
    TRANSLATION_WORKER_SYSTEM_ARTICLE,
    TRANSLATION_WORKER_SYSTEM_CODEFENCE,
    TRANSLATION_WORKER_SYSTEM_WILDCARD,
    TRANSLATION_WORKER_PROMPT_WILDCARD,
    TRANSLATION_WORKER_PROMPT_CODEFENCE,
    TRANSLATION_WORKER_PROMPT_ARTICLE,
    TRANSLATION_WORKER_PROMPT_BLOCKQUOTE,
    FRONTMATTER_WORKER_SYSTEM,
    FRONTMATTER_WORKER_PROMPT,
)
from turtletranslate.parameters import DEFAULT_OPTIONS, STRICT, LENIENT, CREATIVE  # noqa: F401

TRANSLATE_TYPES = {
    # Critics
    "translation_critic_wildcard": (
        TRANSLATION_CRITIC_SYSTEM_WILDCARD,
        TRANSLATION_CRITIC_PROMPT_WILDCARD,
        DEFAULT_OPTIONS,
    ),
    "translation_critic_codefence": (
        TRANSLATION_CRITIC_SYSTEM_CODEFENCE,
        TRANSLATION_CRITIC_PROMPT_CODEFENCE,
        STRICT,
    ),
    "translation_critic_article": (
        TRANSLATION_CRITIC_SYSTEM_ARTICLE,
        TRANSLATION_CRITIC_PROMPT_ARTICLE,
        DEFAULT_OPTIONS,
    ),
    "translation_critic_blockquote": (
        TRANSLATION_CRITIC_SYSTEM_BLOCKQUOTE,
        TRANSLATION_CRITIC_PROMPT_BLOCKQUOTE,
        STRICT,
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
        CREATIVE,
    ),
    "frontmatter_worker": (
        FRONTMATTER_WORKER_SYSTEM,
        FRONTMATTER_WORKER_PROMPT,
        LENIENT,
    ),
    # Token specific workers
    "translation_worker_wildcard": (
        TRANSLATION_WORKER_SYSTEM_WILDCARD,
        TRANSLATION_WORKER_PROMPT_WILDCARD,
        LENIENT,
    ),
    "translation_worker_codefence": (
        TRANSLATION_WORKER_SYSTEM_CODEFENCE,
        TRANSLATION_WORKER_PROMPT_CODEFENCE,
        LENIENT,
    ),
    "translation_worker_article": (
        TRANSLATION_WORKER_SYSTEM_ARTICLE,
        TRANSLATION_WORKER_PROMPT_ARTICLE,
        LENIENT,
    ),
    "translation_worker_blockquote": (
        TRANSLATION_WORKER_SYSTEM_BLOCKQUOTE,
        TRANSLATION_WORKER_PROMPT_BLOCKQUOTE,
        LENIENT,
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
    logger.info("Reviewing summary")
    text = _prompt(data, "summary_critic").response

    if text.lower().strip() == "yes":
        data._critique = ""
        return True
    data._critique = text
    logger.error(f"Summary did not meet the criteria. Reason: {text}")


def _generate_summary(data, _attempts: int = 0) -> str:
    """Internal function to generate a summary, with a maximum number of attempts."""
    if _attempts >= data._max_attempts:
        logger.error(f"Could not generate summary after {_attempts} attempts.")
        raise TurtleTranslateException(f"Could not generate summary after {_attempts} attempts.")
    logger.info(f"Generating summary. Attempt {_attempts + 1}/{data._max_attempts}")

    data._summary = _prompt(data, "summary_worker").response

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
    logger.debug("Reviewing translation")
    text = _prompt(data, f"translation_critic_{token}").response

    if text.lower().strip() == "yes" or "no" not in text.lower().split():
        data._critique = ""
        return True
    data._critique = text
    logger.error(f"Translation did not meet the criteria. Reason: {text}")


def _translate_section(data, _attempts: int = 0, _current_section: int = 1) -> dict[str, str]:
    """Internal function to translate a section, with a maximum number of attempts."""
    if _attempts >= data._max_attempts:
        logger.error(f"Could not translate section after {_attempts} attempts.")
        raise TurtleTranslateException(f"Could not translate section after {_attempts} attempts.")
    logger.info(
        f"Translating section ({_current_section}/{len(data._sections)}). Attempt {_attempts + 1}/{data._max_attempts}"
    )

    # Extract the token and section for the prompt only
    original_section = data._section.copy()
    token, section = list(data._section.items())[0]
    data._section = section
    translated_section = _prompt(data, f"translation_worker_{token}").response
    data._translated_section = {token: translated_section}

    if not _approve_translation(data, token):
        data._section = original_section
        return _translate_section(data, _attempts + 1)

    logger.info("Section translated successfully!")
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
    text = "{" + text.split("{", 1)[1].rsplit("}", 1)[0] + "}"
    return ast.literal_eval(text)


def translate_frontmatter(data, _attempts: int = 0) -> dict:
    """Translate the relevant frontmatter keys (TRANSLATABLE_FRONTMATTER_KEYS) in the frontmatter."""
    if _attempts >= data._max_attempts:
        logger.error(f"Could not translate frontmatter after {_attempts} attempts.")
        raise TurtleTranslateException(f"Could not translate frontmatter after {_attempts} attempts.")
    logger.info(f"Translating frontmatter. Attempt {_attempts + 1}/{data._max_attempts}")
    try:
        new_fm = extrapolate_json(_prompt(data, "frontmatter_worker").response)
        data.translated_frontmatter = new_fm
        for key in new_fm.keys():
            if key not in data.frontmatter.keys():
                logger.error(
                    f"Translated frontmatter key {key} does not exist in original frontmatter (AI Hallucination)"
                )
                return translate_frontmatter(data, _attempts + 1)
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON response")
        return translate_frontmatter(data, _attempts + 1)

    # TODO: Reviewing the frontmatter translation, might not be necessary
    return data.translated_frontmatter


def translate(data) -> str:
    """The only function you need to call to translate a document, with a TurtleTranslateData object as input."""
    logger.info(f"Translating document from {data.source_language} to {data.target_language}")
    _download_model_if_not_exists(data.client, data.model)
    time = timeit.default_timer()
    generate_summary(data)
    translate_frontmatter(data)
    translate_sections(data)
    logger.info("Successfully translated document!")
    logger.debug(f"Translation took {timeit.default_timer() - time:.2f}s")
    return data.reconstruct_translated_document()
