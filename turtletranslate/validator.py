from turtletranslate.logger import logger

from turtletranslate.translate import TRANSLATE_TYPES
import timeit


def validate(data, original_content: str, translated_content: str, section_type: str) -> bool:
    """
    Validate translated content using critique models.

    Args:
        data: TurtleTranslator instance containing client, model, languages, etc.
        original_content: The original text in source language
        translated_content: The translated text
        section_type: Type of section being validated (e.g., 'paragraph', 'heading', 'code')

    Returns:
        True if validation passes, False otherwise
    """

    # TODO: We currently reuse a lot of code, consider refactoring to avoid duplication

    prompt_data = {
        "source_language": data.source_language,
        "target_language": data.target_language,
        "section": original_content,
        "translated_section": translated_content,
    }
    token = f"translation_critic_{section_type}"

    system = TRANSLATE_TYPES[token][0].format(**prompt_data)
    prompt = TRANSLATE_TYPES[token][1].format(**prompt_data)
    opts = TRANSLATE_TYPES[token][2]
    options = {
        "num_ctx": data.num_ctx,
        **opts,
    }

    logger.debug("Prompt: " + prompt.replace("\n", "\\n").replace("\t", "\\t"))
    logger.debug("System: " + system.replace("\n", "\\n").replace("\t", "\\t"))

    logger.debug("Querying Ollama")
    time = timeit.default_timer()
    response = data.client.generate(model=data.model, prompt=prompt, system=system, options=options)
    logger.debug(f"Responded in {timeit.default_timer() - time:.2f}s")
    logger.debug(f"Response: {response.response}")
    text = response.response.strip()

    return text.lower().strip().startswith("yes") or "no" not in text.lower().split()
