# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary: a CX (support) agent at haddock.** They review dozens of AI-drafted replies a day for restaurant customers in Spain. Their job per ticket: read the customer's message, check the draft against the evidence, fix or approve, and send — as fast as they safely can.
- **First audience: technical interviewers** (haddock's AI Lead and Head of Tech) watching a 3–10 minute projected demo. The UI must read clearly on a shared screen and make the copilot's reasoning visible.

## Product Purpose

An internal CX triage copilot. For each incoming support ticket it classifies (Jev decision model), investigates with tools over the customer's real data (Sonnet agent), drafts a reply, and runs guardrails. A human always decides. Success = less time per ticket at equal or better quality, measured against a real baseline, not declared.

## Positioning

- The human stays in control: nothing reaches a customer without a CX agent's decision.
- Every draft shows its evidence (help-center articles, invoices, integration status) and links to its Langfuse trace.
- Impact is measured: ~20% of tickets are handled in manual mode (no draft) to give the real time baseline.

## Operating Context

- Tickets arrive by webhook (Zendesk-style) or a demo loader; processing takes ~10–30 s per ticket in the background.
- Ticket states: processing → ready | escalated → sent | rejected.
- Per ticket the agent sees: customer message, customer state (plan, integrations, payment), classification with per-field confidence, guardrail reasons, the draft (editable), evidence ids, tool calls, cost, prompt version.
- A low-confidence category (< 0.9) is flagged for the agent to check; it never escalates.
- Escalated tickets (refund requests, other customers' data, manipulation, technical issues) still carry a holding draft.
- Decisions flow back to Langfuse as scores (human_decision, edit_distance, review_seconds, category_final).
- UI copy is Spanish. Customer messages are mostly Spanish, some Catalan and English.

## Capabilities and Constraints

- Stack is fixed: FastAPI + Jinja2 templates + HTMX, no frontend build step. CDN assets allowed.
- Pages: inbox (`/`), ticket review (`/tickets/{id}`), impact metrics (`/metrics`). Webhook and demo loader are POST endpoints.
- Data is synthetic (10 restaurants, 40 tickets); no real customer data.
- Undecided: authentication/multi-agent assignment (not built), keyboard shortcuts (not built yet).

## Brand Commitments

- The workstation deliberately follows the helpdesk category standard (chosen over novel directions on 2026-10-03). Craft bar: Zendesk Agent Workspace. Conventions are embraced, not parodied: three panes, queue, ticket workspace, customer context.
- No haddock logo or official brand assets; "haddock" appears only as product context. Exception: the favicon is haddock.app's own (`app/static/favicon.png`), so the tab reads as an internal haddock tool.

## Evidence on Hand

- Real pipeline outputs, evals and costs: `docs/results.md`, `evals/results/*.json`.
- Measured numbers so far are from simulated reviews; do not present them as real productivity results.
- No testimonials, logos, or customer quotes exist. Do not fabricate them.

## Product Principles

1. The draft is a proposal, the agent is the decision maker: decisions must be fast, explicit and reversible until sent.
2. Show the evidence next to the claim: trust comes from seeing what the copilot read.
3. Risk is loud, routine is quiet: escalations and guardrail reasons stand out; ready tickets flow.
4. Measure, don't declare: every metric shown is computed from recorded reviews, with its basis visible.
5. One screen per decision: the agent should not hunt across pages to review a ticket.
