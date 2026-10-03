"""Model ids, thresholds and prices in one place."""

# Classifier: Jev decision model (pinned version) with Haiku as fallback. Spec: docs/specs/classify.md
JEV_MODEL = "typesafe:jev-1.13.0"
FALLBACK_CLASSIFIER_MODEL = "anthropic:claude-haiku-4-5"

# Agent: manual tool-use loop. Spec: docs/specs/agent.md
AGENT_MODEL = "claude-sonnet-5-5"
AGENT_MAX_TOKENS = 8000  # effort lives in the Langfuse prompt config (app/prompts.py)
MAX_AGENT_ITERATIONS = 6

# Below this classifier confidence on `category`, the UI asks the CX agent to check the category.
# It never escalates: escalating on it caused 1-2 wrong escalations per run (docs/results.md).
# 0.9: above it Jev was right 97% of the time in every run.
CATEGORY_REVIEW_CONFIDENCE = 0.9

# USD per million tokens, for cost_details in Langfuse.
PRICES_PER_MTOK = {
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_write": 2.50},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00, "cache_read": 0.10, "cache_write": 1.25},
}

# Haiku as judge agreed with Sonnet on only 56% of groundedness verdicts (evals/rejudge.py): too noisy.
JUDGE_MODEL = "claude-sonnet-5-5"
