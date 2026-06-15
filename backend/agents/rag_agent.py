"""
Maintenance Wizard — RAG Agent
Uses Gemini 1.5 Flash + ChromaDB vector search to answer
maintenance queries grounded in equipment documentation.
"""
import os
import sys
from typing import Optional
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from knowledge_base.vector_store import VectorStore

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", 5))

SYSTEM_PROMPT = """You are the Maintenance Wizard, an expert AI assistant specialized in industrial equipment maintenance for Tata Steel's steel manufacturing plants.

You have deep knowledge of:
- Blast furnaces, rolling mills, pumps, compressors, and conveyor systems
- Fault diagnosis, root cause analysis, and predictive maintenance
- Safety procedures and maintenance SOPs
- Spare parts management and procurement

Your responses must be:
1. Technically precise and practical
2. Structured with clear sections when appropriate
3. Grounded in the provided context documents
4. Explainable — cite sources when making recommendations
5. Safety-conscious — always mention safety precautions for critical issues

When asked about equipment issues, always provide:
- Probable cause(s)
- Immediate action required
- Long-term maintenance recommendation
- Risk assessment (Low/Medium/High/Critical)
"""


class RAGAgent:
    """
    Retrieval-Augmented Generation agent.
    Embeds user query → retrieves relevant docs from ChromaDB → sends to Gemini with context.
    """

    def __init__(self):
        self.vector_store = VectorStore()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "your_gemini_api_key_here":
            raise ValueError(
                "GEMINI_API_KEY not set. Add it to backend/.env file.\n"
                "Get your free key at: https://aistudio.google.com/app/apikey"
            )
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
        )
        self.chat_sessions: dict[str, genai.ChatSession] = {}

    def _get_or_create_session(self, session_id: str) -> genai.ChatSession:
        if session_id not in self.chat_sessions:
            self.chat_sessions[session_id] = self.model.start_chat(history=[])
        return self.chat_sessions[session_id]

    def answer(
        self,
        query: str,
        session_id: str = "default",
        equipment_context: Optional[dict] = None,
    ) -> dict:
        """
        Answer a maintenance query using RAG.
        Returns: {answer, sources, context_used, tokens_used}
        """
        try:
            # 1. Retrieve relevant document chunks
            retrieved = self.vector_store.search(query, top_k=RAG_TOP_K)

            # 2. Build context string
            context_parts = []
            sources = []
            for i, chunk in enumerate(retrieved):
                context_parts.append(
                    f"[Source {i+1}: {chunk['source']}]\n{chunk['text']}"
                )
                if chunk["source"] not in sources:
                    sources.append(chunk["source"])

            context_str = "\n\n---\n\n".join(context_parts) if context_parts else "No specific documentation found."

            # 3. Add live equipment context if provided
            equipment_str = ""
            if equipment_context:
                equipment_str = f"""
## Current Equipment Status
- Equipment ID: {equipment_context.get('equipment_id', 'N/A')}
- Equipment Type: {equipment_context.get('equipment_type', 'N/A')}
- Temperature: {equipment_context.get('temperature_c', 'N/A')}°C
- Vibration: {equipment_context.get('vibration_mm_s', 'N/A')} mm/s
- Pressure: {equipment_context.get('pressure_bar', 'N/A')} bar
- Current: {equipment_context.get('current_amp', 'N/A')} A
- RPM: {equipment_context.get('rpm', 'N/A')}
- Oil Level: {equipment_context.get('oil_level_pct', 'N/A')}%
- Active Fault Code: {equipment_context.get('fault_code', 'None')}
"""

            # 4. Compose full prompt
            full_prompt = f"""## Reference Documentation
{context_str}
{equipment_str}

## Engineer's Query
{query}

Please provide a comprehensive, actionable response based on the above context and your expertise."""

            # 5. Multi-turn chat
            session = self._get_or_create_session(session_id)
            response = session.send_message(full_prompt)

            return {
                "answer": response.text,
                "sources": sources,
                "context_chunks": len(retrieved),
                "session_id": session_id,
                "model": GEMINI_MODEL,
                "success": True,
            }

        except Exception as e:
            return {
                "answer": f"I encountered an error while processing your query: {str(e)}. Please check your GEMINI_API_KEY in the .env file.",
                "sources": [],
                "context_chunks": 0,
                "session_id": session_id,
                "success": False,
                "error": str(e),
            }

    def reset_session(self, session_id: str):
        """Clear conversation history for a session."""
        if session_id in self.chat_sessions:
            del self.chat_sessions[session_id]

    def get_session_ids(self) -> list:
        return list(self.chat_sessions.keys())
