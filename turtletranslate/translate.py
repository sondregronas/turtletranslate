import timeit
from functools import lru_cache

import ollama

from turtletranslate import TurtleTranslateData, TurtleTranslateException
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
)

TRANSLATE_TYPES = {
    "summary_critic": (SUMMARIZER_CRITIC_SYSTEM, SUMMARIZER_CRITIC_PROMPT),
    "summary_worker": (SUMMARIZER_WORKER_SYSTEM, SUMMARIZER_WORKER_PROMPT),
    "translation_critic": (TRANSLATION_CRITIC_SYSTEM, TRANSLATION_CRITIC_PROMPT),
    "translation_worker": (TRANSLATION_WORKER_SYSTEM, TRANSLATION_WORKER_PROMPT),
}


@lru_cache
def _download_model_if_not_exists(client: ollama.Client, model: str):
    logger.info(f"Checking if model {model} exists")
    try:
        client.show(model)
    except ollama.ResponseError:
        logger.info(f"Downloading {model}")
        client.pull(model)
        logger.info(f"Downloaded {model}")


def _prompt(data: TurtleTranslateData, type: str) -> ollama.GenerateResponse:
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


def approve_summary(data: TurtleTranslateData) -> bool:
    logger.info("Reviewing summary")
    text = _prompt(data, "summary_critic").response

    if text.lower().strip() == "yes":
        return True
    logger.error(f"Summary did not meet the criteria. Reason: {text}")


def generate_summary(data: TurtleTranslateData, _attempts: int = 0) -> str:
    if _attempts >= data._max_attempts:
        logger.error(f"Could not generate summary after {_attempts} attempts.")
        raise TurtleTranslateException(f"Could not generate summary after {_attempts} attempts.")
    logger.info(f"Generating summary, attempt {_attempts + 1}")

    data._summary = _prompt(data, "summary_worker").response

    if not approve_summary(data):
        return generate_summary(data, _attempts + 1)

    logger.info("Summary generated successfully!")
    return data._summary


def approve_translation(data: TurtleTranslateData) -> bool:
    logger.info("Reviewing translation")
    text = _prompt(data, "translation_critic").response

    if text.lower().strip() == "yes" or not "no" in text.lower().split():
        return True
    logger.error(f"Translation did not meet the criteria. Reason: {text}")


def translate_section(data: TurtleTranslateData, _attempts: int = 0) -> str:
    if _attempts >= data._max_attempts:
        logger.error(f"Could not translate section after {_attempts} attempts.")
        raise TurtleTranslateException(f"Could not translate section after {_attempts} attempts.")
    logger.info(f"Translating section, attempt {_attempts + 1}")

    data._section = _prompt(data, "translation_worker").response

    if not approve_translation(data):
        return translate_section(data, _attempts + 1)

    logger.info("Section translated successfully!")
    return data._section


def translate_sections(data: TurtleTranslateData) -> list[str]:
    logger.info("Translating sections")
    data._translated_sections = []
    for section in data._sections:
        data._section = section
        data._translated_sections.append(translate_section(data))

    return data._translated_sections
