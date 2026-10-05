"""
High-Impact Action Tool: Escalate ITSM Ticket Tool.
Requires Human-in-the-Loop (HITL) approval prior to execution.
"""

from typing import Dict, Any
from .itsm_tool import ITSMTool


class EscalateTicketTool:
    """Tool for escalating ITSM tickets."""

    name = "escalate_ticket_tool"
    description = (
        "Escalate an ITSM ticket to Critical priority P1 or update its status. "
        "HIGH-IMPACT write action requiring explicit human confirmation."
    )
    impact_level = "HIGH"
    requires_approval = True

    parameters = {
        "type": "object",
        "properties": {
            "ticket_id": {
                "type": "string",
                "description": "The unique Ticket ID to escalate (e.g. 'INC-1042', 'REQ-5510')"
            },
            "priority": {
                "type": "string",
                "description": "Target priority (e.g. 'P1 - Critical', 'P2 - High')"
            },
            "note": {
                "type": "string",
                "description": "Escalation reason or incident update note"
            }
        },
        "required": ["ticket_id"]
    }

    def __init__(self, itsm_tool: ITSMTool):
        self.itsm_tool = itsm_tool

    def execute(self, ticket_id: str, priority: str = "P1 - Critical", note: str = "Escalated by supervisor") -> Dict[str, Any]:
        """Execute ticket escalation."""
        return self.itsm_tool.escalate_ticket(ticket_id, priority=priority, note=note)
