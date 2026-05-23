DEFAULT_OPTIONS = {
    "num_batch": 512,
    "num_thread": 16,
    "temperature": 0.85,
    "top_k": 64,
    "top_p": 0.95,
    "min_p": 0.0,
    "repeat_penalty": 1.12,
    "repeat_last_n": 256,
}

STRICT = {
    **DEFAULT_OPTIONS,
    "temperature": 0.55,
    "top_p": 0.9,
    "min_p": 0.0,
    "repeat_penalty": 1.18,
    "repeat_last_n": 256,
}

LENIENT = {
    **DEFAULT_OPTIONS,
    "temperature": 0.8,
    "top_p": 0.95,
    "min_p": 0.0,
    "repeat_penalty": 1.1,
    "repeat_last_n": 256,
}

CREATIVE = {
    **DEFAULT_OPTIONS,
    "temperature": 0.95,
    "top_p": 0.97,
    "min_p": 0.0,
    "repeat_penalty": 1.08,
    "repeat_last_n": 192,
}

CODING = {
    **DEFAULT_OPTIONS,
    "temperature": 0.65,
    "top_p": 0.95,
    "min_p": 0.0,
    "repeat_penalty": 1.15,
    "repeat_last_n": 256,
}
