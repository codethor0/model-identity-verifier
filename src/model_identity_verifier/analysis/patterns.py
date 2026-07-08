"""Known model identity strings for detection."""

# Strong model-family aliases used for self-identity detection.
STRONG_MODEL_ALIASES: dict[str, list[str]] = {
    "chatgpt": [
        "chatgpt",
        "gpt",
        "gpt-4",
        "gpt-4o",
        "gpt-4.1",
        "gpt-3.5",
        "openai assistant",
    ],
    "claude": ["claude", "claude sonnet", "claude opus", "anthropic claude"],
    "gemini": ["gemini", "gemini pro", "google gemini"],
    "deepseek": ["deepseek", "deepseek chat", "deepseek r1"],
    "llama": ["llama", "llama 3", "llama 3.1", "meta llama"],
    "grok": ["grok", "xai grok"],
    "mistral": ["mistral", "mistral large"],
    "qwen": ["qwen", "alibaba qwen", "tongyi"],
    "kimi": ["kimi", "moonshot kimi"],
}

# Weak company aliases — only count in developer/provider-claim context.
COMPANY_ALIASES: dict[str, str] = {
    "openai": "chatgpt",
    "anthropic": "claude",
    "google": "gemini",
    "meta": "llama",
    "xai": "grok",
    "mistral ai": "mistral",
    "alibaba": "qwen",
    "moonshot": "kimi",
}

# Backwards-compatible alias for existing imports.
KNOWN_IDENTITIES = STRONG_MODEL_ALIASES

IDENTITY_ALIASES: dict[str, str] = {
    "chatgpt": "chatgpt",
    "gpt": "chatgpt",
    "gpt-4": "chatgpt",
    "gpt-4o": "chatgpt",
    "gpt-4.1": "chatgpt",
    "gpt-3.5": "chatgpt",
    "openai assistant": "chatgpt",
    "openai": "chatgpt",
    "claude": "claude",
    "claude sonnet": "claude",
    "claude opus": "claude",
    "anthropic claude": "claude",
    "anthropic": "claude",
    "deepseek": "deepseek",
    "deepseek chat": "deepseek",
    "deepseek r1": "deepseek",
    "gemini": "gemini",
    "gemini pro": "gemini",
    "google gemini": "gemini",
    "google": "gemini",
    "llama": "llama",
    "llama 3": "llama",
    "llama 3.1": "llama",
    "meta llama": "llama",
    "meta": "llama",
    "grok": "grok",
    "xai grok": "grok",
    "xai": "grok",
    "mistral": "mistral",
    "mistral large": "mistral",
    "mistral ai": "mistral",
    "qwen": "qwen",
    "alibaba qwen": "qwen",
    "alibaba": "qwen",
    "tongyi": "qwen",
    "kimi": "kimi",
    "moonshot kimi": "kimi",
    "moonshot": "kimi",
}

MODEL_NAME_ALIASES: dict[str, list[str]] = {
    "gpt-4o-mini": ["gpt-4o", "gpt-4o-mini", "gpt-4"],
    "gpt-4o": ["gpt-4o", "gpt-4o-mini", "gpt-4"],
    "claude-3-5-sonnet-20241022": ["claude-3-5-sonnet", "claude-3-5-sonnet-20241022"],
}

NEGATION_PATTERNS: list[str] = [
    r"\bnot\b",
    r"\bno\b",
    r"\bnot actually\b",
    r"\bnot really\b",
    r"\bneither\b",
    r"\bnor\b",
    r"\bnever\b",
    r"\bn't\b",
    r"不是",
    r"我不是",
    r"并不是",
    r"ではありません",
    r"じゃない",
    r"ではない",
    r"아닙니다",
    r"아니",
    r"ne suis pas",
    r"je ne suis pas",
    r"\bpas\b",
    r"no soy",
    r"no es",
    r"ich bin nicht",
    r"\bnicht\b",
    r"não sou",
    r"nao sou",
    r"não é",
    r"nao e",
    r"non sono",
    r"non è",
    r"я не",
    r"\bне\b",
    r"لست",
    r"ليس",
    r"ليست",
    r"मैं नहीं",
    r"नहीं",
]

QUOTE_INDICATORS: list[str] = [
    r"the prompt said",
    r"you asked",
    r"user asked",
    r"the sentence",
    r"an example",
    r"for example",
    r"in this story",
    r"in the story",
    r"hypothetically",
    r"if i were",
    r"quoted",
    r"\"",
    r"'",
    r"「",
    r"」",
]

FICTION_INDICATORS: list[str] = [
    r"\bpretend\b",
    r"\broleplay\b",
    r"in this story",
    r"in a story",
    r"fictional",
    r"character says",
    r"the ai says",
    r"imagine",
    r"hypothetically",
]

TRANSLATION_INDICATORS: list[str] = [
    r"\btranslate\b",
    r"\btranslation\b",
    r"\btranslating\b",
    r"翻译",
    r"訳",
]

AFFIRM_PATTERNS: list[str] = [
    r"\bi am\b",
    r"\bi'm\b",
    r"\bmy name is\b",
    r"我是",
    r"我叫",
    r"私は",
    r"je suis",
    r"soy\s+",
    r"ich bin\s+",
    r"sou\s+",
    r"저는",
    r"나는",
    r"أنا",
    r"मैं",
    r"я\s+",
    r"sono\s+",
]

DEVELOPER_CLAIM_PATTERNS: list[str] = [
    r"\bi was developed by\b",
    r"\bi was created by\b",
    r"\bi was built by\b",
    r"\bi am developed by\b",
    r"\bi am created by\b",
    r"\bi am built by\b",
]

THIRD_PARTY_MENTION_PATTERNS: list[str] = [
    r"\bmakes\b",
    r"\bmade by\b",
    r"\bcreated\b",
    r"\bdevelops\b",
    r"\bdeveloped\b",
    r"\bproduces\b",
]
