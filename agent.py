"""
Educational AI Agent with Tool Calling Architecture.

Architecture Flow:
  1. USER -> AI AGENT receives prompt
  2. Understand Intent (Classifies goal & extracts entities)
  3. Tool Selector (Picks CRM Tool, DB Tool, ITSM Tool, or Direct Answer)
  4. Tool Execution (Calls tool and gets Tool Results)
  5. AI AGENT Synthesis (Reasons over tool results)
  6. Final Answer returned to USER
"""

import json
import re
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

from tools.crm_tool import CRMTool
from tools.db_tool import DBTool
from tools.itsm_tool import ITSMTool
from tools.crm_kb_tool import CRMKnowledgeBaseTool
from tools.order_cancel_tool import CancelOrderTool
from tools.ticket_escalate_tool import EscalateTicketTool
from guardrails import InputGuardrail, OutputGuardrail
from memory import MemoryStore
from llm_client import LLMClient


@dataclass
class AgentStep:
    step_id: str
    phase: str          # e.g., "intent", "tool_selection", "tool_execution", "synthesis", "guardrail", "session_memory", "hitl_approval"
    title: str
    description: str
    data: Optional[Dict[str, Any]] = None


@dataclass
class AgentResponse:
    user_query: str
    intent: str
    tool_selected: Optional[str]
    tool_input: Optional[Dict[str, Any]]
    tool_result: Optional[Dict[str, Any]]
    final_answer: str
    steps: List[Dict[str, Any]]
    guardrail_blocked: bool = False
    session_id: str = "default"
    session_context: Optional[Dict[str, Any]] = None
    requires_confirmation: bool = False
    pending_action: Optional[Dict[str, Any]] = None


class AIAgent:
    """
    Modular AI Agent illustrating Tool Calling with Enterprise Guardrails,
    Session Memory, Human-in-the-Loop Approvals, and Real LLM Connectivity.
    """

    def __init__(self, api_key: Optional[str] = None, llm_provider: str = "auto"):
        self.api_key = api_key
        # Enterprise Safety Guardrails
        self.input_guardrail = InputGuardrail()
        self.output_guardrail = OutputGuardrail()
        # Session Memory Store
        self.memory_store = MemoryStore()

        # Shared backend tools
        db_tool = DBTool()
        itsm_tool = ITSMTool()

        # Register available tools (both read and high-impact write tools)
        self.tools = {
            "crm_tool": CRMTool(),
            "crm_kb_tool": CRMKnowledgeBaseTool(),
            "db_tool": db_tool,
            "itsm_tool": itsm_tool,
            "cancel_order_tool": CancelOrderTool(db_tool),
            "escalate_ticket_tool": EscalateTicketTool(itsm_tool)
        }

        # Real LLM Adapter (Google Gemini / OpenAI / Standalone fallback)
        self.llm_client = LLMClient(provider=llm_provider, api_key=api_key)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Returns the registered tool schemas presented to the agent."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
            for tool in self.tools.values()
        ]

    def understand_intent(self, user_query: str) -> Dict[str, Any]:
        """
        Step 2: Understand Intent.
        Analyzes the user's message to determine if an external tool is required,
        which domain it touches, and extracts potential parameters.
        """
        q = user_query.strip().lower()

        # 1. Real LLM Function Calling (if live provider configured with API key)
        if self.llm_client.provider in ["gemini", "openai"] and self.llm_client.api_key:
            tool_name, tool_args, direct_msg = self.llm_client.generate_tool_call(user_query, self.tools)
            if tool_name and tool_name in self.tools:
                return {
                    "intent": f"llm_function_call_{tool_name}",
                    "domain": f"Live LLM Tool Calling ({self.llm_client.provider.title()})",
                    "recommended_tool": tool_name,
                    "extracted_params": tool_args or {},
                    "reasoning": f"Real LLM ({self.llm_client.provider.title()}) invoked function '{tool_name}'."
                }
            elif direct_msg:
                return {
                    "intent": "llm_direct_response",
                    "domain": f"Direct LLM Answer ({self.llm_client.provider.title()})",
                    "recommended_tool": None,
                    "extracted_params": {"direct_message": direct_msg},
                    "reasoning": f"Real LLM ({self.llm_client.provider.title()}) formulated response directly."
                }

        # 2. Check for Session Memory / Dialogue History Recall intents
        recall_triggers = [
            "earlier ask", "earlier question", "previous ask", "previous question", 
            "what did i ask", "what did i say", "what card number", "card number i", 
            "card number was given", "card number was i", "earlier prompt", "last prompt", 
            "what was my last", "earlier message", "previous message"
        ]
        if any(w in q for w in recall_triggers):
            return {
                "intent": "recall_session_history",
                "domain": "Session Memory Buffer",
                "recommended_tool": None,
                "extracted_params": {"query": user_query.strip()},
                "reasoning": "User is asking about conversational history or past turn content from session memory."
            }

        # 3. Check for High-Impact Write Action: Order Cancellation (Requires HITL Approval)
        if any(w in q for w in ["cancel order", "cancel ord-", "cancellation", "abort order"]):
            order_match = re.search(r'\b(ord-\d+)\b', user_query, re.IGNORECASE)
            ord_id = order_match.group(1).upper() if order_match else "ORD-9901"
            return {
                "intent": "cancel_order",
                "domain": "Relational DB (Write / High Impact)",
                "recommended_tool": "cancel_order_tool",
                "extracted_params": {"order_id": ord_id, "reason": "Customer cancellation request"},
                "reasoning": f"Identified request to cancel order {ord_id}. High-impact write action requiring human confirmation."
            }

        # 4. Check for High-Impact Write Action: Ticket Escalation (Requires HITL Approval)
        if any(w in q for w in ["escalate ticket", "escalate inc-", "escalate incident", "mark p1", "critical escalation", "escalate"]):
            tkt_match = re.search(r'\b(inc-\d+|req-\d+)\b', user_query, re.IGNORECASE)
            tkt_id = tkt_match.group(1).upper() if tkt_match else "INC-1042"
            return {
                "intent": "escalate_ticket",
                "domain": "ITSM (Write / High Impact)",
                "recommended_tool": "escalate_ticket_tool",
                "extracted_params": {"ticket_id": tkt_id, "priority": "P1 - Critical", "note": "Priority escalated by user request"},
                "reasoning": f"Identified request to escalate ticket {tkt_id}. High-impact write action requiring human confirmation."
            }

        # Check for ITSM intents (incidents, tickets, outages, bugs, IT help)
        if any(re.search(rf"\b{w}\b", q) for w in ["ticket", "incident", "inc", "req", "outage", "vpn", "sso", "itsm"]):
            ticket_match = re.search(r'\b(inc-\d+|req-\d+)\b', user_query, re.IGNORECASE)
            if ticket_match:
                keyword = ticket_match.group(1).upper()
                return {
                    "intent": "check_itsm_ticket",
                    "domain": "ITSM (IT Service Management)",
                    "recommended_tool": "itsm_tool",
                    "extracted_params": {"ticket_or_keyword": keyword.strip()},
                    "reasoning": f"Identified ticket ID {keyword} in query. Routing to ITSM tool."
                }
            
            # Check for known incident topic keywords with strict word boundaries (prevents 'associated' matching 'sso')
            for kw in ["vpn", "sso", "sandbox", "outage"]:
                if re.search(rf"\b{kw}\b", q):
                    return {
                        "intent": "check_itsm_ticket",
                        "domain": "ITSM (IT Service Management)",
                        "recommended_tool": "itsm_tool",
                        "extracted_params": {"ticket_or_keyword": kw},
                        "reasoning": f"Identified IT incident topic '{kw}' in query. Routing to ITSM tool."
                    }

            # Mentions ticket but no valid ticket ID or known keyword was found
            return {
                "intent": "missing_ticket_id",
                "domain": "ITSM (IT Service Management)",
                "recommended_tool": None,
                "extracted_params": {},
                "reasoning": "User asked about a ticket but did not supply a ticket ID (e.g. INC-1042)."
            }

        # Check for DB intents (orders, invoices, inventory, stock, amount, delivery)
        if any(w in q for w in ["order", "ord-", "invoice", "inventory", "stock", "sku", "warehouse", "delivery date", "bought"]):
            order_match = re.search(r'\b(ord-\d+)\b', user_query, re.IGNORECASE)
            sku_match = re.search(r'\b(sku-[\w-]+)\b', user_query, re.IGNORECASE)

            if order_match:
                filter_key = order_match.group(1).upper()
                q_type = "orders"
            elif sku_match:
                filter_key = sku_match.group(1).upper()
                q_type = "inventory"
            elif "stock" in q or "inventory" in q or "sku" in q:
                filter_key = "sku"
                q_type = "inventory"
            else:
                # Look for customer name within orders
                for name in ["acme", "stark", "wayne", "cyberdyne"]:
                    if name in q:
                        filter_key = name
                        break
                else:
                    filter_key = user_query
                q_type = "orders"

            return {
                "intent": "query_database_records",
                "domain": "Relational DB (Orders & Inventory)",
                "recommended_tool": "db_tool",
                "extracted_params": {"filter_key": filter_key, "query_type": q_type},
                "reasoning": "Query asks for transactions, order statuses, or inventory. DB tool holds structured records."
            }

        # Check for CRM Policy / Knowledge Base (Vector RAG) intents
        if any(w in q for w in ["policy", "sla", "discount rule", "guideline", "perk", "contract rule", "escalation policy", "renewal discount"]):
            return {
                "intent": "search_crm_policy_knowledge_base",
                "domain": "CRM Knowledge Base (Vector RAG)",
                "recommended_tool": "crm_kb_tool",
                "extracted_params": {"query": user_query.strip()},
                "reasoning": "Query asks about unstructured CRM policies, SLA response times, or discount rules. Vector RAG is appropriate."
            }

        # Check for CRM intents (customer, client, account manager, contact, sales stage)
        if any(w in q for w in ["customer", "client", "contact", "crm", "account manager", "cust-", "sales stage", "acme", "stark", "wayne", "cyberdyne"]):
            cust_match = re.search(r'\b(cust-\d+)\b', user_query, re.IGNORECASE)
            if cust_match:
                query_val = cust_match.group(1).upper()
            else:
                for company in ["acme corporation", "acme corp", "acme", "stark industries", "stark", "wayne enterprises", "wayne", "cyberdyne systems", "cyberdyne"]:
                    if company in q:
                        query_val = company
                        break
                else:
                    query_val = user_query

            return {
                "intent": "lookup_customer_crm",
                "domain": "CRM (Customer Profiles & Contacts)",
                "recommended_tool": "crm_tool",
                "extracted_params": {"query": query_val},
                "reasoning": "Query is regarding customer account, account manager, or CRM information."
            }

        # Conversational / General greeting
        return {
            "intent": "general_conversation",
            "domain": "Direct AI Knowledge",
            "recommended_tool": None,
            "extracted_params": {},
            "reasoning": "User message is a greeting or general inquiry that does not require enterprise tools."
        }

    def select_tool(self, intent_analysis: Dict[str, Any]) -> Optional[str]:
        """
        Step 3: Tool Selector.
        Matches intent to tool definition from the available registry.
        """
        tool_name = intent_analysis.get("recommended_tool")
        if tool_name and tool_name in self.tools:
            return tool_name
        return None

    def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 4: Execute the selected tool and return raw Tool Results.
        """
        tool = self.tools.get(tool_name)
        if not tool:
            return {"error": f"Tool '{tool_name}' not found."}

        try:
            return tool.execute(**tool_args)
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}

    def synthesize_answer(
        self, 
        user_query: str, 
        tool_name: Optional[str], 
        tool_result: Optional[Dict[str, Any]],
        session_memory: Optional[Any] = None,
        intent: Optional[str] = None
    ) -> str:
        """
        Step 5: Synthesize Final Answer.
        Takes user query + raw tool output to formulate a professional, human-like response.
        """
        # Handle meta-dialogue history / session memory queries
        if intent == "recall_session_history":
            if session_memory and session_memory.turns:
                user_turns = [t for t in session_memory.turns if t.role == "user"]
                if "card" in user_query.lower():
                    found_card = None
                    for t in reversed(user_turns):
                        card_m = re.search(r'\b(?:\d{4}[-\s]?){3}\d{1,4}\b|\b\d{13,19}\b', t.content)
                        if card_m:
                            found_card = card_m.group(0)
                            break
                    if found_card:
                        return (
                            f"In your earlier ask, you mentioned card number **`{found_card}`**.\n\n"
                            f"🛡️ **Enterprise Security & PII Notice**:\n"
                            f"• In production enterprise systems, payment cards are sensitive PII subject to **PCI-DSS** compliance. They are redacted by output safety guardrails and never stored in plain text.\n"
                            f"• Our ITSM system tracks tickets by Ticket ID (e.g. `INC-1042`), not by payment card numbers."
                        )
                    else:
                        return "I reviewed our conversation history in this session, but no credit card number was found in your earlier messages."
                else:
                    if user_turns:
                        prev_q = user_turns[-1].content
                        return f"In your earlier message, you asked:\n\n> *\"{prev_q}\"*"
            return "There are no previous messages in this session's memory buffer yet."

        # Handle queries that mention a ticket but lack a valid ID
        if intent == "missing_ticket_id":
            return (
                "You requested a ticket status, but I could not find a valid ticket identifier in your request.\n\n"
                "• **Sample Ticket IDs**: `INC-1042`, `INC-1043`, or `REQ-5510`\n"
                "• **Incident Topics**: `VPN`, `SSO`, or `Sandbox`\n\n"
                "*(Note: In enterprise systems, tickets are indexed by ticket ID or customer account, not by payment card numbers.)*"
            )

        if not tool_name or not tool_result:
            return (
                f"Hello! I am your AI Agent equipped with Tool Calling capabilities.\n"
                f"I can connect to three integrated enterprise systems:\n"
                f"• 📋 **CRM Tool**: Customer accounts, tiers, contacts, sales stages.\n"
                f"• 🗄️ **DB Tool**: Orders, amounts, deliveries, inventory items.\n"
                f"• 🎫 **ITSM Tool**: Incident tickets, outages, status updates.\n\n"
                f"Try asking: 'Look up customer Acme in CRM', 'Show order ORD-9902 in DB', or 'Check ITSM ticket INC-1042'!"
            )

        if tool_result.get("status") == "not_found":
            return f"I queried the **{tool_name}**, but could not find matching records: {tool_result.get('message', 'No details available.')}"

        if "error" in tool_result:
            return f"An error occurred while executing **{tool_name}**: {tool_result['error']}"

        # Synthesize CRM KB (Vector RAG) Result
        if tool_name == "crm_kb_tool":
            top_chunk = tool_result.get("top_chunk", {})
            score = top_chunk.get("similarity_score", 0.0)
            score_pct = int(score * 100)
            return (
                f"📚 **Retrieved from CRM Knowledge Base (Vector RAG Search)**\n"
                f"• **Document**: *{top_chunk.get('title', 'CRM Policy')}* (`{top_chunk.get('doc_id')}`)\n"
                f"• **Semantic Match Confidence**: `{score_pct}% match`\n\n"
                f"**Policy Excerpt:**\n"
                f"> \"{top_chunk.get('excerpt')}\"\n\n"
                f"*(Retrieved {tool_result.get('matched_chunks', 1)} relevant document chunk(s) from unstructured policy documents)*"
            )

        # Synthesize CRM Result
        if tool_name == "crm_tool":
            data = tool_result.get("data")
            if isinstance(data, list):
                summary = "\n".join([f"- **{c['name']}** ({c['id']}): Contact {c['contact_person']} ({c['email']}), Tier: {c['tier']}, Sales Stage: {c['sales_stage']}" for c in data])
                return f"I retrieved **{len(data)} customer record(s)** from the CRM:\n\n{summary}"
            else:
                c = data
                return (
                    f"Here is the customer record for **{c['name']}** from the CRM:\n\n"
                    f"• **Customer ID**: `{c['id']}`\n"
                    f"• **Primary Contact**: {c['contact_person']} ({c['email']}, {c['phone']})\n"
                    f"• **Tier**: {c['tier']}\n"
                    f"• **Sales Stage**: {c['sales_stage']}\n"
                    f"• **Account Manager**: {c['account_manager']}\n"
                    f"• **Region**: {c['region']}"
                )

        # Synthesize DB Result
        if tool_name == "db_tool":
            table = tool_result.get("table")
            data = tool_result.get("data", [])
            if table == "inventory":
                lines = [f"• **{item['name']}** (`{item['sku']}`): **{item['in_stock']} units** in warehouse *{item['warehouse']}*" for item in data]
                return f"Here is the inventory information from the database:\n\n" + "\n".join(lines)
            else:
                lines = [
                    f"• **Order `{ord_rec['order_id']}`** for **{ord_rec['customer_name']}**:\n"
                    f"  - Product: {ord_rec['product']}\n"
                    f"  - Amount: ${ord_rec['amount_usd']:,}\n"
                    f"  - Status: **{ord_rec['status']}**\n"
                    f"  - Delivery Date: {ord_rec['delivery_date']}"
                    for ord_rec in data
                ]
                return f"Found **{len(data)} matching order(s)** in the database:\n\n" + "\n\n".join(lines)

        # Synthesize ITSM Result
        if tool_name == "itsm_tool":
            data = tool_result.get("data")
            if isinstance(data, list):
                lines = [f"• **`{t['ticket_id']}`** - {t['title']} (Status: **{t['status']}**, Priority: {t['priority']})" for t in data]
                return f"Found **{len(data)} ITSM ticket(s)**:\n\n" + "\n".join(lines)
            else:
                t = data
                return (
                    f"Here are the details for ITSM Ticket **`{t['ticket_id']}`**:\n\n"
                    f"• **Title**: {t['title']}\n"
                    f"• **Category**: {t['category']}\n"
                    f"• **Priority**: {t['priority']}\n"
                    f"• **Status**: **{t['status']}**\n"
                    f"• **Assigned To**: {t['assigned_to']}\n"
                    f"• **Reporter**: {t['reporter']}\n"
                    f"• **Latest Update**: *\"{t['last_update']}\"*"
                )

        # Direct LLM message synthesis
        if intent == "llm_direct_response" and tool_result and "direct_message" in tool_result:
            return tool_result["direct_message"]

        # Synthesize Cancel Order Tool Result (Post-HITL execution)
        if tool_name == "cancel_order_tool":
            return (
                f"✅ **Order Successfully Cancelled**\n\n"
                f"• **Order ID**: `{tool_result.get('order_id')}`\n"
                f"• **Customer**: **{tool_result.get('customer_name', 'Customer')}**\n"
                f"• **Product**: {tool_result.get('product', 'N/A')}\n"
                f"• **Amount**: ${tool_result.get('amount_usd', 0):,}\n"
                f"• **New Status**: **Cancelled** (was: `{tool_result.get('previous_status')}`)\n\n"
                f"🛡️ *Audit Trail: High-impact financial cancellation approved and committed to database.*"
            )

        # Synthesize Escalate Ticket Tool Result (Post-HITL execution)
        if tool_name == "escalate_ticket_tool":
            return (
                f"✅ **Ticket Escalation Applied**\n\n"
                f"• **Ticket ID**: `{tool_result.get('ticket_id')}`\n"
                f"• **Title**: *{tool_result.get('title')}*\n"
                f"• **New Priority**: **{tool_result.get('new_priority')}** (was: `{tool_result.get('previous_priority')}`)\n"
                f"• **Escalation Note**: *\"{tool_result.get('note')}\"*\n\n"
                f"🛡️ *Audit Trail: High-impact operational escalation approved and committed to ITSM system.*"
            )

        return f"Tool Execution Completed. Raw Data: {json.dumps(tool_result, indent=2)}"

    def process_query(self, user_query: str, session_id: str = "default") -> AgentResponse:
        """
        Full End-to-End Execution Pipeline with Enterprise Guardrails and Session Memory:
        0. Input Guardrail (Safety, Prompt Injection, SQL Injection)
        1. Session Memory Context Resolution (Pronoun / Multi-turn Entity Tracking)
        2. Receive User Query
        3. Understand Intent
        4. Tool Selector
        5. Tool Execution & Results
        6. AI Agent Synthesizes Final Answer
        7. Output Guardrail (Faithfulness Verification, PII Redaction)
        8. Update Session Memory
        """
        steps: List[Dict[str, Any]] = []
        session_memory = self.memory_store.get_or_create(session_id)

        # 0. Input Guardrail Check
        input_guard = self.input_guardrail.validate(user_query)
        if not input_guard.passed:
            steps.append(asdict(AgentStep(
                step_id="0_input_guardrail",
                phase="input_guardrail",
                title="🛡️ Input Guardrail (Blocked)",
                description=input_guard.message,
                data={"category": input_guard.category, "passed": False}
            )))
            return AgentResponse(
                user_query=user_query,
                intent="blocked_by_guardrail",
                tool_selected=None,
                tool_input=None,
                tool_result=None,
                final_answer=input_guard.message,
                steps=steps,
                guardrail_blocked=True,
                session_id=session_id,
                session_context=session_memory.get_summary()["active_context"]
            )

        steps.append(asdict(AgentStep(
            step_id="0_input_guardrail",
            phase="input_guardrail",
            title="🛡️ Input Guardrail (Passed)",
            description=input_guard.message,
            data={"category": input_guard.category, "passed": True}
        )))

        # 1. Session Memory: Resolve Pronouns and Context from Previous Turns
        resolved_query, memory_applied = session_memory.resolve_pronouns_and_context(user_query)
        if memory_applied:
            steps.append(asdict(AgentStep(
                step_id="1_session_memory",
                phase="session_memory",
                title="🧠 Session Memory (Context Resolved)",
                description=f"Resolved reference to {memory_applied.get('entity_type', 'entity')} '{memory_applied.get('resolved_entity')}' from conversation memory.",
                data={
                    "original_query": user_query,
                    "resolved_query": resolved_query,
                    "active_context": session_memory.get_summary()["active_context"]
                }
            )))
        else:
            steps.append(asdict(AgentStep(
                step_id="1_session_memory",
                phase="session_memory",
                title="🧠 Session Memory Checked",
                description=f"Active context in session: {session_memory.get_summary()['active_context'] or 'None (Fresh context)'}",
                data=session_memory.get_summary()
            )))

        # 2. Received User Query
        steps.append(asdict(AgentStep(
            step_id="2_input",
            phase="user_input",
            title="2. User Input Processed",
            description=f"Using query: '{resolved_query}'",
            data={"original_query": user_query, "resolved_query": resolved_query}
        )))

        # 2b. Human-in-the-Loop: Check if awaiting decision on a pending high-impact action
        pending_act = session_memory.get_pending_action()
        if pending_act:
            lower_q = resolved_query.strip().lower()
            if any(w in lower_q for w in ["yes", "approve", "confirm", "proceed", "go ahead", "do it", "ok"]):
                # Action Approved
                t_name = pending_act["tool_name"]
                t_args = pending_act["tool_args"]
                tool_result = self.execute_tool(t_name, t_args)
                session_memory.clear_pending_action()

                steps.append(asdict(AgentStep(
                    step_id="hitl_approved",
                    phase="hitl_approval",
                    title="✅ Human-in-the-Loop Gate (Approved)",
                    description=f"Human user explicitly confirmed action '{t_name}'. Executed with parameters {t_args}.",
                    data={"action": pending_act, "tool_result": tool_result}
                )))

                raw_answer = self.synthesize_answer(resolved_query, t_name, tool_result, session_memory=session_memory)
                session_memory.add_user_turn(user_query)
                session_memory.add_assistant_turn(raw_answer, t_name, {})

                return AgentResponse(
                    user_query=user_query,
                    intent="hitl_approved",
                    tool_selected=t_name,
                    tool_input=t_args,
                    tool_result=tool_result,
                    final_answer=raw_answer,
                    steps=steps,
                    guardrail_blocked=False,
                    session_id=session_id,
                    session_context=session_memory.get_summary()["active_context"]
                )

            elif any(w in lower_q for w in ["no", "reject", "cancel", "abort", "stop", "nevermind"]):
                # Action Rejected
                session_memory.clear_pending_action()
                steps.append(asdict(AgentStep(
                    step_id="hitl_rejected",
                    phase="hitl_approval",
                    title="🛑 Human-in-the-Loop Gate (Rejected)",
                    description=f"Human user aborted action '{pending_act['tool_name']}'. Operation aborted safely.",
                    data={"action": pending_act}
                )))
                abort_msg = (
                    f"🛑 **Action Cancelled by User**\n\n"
                    f"The operation to **{pending_act['summary']}** was cancelled. No changes were made."
                )
                session_memory.add_user_turn(user_query)
                session_memory.add_assistant_turn(abort_msg, None, {})

                return AgentResponse(
                    user_query=user_query,
                    intent="hitl_rejected",
                    tool_selected=None,
                    tool_input=None,
                    tool_result=None,
                    final_answer=abort_msg,
                    steps=steps,
                    guardrail_blocked=False,
                    session_id=session_id,
                    session_context=session_memory.get_summary()["active_context"]
                )

        # 3. Understand Intent
        intent_analysis = self.understand_intent(resolved_query)
        steps.append(asdict(AgentStep(
            step_id="3_intent",
            phase="understand_intent",
            title="3. Understand Intent",
            description=f"Classified intent as '{intent_analysis['intent']}' with domain '{intent_analysis['domain']}'.",
            data=intent_analysis
        )))

        # 4. Tool Selector
        selected_tool_name = self.select_tool(intent_analysis)
        tool_args = intent_analysis.get("extracted_params", {})

        steps.append(asdict(AgentStep(
            step_id="4_selector",
            phase="tool_selector",
            title="4. Tool Selector",
            description=(
                f"Selected '{selected_tool_name}' with parameters {tool_args}"
                if selected_tool_name else "No tool required (Direct response)."
            ),
            data={
                "tool_selected": selected_tool_name,
                "arguments": tool_args,
                "available_tools": list(self.tools.keys())
            }
        )))

        # Check if selected tool requires Human-in-the-Loop (HITL) approval
        selected_tool_obj = self.tools.get(selected_tool_name) if selected_tool_name else None
        requires_approval = getattr(selected_tool_obj, "requires_approval", False)

        if selected_tool_name and requires_approval:
            action_id = f"act_{uuid.uuid4().hex[:8]}"
            preview = ""
            if selected_tool_name == "cancel_order_tool":
                preview = f"Cancel Order {tool_args.get('order_id', '')} in database (Financial Action)"
            elif selected_tool_name == "escalate_ticket_tool":
                preview = f"Escalate Ticket {tool_args.get('ticket_id', '')} to {tool_args.get('priority', 'Critical P1')}"
            else:
                preview = f"Execute high-impact write action via {selected_tool_name}"

            pending_action = {
                "action_id": action_id,
                "tool_name": selected_tool_name,
                "tool_args": tool_args,
                "summary": preview
            }
            session_memory.set_pending_action(pending_action)

            steps.append(asdict(AgentStep(
                step_id="4_hitl_gate",
                phase="hitl_approval_gate",
                title="⏸️ Human-in-the-Loop Gate (Awaiting Approval)",
                description=f"Tool '{selected_tool_name}' classified as HIGH IMPACT write action. Execution suspended pending explicit confirmation.",
                data={"pending_action": pending_action}
            )))

            confirmation_msg = (
                f"⚠️ **Human-in-the-Loop (HITL) Confirmation Required**\n\n"
                f"You requested a high-impact write action:\n\n"
                f"• **Action**: {preview}\n"
                f"• **Tool**: `{selected_tool_name}`\n"
                f"• **Parameters**: `{json.dumps(tool_args)}`\n\n"
                f"👉 Please reply **\"Yes, proceed\"** to approve and execute, or **\"No, abort\"** to cancel."
            )

            session_memory.add_user_turn(user_query)
            session_memory.add_assistant_turn(confirmation_msg, None, {})

            return AgentResponse(
                user_query=user_query,
                intent=intent_analysis["intent"],
                tool_selected=selected_tool_name,
                tool_input=tool_args,
                tool_result=None,
                final_answer=confirmation_msg,
                steps=steps,
                guardrail_blocked=False,
                session_id=session_id,
                session_context=session_memory.get_summary()["active_context"],
                requires_confirmation=True,
                pending_action=pending_action
            )

        # 5. Tool Execution & Results
        tool_result = None
        if selected_tool_name:
            tool_result = self.execute_tool(selected_tool_name, tool_args)
            steps.append(asdict(AgentStep(
                step_id="5_execution",
                phase="tool_execution",
                title=f"5. Tool Execution ({selected_tool_name})",
                description=f"Invoked {selected_tool_name} and received structured response.",
                data={"tool": selected_tool_name, "raw_result": tool_result}
            )))
        else:
            steps.append(asdict(AgentStep(
                step_id="5_execution",
                phase="tool_execution",
                title="5. Tool Execution (Skipped)",
                description="Bypassed tool invocation as query is general conversational.",
                data={"tool": None, "raw_result": None}
            )))

        # 6. Synthesize Final Answer
        raw_final_answer = self.synthesize_answer(
            resolved_query, 
            selected_tool_name, 
            tool_result,
            session_memory=session_memory,
            intent=intent_analysis.get("intent")
        )
        steps.append(asdict(AgentStep(
            step_id="6_synthesis",
            phase="agent_synthesis",
            title="6. AI Agent Synthesis",
            description="Synthesized tool results into final user-friendly response.",
            data={"final_answer": raw_final_answer}
        )))

        # 7. Output Guardrail Check (Faithfulness & PII)
        output_guard = self.output_guardrail.validate(raw_final_answer, tool_result)
        final_answer = output_guard.sanitized_text
        status_title = "🛡️ Output Guardrail (Hallucination Sanitized)" if output_guard.hallucination_detected else "🛡️ Output Guardrail (Verified Faithful)"
        steps.append(asdict(AgentStep(
            step_id="7_output_guardrail",
            phase="output_guardrail",
            title=status_title,
            description=output_guard.message,
            data={
                "passed": output_guard.passed,
                "category": output_guard.category,
                "hallucination_detected": output_guard.hallucination_detected,
                "flagged_entities": output_guard.flagged_entities
            }
        )))

        # 8. Update Session Memory with new entities
        entities = {}
        if selected_tool_name == "crm_tool" and tool_result and tool_result.get("data"):
            d = tool_result["data"]
            if isinstance(d, dict):
                entities["customer_name"] = d.get("name")
                entities["customer_id"] = d.get("id")
            elif isinstance(d, list) and len(d) > 0:
                entities["customer_name"] = d[0].get("name")
                entities["customer_id"] = d[0].get("id")
        elif selected_tool_name == "db_tool" and tool_result and tool_result.get("data"):
            d = tool_result["data"]
            if isinstance(d, list) and len(d) > 0:
                entities["order_id"] = d[0].get("order_id")
                entities["customer_name"] = d[0].get("customer_name")
        elif selected_tool_name == "itsm_tool" and tool_result and tool_result.get("data"):
            d = tool_result["data"]
            if isinstance(d, dict):
                entities["ticket_id"] = d.get("ticket_id")
            elif isinstance(d, list) and len(d) > 0:
                entities["ticket_id"] = d[0].get("ticket_id")

        session_memory.add_user_turn(user_query)
        session_memory.add_assistant_turn(final_answer, selected_tool_name, entities)

        return AgentResponse(
            user_query=user_query,
            intent=intent_analysis["intent"],
            tool_selected=selected_tool_name,
            tool_input=tool_args if selected_tool_name else None,
            tool_result=tool_result,
            final_answer=final_answer,
            steps=steps,
            guardrail_blocked=False,
            session_id=session_id,
            session_context=session_memory.get_summary()["active_context"]
        )


def main_cli():
    """Terminal CLI for testing and learning."""
    agent = AIAgent()
    print("=" * 70)
    print("🤖 AI AGENT TOOL CALLING DEMONSTRATION")
    print("Architecture: User -> AI Agent -> Understand Intent -> Tool Selector")
    print("              -> [CRM | DB | ITSM] -> Tool Results -> Final Answer")
    print("=" * 70)
    print("Sample Queries:")
    print("  1. 'What is the contact information and sales stage for Acme Corp?' (CRM)")
    print("  2. 'Show me order ORD-9902 and its delivery status.' (DB)")
    print("  3. 'What is the status of VPN incident INC-1042?' (ITSM)")
    print("  4. 'Hi, who are you and what tools do you have?' (Conversational)")
    print("Type 'exit' to quit.\n")

    while True:
        try:
            query = input("\n👤 USER: ")
            if not query.strip():
                continue
            if query.strip().lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break

            response = agent.process_query(query)

            print("\n" + "─" * 50)
            print("🔍 AGENT INTERNAL TRACE:")
            for s in response.steps:
                print(f"  [{s['title']}]")
                print(f"   ↳ {s['description']}")
                if s["phase"] == "tool_execution" and s["data"].get("raw_result"):
                    print(f"   ↳ Results: {json.dumps(s['data']['raw_result'], indent=6)}")
            print("─" * 50)
            print(f"\n🤖 FINAL ANSWER:\n{response.final_answer}\n")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break


if __name__ == "__main__":
    main_cli()
