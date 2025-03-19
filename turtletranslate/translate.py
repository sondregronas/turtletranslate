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
    TRANSLATION_CRITIC_PROMPT,
    TRANSLATION_CRITIC_SYSTEM,
    TRANSLATION_WORKER_PROMPT,
    TRANSLATION_WORKER_SYSTEM,
    FRONTMATTER_TRANSLATION_WORKER_PROMPT,
)

TRANSLATE_TYPES = {
    "summary_critic": (SUMMARIZER_CRITIC_SYSTEM, SUMMARIZER_CRITIC_PROMPT),
    "summary_worker": (SUMMARIZER_WORKER_SYSTEM, SUMMARIZER_WORKER_PROMPT),
    "translation_critic": (TRANSLATION_CRITIC_SYSTEM, TRANSLATION_CRITIC_PROMPT),
    "translation_worker": (TRANSLATION_WORKER_SYSTEM, TRANSLATION_WORKER_PROMPT),
    "frontmatter_worker": (TRANSLATION_WORKER_SYSTEM, FRONTMATTER_TRANSLATION_WORKER_PROMPT),
}

DEFAULT_OPTIONS = {
    "temperature": 0.2,  # Lower temperature for more deterministic results, default 0.8
    "top_k": 10,  # Lower = conservative sampling, default 40
    "top_p": 0.3,  # Lower = conservative sampling, default 0.9
    "repeat_last_n": -1,  # -1 = uses context size, 0 = disabled, default 64
}

SUMMARY_CACHE = dict()  # Cache for summaries, to avoid re-generating them


@lru_cache
def _download_model_if_not_exists(client: ollama.Client, model: str):
    """Issues a pull command to the Ollama API if the model does not exist."""
    logger.info(f"Checking if model {model} exists")
    try:
        client.show(model)
        logger.info(f"{model} exists! Proceeding")
    except ollama.ResponseError:
        logger.info(f"{model} did not exist, downloading")
        client.pull(model)
        logger.info(f"Downloaded {model}")


def _prompt(data, type: str) -> ollama.GenerateResponse:
    """Prompt the Ollama API with the correct system and prompt for the given type (ENUM)."""
    system = TRANSLATE_TYPES[type][0].format(**data.format())
    prompt = TRANSLATE_TYPES[type][1].format(**data.format())
    _download_model_if_not_exists(data.client, data.model)

    logger.debug("Querying Ollama")
    time = timeit.default_timer()
    options = {
        "num_ctx": data.num_ctx,
        **DEFAULT_OPTIONS,
    }
    response = data.client.generate(model=data.model, prompt=prompt, system=system, options=options)
    logger.debug(f"Responded in {timeit.default_timer() - time:.2f}s")
    logger.debug(f"Response: {response.response}")
    return response


def _approve_summary(data) -> bool:
    """Approve the summary, or retry if it does not meet the criteria."""
    logger.info("Reviewing summary")
    text = _prompt(data, "summary_critic").response

    if text.lower().strip() == "yes":
        return True
    logger.error(f"Summary did not meet the criteria. Reason: {text}")


@lru_cache
def hash_document(document: str, num_ctx: int) -> str:
    """A simple hash function to hash the document and the number of context tokens, for caching purposes."""
    return hashlib.sha256(f"{document}-{num_ctx}".encode()).hexdigest()


def _generate_summary(data, _attempts: int = 0) -> str:
    """Internal function to generate a summary, with a maximum number of attempts."""
    if _attempts >= data._max_attempts:
        logger.error(f"Could not generate summary after {_attempts} attempts.")
        raise TurtleTranslateException(f"Could not generate summary after {_attempts} attempts.")
    logger.info(f"Generating summary, attempt {_attempts + 1}")

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


def _approve_translation(data) -> bool:
    """Approve the translation, or retry if it does not meet the criteria."""
    logger.info("Reviewing translation")
    text = _prompt(data, "translation_critic").response

    if text.lower().strip() == "yes" or "no" not in text.lower().split():
        return True
    logger.error(f"Translation did not meet the criteria. Reason: {text}")


def _translate_section(data, _attempts: int = 0) -> str:
    """Internal function to translate a section, with a maximum number of attempts."""
    if _attempts >= data._max_attempts:
        logger.error(f"Could not translate section after {_attempts} attempts.")
        raise TurtleTranslateException(f"Could not translate section after {_attempts} attempts.")
    logger.info(f"Translating section, attempt {_attempts + 1}")

    data._translated_section = _prompt(data, "translation_worker").response

    if not _approve_translation(data):
        return _translate_section(data, _attempts + 1)

    logger.info("Section translated successfully!")
    return data._translated_section


def translate_sections(data) -> list[str]:
    """Translate all sections in the document, one by one"""
    logger.info("Translating sections")
    data._translated_sections = []
    for section in data._sections:
        data._section = section
        data._translated_sections.append(_translate_section(data))

    return data._translated_sections


def extrapolate_json(text: str) -> dict:
    """Extract the JSON from a string with some leniency."""
    text = "{" + text.split("{", 1)[1].rsplit("}", 1)[0] + "}"
    return json.loads(text)


def translate_frontmatter(data, _attempts: int = 0) -> dict:
    """Translate the relevant frontmatter keys (TRANSLATABLE_FRONTMATTER_KEYS) in the frontmatter."""
    if _attempts >= data._max_attempts:
        logger.error(f"Could not translate frontmatter after {_attempts} attempts.")
        raise TurtleTranslateException(f"Could not translate frontmatter after {_attempts} attempts.")
    logger.info("Translating frontmatter")
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
    time = timeit.default_timer()
    generate_summary(data)
    translate_frontmatter(data)
    translate_sections(data)
    logger.info("Successfully translated document!")
    logger.debug(f"Translation took {timeit.default_timer() - time:.2f}s")
    return data.reconstruct_translated_document()
