import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL       = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DOCS_FOLDER        = os.getenv("DOCS_FOLDER", "./docs")
INGESTION_PROVIDER = os.getenv("INGESTION_PROVIDER", "llamaparse")
LLAMAPARSE_API_KEY = os.getenv("LLAMAPARSE_API_KEY", "")
