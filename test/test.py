import os
from logging import DEBUG

import ollama
from dotenv import load_dotenv

from turtletranslate import file_handler, TurtleTranslateData
from turtletranslate.logger import logger
from turtletranslate.translate import generate_summary

load_dotenv()

with open("docs/index.md", "r", encoding="utf-8") as f:
    md = f.read()

prepend_md = """
> [!NOTE] Dette er en AI generert oversettelse som kan inneholde feil og mangler.
"""

logger.setLevel(DEBUG)

frontmatter, sections = file_handler.parse(md, prepend_md=prepend_md)

client = ollama.Client(os.getenv("OLLAMA_HOST", "127.0.0.1"))
data = TurtleTranslateData(client=client, document=md, source_language="Norwegian", target_language="English")
summary = generate_summary(data)
print(summary)

# print(frontmatter)
# for s in sections:
#    print("#" * 10)
#    print(s)

# Output:
output = file_handler.reconstruct(frontmatter, sections)
# print(output)
