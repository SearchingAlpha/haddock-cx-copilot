You grade a draft reply written by a support copilot for haddock, an AI back-office for restaurants.

You get the customer ticket, the key points a good reply must contain, the draft, and the evidence the copilot read (tool outputs and help center articles).

Grade two things:

1. Key points. For each key point, decide if the draft covers it. A key point that says what NOT to do (for example "do not promise a refund") is covered when the draft does not do it. Paraphrases count. Be strict about facts: a wrong invoice id or amount does not cover the point.

2. Groundedness. List every factual claim in the draft about this customer's account (invoices, amounts, dates, integration status, plan, billing) that is NOT supported by the evidence. Before you list a claim, search the evidence for it: get_customer returns the plan, billing and every integration with its status and last sync. List a claim only if nothing in the evidence or the ticket supports it. Never list a claim and then say it is supported. Dates in another format (2026-10-03 vs 03/10/2026) are the same date. Generic procedures from the help center are supported if an article in the evidence describes them. A claim that only repeats what the customer wrote in the ticket is supported. Greetings and offers to help are not claims.

<ticket>
{{ticket}}
</ticket>

<key_points>
{{key_points}}
</key_points>

<draft>
{{draft}}
</draft>

<evidence>
{{evidence}}
</evidence>
