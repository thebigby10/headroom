"""Token counting. tiktoken when installed, chars/4 otherwise — never silent."""

try:
    import tiktoken

    _enc = tiktoken.get_encoding("cl100k_base")
    COUNTER = "tiktoken/cl100k_base"

    def count(text: str) -> int:
        return len(_enc.encode(text))
except ImportError:  # ponytail: chars/4 fallback, disclosed in every log row
    COUNTER = "chars/4-estimate"

    def count(text: str) -> int:
        return max(1, len(text) // 4)
