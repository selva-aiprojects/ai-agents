"""
CRM Knowledge Base & Policy Tool (Vector RAG Simulator).
Performs semantic text retrieval over unstructured CRM policy documents, 
SLA agreements, discount matrices, and contract guidelines.
"""

import math
import re
from typing import Dict, Any, List

# Simulated Unstructured Document Corpus (e.g. from CRM_Policy_Handbook.pdf)
CRM_POLICY_DOCUMENTS = [
    {
        "doc_id": "POL-SLA-01",
        "title": "Customer Tier SLA & Support Matrix",
        "content": (
            "Enterprise Platinum Tier: Customers receive a 15-minute SLA response time, "
            "24/7 dedicated NetOps hotline, and an assigned Technical Account Manager. "
            "Enterprise Gold Tier: 1-hour SLA response time with 24/5 support. "
            "Standard Tier: 24-hour SLA response time via email ticket only."
        ),
        "tags": ["sla", "support", "response time", "platinum", "gold", "tier"]
    },
    {
        "doc_id": "POL-DISC-02",
        "title": "Annual Contract Renewal & Discount Guidelines",
        "content": (
            "Discounts for contract renewals are strictly tier-based: "
            "Enterprise Platinum accounts qualify for up to 15% discretionary discount on multi-year renewals. "
            "Enterprise Gold accounts qualify for up to 8% discount. "
            "Standard accounts receive 0% discount without VP of Sales sign-off."
        ),
        "tags": ["discount", "renewal", "pricing", "platinum", "gold", "contract"]
    },
    {
        "doc_id": "POL-ESC-03",
        "title": "Account Escalation & Executive Liaison Policy",
        "content": (
            "Any P1 critical outage or contract cancellation risk on Strategic or Enterprise Platinum "
            "accounts must be escalated immediately to the assigned Account Manager and the VP of Customer Success "
            "within 30 minutes of notification."
        ),
        "tags": ["escalation", "executive", "critical", "cancellation", "platinum", "risk"]
    }
]


class CRMKnowledgeBaseTool:
    """Tool that simulates Vector RAG retrieval over unstructured CRM policy documents."""

    name = "crm_kb_tool"
    description = (
        "Search unstructured CRM policy documents, tier SLAs, discount guidelines, "
        "and contract rules using semantic knowledge retrieval."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Semantic search query regarding CRM policies, SLAs, or discount rules (e.g. 'Platinum discount policy', 'SLA response times')"
            }
        },
        "required": ["query"]
    }

    def _calculate_similarity(self, query: str, document_text: str, tags: List[str]) -> float:
        """
        Simulates cosine similarity of embeddings by comparing semantic overlap
        between query tokens, text content, and tagged embeddings.
        """
        q_tokens = set(re.findall(r'\w+', query.lower()))
        doc_tokens = set(re.findall(r'\w+', document_text.lower()))
        tag_tokens = set(tags)

        if not q_tokens:
            return 0.0

        # Overlap with body + boost from semantic tags
        body_overlap = len(q_tokens.intersection(doc_tokens))
        tag_overlap = len(q_tokens.intersection(tag_tokens)) * 2

        score = (body_overlap + tag_overlap) / math.sqrt(len(q_tokens) + 1)
        return min(0.98, score * 0.25)

    def execute(self, query: str) -> Dict[str, Any]:
        """Execute Vector RAG semantic search."""
        ranked_results = []
        for doc in CRM_POLICY_DOCUMENTS:
            similarity = self._calculate_similarity(query, doc["content"], doc["tags"])
            if similarity > 0.15:
                ranked_results.append({
                    "doc_id": doc["doc_id"],
                    "title": doc["title"],
                    "similarity_score": round(similarity, 3),
                    "excerpt": doc["content"]
                })

        ranked_results.sort(key=lambda x: x["similarity_score"], reverse=True)

        if ranked_results:
            return {
                "status": "success",
                "tool": self.name,
                "retrieval_type": "Vector RAG (Semantic Search)",
                "matched_chunks": len(ranked_results),
                "top_chunk": ranked_results[0],
                "all_results": ranked_results
            }

        return {
            "status": "not_found",
            "tool": self.name,
            "retrieval_type": "Vector RAG",
            "matched_chunks": 0,
            "message": f"No CRM policy document matched query '{query}'. Try queries about 'SLA response times', 'renewal discounts', or 'escalation policy'."
        }
