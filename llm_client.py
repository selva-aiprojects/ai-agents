"""
Enterprise LLM Client Adapter for AI Agent Tool Calling.
Supports Google Gemini API, OpenAI Function Calling, and offline Standalone mode.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("LLMClient")


class LLMClient:
    """
    Unified LLM Client supporting:
      1. Google Gemini (via google.genai SDK or direct REST API)
      2. OpenAI Function Calling (OpenAI, Azure, Groq, Ollama)
      3. Standalone Offline Mode (educational heuristics fallback)
    """

    def __init__(self, provider: str = "auto", api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.provider = provider
        self.model = model

        # Auto-detect provider if not specified
        if self.provider == "auto":
            if os.environ.get("GEMINI_API_KEY") or (self.api_key and self.api_key.startswith("AIza")):
                self.provider = "gemini"
                self.model = self.model or "gemini-2.5-flash"
            elif os.environ.get("OPENAI_API_KEY") or (self.api_key and self.api_key.startswith("sk-")):
                self.provider = "openai"
                self.model = self.model or "gpt-4o-mini"
            else:
                self.provider = "standalone"

    def get_status(self) -> Dict[str, Any]:
        """Returns the current active LLM provider configuration."""
        has_key = bool(self.api_key)
        masked_key = f"{self.api_key[:6]}...{self.api_key[-4:]}" if has_key and len(self.api_key) > 10 else ("Set" if has_key else "None")
        return {
            "provider": self.provider,
            "model": self.model or ("Built-in Heuristic Engine" if self.provider == "standalone" else "Default"),
            "has_api_key": has_key,
            "masked_key": masked_key,
            "mode": "Live LLM Connected" if self.provider in ["gemini", "openai"] and has_key else "Standalone Heuristic Engine (Offline)"
        }

    def update_config(self, provider: str, api_key: Optional[str] = None, model: Optional[str] = None):
        """Dynamically update LLM provider and credentials from UI or API."""
        self.provider = provider
        if api_key is not None:
            self.api_key = api_key.strip()
            if provider == "gemini":
                os.environ["GEMINI_API_KEY"] = self.api_key
            elif provider == "openai":
                os.environ["OPENAI_API_KEY"] = self.api_key
        if model:
            self.model = model.strip()

    def format_tools_for_gemini(self, tools_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert tool schemas to Gemini function declarations."""
        declarations = []
        for name, tool in tools_dict.items():
            declarations.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            })
        return declarations

    def format_tools_for_openai(self, tools_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert tool schemas to OpenAI function calling format."""
        openai_tools = []
        for name, tool in tools_dict.items():
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })
        return openai_tools

    def generate_tool_call(
        self, 
        prompt: str, 
        tools_dict: Dict[str, Any], 
        session_history: Optional[List[Dict[str, str]]] = None
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
        """
        Queries the real LLM with function definitions.
        Returns: (tool_name, tool_args, direct_llm_response)
        """
        if self.provider == "gemini" and self.api_key:
            return self._call_gemini(prompt, tools_dict, session_history)
        elif self.provider == "openai" and self.api_key:
            return self._call_openai(prompt, tools_dict, session_history)
        
        # Standalone / Offline mode: signals caller to use rule-based intent engine
        return None, None, None

    def _call_gemini(
        self, 
        prompt: str, 
        tools_dict: Dict[str, Any], 
        session_history: Optional[List[Dict[str, str]]]
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
        """Execute Gemini API call using google.genai SDK or direct REST."""
        try:
            import urllib.request
            import urllib.error

            model_name = self.model or "gemini-2.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            
            gemini_tools = [{"function_declarations": self.format_tools_for_gemini(tools_dict)}]
            
            contents = []
            if session_history:
                for turn in session_history[-6:]:
                    contents.append({
                        "role": "user" if turn.get("role") == "user" else "model",
                        "parts": [{"text": turn.get("content", "")}]
                    })
            contents.append({"role": "user", "parts": [{"text": prompt}]})

            payload = {
                "contents": contents,
                "tools": gemini_tools,
                "system_instruction": {
                    "parts": [{
                        "text": (
                            "You are an enterprise AI Agent. You have access to tools for CRM, Database orders, "
                            "ITSM tickets, and CRM policy documents. Call the appropriate tool when asked for enterprise data. "
                            "Do not hallucinate unverified facts."
                        )
                    }]
                }
            }

            req = urllib.request.Request(
                url, 
                data=json.dumps(payload).encode("utf-8"), 
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=12) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                
                candidates = res_data.get("candidates", [])
                if not candidates:
                    return None, None, None
                
                parts = candidates[0].get("content", {}).get("parts", [])
                for p in parts:
                    if "functionCall" in p:
                        fc = p["functionCall"]
                        return fc.get("name"), fc.get("args", {}), None
                    if "text" in p:
                        return None, None, p["text"]

        except Exception as e:
            logger.warning(f"Gemini API call failed, falling back to local engine: {str(e)}")
            return None, None, None

        return None, None, None

    def _call_openai(
        self, 
        prompt: str, 
        tools_dict: Dict[str, Any], 
        session_history: Optional[List[Dict[str, str]]]
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
        """Execute OpenAI Function Calling API call via REST."""
        try:
            import urllib.request
            base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            url = f"{base_url}/chat/completions"
            model_name = self.model or "gpt-4o-mini"

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an enterprise AI Agent. Call tools to query CRM, relational DB, ITSM, and Vector RAG. "
                        "Stay 100% faithful to tool results."
                    )
                }
            ]
            if session_history:
                for turn in session_history[-6:]:
                    messages.append({
                        "role": turn.get("role", "user"),
                        "content": turn.get("content", "")
                    })
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": model_name,
                "messages": messages,
                "tools": self.format_tools_for_openai(tools_dict),
                "tool_choice": "auto"
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=12) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                choice = res_data.get("choices", [{}])[0].get("message", {})
                tool_calls = choice.get("tool_calls", [])
                if tool_calls:
                    tc = tool_calls[0].get("function", {})
                    fn_name = tc.get("name")
                    fn_args = json.loads(tc.get("arguments", "{}"))
                    return fn_name, fn_args, None
                return None, None, choice.get("content")

        except Exception as e:
            logger.warning(f"OpenAI API call failed, falling back to local engine: {str(e)}")
            return None, None, None

        return None, None, None

    def test_connection(self, provider: str, api_key: str) -> Dict[str, Any]:
        """Test user-supplied API key."""
        if not api_key:
            return {"success": False, "message": "API Key cannot be empty."}

        try:
            import urllib.request
            if provider == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key.strip()}"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=8) as resp:
                    if resp.status == 200:
                        return {"success": True, "provider": "gemini", "message": "Successfully connected to Google Gemini API!"}
            elif provider == "openai":
                base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
                url = f"{base_url}/models"
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key.strip()}"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    if resp.status == 200:
                        return {"success": True, "provider": "openai", "message": "Successfully connected to OpenAI API!"}
        except Exception as e:
            return {"success": False, "provider": provider, "message": f"Connection test failed: {str(e)}"}

        return {"success": False, "provider": provider, "message": "Unsupported provider."}
