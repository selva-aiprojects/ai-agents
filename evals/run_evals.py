#!/usr/bin/env python
"""
Command-line runner for Agent Evaluation Benchmark.
Usage:
    python evals/run_evals.py
"""

import os
import sys

# Ensure root directory is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evals.evaluator import AgentEvaluator

if __name__ == "__main__":
    evaluator = AgentEvaluator()
    evaluator.run_evaluations()
