import json
import os

SETTINGS_FILE = "./settings_llm.json"

_DEFAULTS = {
    "LLM_PROVIDER": "gemini",
    "GEMINI_API_KEY": "",
    "GEMINI_MODEL": "gemini-2.5-flash",
    "CLAUDE_API_KEY": "",
    "CLAUDE_MODEL": "claude-sonnet-5",
    "INGESTION_PROVIDER": "langchain",
    "LLAMAPARSE_API_KEY": "",
}


def load() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        from dotenv import load_dotenv
        load_dotenv()
        settings = {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
            "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            "CLAUDE_API_KEY": "",
            "CLAUDE_MODEL": "claude-sonnet-5",
            "INGESTION_PROVIDER": os.getenv("INGESTION_PROVIDER", "langchain"),
            "LLAMAPARSE_API_KEY": os.getenv("LLAMAPARSE_API_KEY", ""),
        }
        save(settings)
        return settings

    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        settings = json.load(f)

    # Migrate: add any missing keys introduced in later versions
    changed = False
    for key, default in _DEFAULTS.items():
        if key not in settings:
            settings[key] = default
            changed = True
    if changed:
        save(settings)

    return settings


def save(settings: dict) -> None:
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
