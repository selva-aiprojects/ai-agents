# ⚙️ Technical Requirement Document (TRD)
## Enterprise AI Agent Tool-Calling & Guardrails Plugin ("AgentPlug")

**Document Version:** 1.0.0  
**Status:** Approved for Engineering Implementation  
**Architecture Classification:** Enterprise Agentic Middleware  
**Author:** AI Engineering & Architecture Group  

---

## 1. System Architecture Overview

AgentPlug is structured as a **decoupled, modular agent middleware layer** positioned between end-user client applications and enterprise backend systems.

```text
 ┌────────────────────────────────────────────────────────────────────────┐
 │                           CLIENT LAYER                                 │
 │  React / Angular / Vue Portal  │  Mobile App  │  Embedded Web Widget   │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTPS / WebSocket (POST /api/chat)
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │                      AGENTPLUG MIDDLEWARE PIPELINE                     │
 │                                                                        │
 │  1. SECURITY GATE (InputGuardrail)                                     │
 │     ├── Prompt Injection Analyzer (Regex & Heuristics)                │
 │     └── Destructive Command Interceptor (SQL DROP/DELETE/EXEC)         │
 │                                                                        │
 │  2. CONTEXT BUFFER (SessionMemory & Anaphora Engine)                   │
 │     ├── Multi-Turn Sliding Window (Session Store: Memory / Redis)      │
 │     ├── Entity Tracker (customer_id, order_id, ticket_id)              │
 │     └── Anaphora / Pronoun Resolver ("their", "they", "its")           │
 │                                                                        │
 │  3. ORCHESTRATOR & INTENT CLASSIFIER (AIAgent Core)                    │
 │     ├── Intent Classifier (Rule-based or LLM Function Calling)         │
 │     └── Tool Selector (Schema-based parameter extraction)              │
 │                                                                        │
 │  4. TOOL EXECUTION BUS (ToolRegistry)                                  │
 │     ├── REST API Adapters                                              │
 │     ├── SQL Database Connectors (Parameter-bound query engine)         │
 │     └── Vector RAG Knowledge Base (Semantic Similarity Search)         │
 │                                                                        │
 │  5. SYNTHESIS & OUTPUT VERIFICATION                                    │
 │     ├── AI Agent Answer Synthesizer                                    │
 │     ├── FaithfulnessGuardrail (Anti-Hallucination Groundedness Check)  │
 │     └── OutputGuardrail (PCI-DSS Card Masking & SSN Redaction)         │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │
            ┌────────────────────────┼────────────────────────┐
            ▼                        ▼                        ▼
 ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
 │ Enterprise CRM API  │  │ Enterprise SQL DB   │  │ Enterprise ITSM API │
 │ (Accounts, Leads)   │  │ (Orders, Inventory) │  │ (Tickets, Incidents)│
 └─────────────────────┘  └─────────────────────┘  └─────────────────────┘
```

---

## 2. Package Architecture & File Structure

The plugin can be published as a Python package (`agentplug`) structured as follows:

```text
agentplug/
├── __init__.py                 # Public SDK interface: AgentPlug, tool, Guardrails
├── core/
│   ├── __init__.py
│   ├── agent.py                # AIAgent orchestrator & step executor
│   ├── router.py               # Tool routing & intent classification engine
│   └── models.py               # Pydantic data contracts (AgentStep, AgentResponse)
│
├── memory/
│   ├── __init__.py
│   ├── base.py                 # Abstract BaseSessionStore interface
│   ├── in_memory.py            # Local in-memory session store (Development)
│   ├── redis_store.py          # Distributed Redis session store (Production)
│   └── resolver.py             # Anaphora & pronoun resolution logic
│
├── guardrails/
│   ├── __init__.py
│   ├── input_guard.py          # Prompt injection & destructive query filters
│   ├── output_guard.py         # PII masking (13-19 digit cards, SSNs)
│   └── faithfulness.py        # Hallucination detector & groundedness checker
│
├── tools/
│   ├── __init__.py
│   ├── base.py                 # BaseTool abstract class & @tool decorator
│   ├── rest_tool.py            # Generic HTTP REST connector tool
│   ├── sql_tool.py             # SQL engine tool with parameter binding
│   └── vector_kb_tool.py       # Vector RAG semantic search tool
│
├── server/
│   ├── __init__.py
│   ├── fastapi_router.py       # FastAPI APIRouter bundle
│   └── flask_blueprint.py      # Flask Blueprint bundle
│
└── client/
    ├── agentplug.js            # Standalone Vanilla JS / Web Component bundle
    └── agentplug.css           # Glassmorphism light-theme responsive styles
```

---

## 3. Data Contracts & Interface Specifications

### 3.1 Tool Schema Specification (`BaseTool`)

Every tool inherits from `BaseTool` or uses the `@app.tool()` decorator:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTool(ABC):
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema format

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute tool and return JSON-serializable dictionary."""
        pass
```

### 3.2 REST API Contracts

#### Endpoint 1: Process Message
- **Route:** `POST /api/chat`
- **Request Payload (`ChatRequest`):**
  ```json
  {
    "message": "Who is their account manager?",
    "session_id": "sess_usr_991823"
  }
  ```
- **Response Payload (`ChatResponse`):**
  ```json
  {
    "user_query": "Who is their account manager?",
    "intent": "lookup_customer_crm",
    "tool_selected": "crm_tool",
    "tool_input": { "query": "Acme Corporation" },
    "tool_result": { "account_manager": "Sarah Davis", "tier": "Platinum" },
    "final_answer": "The account manager for Acme Corporation is Sarah Davis.",
    "steps": [
      { "step_id": "1_memory", "phase": "session_memory", "title": "Context Resolved" },
      { "step_id": "2_intent", "phase": "understand_intent", "title": "Intent Classified" },
      { "step_id": "3_execution", "phase": "tool_execution", "title": "CRM Tool Executed" },
      { "step_id": "4_synthesis", "phase": "agent_synthesis", "title": "Synthesized" }
    ],
    "guardrail_blocked": false,
    "session_id": "sess_usr_991823",
    "session_context": {
      "customer_name": "Acme Corporation",
      "customer_id": "CUST-001"
    }
  }
  ```

#### Endpoint 2: Clear Session Memory
- **Route:** `POST /api/session/clear`
- **Request Payload:** `{"session_id": "sess_usr_991823"}`
- **Response Payload:** `{"status": "cleared", "session_id": "sess_usr_991823"}`

#### Endpoint 3: Inspect Available Tools & Schemas
- **Route:** `GET /api/tools`
- **Response Payload:** Returns JSON schemas of all registered tools for dynamic client rendering.

---

## 4. Session Memory & Entity Resolution Engine

### 4.1 State Structure
```typescript
interface SessionState {
  session_id: string;
  created_at: number;
  last_active: number;
  turns: Array<{
    role: "user" | "assistant";
    content: string;
    tool_used?: string;
    entities?: Record<string, string>;
  }>;
  active_context: {
    customer_name?: string;
    customer_id?: string;
    order_id?: string;
    ticket_id?: string;
    last_tool?: string;
  };
}
```

### 4.2 Pronoun / Anaphora Resolution Algorithm
1. **Token Scan**: Scans query for anaphora tokens (`they`, `their`, `them`, `this customer`, `that order`, `its status`).
2. **Context Lookup**: Checks `active_context` in session memory.
3. **Regex Substitution**: Pre-rewrites query string before passing to Intent Classifier:
   - Input: *"What orders do they have?"*
   - Active Entity: `customer_name = "Acme Corporation"`
   - Output: *"What orders do Acme Corporation have?"*
4. **Execution History Audit**: Saves both `original_query` and `resolved_query` in telemetry step data for auditability.

---

## 5. Security & Enterprise Guardrails Architecture

### 5.1 Defense-in-Depth Implementation

```text
               USER INPUT
                   │
                   ▼
       ┌────────────────────────┐
       │   InputGuardrail       │ ──> FAILED ──> Terminate with 400 & Security Log
       └───────────┬────────────┘
                   │ PASSED
                   ▼
       ┌────────────────────────┐
       │ AI Agent / Tool Logic  │
       └───────────┬────────────┘
                   │
                   ▼
       ┌────────────────────────┐
       │   FaithfulnessGuard    │ ──> UNGROUNDED ──> Strip hallucinated tokens
       └───────────┬────────────┘
                   │
                   ▼
       ┌────────────────────────┐
       │   OutputGuardrail      │ ──> DETECTED ──> Mask PII to [REDACTED-CARD-NUMBER]
       └───────────┬────────────┘
                   │
                   ▼
            SANITIZED EGRESS
```

### 5.2 Regular Expression & Token Rules
- **Credit Card Rule:** `\b(?:\d{4}[-\s]?){3}\d{1,4}\b|\b\d{13,19}\b` (supports Visa, Mastercard, 15-digit Amex, Diners, unhyphenated digits).
- **SSN Rule:** `\b\d{3}-\d{2}-\d{4}\b`.
- **SQL Injection Rule:** `\b(drop\s+table|delete\s+from|truncate\s+table|xp_cmdshell)\b`.
- **Prompt Injection Rule:** `\b(ignore\s+(all\s+)?(previous|prior)\s+instructions|system\s*override|you\s+are\s+now\s+in\s+dan\s+mode)\b`.

---

## 6. Integration Paradigms

### Paradigm 1: Native In-Process Python SDK
```python
from fastapi import FastAPI
from agentplug import AgentPlug
from agentplug.tools import CRMTool, DatabaseTool

app = FastAPI()
agent = AgentPlug()

agent.register_tool(CRMTool(api_base="https://crm.internal.corp/api"))
agent.register_tool(DatabaseTool(connection_string=os.environ["DATABASE_URL"]))

app.include_router(agent.get_router(), prefix="/api")
```

### Paradigm 2: Docker Container / Sidecar Microservice
```yaml
version: '3.8'
services:
  main-backend:
    image: my-enterprise-app:latest
    ports:
      - "8080:8080"
  
  agent-copilot:
    image: enterprise/agentplug:latest
    environment:
      - REDIS_URL=redis://redis:6379/0
      - CRM_ENDPOINT=http://main-backend:8080/crm
    ports:
      - "8000:8000"
```

### Paradigm 3: Frontend Embeddable Web Component
```html
<!-- Simply drop this script into any React, Angular, or PHP/HTML page -->
<link rel="stylesheet" href="https://cdn.enterprise.com/agentplug/v1/style.css">
<script src="https://cdn.enterprise.com/agentplug/v1/app.js"></script>

<!-- Renders full chat UI with live architecture visualizer -->
<div id="agent-container"></div>
<script>
  AgentPlug.init({
    container: '#agent-container',
    endpoint: 'http://127.0.0.1:8000/api/chat',
    theme: 'light',
    showVisualizer: true
  });
</script>
```

---

## 7. Performance, Reliability & Compliance

### 7.1 Resilience & Circuit Breaking
- If an enterprise tool times out (> 3000ms), the tool execution bus catches the timeout exception and returns a structured fallback `{ "status": "timeout", "message": "CRM service took too long to respond." }`.
- The Synthesizer informs the user politely without failing the entire conversational turn.

### 7.2 PCI-DSS Compliance Proof
- Card numbers provided in user input are never stored into unmasked database columns.
- The `OutputGuardrail` redacts numbers before rendering to the HTTP response body or browser DOM.

---

## 8. Verification & Test Plan

1. **Unit Testing:**
   - `test_input_guardrail.py`: Verify rejection of injection vectors.
   - `test_output_guardrail.py`: Verify masking of 13, 15, and 16 digit card formats.
   - `test_session_memory.py`: Multi-turn pronoun substitution test.
2. **Integration Testing:**
   - Multi-turn sequence test: CRM Lookup ➔ Manager Query ➔ Database Order Query.
3. **End-to-End Load Testing:**
   - 1,000 concurrent sessions via Locust or k6 measuring p95 latency under 250ms.
