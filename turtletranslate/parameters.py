DEFAULT_OPTIONS = {
    "temperature": 0.7,  # Low randomness for consistency but not completely deterministic
    "top_k": 40,  # Slightly conservative, but allows some variety
    "top_p": 0.9,  # Keeps sampling fairly safe
    "repeat_last_n": 64,  # Uses context size for consistency
}

STRICT = {
    "temperature": 0.3,
    "top_k": 15,
    "top_p": 0.3,
    "repeat_last_n": -1,
}

LENIENT = {
    "temperature": 0.5,
    "top_k": 25,
    "top_p": 0.5,
    "repeat_last_n": -1,
}

CREATIVE = {
    "temperature": 0.9,
    "top_k": 50,
    "top_p": 0.9,
    "repeat_last_n": -1,
}
