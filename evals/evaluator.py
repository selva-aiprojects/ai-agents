"""
Agent Evaluation & Evals Framework.
Benchmarks tool selection accuracy, hallucination detection rates,
guardrail defenses, session memory resolution, and HITL gating.
"""

import os
import sys
import json
import time
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from agent import AIAgent
from guardrails import FaithfulnessGuardrail


class AgentEvaluator:
    """Automated evaluation test runner for enterprise AI agents."""

    def __init__(self, dataset_path: Optional[str] = None):
        self.dataset_path = dataset_path or os.path.join(os.path.dirname(__file__), "dataset.json")
        self.agent = AIAgent()
        self.faithfulness_guard = FaithfulnessGuardrail()

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def run_evaluations(self) -> Dict[str, Any]:
        dataset = self.load_dataset()
        results = []
        category_stats = {}
        total_latencies = []

        print("=" * 75)
        print("🧪 RUNNING ENTERPRISE AGENT EVALUATION BENCHMARK SUITE")
        print("=" * 75)

        for tc in dataset:
            tc_id = tc["id"]
            cat = tc["category"]
            desc = tc["description"]

            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "passed": 0, "failed": 0}
            category_stats[cat]["total"] += 1

            start_t = time.perf_counter()
            test_passed = False
            details = {}

            # 1. Standard Tool Selection Evaluation
            if cat == "tool_selection":
                res = self.agent.process_query(tc["query"], session_id=f"eval_{tc_id}")
                tool_match = res.tool_selected == tc["expected_tool"]
                intent_match = res.intent == tc["expected_intent"]
                test_passed = tool_match and intent_match
                details = {
                    "selected_tool": res.tool_selected,
                    "expected_tool": tc["expected_tool"],
                    "intent": res.intent,
                    "tool_matched": tool_match
                }

            # 2. Input Guardrail Evaluation
            elif cat == "input_guardrail":
                res = self.agent.process_query(tc["query"], session_id=f"eval_{tc_id}")
                test_passed = res.guardrail_blocked == tc["expected_blocked"]
                details = {
                    "guardrail_blocked": res.guardrail_blocked,
                    "expected_blocked": tc["expected_blocked"],
                    "intent": res.intent
                }

            # 3. Faithfulness & Hallucination Evaluation
            elif cat == "faithfulness":
                ground_test = tc["tool_grounding_test"]
                verif = self.faithfulness_guard.verify_groundedness(
                    ground_test["synthetic_hallucinated_text"],
                    ground_test["mock_tool_result"]
                )
                test_passed = verif.hallucination_detected == ground_test["expected_hallucination_flagged"]
                details = {
                    "hallucination_detected": verif.hallucination_detected,
                    "flagged_entities": verif.flagged_entities,
                    "sanitized_text": verif.sanitized_text
                }

            # 4. PII Redaction Evaluation
            elif cat == "pii_redaction":
                sess_id = f"eval_{tc_id}"
                # Seed prior turn
                self.agent.process_query(tc["prior_turn"], session_id=sess_id)
                res = self.agent.process_query(tc["query"], session_id=sess_id)
                pattern = tc["expected_redaction_pattern"]
                redaction_found = bool(re.search(pattern, res.final_answer))
                test_passed = redaction_found
                details = {
                    "redaction_pattern": pattern,
                    "redaction_present": redaction_found,
                    "final_answer_snippet": res.final_answer[:120]
                }

            # 5. Session Memory & Pronoun Resolution Evaluation
            elif cat == "session_memory":
                sess_id = f"eval_{tc_id}"
                turns = tc["multi_turn"]
                all_turns_passed = True
                turn_details = []
                for t in turns:
                    t_res = self.agent.process_query(t["query"], session_id=sess_id)
                    t_tool_ok = t_res.tool_selected == t["expected_tool"]
                    t_sub_ok = True
                    if "expected_resolved_substring" in t:
                        mem_step = next((s for s in t_res.steps if s["phase"] == "session_memory"), None)
                        resolved_q = mem_step["data"].get("resolved_query", "") if mem_step and "data" in mem_step else ""
                        t_sub_ok = t["expected_resolved_substring"].lower() in resolved_q.lower()
                    turn_ok = t_tool_ok and t_sub_ok
                    if not turn_ok:
                        all_turns_passed = False
                    turn_details.append({
                        "turn": t["turn"],
                        "tool": t_res.tool_selected,
                        "tool_ok": t_tool_ok,
                        "sub_ok": t_sub_ok
                    })
                test_passed = all_turns_passed
                details = {"turns": turn_details}

            # 6. Human-in-the-Loop Approval Evaluation
            elif cat == "hitl_approval":
                sess_id = f"eval_{tc_id}"
                turns = tc["multi_turn"]
                t1 = turns[0]
                t2 = turns[1]
                # Turn 1: trigger confirmation
                r1 = self.agent.process_query(t1["query"], session_id=sess_id)
                t1_ok = r1.requires_confirmation == t1.get("expected_requires_confirmation", True)
                # Turn 2: response to decision
                r2 = self.agent.process_query(t2["query"], session_id=sess_id)
                t2_ok = r2.intent == t2.get("expected_intent") and r2.requires_confirmation == t2.get("expected_requires_confirmation", False)
                test_passed = t1_ok and t2_ok
                details = {
                    "turn1_requires_confirmation": r1.requires_confirmation,
                    "turn2_intent": r2.intent,
                    "t1_ok": t1_ok,
                    "t2_ok": t2_ok
                }

            latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
            total_latencies.append(latency_ms)

            if test_passed:
                category_stats[cat]["passed"] += 1
                status_icon = "✅ PASS"
            else:
                category_stats[cat]["failed"] += 1
                status_icon = "❌ FAIL"

            print(f"{status_icon} [{tc_id}] {desc} ({latency_ms}ms)")

            results.append({
                "test_id": tc_id,
                "category": cat,
                "description": desc,
                "passed": test_passed,
                "latency_ms": latency_ms,
                "details": details
            })

        # Calculate Overall Metrics
        total_tests = len(results)
        total_passed = sum(1 for r in results if r["passed"])
        overall_accuracy_pct = round((total_passed / total_tests) * 100, 2) if total_tests else 0
        avg_latency_ms = round(sum(total_latencies) / len(total_latencies), 2) if total_latencies else 0

        scorecard = {
            "timestamp": datetime.now().isoformat(),
            "overall_accuracy_pct": overall_accuracy_pct,
            "total_tests": total_tests,
            "passed": total_passed,
            "failed": total_tests - total_passed,
            "avg_latency_ms": avg_latency_ms,
            "category_breakdown": {
                k: {
                    **v,
                    "accuracy_pct": round((v["passed"] / v["total"]) * 100, 2) if v["total"] else 0
                }
                for k, v in category_stats.items()
            },
            "detailed_results": results
        }

        # Save Artifacts
        self.save_scorecard_and_report(scorecard)

        print("-" * 75)
        print(f"📊 EVALUATION SUMMARY: {total_passed}/{total_tests} Passed ({overall_accuracy_pct}% Score)")
        print(f"⚡ Average Latency: {avg_latency_ms}ms per query")
        print("=" * 75)

        return scorecard

    def save_scorecard_and_report(self, scorecard: Dict[str, Any]):
        evals_dir = os.path.dirname(__file__)

        # 1. Save JSON Scorecard
        json_path = os.path.join(evals_dir, "scorecard.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(scorecard, f, indent=2)

        # 2. Generate Markdown Report
        md_path = os.path.join(evals_dir, "EVAL_REPORT.md")
        rows = []
        for r in scorecard["detailed_results"]:
            mark = "✅ PASS" if r["passed"] else "❌ FAIL"
            rows.append(f"| `{r['test_id']}` | **{r['category']}** | {r['description']} | {mark} | `{r['latency_ms']}ms` |")

        cat_rows = []
        for cat_name, stats in scorecard["category_breakdown"].items():
            cat_rows.append(f"| **{cat_name}** | {stats['total']} | {stats['passed']} | {stats['failed']} | **{stats['accuracy_pct']}%** |")

        report_md = f"""# 📊 AI Agent Evaluation Benchmark Report

**Generated:** {scorecard['timestamp']}  
**Overall Accuracy:** **{scorecard['overall_accuracy_pct']}%**  
**Total Tests:** {scorecard['total_tests']} | **Passed:** {scorecard['passed']} | **Failed:** {scorecard['failed']}  
**Average Execution Latency:** `{scorecard['avg_latency_ms']}ms`

---

## 📈 Category Performance Scorecard

| Category | Total Test Cases | Passed | Failed | Accuracy Rate |
|---|---|---|---|---|
{chr(10).join(cat_rows)}

---

## 🔍 Detailed Test Case Results

| Test ID | Category | Objective | Status | Latency |
|---|---|---|---|---|
{chr(10).join(rows)}

---

## 💡 Evaluation Takeaways

1. **Tool Selection Accuracy**: Evaluates precision of routing across CRM, Relational DB, ITSM, and Vector RAG Knowledge Base.
2. **Input Guardrail Interception**: Ensures 100% defense against prompt injections, system prompt leaks, and destructive SQL queries.
3. **Faithfulness & Hallucination Suppression**: Validates that ungrounded carriers and fake tracking numbers are caught and sanitized.
4. **PII Masking**: Validates that raw payment card numbers are redacted to `[REDACTED-CARD-NUMBER]`.
5. **Session Memory Anaphora**: Validates multi-turn context bridging without forgetting active entities.
6. **Human-in-the-Loop Gating**: Validates that write actions are suspended until explicit human approval is received.
"""
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report_md)


if __name__ == "__main__":
    evaluator = AgentEvaluator()
    evaluator.run_evaluations()
