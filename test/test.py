import os
from logging import DEBUG
from pathlib import Path

import ollama
from dotenv import load_dotenv

from turtletranslate import TurtleTranslator
from turtletranslate.logger import logger

load_dotenv()
client = ollama.Client(os.getenv("OLLAMA_SERVER", "127.0.0.1"))
prepend_md = """> [!NOTE] Dette er en AI generert oversettelse som kan inneholde feil eller mangler.\n"""
languages = ["English"]
logger.setLevel(DEBUG)

for document in Path("docs").rglob("*.md"):
    logger.info(f"Translating {document}")
    with open(document, "r", encoding="utf-8") as f:
        md = f.read()

    data = TurtleTranslator(
        client=client, document=md, source_language="Norwegian", target_language="English", prepend_md=prepend_md
    )

    os.makedirs(Path(__file__).parent / "translated", exist_ok=True)
    for language in languages:
        data.target_language = language
        translated_document = data.translate()
        filename = document.stem
        with open(Path(__file__).parent / "translated" / f"{filename}_{language}.md", "w", encoding="utf-8") as f:
            f.write(translated_document)

    logger.info("Translation complete!")
    logger.info(f"Summary generated: {data._summary}")
