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
    logger.debug(f"Ollama response received in {timeit.default_timer() - time:.2f}s")
    logger.debug(f"Ollama response: {response.response}")
    return response


def approve_summary(data: TurtleTranslateData) -> bool:
    logger.info("Reviewing summary")
    text = _prompt(data, "summary_critic").response

    if "no" in text.lower():
        logger.error(f"Summary did not meet the criteria. Reason: {text}")
        return False
    return True


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
