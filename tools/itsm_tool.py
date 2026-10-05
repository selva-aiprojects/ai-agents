"""
ITSM (IT Service Management) Tool.
Handles queries and actions related to IT support tickets, system incidents, outages, and service requests (e.g., ServiceNow/Jira).
"""

from typing import Dict, Any

# Realistic Mock ITSM Tickets Database
ITSM_TICKETS = {
    "INC-1042": {
        "ticket_id": "INC-1042",
        "title": "Corporate VPN gateway intermittent connection drops",
        "category": "Network & Infrastructure",
        "priority": "P2 - High",
        "status": "In Progress",
        "assigned_to": "NetOps Tier 3 (Marcus Vance)",
        "reporter": "Alice Johnson (Acme Corp liaison)",
        "created_at": "2026-10-03 08:30 UTC",
        "last_update": "Technician applied firmware patch 4.2.1; monitoring stability."
    },
    "INC-1043": {
        "ticket_id": "INC-1043",
        "title": "SSO Login failure on European regional nodes",
        "category": "Identity & Access Management",
        "priority": "P1 - Critical",
        "status": "Resolved",
        "assigned_to": "IAM Security Team",
        "reporter": "System Health Monitor",
        "created_at": "2026-10-02 14:10 UTC",
        "last_update": "Certificate renewal completed; all health checks passing."
    },
    "REQ-5510": {
        "ticket_id": "REQ-5510",
        "title": "Developer Sandbox Environment Provisioning for Cyberdyne",
        "category": "Service Request",
        "priority": "P3 - Medium",
        "status": "Awaiting Approval",
        "assigned_to": "Cloud Ops Team",
        "reporter": "Miles Dyson",
        "created_at": "2026-10-04 09:15 UTC",
        "last_update": "Waiting for departmental budget sign-off."
    }
}


class ITSMTool:
    """Tool for querying IT Service Management tickets and system alerts."""

    name = "itsm_tool"
    description = (
        "Check IT service management tickets, incident reports, "
        "system outages, ticket status, and resolution details."
    )
    parameters = {
        "type": "object",
        "properties": {
            "ticket_or_keyword": {
                "type": "string",
                "description": "Ticket ID (e.g. 'INC-1042', 'REQ-5510') or incident keyword ('VPN', 'SSO', 'Sandbox')"
            }
        },
        "required": ["ticket_or_keyword"]
    }

    def execute(self, ticket_or_keyword: str) -> Dict[str, Any]:
        """Execute the ITSM search."""
        search = ticket_or_keyword.strip().upper()

        # 1. Exact ticket ID match
        if search in ITSM_TICKETS:
            return {
                "status": "success",
                "tool": self.name,
                "found": True,
                "data": ITSM_TICKETS[search]
            }

        # 2. Keyword search in titles/descriptions
        search_lower = ticket_or_keyword.strip().lower()
        matches = []
        for tkt in ITSM_TICKETS.values():
            if (
                search_lower in tkt["ticket_id"].lower()
                or search_lower in tkt["title"].lower()
                or search_lower in tkt["category"].lower()
                or search_lower in tkt["reporter"].lower()
            ):
                matches.append(tkt)

        if matches:
            return {
                "status": "success",
                "tool": self.name,
                "found": True,
                "count": len(matches),
                "data": matches[0] if len(matches) == 1 else matches
            }

        return {
            "status": "not_found",
            "tool": self.name,
            "found": False,
            "message": f"No ITSM ticket found for '{ticket_or_keyword}'. Available tickets: INC-1042, INC-1043, REQ-5510, or search keywords like 'VPN' or 'SSO'."
        }

    def escalate_ticket(self, ticket_id: str, priority: str = "P1 - Critical", note: str = "Escalated by supervisor") -> Dict[str, Any]:
        """Escalate an ITSM ticket priority or update status (write operation)."""
        target_id = ticket_id.strip().upper()
        if target_id in ITSM_TICKETS:
            tkt = ITSM_TICKETS[target_id]
            old_prio = tkt["priority"]
            tkt["priority"] = priority
            tkt["last_update"] = f"CRITICAL ESCALATION: {note}"
            return {
                "status": "success",
                "action": "ticket_escalated",
                "ticket_id": target_id,
                "title": tkt["title"],
                "previous_priority": old_prio,
                "new_priority": priority,
                "note": note,
                "message": f"Ticket {target_id} ('{tkt['title']}') priority has been escalated from {old_prio} to {priority}."
            }
        return {
            "status": "not_found",
            "action": "ticket_escalated",
            "ticket_id": target_id,
            "message": f"Cannot escalate: Ticket {target_id} was not found."
        }
