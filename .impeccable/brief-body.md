# Surface: CX review workstation (app/templates)

Mode: Operate. Users: haddock CX agent reviewing AI drafts all day; first shown in a projected interview demo.
Task: clear the queue — verify evidence, decide (send as is / edit / reject), move to next. Risk must be loud, routine quiet.
Confirmed needs: evidence verification beside the draft, keyboard speed, visible risk, draft rendered as the customer will see it. Inbox is a work queue. Avoid: over-decoration, toy feel.
Constraints: FastAPI + Jinja2 + HTMX, no build step; Spanish UI copy.

## Direction contract

THESIS: The helpdesk agent workspace, played straight at Zendesk craft level: queue, ticket, context in one screen. Refuses the card-and-badge admin template and any decorative AI theatre.

OWN-WORLD: Dark deep-teal product rail, white working panes on a cool gray ground, one blue for primary action, red only for risk, amber only for "check this". One system UI face, tabular numerals, 1px dividers, 4px radii, no shadows on panes.

STORY: The agent sees what needs a decision first, reads the customer, sees the draft exactly as sent, checks every cited fact in the context panel, decides with one key, and lands on the next ticket.

FIRST VIEWPORT: Left 56px rail (Cola, Impacto). Queue column 340px: grouped Escalados / Listos / En proceso / Enviados, rows with priority, customer, subject, age. Center: ticket header, customer message, copilot draft as rendered reply with guardrail banner above it, composer actions pinned bottom (Enviar · Editar · Rechazar, keys A/E/R, J/K). Right 360px: customer, classification with confidence, evidence items expandable, agent trail.

FORM: Category standard (canon), chosen by the user over the roll; seed key 40ec98bf.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
