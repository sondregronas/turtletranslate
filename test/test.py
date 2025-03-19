import os
from logging import DEBUG

import ollama
from dotenv import load_dotenv

from turtletranslate import TurtleTranslateData
from turtletranslate.logger import logger

load_dotenv()

with open("docs/index.md", "r", encoding="utf-8") as f:
    md = f.read()

prepend_md = """
> [!NOTE] Dette er en AI generert oversettelse som kan inneholde feil og mangler.
"""

logger.setLevel(DEBUG)

client = ollama.Client(os.getenv("OLLAMA_HOST", "127.0.0.1"))
data = TurtleTranslateData(
    client=client, document=md, source_language="Norwegian", target_language="English", prepend_md=prepend_md
)

with open("docs/index_en.md", "w+", encoding="utf-8") as f:
    f.write(data.translate())

data.target_language = "Spanish"
with open("docs/index_es.md", "w+", encoding="utf-8") as f:
    f.write(data.translate())
