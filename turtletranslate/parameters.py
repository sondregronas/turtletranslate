DEFAULT_OPTIONS = {
    "num_batch": 512,
    "num_thread": 16,
    "temperature": 0.85,
    "top_k": 64,
    "top_p": 0.95,
    "min_p": 0.05,
    "repeat_penalty": 1.08,
    "repeat_last_n": 512,
}

STRICT = {
    **DEFAULT_OPTIONS,
    "temperature": 0.4,
    "min_p": 0.08,
    "repeat_penalty": 1.15,
    "repeat_last_n": 1024,
}

LENIENT = {
    **DEFAULT_OPTIONS,
    "temperature": 0.8,
}

CREATIVE = {
    **DEFAULT_OPTIONS,
    "temperature": 0.95,
    "top_p": 0.97,
    "min_p": 0.03,
    "repeat_penalty": 1.05,
    "repeat_last_n": 256,
}

CODING = {
    **DEFAULT_OPTIONS,
    "temperature": 0.65,
    "min_p": 0.1,
    "repeat_penalty": 1.12,
    "repeat_last_n": 1024,
}
