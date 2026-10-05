"""
High-Impact Action Tool: Cancel Order Tool.
Requires Human-in-the-Loop (HITL) approval prior to execution.
"""

from typing import Dict, Any
from .db_tool import DBTool


class CancelOrderTool:
    """Tool for cancelling customer orders in the database."""

    name = "cancel_order_tool"
    description = (
        "Cancel an existing customer order in the database. "
        "HIGH-IMPACT write action requiring explicit human confirmation."
    )
    impact_level = "HIGH"
    requires_approval = True

    parameters = {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "The unique Order ID to cancel (e.g. 'ORD-9901', 'ORD-9902')"
            },
            "reason": {
                "type": "string",
                "description": "Optional cancellation reason (e.g. 'Customer requested cancellation')"
            }
        },
        "required": ["order_id"]
    }

    def __init__(self, db_tool: DBTool):
        self.db_tool = db_tool

    def execute(self, order_id: str, reason: str = "Customer request") -> Dict[str, Any]:
        """Execute the order cancellation."""
        return self.db_tool.cancel_order(order_id, reason=reason)
