import os
from logging import DEBUG
from pathlib import Path

import ollama
from dotenv import load_dotenv

from turtletranslate import TurtleTranslator
from turtletranslate.exceptions import TurtleTranslateException
from turtletranslate.logger import logger

load_dotenv()
client = ollama.Client(os.getenv("OLLAMA_SERVER", "127.0.0.1"))
prepend_md = """> [!NOTE] Dette er en AI generert oversettelse som kan inneholde feil eller mangler.\n"""
languages = ["English"]
models = [
    "llama3.2",
    "llama3.1",
    "mistral",
    "gemma:7b",
    "phi4",
]
logger.setLevel(DEBUG)


def translate(model, document):
    logger.info(f"Translating {document}")
    with open(document, "r", encoding="utf-8") as f:
        md = f.read()

    data = TurtleTranslator(
        client=client,
        model=model,
        document=md,
        source_language="Norwegian",
        target_language="English",
        prepend_md=prepend_md,
    )

    os.makedirs(Path(__file__).parent / "translated", exist_ok=True)
    for language in languages:
        data.target_language = language
        translated_document = data.translate()
        filename = document.stem
        with open(
            Path(__file__).parent / "translated" / f"{filename}_{model.replace(':','-')}_{language}.md",
            "w+",
            encoding="utf-8",
        ) as f:
            f.write(translated_document)

    logger.info("Translation complete!")
    logger.info(f"Summary generated: {data._summary}")


DNF = []
TIME_TO_COMPLETE = []
import timeit

for model in models:
    for document in Path(Path(__file__).parent / "docs").glob("*.md"):
        try:
            start = timeit.default_timer()
            translate(model, document)
            TIME_TO_COMPLETE.append((model, document, timeit.default_timer() - start))
        except (Exception, TurtleTranslateException) as e:
            logger.error(f"{model} DID NOT FINISH ({document}): {e}")
            DNF.append((model, document))
            continue

for model, document in DNF:
    logger.info(f"Did not finish ({model}, {document})")

for model, document, time in TIME_TO_COMPLETE:
    logger.info(f"Finished {model} in {time} seconds ({document})")
