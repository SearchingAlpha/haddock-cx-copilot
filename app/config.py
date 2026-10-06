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

# Product radar. Spec: docs/specs/radar.md
SIGNAL_MODEL = JEV_MODEL  # component and kind: typed decisions
SYMPTOM_MODEL = FALLBACK_CLASSIFIER_MODEL  # one normalized sentence: generative, so Haiku
MATCH_MODEL = JEV_MODEL  # "same product problem?" yes/no per candidate; Haiku as fallback
# A "yes" below it opens a new problem. Spike (scripts/hello_radar_match.py): Jev 20/20 right, but its
# right "yes" answers had confidence 0.46-0.82, so 0.8 would split almost every problem.
RADAR_MATCH_CONFIDENCE = 0.4
RADAR_BM25_TOP_K = 3  # candidates per ticket sent to the matcher
RADAR_PROBLEM_SYMPTOMS = 10  # a problem's document: its title and its last N symptoms
# A problem becomes a candidate with 3 customers, or with 2 customers whose MRR adds up to 400 EUR.
# One enterprise customer alone (420-700 EUR) is never enough: one voice is not a pattern.
RADAR_THRESHOLD = {"customers": 3, "mrr_eur": 400.0, "mrr_min_customers": 2}
TREND_WINDOW_DAYS = 7

# Product requests and the closed loop. Specs: docs/specs/product-request.md, github.md, notify.md
REQUEST_MODEL = AGENT_MODEL  # writes the GitHub issue: generative, grounded on the tickets
NOTICE_MODEL = AGENT_MODEL  # writes one proactive notice per affected customer
REQUEST_MAX_TICKETS = 12  # tickets Sonnet reads per request: the first 3 and the last 9
GITHUB_API = "https://api.github.com"
