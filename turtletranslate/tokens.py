# TODO: Use enum
TOKENS = {
    "#": "article",  # Headers + content, up until a new delimiter
    ">": "blockquote",  # Blockquotes in their entirety
    "```": "codefence",  # Code fences in their entirety (not including inside blockquotes)
}
DEFAULT_TOKEN = "wildcard"
PREPEND_TOKEN = "prepend"
NO_TRANSLATE_TOKEN = "no_translate"

TOKENS_CH_LEN = max(len(token) for token in list(TOKENS.values()) + [DEFAULT_TOKEN, PREPEND_TOKEN, NO_TRANSLATE_TOKEN])
