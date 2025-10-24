# Turtle Translate [WIP]

A slow and steady way to translate markdown documents using Ollama

> [!NOTE]
> This project is a work in progress - a lot of refactoring and improvements are needed.

## Installation

```bash
pip install git+https://github.com/sondregronas/turtletranslate@main
```

## Usage

```python
import ollama
import os
from turtletranslate import TurtleTranslator

client = ollama.Client(os.getenv("OLLAMA_SERVER", "127.0.0.1"))
prepend_md = "> This text has been automatically translated from Norwegian to English using Ollama!\n\n"
with open("document.md", "r", encoding="utf-8") as f:
    md = f.read()

turtle = TurtleTranslator(
    client=client, 
    document=md, 
    source_language="Norwegian", 
    target_language="English", 
    prepend_md=prepend_md,
    target_filename="document_en.md",
)

translated_document = turtle.translate()

print(f"Document saved to: {turtle.target_filename}")
print(translated_document)
```

## Options

```python
class TurtleTranslator:
    client: ollama.Client
    document: str
    model: str = "gemma3:27b-it-q4_K_M"
    num_ctx: int = 6 * 1024
    source_language: str = "English"
    target_language: str = "Spanish"
    prepend_md: str = ""  # Markdown to prepend to the translated document (i.e. "> NOTE: This is a machine generated translation.")
    review: bool = True  # Whether to enable the review process (critique and revision)
    wrap_in_span: bool = True  # Whether to wrap each section in a span tag with data attributes for type and index
    target_filename: str = None  # Target filename for translation output and reuse
    write_file: bool = None  # Whether to write the output to a file (defaults to True if target_filename is provided)
    add_stats: bool = True  # Whether to add translation statistics to the frontmatter
    _max_attempts: int = 100  # Maximum number of attempts to make before giving up on a translation
```