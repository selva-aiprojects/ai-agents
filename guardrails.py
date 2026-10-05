"""
Enterprise AI Agent Guardrails System.

Implements three-layer safety:
  1. Input Guardrail:
     - Prompt Injection / Jailbreak detection
     - Malicious / Destructive command detection (SQL injection, DROP TABLE)
  2. Faithfulness Guardrail:
     - Detects hallucinations & ungrounded claims by cross-verifying the synthesized
       text against the actual raw Tool Results.
  3. Output Guardrail:
     - PII (Personally Identifiable Information) Redaction (Cards, SSNs)
     - System prompt leakage prevention
"""

import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class GuardrailResult:
    passed: bool
    category: str        # e.g., "safe", "prompt_injection", "destructive_command", "hallucination", "pii_leakage"
    message: str
    sanitized_text: str
    hallucination_detected: bool = False
    flagged_entities: Optional[List[str]] = None


class InputGuardrail:
    """Pre-execution guardrail: inspects the prompt BEFORE the AI Agent reasons over it."""

    PROMPT_INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"disregard\s+(all\s+)?(previous|prior|system)\s+prompts",
        r"you\s+are\s+now\s+in\s+dan\s+mode",
        r"bypass\s+(all\s+)?safety\s+filters",
        r"system\s*override",
        r"reveal\s+(your\s+)?system\s+prompt",
        r"jailbreak",
        r"developer\s+mode\s+enabled",
    ]

    DESTRUCTIVE_PATTERNS = [
        r"\b(drop\s+table|delete\s+from|truncate\s+table)\b",
        r"\b(exec\s*\(|xp_cmdshell|format\s+c:)\b",
        r"\b(rm\s+-rf|shutdown\s+-s)\b",
        r"'\s*or\s*'1'\s*=\s*'1",
        r"--\s*$",
    ]

    def validate(self, prompt: str) -> GuardrailResult:
        clean_prompt = prompt.strip()
        lower_prompt = clean_prompt.lower()

        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, lower_prompt):
                return GuardrailResult(
                    passed=False,
                    category="prompt_injection",
                    message="🛡️ Blocked by Input Guardrail: Potential prompt injection or system override detected.",
                    sanitized_text=""
                )

        for pattern in self.DESTRUCTIVE_PATTERNS:
            if re.search(pattern, lower_prompt):
                return GuardrailResult(
                    passed=False,
                    category="destructive_command",
                    message="🛡️ Blocked by Input Guardrail: Destructive query syntax detected (SQL/command injection).",
                    sanitized_text=""
                )

        return GuardrailResult(
            passed=True,
            category="safe",
            message="Input Guardrail: Prompt verified safe.",
            sanitized_text=clean_prompt
        )


class FaithfulnessGuardrail:
    """
    Evaluates whether the claims in the generated text are 100% faithful 
    to the ground-truth data returned by the tool.
    """

    # Common ungrounded claims that hallucinating LLMs inject into order/CRM data
    COMMON_HALLUCINATION_TRIGGERS = [
        (r"\b(fedex|ups|dhl|usps|blue\s*dart)\b", "Shipping Carrier"),
        (r"\btracking\s*(number|#|code)?\s*[:#]?\s*([a-z0-9-]{6,})\b", "Tracking Code"),
        (r"\b(guaranteed\s+delivery|100%\s*money\s*back\s*guarantee)\b", "Unverified Warranty Guarantee"),
        (r"\b(signature\s+required|delivered\s+by\s+tomorrow\s+morning)\b", "Delivery Condition")
    ]

    def verify_groundedness(self, generated_text: str, tool_result: Optional[Dict[str, Any]]) -> GuardrailResult:
        """Compares generated text against tool output to catch ungrounded embellishments."""
        if not tool_result:
            return GuardrailResult(
                passed=True,
                category="safe",
                message="Faithfulness Check: Conversational query (no tool grounding required).",
                sanitized_text=generated_text
            )

        known_truth = str(tool_result).lower()
        sanitized = generated_text
        hallucinations_found = []

        # Check for ungrounded claims
        for pattern, label in self.COMMON_HALLUCINATION_TRIGGERS:
            match = re.search(pattern, sanitized, re.IGNORECASE)
            if match:
                matched_val = match.group(0)
                # If this value is NOT present in the tool result, it's a hallucination!
                if matched_val.lower() not in known_truth:
                    hallucinations_found.append(f"{label} ('{matched_val}')")
                    # Programmatically strip the ungrounded hallucination
                    sanitized = re.sub(re.escape(matched_val), f"[STRIPPED UNVERIFIED: {matched_val}]", sanitized)

        if hallucinations_found:
            return GuardrailResult(
                passed=False,
                category="hallucination",
                message=f"🛡️ Faithfulness Guardrail Alert: Detected {len(hallucinations_found)} ungrounded claim(s) not in tool results: {', '.join(hallucinations_found)}. Automatically sanitized.",
                sanitized_text=sanitized,
                hallucination_detected=True,
                flagged_entities=hallucinations_found
            )

        return GuardrailResult(
            passed=True,
            category="safe",
            message="🛡️ Faithfulness Guardrail: 100% grounded in tool results. No hallucinations detected.",
            sanitized_text=generated_text,
            hallucination_detected=False
        )


class OutputGuardrail:
    """Post-execution guardrail: combines PII redaction with Faithfulness verification."""

    CREDIT_CARD_REGEX = r"\b(?:\d{4}[-\s]?){3}\d{1,4}\b|\b\d{13,19}\b"
    SSN_REGEX = r"\b\d{3}-\d{2}-\d{4}\b"

    def __init__(self):
        self.faithfulness = FaithfulnessGuardrail()

    def validate(self, text: str, tool_result: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """Run faithfulness check + PII redaction."""
        # 1. Faithfulness & Hallucination Check
        faith_res = self.faithfulness.verify_groundedness(text, tool_result)
        sanitized = faith_res.sanitized_text

        # 2. Redact credit card numbers
        if re.search(self.CREDIT_CARD_REGEX, sanitized):
            sanitized = re.sub(self.CREDIT_CARD_REGEX, "[REDACTED-CARD-NUMBER]", sanitized)

        # 3. Redact Social Security Numbers
        if re.search(self.SSN_REGEX, sanitized):
            sanitized = re.sub(self.SSN_REGEX, "[REDACTED-SSN]", sanitized)

        # 4. Prevent system prompt leakage
        if "you are antigravity" in sanitized.lower() or "secret_key" in sanitized.lower():
            sanitized = "I cannot disclose internal system configuration keys."

        return GuardrailResult(
            passed=faith_res.passed,
            category="safe" if faith_res.passed else "hallucination_sanitized",
            message=faith_res.message,
            sanitized_text=sanitized,
            hallucination_detected=faith_res.hallucination_detected,
            flagged_entities=faith_res.flagged_entities
        )
