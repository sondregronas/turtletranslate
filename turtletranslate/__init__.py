TRANSLATABLE_FRONTMATTER_KEYS = [
    "title",
    "description",
    "summary",
]

# TODO: This is just a placeholder for now
OPTIONS = {
    "source_language": "en",
    "target_language": "es",
    "section": "<section>",
}

TRANSLATION_MODEL_FRONTMATTER = """\
You are an advanced translator, specializing in translating markdown documents from {source_language} to {target_language}.

You will translate the given values and translate them to {target_language} based on the context of the document you translated prior.
"""
TRANSLATION_MODEL_SECTION = """\
You are an advanced translator, specializing in translating markdown documents from {source_language} to {target_language}.

You will be given a single section to translate at a time, and you must only translate the content within the section.
"""

CRITIC_MODEL = """\
You are a translation teacher, specializing in critiquing translations from {source_language} to {target_language}.


"""

CRITIC_PROMPT = """\
You must only reply with a "YES" or "NO <Explanation>" to the following questions:

1. Is the translation accurate?
2. Is the translation natural?
3. Is the markdown syntax correct?
4. Are special symbols preserved?
5. Are the code blocks formatted correctly?
6. Are the comments inside the code blocks translated?
7. Is the code inside code blocks still in the original language?

If you answer "NO" to any of the questions, you must provide an explanation for why you answered "NO".

Here is the section you must critique, translated from {source_language} to {target_language}, which is only a small part of the entire document.

--- SECTION START ---
{section}
--- SECTION END ---
"""
