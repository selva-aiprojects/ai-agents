"""
Database (DB) Tool.
Handles queries related to structured business data such as orders, invoices, and inventory records.
"""

from typing import Dict, Any, List

# Realistic Mock Database Tables
ORDERS_TABLE = [
    {
        "order_id": "ORD-9901",
        "customer_id": "CUST-001",
        "customer_name": "Acme Corporation",
        "product": "Cloud Infrastructure Suite",
        "amount_usd": 45000,
        "status": "Shipped",
        "order_date": "2026-09-12",
        "delivery_date": "2026-09-15"
    },
    {
        "order_id": "ORD-9902",
        "customer_id": "CUST-002",
        "customer_name": "Stark Industries",
        "product": "Quantum Processing Units (10x)",
        "amount_usd": 125000,
        "status": "Processing",
        "order_date": "2026-10-01",
        "delivery_date": "2026-10-10"
    },
    {
        "order_id": "ORD-9903",
        "customer_id": "CUST-003",
        "customer_name": "Wayne Enterprises",
        "product": "Surveillance Analytics Hub",
        "amount_usd": 89000,
        "status": "Delivered",
        "order_date": "2026-08-20",
        "delivery_date": "2026-08-25"
    },
    {
        "order_id": "ORD-9904",
        "customer_id": "CUST-001",
        "customer_name": "Acme Corporation",
        "product": "Premium Security Patching Subscription",
        "amount_usd": 12000,
        "status": "Completed",
        "order_date": "2026-07-15",
        "delivery_date": "2026-07-15"
    }
]

INVENTORY_TABLE = [
    {"sku": "SKU-QPU-01", "name": "Quantum Processor Unit", "in_stock": 42, "warehouse": "Austin-Central"},
    {"sku": "SKU-SRV-99", "name": "Enterprise Server Rack 42U", "in_stock": 8, "warehouse": "Chicago-East"},
    {"sku": "SKU-SW-SEC", "name": "Security License Key", "in_stock": 500, "warehouse": "Digital Vault"}
]


class DBTool:
    """Tool for querying the relational SQL database."""

    name = "db_tool"
    description = (
        "Query relational business database for order history, transactions, "
        "order statuses, totals, and warehouse inventory stock."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "enum": ["orders", "inventory"],
                "description": "Whether to query 'orders' or 'inventory'"
            },
            "filter_key": {
                "type": "string",
                "description": "Identifier to search by (e.g. order ID 'ORD-9901', customer name 'Acme', or SKU 'SKU-QPU-01')"
            }
        },
        "required": ["filter_key"]
    }

    def execute(self, filter_key: str, query_type: str = "orders") -> Dict[str, Any]:
        """Execute the Database query."""
        search = filter_key.strip().lower()

        # Check inventory if explicitly requested or if search relates to inventory
        if query_type == "inventory" or "sku" in search or "stock" in search:
            results = [
                item for item in INVENTORY_TABLE
                if search in item["sku"].lower() or search in item["name"].lower()
            ]
            if results:
                return {
                    "status": "success",
                    "tool": self.name,
                    "table": "inventory",
                    "records_found": len(results),
                    "data": results
                }

        # Search Orders
        order_matches = []
        for ord_record in ORDERS_TABLE:
            if (
                search in ord_record["order_id"].lower()
                or search in ord_record["customer_id"].lower()
                or search in ord_record["customer_name"].lower()
                or search in ord_record["product"].lower()
            ):
                order_matches.append(ord_record)

        if order_matches:
            return {
                "status": "success",
                "tool": self.name,
                "table": "orders",
                "records_found": len(order_matches),
                "data": order_matches
            }

        return {
            "status": "not_found",
            "tool": self.name,
            "table": "orders/inventory",
            "records_found": 0,
            "message": f"No database records found matching '{filter_key}'. Try 'ORD-9901', 'Stark', 'Acme', or 'SKU-QPU-01'."
        }

    def cancel_order(self, order_id: str, reason: str = "Customer request") -> Dict[str, Any]:
        """Cancel an order in the database (write operation)."""
        target_id = order_id.strip().upper()
        for ord_record in ORDERS_TABLE:
            if ord_record["order_id"] == target_id:
                old_status = ord_record["status"]
                ord_record["status"] = "Cancelled"
                return {
                    "status": "success",
                    "action": "order_cancelled",
                    "order_id": target_id,
                    "customer_name": ord_record["customer_name"],
                    "product": ord_record["product"],
                    "amount_usd": ord_record["amount_usd"],
                    "previous_status": old_status,
                    "new_status": "Cancelled",
                    "cancellation_reason": reason,
                    "message": f"Order {target_id} ({ord_record['product']} for {ord_record['customer_name']}) has been successfully cancelled in the database."
                }
        return {
            "status": "not_found",
            "action": "order_cancelled",
            "order_id": target_id,
            "message": f"Cannot cancel: Order {target_id} was not found in the database."
        }
