from typing import Dict

from agents.rag_agent import RAGAgent


class Orchestrator:
    def __init__(self):
        self.rag_agent = RAGAgent()
        self.sessions: Dict[str, Dict] = {}

    def _get_session(self, session_id: str, ambito: str) -> Dict:
        key = f"{session_id}__{ambito}"
        if key not in self.sessions:
            self.sessions[key] = {"history": []}
        return self.sessions[key]

    def process(self, message: str, session_id: str, ambito: str) -> Dict:
        session = self._get_session(session_id, ambito)
        session["history"].append({"role": "user", "content": message})

        result = self.rag_agent.answer(message, session["history"], ambito)
        session["history"].append({"role": "assistant", "content": result["response"]})

        return {
            "response": result["response"],
            "sources": result.get("sources", []),
        }
