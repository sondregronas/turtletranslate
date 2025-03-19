# Turtle Translate [WIP]

A slow and steady way to translate markdown documents using Ollama

## Installation

```bash
pip install git+https://github.com/sondregronas/turtletranslate@main
```

## Usage

```python
import ollama
from turtletranslate import TurtleTranslator

client = ollama.Client(os.getenv("OLLAMA_SERVER", "127.0.0.1"))
prepend_md = "> This text has been automatically translated from Norwegian to English using Ollama!\n\n"
with open("document.md", "r", encoding="utf-8") as f:
    md = f.read()

data = TurtleTranslator(
    client=client, document=md, source_language="Norwegian", target_language="English", prepend_md=prepend_md
)

translated_document = data.translate()

print(translated_document)
```

## Options

```python
class TurtleTranslator:
    client: ollama.Client
    document: str
    model: str = "llama3.1"
    num_ctx: int = 16 * 1024
    source_language: str = "English"
    target_language: str = "Spanish"
    prepend_md: str = ""  # Markdown to prepend to the translated document (i.e. "> NOTE: This is a machine generated translation.")
    _max_attempts: int = 100
```