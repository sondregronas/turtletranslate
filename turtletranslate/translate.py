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

SUMMARY_CACHE = dict()  # Cache for summaries, to avoid re-generating them


@lru_cache
def _download_model_if_not_exists(client: ollama.Client, model: str):
    logger.info(f"Checking if model {model} exists")
    try:
        client.show(model)
    except ollama.ResponseError:
        logger.info(f"{model} did not exist, downloading")
        client.pull(model)
        logger.info(f"Downloaded {model}")


def _prompt(data, type: str) -> ollama.GenerateResponse:
    system = TRANSLATE_TYPES[type][0].format(**data.format())
    prompt = TRANSLATE_TYPES[type][1].format(**data.format())
    _download_model_if_not_exists(data.client, data.model)

    logger.debug("Querying Ollama")
    time = timeit.default_timer()
    options = {
        "num_ctx": data.num_ctx,
    }
    response = data.client.generate(model=data.model, prompt=prompt, system=system, options=options)
    logger.debug(f"Responded in {timeit.default_timer() - time:.2f}s")
    logger.debug(f"Response: {response.response}")
    return response


def approve_summary(data) -> bool:
    logger.info("Reviewing summary")
    text = _prompt(data, "summary_critic").response

    if text.lower().strip() == "yes":
        return True
    logger.error(f"Summary did not meet the criteria. Reason: {text}")


@lru_cache
def hash_document(document: str, num_ctx: int) -> str:
    return hashlib.sha256(f"{document}-{num_ctx}".encode()).hexdigest()


def _generate_summary(data, _attempts: int = 0) -> str:
    if _attempts >= data._max_attempts:
        logger.error(f"Could not generate summary after {_attempts} attempts.")
        raise TurtleTranslateException(f"Could not generate summary after {_attempts} attempts.")
    logger.info(f"Generating summary, attempt {_attempts + 1}")

    data._summary = _prompt(data, "summary_worker").response

    if not approve_summary(data):
        return _generate_summary(data, _attempts + 1)
    logger.info("Summary generated successfully!")
    return data._summary


def generate_summary(data) -> str:
    if hash_document(data.document, data.num_ctx) in SUMMARY_CACHE:
        logger.debug("Using cached summary")
        return SUMMARY_CACHE[hash_document(data.document, data.num_ctx)]
    summary = _generate_summary(data)
    SUMMARY_CACHE[hash_document(data.document, data.num_ctx)] = summary
    return summary


def approve_translation(data) -> bool:
    logger.info("Reviewing translation")
    text = _prompt(data, "translation_critic").response

    if text.lower().strip() == "yes" or "no" not in text.lower().split():
        return True
    logger.error(f"Translation did not meet the criteria. Reason: {text}")


def translate_section(data, _attempts: int = 0) -> str:
    if _attempts >= data._max_attempts:
        logger.error(f"Could not translate section after {_attempts} attempts.")
        raise TurtleTranslateException(f"Could not translate section after {_attempts} attempts.")
    logger.info(f"Translating section, attempt {_attempts + 1}")

    data._translated_section = _prompt(data, "translation_worker").response

    if not approve_translation(data):
        return translate_section(data, _attempts + 1)

    logger.info("Section translated successfully!")
    return data._translated_section


def translate_sections(data) -> list[str]:
    logger.info("Translating sections")
    data._translated_sections = []
    for section in data._sections:
        data._section = section
        data._translated_sections.append(translate_section(data))

    return data._translated_sections


def translate_frontmatter(data, _attempts: int = 0) -> dict:
    if _attempts >= data._max_attempts:
        logger.error(f"Could not translate frontmatter after {_attempts} attempts.")
        raise TurtleTranslateException(f"Could not translate frontmatter after {_attempts} attempts.")
    logger.info("Translating frontmatter")
    try:
        new_fm = json.loads(_prompt(data, "frontmatter_worker").response)
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
    return data.translated_frontmatter


def translate(data) -> str:
    logger.info(f"Translating document from {data.source_language} to {data.target_language}")
    time = timeit.default_timer()
    generate_summary(data)
    translate_frontmatter(data)
    translate_sections(data)
    logger.info("Successfully translated document!")
    logger.debug(f"Translation took {timeit.default_timer() - time:.2f}s")
    return data.reconstruct_translated_document()
