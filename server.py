"""
FastAPI Server for AI Agent Tool Calling Chatbot.
Exposes REST endpoints for chatting, inspecting tool schemas, and visualizing execution traces.
"""

import os
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import AIAgent

app = FastAPI(
    title="AI Agent Tool Calling Demo",
    description="Interactive chatbot showing Agent -> Understand Intent -> Tool Selector -> [CRM | DB | ITSM] -> Final Answer",
    version="1.0.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = AIAgent()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    user_query: str
    intent: str
    tool_selected: Optional[str]
    tool_input: Optional[Dict[str, Any]]
    tool_result: Optional[Dict[str, Any]]
    final_answer: str
    steps: list
    guardrail_blocked: bool = False
    session_id: str = "default"
    session_context: Optional[Dict[str, Any]] = None
    requires_confirmation: bool = False
    pending_action: Optional[Dict[str, Any]] = None


class HITLDecisionRequest(BaseModel):
    decision: str          # "approve" or "reject"
    session_id: Optional[str] = "default"


class LLMConfigRequest(BaseModel):
    provider: str          # "gemini", "openai", or "standalone"
    api_key: Optional[str] = None
    model: Optional[str] = None


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    response = agent.process_query(req.message, session_id=req.session_id or "default")
    return response


@app.post("/api/chat/action", response_model=ChatResponse)
async def hitl_action_endpoint(req: HITLDecisionRequest):
    """Handle one-click human approval or rejection of high-impact write actions."""
    user_msg = "Yes, proceed" if req.decision.lower() in ["approve", "yes", "confirm"] else "No, abort"
    response = agent.process_query(user_msg, session_id=req.session_id or "default")
    return response


@app.get("/api/llm/status")
async def get_llm_status():
    """Return active LLM provider, model, and connectivity status."""
    return agent.llm_client.get_status()


@app.post("/api/llm/config")
async def set_llm_config(req: LLMConfigRequest):
    """Dynamically update LLM provider credentials and model."""
    agent.llm_client.update_config(req.provider, req.api_key, req.model)
    return agent.llm_client.get_status()


@app.post("/api/evals/run")
async def run_evals_endpoint():
    """Execute automated evaluation benchmark suite and return scorecard."""
    from evals.evaluator import AgentEvaluator
    evaluator = AgentEvaluator()
    scorecard = evaluator.run_evaluations()
    return scorecard


@app.post("/api/session/clear")
async def clear_session_endpoint(req: Optional[ChatRequest] = None):
    sid = req.session_id if req and req.session_id else "default"
    agent.memory_store.clear_session(sid)
    return {"status": "cleared", "session_id": sid}


@app.get("/api/tools")
async def get_tools_endpoint():
    """Return tool schemas and mock databases for interactive inspection."""
    from tools.crm_tool import CRM_DATABASE
    from tools.crm_kb_tool import CRM_POLICY_DOCUMENTS
    from tools.db_tool import ORDERS_TABLE, INVENTORY_TABLE
    from tools.itsm_tool import ITSM_TICKETS

    return {
        "schemas": agent.get_tool_schemas(),
        "mock_data": {
            "crm_accounts": CRM_DATABASE,
            "crm_policies_vector_rag": CRM_POLICY_DOCUMENTS,
            "db": {
                "orders": ORDERS_TABLE,
                "inventory": INVENTORY_TABLE
            },
            "itsm": ITSM_TICKETS
        }
    }


# Mount static files directory for the frontend UI
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting AI Agent Tool Calling Server on http://localhost:8000 ...")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
