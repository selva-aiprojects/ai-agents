"""
Session-Level Memory Management System for AI Agents.

Maintains multi-turn conversational context:
  1. Conversational Buffer: Stores past user and assistant dialog turns.
  2. Active Entity Tracker: Tracks the current customer, order, or ticket in focus.
  3. Context Resolver (Pronoun / Anaphora Resolution):
     Resolves references like "they", "their", "it", "this customer", "that order"
     to the correct historical entity in memory.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ConversationTurn:
    role: str            # "user" or "assistant"
    content: str
    tool_used: Optional[str] = None
    extracted_entities: Dict[str, Any] = field(default_factory=dict)


class SessionMemory:
    """Stores the conversational history and entity state for a single user session."""

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.turns: List[ConversationTurn] = []
        # Active entities tracked across turns
        self.active_context = {
            "customer_name": None,
            "customer_id": None,
            "order_id": None,
            "ticket_id": None,
            "last_tool": None
        }
        # Human-in-the-Loop pending action buffer
        self.pending_action: Optional[Dict[str, Any]] = None

    def set_pending_action(self, action: Dict[str, Any]):
        """Stage a high-impact action awaiting human confirmation."""
        self.pending_action = action

    def get_pending_action(self) -> Optional[Dict[str, Any]]:
        """Retrieve current pending action."""
        return self.pending_action

    def clear_pending_action(self):
        """Clear pending action after execution or rejection."""
        self.pending_action = None

    def add_user_turn(self, query: str):
        """Record user query."""
        self.turns.append(ConversationTurn(role="user", content=query))

    def add_assistant_turn(self, answer: str, tool_used: Optional[str] = None, entities: Optional[Dict[str, Any]] = None):
        """Record assistant response and update active entity memory."""
        entities = entities or {}
        self.turns.append(ConversationTurn(
            role="assistant",
            content=answer,
            tool_used=tool_used,
            extracted_entities=entities
        ))

        # Update active context state
        if "customer_name" in entities:
            self.active_context["customer_name"] = entities["customer_name"]
        if "customer_id" in entities:
            self.active_context["customer_id"] = entities["customer_id"]
        if "order_id" in entities:
            self.active_context["order_id"] = entities["order_id"]
        if "ticket_id" in entities:
            self.active_context["ticket_id"] = entities["ticket_id"]
        if tool_used:
            self.active_context["last_tool"] = tool_used

    def resolve_pronouns_and_context(self, current_query: str) -> Tuple[str, Dict[str, Any]]:
        """
        Context & Pronoun Resolution:
        If the user says 'their manager', 'its status', 'what orders do they have',
        substitute with the active entity from session memory!
        """
        q = current_query.strip()
        lower_q = q.lower()
        applied_memory = {}

        # 1. Check for Customer Pronouns: "they", "their", "them", "this customer", "the client"
        customer_pronouns = [r"\btheir\b", r"\bthey\b", r"\bthem\b", r"\bthis customer\b", r"\bthe customer\b", r"\bthe client\b"]
        if any(re.search(p, lower_q) for p in customer_pronouns):
            if self.active_context.get("customer_name"):
                cust = self.active_context["customer_name"]
                applied_memory["resolved_entity"] = cust
                applied_memory["entity_type"] = "customer"
                # Rewrite query for intent detection
                resolved_query = re.sub(r"\b(their|they|them|this customer|the customer|the client)\b", cust, q, flags=re.IGNORECASE)
                return resolved_query, applied_memory

        # 2. Check for Order / Ticket Pronouns: "it", "its status", "this order", "that ticket"
        order_ticket_pronouns = [r"\bits\b", r"\bit\b", r"\bthis order\b", r"\bthat order\b", r"\bthis ticket\b", r"\bthat ticket\b"]
        if any(re.search(p, lower_q) for p in order_ticket_pronouns):
            # Prefer order if asking about delivery/order
            if any(w in lower_q for w in ["order", "delivery", "delivered", "shipping", "bought"]) and self.active_context.get("order_id"):
                ord_id = self.active_context["order_id"]
                applied_memory["resolved_entity"] = ord_id
                applied_memory["entity_type"] = "order"
                resolved_query = re.sub(r"\b(its|it|this order|that order)\b", f"order {ord_id}", q, flags=re.IGNORECASE)
                return resolved_query, applied_memory

            # Prefer ticket if asking about ticket/incident/outage/vpn
            if any(w in lower_q for w in ["ticket", "incident", "status", "fix", "update"]) and self.active_context.get("ticket_id"):
                tkt_id = self.active_context["ticket_id"]
                applied_memory["resolved_entity"] = tkt_id
                applied_memory["entity_type"] = "ticket"
                resolved_query = re.sub(r"\b(its|it|this ticket|that ticket)\b", f"ticket {tkt_id}", q, flags=re.IGNORECASE)
                return resolved_query, applied_memory

        return current_query, applied_memory

    def get_summary(self) -> Dict[str, Any]:
        """Returns snapshot of current session memory state."""
        return {
            "session_id": self.session_id,
            "total_turns": len(self.turns),
            "active_context": {k: v for k, v in self.active_context.items() if v is not None}
        }

    def clear(self):
        """Reset session memory."""
        self.turns.clear()
        self.active_context = {
            "customer_name": None,
            "customer_id": None,
            "order_id": None,
            "ticket_id": None,
            "last_tool": None
        }
        self.pending_action = None


class MemoryStore:
    """Registry managing multi-tenant or multi-tab sessions."""

    def __init__(self):
        self.sessions: Dict[str, SessionMemory] = {}

    def get_or_create(self, session_id: str = "default") -> SessionMemory:
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionMemory(session_id)
        return self.sessions[session_id]

    def clear_session(self, session_id: str = "default"):
        if session_id in self.sessions:
            self.sessions[session_id].clear()
