"""
CRM (Customer Relationship Management) Tool.
Handles queries related to customer accounts, contact details, account managers, and sales stages.
"""

from typing import Dict, Any, Optional

# Realistic Mock CRM Database
CRM_DATABASE = {
    "CUST-001": {
        "id": "CUST-001",
        "name": "Acme Corporation",
        "contact_person": "Alice Johnson",
        "email": "alice@acmecorp.com",
        "phone": "+1-555-0192",
        "tier": "Enterprise Platinum",
        "status": "Active",
        "sales_stage": "Closed Won",
        "account_manager": "Sarah Davis",
        "region": "North America"
    },
    "CUST-002": {
        "id": "CUST-002",
        "name": "Stark Industries",
        "contact_person": "Tony Stark",
        "email": "tony@stark.com",
        "phone": "+1-555-0810",
        "tier": "Enterprise Gold",
        "status": "Active",
        "sales_stage": "Contract Review",
        "account_manager": "James Rhodes",
        "region": "Global"
    },
    "CUST-003": {
        "id": "CUST-003",
        "name": "Wayne Enterprises",
        "contact_person": "Bruce Wayne",
        "email": "bruce@wayne.com",
        "phone": "+1-555-0344",
        "tier": "Strategic Partner",
        "status": "Active",
        "sales_stage": "Renewal Ongoing",
        "account_manager": "Lucius Fox",
        "region": "Gotham / East Coast"
    },
    "CUST-004": {
        "id": "CUST-004",
        "name": "Cyberdyne Systems",
        "contact_person": "Miles Dyson",
        "email": "miles@cyberdyne.ai",
        "phone": "+1-555-0999",
        "tier": "Standard",
        "status": "Lead",
        "sales_stage": "Discovery Phase",
        "account_manager": "Sarah Davis",
        "region": "West Coast"
    }
}


class CRMTool:
    """Tool for interacting with the CRM System."""

    name = "crm_tool"
    description = (
        "Look up customer profiles, contact info, sales stage, "
        "tier, and account manager from the CRM system."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Customer name, company name, or customer ID (e.g., 'Acme Corp', 'CUST-001', 'Tony Stark')"
            }
        },
        "required": ["query"]
    }

    def execute(self, query: str) -> Dict[str, Any]:
        """Execute the CRM lookup."""
        query_norm = query.strip().lower()

        # 1. Exact ID match
        query_upper = query.strip().upper()
        if query_upper in CRM_DATABASE:
            return {
                "status": "success",
                "tool": self.name,
                "found": True,
                "data": CRM_DATABASE[query_upper]
            }

        # 2. Search by company name, contact person, or email
        matches = []
        for cust in CRM_DATABASE.values():
            if (
                query_norm in cust["name"].lower()
                or query_norm in cust["contact_person"].lower()
                or query_norm in cust["email"].lower()
                or query_norm in cust["id"].lower()
            ):
                matches.append(cust)

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
            "message": f"No customer record found matching '{query}'. Available sample companies: Acme Corporation, Stark Industries, Wayne Enterprises, Cyberdyne Systems."
        }
