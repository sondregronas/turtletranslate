import itertools
import os
import timeit
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

languages = [
    "English",
    "Spanish",
]
models = [
    "llama3.1",
    "llama3.2",
    "mistral",
    "gemma:7b",
    "phi4",
]
context_sizes = [
    4 * 1024,
    8 * 1024,
    16 * 1024,
    32 * 1024,
    64 * 1024,
]

logger.setLevel(DEBUG)


def translate(model, file, context_size):
    logger.info(f"Translating {file}")
    with open(file, "r", encoding="utf-8") as f:
        md = f.read()

    data = TurtleTranslator(
        client=client,
        model=model,
        document=md,
        source_language="Norwegian",
        target_language="English",
        prepend_md=prepend_md,
        num_ctx=context_size,
    )

    os.makedirs(Path(__file__).parent / "translated", exist_ok=True)
    for language in languages:
        data.target_language = language
        start = timeit.default_timer()
        translated_document = data.translate()
        end = timeit.default_timer()
        translated_document = translated_document.replace("---", f"---\ntime_to_translate: {end - start:.2f}s", 1)
        filename = file.stem
        with open(
            Path(__file__).parent / "translated" / f"{filename}_{model.replace(':','-')}_{language}_{context_size}.md",
            "w+",
            encoding="utf-8",
        ) as f:
            f.write(translated_document)

    logger.info("Translation complete!")
    logger.info(f"Summary generated: {data._summary}")


DNF = []
TIME_TO_COMPLETE = []


files = Path(Path(__file__).parent / "docs").glob("*.md")
for model, file, context_size in itertools.product(
    models,
    files,
    context_sizes,
):
    try:
        start = timeit.default_timer()
        translate(model, file, context_size)
        TIME_TO_COMPLETE.append((model, file, timeit.default_timer() - start))
    except TurtleTranslateException as e:
        logger.error(f"{model} DID NOT FINISH ({file}): {e}")
        DNF.append((model, file))
        continue

for model, document in DNF:
    logger.info(f"Did not finish ({model}, {document})")

for model, document, time in TIME_TO_COMPLETE:
    logger.info(f"Finished {model} in {time} seconds ({document})")
