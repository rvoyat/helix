from typing import List, Dict

from backend.vector_store import search as vector_search

_SYSTEM_PROMPT = """Sei HELIX, l'assistente virtuale AI del gruppo Industry Enterprise - Health di Accenture, specializzato nel supporto ai team nei progetti di Delivery.

Il tuo ruolo è supportare i colleghi rispondendo a domande tecniche, metodologiche e operative basandoti ESCLUSIVAMENTE sulla documentazione ufficiale fornita nel contesto, relativa all'ambito attivamente selezionato.

Regole fondamentali:
- Rispondi SEMPRE in italiano, con tono professionale e orientato al delivery
- Basa le risposte SOLO sui documenti forniti nel contesto dell'ambito attivo
- Se l'informazione non è presente nella documentazione disponibile, dillo chiaramente e suggerisci di verificare in altri ambiti o di contattare il team di riferimento
- Struttura le risposte in modo chiaro, usando elenchi puntati o sezioni quando utile
- NON aggiungere il footer delle fonti: verrà apposto automaticamente dal sistema
"""

_FOOTER_TEMPLATE = (
    "\n\n---\n📚 **Fonti utilizzate:**\n{sources}\n"
    "Consulta la documentazione completa nella sezione Gestione Documenti."
)

_OUT_OF_SCOPE = (
    "Non ho trovato informazioni pertinenti nella documentazione dell'ambito selezionato.\n\n"
    "Ti suggerisco di:\n"
    "- Verificare se la domanda rientra in un altro ambito disponibile\n"
    "- Consultare direttamente il team di riferimento per questo argomento\n"
    "- Aggiungere la documentazione pertinente tramite la sezione Gestione Documenti"
)

_NO_SOURCE_FOOTER = "\n\n---\n📚 **Fonti utilizzate:**\nRisposta generata senza riferimento a documentazione specifica."


def _build_prompt_parts(query: str, history: List[Dict], ambito: str,
                        relevant_docs: List[Dict]) -> tuple[str, str]:
    """Returns (context_block, user_block) for use in both providers."""
    context = "\n\n".join(
        f"[{d['filename']}]\n{d['excerpt']}" for d in relevant_docs
    )
    history_text = ""
    for msg in history[-6:]:
        role = "Utente" if msg["role"] == "user" else "HELIX"
        history_text += f"{role}: {msg['content']}\n"

    user_block = (
        f"AMBITO ATTIVO: {ambito}\n\n"
        f"DOCUMENTAZIONE RILEVANTE:\n{context}\n\n"
        f"STORICO CONVERSAZIONE:\n{history_text}\n"
        f"DOMANDA ATTUALE: {query}"
    )
    return user_block


class RAGAgent:
    def __init__(self):
        pass

    def answer(self, query: str, history: List[Dict], ambito: str) -> Dict:
        from backend.llm_settings import load as _load_settings
        _s = _load_settings()

        relevant_docs = vector_search(query, ambito)
        if not relevant_docs:
            return {"response": _OUT_OF_SCOPE + _NO_SOURCE_FOOTER, "sources": []}

        user_block = _build_prompt_parts(query, history, ambito, relevant_docs)

        provider = _s.get("LLM_PROVIDER", "gemini").lower()
        try:
            if provider == "claude":
                answer_text = self._call_claude(_s, user_block)
            else:
                answer_text = self._call_gemini(_s, user_block)
        except Exception as exc:
            error_msg = str(exc)
            return {
                "response": (
                    f"⚠️ **Errore LLM ({provider.upper()}):**\n\n```\n{error_msg}\n```\n\n"
                    "Verifica la configurazione nel pannello **Admin → Parametri LLM**."
                ),
                "sources": [],
            }

        source_lines = "\n".join(f"- {d['filename']}" for d in relevant_docs)
        return {
            "response": answer_text + _FOOTER_TEMPLATE.format(sources=source_lines),
            "sources": [d["filename"] for d in relevant_docs],
        }

    def _call_gemini(self, settings: dict, user_block: str) -> str:
        import google.generativeai as genai
        api_key = settings.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("Gemini API key non configurata. Inseriscila nel pannello admin → Parametri LLM.")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(settings["GEMINI_MODEL"])
        full_prompt = f"{_SYSTEM_PROMPT}\n\n{user_block}"
        response = model.generate_content(
            full_prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=8192,
                temperature=0.3,
            ),
        )
        return response.text

    def _call_claude(self, settings: dict, user_block: str) -> str:
        import anthropic
        api_key = settings.get("CLAUDE_API_KEY", "")
        if not api_key:
            raise ValueError("Claude API key non configurata. Inseriscila nel pannello admin → Parametri LLM.")
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=settings["CLAUDE_MODEL"],
            max_tokens=8192,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_block}],
        )
        return message.content[0].text
