---
name: haddock CX copilot
description: Helpdesk agent workspace for reviewing copilot drafts, played straight at Zendesk Agent Workspace craft level.
colors:
  rail: "#03363d"
  rail-ink: "#b8cfd1"
  rail-ink-strong: "#ffffff"
  rail-active: "#0b4a52"
  ground: "#eef1f2"
  pane: "#ffffff"
  wash: "#f6f8f9"
  wash-header: "#f8f9f9"
  line: "#d8dcde"
  line-soft: "#e9ebed"
  line-strong: "#aeb8bd"
  ink: "#2f3941"
  ink-strong: "#17202a"
  muted: "#5c6970"
  agent-gray: "#e3e7e9"
  blue: "#1f73b7"
  blue-hover: "#144a75"
  blue-select: "#e1edf8"
  red: "#b8243a"
  red-tint: "#fff0f1"
  red-line: "#f5b5be"
  red-ink-deep: "#7d1726"
  amber-ink: "#8a4410"
  amber-tint: "#fff7ed"
  amber-line: "#fbcf9a"
  amber-meter: "#e38215"
  meter-neutral: "#8aa6b5"
typography:
  headline:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "22px"
    fontWeight: 600
    letterSpacing: "-0.01em"
  title:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "18px"
    fontWeight: 600
    letterSpacing: "-0.01em"
  title-sm:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    letterSpacing: "-0.01em"
  section:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 600
  body:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
  label:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 600
  mono:
    fontFamily: "ui-monospace, Cascadia Mono, SF Mono, Menlo, Consolas, monospace"
    fontSize: "11px"
    fontWeight: 600
rounded:
  xs: "2px"
  kbd: "3px"
  base: "4px"
  rail: "6px"
  pill: "10px"
  full: "50%"
spacing:
  "4": "4px"
  "6": "6px"
  "8": "8px"
  "10": "10px"
  "12": "12px"
  "16": "16px"
  "24": "24px"
  "32": "32px"
components:
  button:
    backgroundColor: "{colors.pane}"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    padding: "9px 14px"
    typography: "{typography.body}"
  button-hover:
    backgroundColor: "{colors.wash}"
  button-primary:
    backgroundColor: "{colors.blue}"
    textColor: "{colors.pane}"
    rounded: "{rounded.base}"
    padding: "9px 14px"
  button-primary-hover:
    backgroundColor: "{colors.blue-hover}"
  button-danger:
    backgroundColor: "{colors.pane}"
    textColor: "{colors.red}"
    rounded: "{rounded.base}"
    padding: "9px 14px"
  button-danger-hover:
    backgroundColor: "{colors.red-tint}"
  tag:
    backgroundColor: "{colors.pane}"
    textColor: "{colors.muted}"
    rounded: "{rounded.pill}"
    padding: "1px 7px"
    typography: "{typography.label}"
  tag-risk:
    backgroundColor: "{colors.red-tint}"
    textColor: "{colors.red}"
    rounded: "{rounded.pill}"
  tag-check:
    backgroundColor: "{colors.amber-tint}"
    textColor: "{colors.amber-ink}"
    rounded: "{rounded.pill}"
  tag-info:
    backgroundColor: "{colors.wash}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
  banner-risk:
    backgroundColor: "{colors.red-tint}"
    textColor: "{colors.red-ink-deep}"
    rounded: "{rounded.base}"
    padding: "12px 14px"
  banner-check:
    backgroundColor: "{colors.amber-tint}"
    textColor: "{colors.amber-ink}"
    rounded: "{rounded.base}"
    padding: "12px 14px"
  banner-info:
    backgroundColor: "{colors.wash}"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    padding: "12px 14px"
  queue-row:
    backgroundColor: "{colors.pane}"
    textColor: "{colors.ink}"
    padding: "10px 16px"
  queue-row-hover:
    backgroundColor: "{colors.wash}"
  queue-row-selected:
    backgroundColor: "{colors.blue-select}"
  message-card:
    backgroundColor: "{colors.pane}"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    padding: "14px 16px"
  rail-link:
    backgroundColor: "{colors.rail}"
    textColor: "{colors.rail-ink}"
    rounded: "{rounded.rail}"
    size: "40px"
  rail-link-active:
    backgroundColor: "{colors.rail-active}"
    textColor: "{colors.rail-ink-strong}"
  avatar-copilot:
    backgroundColor: "{colors.rail}"
    textColor: "{colors.rail-ink-strong}"
    rounded: "{rounded.full}"
    size: "28px"
  avatar-agent:
    backgroundColor: "{colors.agent-gray}"
    textColor: "{colors.ink}"
    rounded: "{rounded.full}"
    size: "28px"
  select:
    backgroundColor: "{colors.pane}"
    textColor: "{colors.ink}"
    rounded: "{rounded.base}"
    padding: "6px 28px 6px 10px"
---

# Design System: haddock CX copilot

## Overview

**Creative North Star: "The Agent Workspace, Played Straight"**

This is the helpdesk category standard on purpose, held to the craft bar of Zendesk Agent Workspace. One screen carries the whole decision: a dark teal product rail, a queue column, the ticket workspace, and a customer context panel. The conventions are embraced, not parodied; an agent who has worked in any modern helpdesk should be productive in the first minute.

The world is light, dense and quiet, built for eight hours of daytime reading in an office. White working panes sit on a cool gray ground, separated by 1px hairlines, never by shadows. Color is a signal vocabulary, not decoration: one blue means "act or selected", red means risk, amber means "check this", and everything routine stays in plain gray text. The copilot shares the product's teal; the human agent is neutral gray.

The interface refuses the card-and-badge admin template and any decorative AI theatre: no gradients, glows, sparkle washes or chat-bubble playfulness. The draft is shown exactly as the customer will read it.

**Key Characteristics:**
- Four-column shell: 56px rail, 340px queue, fluid workspace, 360px context panel.
- One system UI face at 14px, tabular numerals everywhere; monospace only for IDs, keys and tool names.
- Flat panes, 1px dividers, 4px radii.
- Color carries meaning only: blue action, red risk, amber check; routine is muted text.
- Keyboard-first: every primary action shows its key (A, E, R, J, K, Esc).

## Colors

A cool, low-chroma neutral field with one deep teal anchor and three strictly-scoped signal hues.

### Primary
- **Deep Helpdesk Teal** (rail): the product rail and the copilot avatar. It names the product and the copilot as one thing. Rail icons sit in **Rail Mist** (rail-ink) and go white with **Rail Teal Active** (rail-active) behind them on hover and current page.
- **Action Blue** (blue): the primary button, links, focus ring and the spinner's leading edge. Darkens to **Action Blue Deep** (blue-hover) on hover. **Selection Blue Wash** (blue-select) marks the currently open queue row.

### Secondary
- **Risk Red** (red): urgent priority dot, risk tags, the danger button's text, risk evidence titles. Banners use **Risk Wash** (red-tint) with **Risk Hairline** (red-line) and the darker **Risk Ink** (red-ink-deep) for readable body text.

### Tertiary
- **Check Amber Ink** (amber-ink) on **Check Wash** (amber-tint) with **Check Hairline** (amber-line): the "Revisar categoría" tag and banner, and the category select when its value needs review. **Meter Amber** (amber-meter) fills a confidence meter below 60%.

### Neutral
- **Cool Gray Ground** (ground): the page behind panes.
- **Pane White** (pane): queue, workspace headers, messages, context panel, tables.
- **Hover Wash** (wash): row and button hover, neutral info tags and banners. **Header Wash** (wash-header) sits behind table headers and keycaps.
- **Hairline** (line) for pane and card borders; **Soft Hairline** (line-soft) for dividers inside a pane; **Strong Hairline** (line-strong) for pressed buttons and cited evidence.
- **Slate Ink** (ink) body text, **Near-Black Ink** (ink-strong) headings and values, **Muted Slate** (muted, 5.3:1 on white) for metadata, labels and routine states.
- **Agent Gray** (agent-gray): the human agent's avatar.
- **Steel Meter** (meter-neutral): a confidence meter at or above 60%.

### Named Rules
**The One Blue Rule.** Blue means action, selection or focus, and nothing else. Informational tags and banners are neutral gray, never blue.

**The Red Means Risk Rule.** Red appears only where something can hurt the customer or the business: escalation, urgent priority, failed payment or integration, blocking guardrails, the reject action.

**The Amber Means Check Rule.** Amber appears only for "check this": a category to review and a low-confidence meter. It is never a softer red.

**The Quiet Routine Rule.** Routine and OK states are plain muted text ("Al día", "conectado", "Listo para revisar"). Never a green pill, never a success badge.

**The Never Color Alone Rule.** Risk is always an icon plus a text label, never color alone.

**The Teal Is the Product Rule.** Teal belongs to the rail and the copilot avatar. The human agent mark is neutral gray, so who wrote a message reads at a glance.

## Typography

**Body Font:** system-ui (with -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial)
**Label/Mono Font:** ui-monospace (with Cascadia Mono, SF Mono, Menlo, Consolas)

**Character:** One native UI face, set dense and calm, with tabular numerals so ages, percentages and amounts align. Monospace is a data marker, not a voice.

### Hierarchy
- **Headline** (600, 22px, -0.01em): the page title on full-width pages (Impacto).
- **Title** (600, 18px, -0.01em): the ticket subject in the workspace header, empty-state headings, ledger values.
- **Title Small** (600, 16px): the queue heading. Secondary page headings run at 15px.
- **Section** (600, 13px): context-panel section headings, each led by a 16px line icon.
- **Body** (400, 14px, 1.5): everything readable. Customer messages and drafts cap at 70ch; the draft editor uses 1.6 line height.
- **Label** (600, 12px): queue group headers, tag text, table headers, metadata; sentence case, never uppercase. Evidence kinds drop to 11px.
- **Mono** (600, 11–12px): ticket and evidence IDs, keycaps, tool names in the agent trail, step numbers.

### Named Rules
**The One Face Rule.** One system UI family for all text. No display face, no uppercase tracking, no italics for emphasis.

**The Tabular Numbers Rule.** `tabular-nums` is set on the body; every number in the product aligns.

## Layout

A full-height grid shell: rail 56px, queue 340px, workspace `minmax(0, 1fr)`, context 360px. Pages without context (home, metrics) drop the fourth column. Each column scrolls on its own; the composer bar is pinned to the bottom of the workspace.

Inside the workspace, content is centered with a 760px maximum width and 16px gaps between blocks; full-width pages cap at 920px. Padding: workspace header 14px 24px, workspace body 20px 24px, context sections 16px 18px, queue rows 10px 16px. The rhythm runs in small steps (4, 6, 8, 10, 12, 16, 24, 32px) for density.

Responsive: at 1280px the queue narrows to 300px and context to 320px. At 1080px the context panel leaves the shell and renders inline under the draft. At 760px the shell becomes one column with a 52px horizontal rail on top; the queue and the ticket become separate views, with a back arrow in the ticket header and the keyboard hints hidden.

## Elevation & Depth

Flat. Panes are separated by 1px hairlines and by the white-on-gray tonal step between pane and ground. No pane, card or message casts a shadow. Box-shadow appears only for state.

### Shadow Vocabulary
- **Focus ring** (`box-shadow: 0 0 0 3px rgba(31, 115, 183, 0.35)`): every `:focus-visible` element.
- **Editor focus** (`box-shadow: inset 0 0 0 2px rgba(31, 115, 183, .45)`): the draft textarea while focused.
- **Pressed toggle** (`box-shadow: inset 0 1px 2px rgba(23, 32, 42, .12)`): a button with `aria-pressed="true"` (Editar while editing).

### Named Rules
**The Flat Panes Rule.** Depth comes from hairlines and the ground-to-pane step. Shadows only answer focus or a pressed state.

## Shapes

Small, even corners: 4px on buttons, messages, banners, evidence items, tables, selects and focus rings. Rail links and the product mark use 6px. Tags are soft pills (10px). Avatars and priority dots are circles. Keycaps are 3px with a 2px bottom border so they read as keys. Meters are 4px tall bars with 2px ends. Borders are 1px throughout.

## Components

### Buttons
Plain, firm and keyboard-labelled.
- **Shape:** gently squared (4px), 600 weight 14px, 9px 14px padding, 8px gap to a 16px line icon.
- **Default:** white with a hairline border and slate ink; hover goes to Hover Wash.
- **Primary:** Action Blue fill and border with white text; hover darkens to Action Blue Deep. Exactly one per decision (Enviar, "Abrir el primero").
- **Danger:** white with Risk Red text and Risk Hairline border; hover gains the Risk Wash.
- **Pressed toggle:** a light gray fill, Strong Hairline border and a faint inset shadow.
- **Disabled:** 50% opacity, not-allowed cursor; the title explains why.
- **Keycaps:** each composer button ends with its key (A, E, R).

### Tags
- **Style:** 12px pill (10px radius), 1px border, 12px icon before the text.
- **Neutral:** white, hairline, muted text, for process states (Investigando, En proceso, Citada).
- **Risk:** Risk Wash, Risk Hairline, Risk Red text, with an alert icon (Escalado, Fallido, integration errors).
- **Check:** Check Wash, Check Hairline, Check Amber Ink (Revisar categoría).
- **Info:** Hover Wash with ink text (Manual). Deliberately not blue.

### Banners
A full-width notice above the draft: icon on the left, a bold sentence-case lead, then detail or a reason list. Red by default (blocked or escalated, `role="alert"`), amber for "check this", neutral gray for info (manual mode, already decided).

### Cards / Containers
- **Corner Style:** 4px.
- **Background:** Pane White on the gray ground.
- **Shadow Strategy:** none (see Elevation & Depth).
- **Border:** 1px Hairline outside; a Soft Hairline divides a message header from its body.
- **Internal Padding:** 12px 16px headers, 14px 16px bodies.

### Inputs / Fields
- **Select:** white, hairline border, 4px radius, 6px 10px padding with room for the arrow. Under "check this" it takes the amber wash and hairline.
- **Draft editor:** borderless textarea inside the draft message, faint off-white fill, 320px minimum height, inset blue ring on focus.

### Navigation
- **Rail:** Deep Helpdesk Teal, 40px icon-only links (20px icons) with screen-reader labels and titles. Current page and hover share the Rail Teal Active fill and white icon. A pale pill count sits top-right on Cola. On mobile the rail turns horizontal at 52px.
- **Queue:** grouped by state (Escalados, Listos, En proceso, then collapsed Enviados and Rechazados) under 12px muted summary headers with a rotating chevron. Rows show a priority dot, bold customer, age, muted one-line subject, then tags and a muted ID and channel line. Hover is Hover Wash; the open ticket is Selection Blue Wash.

### Message and Draft
The customer message and the copilot draft share one shape: an avatar, a bold name with muted context, and muted channel or time on the right. The customer avatar is a muted-slate initial; the copilot avatar is a teal circle with a sparkles icon; the human agent's avatar is Agent Gray with a pen icon. The draft renders as the customer will read it, with lists and bold text.

### Context Panel
Sections split by Soft Hairlines: customer facts in a two-column key/value list (96px muted keys, strong values); classification as label, value, percent and a 4px meter (Steel above 60%, Meter Amber below); evidence as collapsible bordered items (kind, "Citada" tag, mono ID, bold title; cited items get the Strong Hairline, risky ones a red title); and the agent trail as a numbered mono list.

### Ledger Table
Metrics live in a bordered white table: 12px muted headers on Header Wash, 18px 600 values, and a muted "basis" column so every number shows how it was computed.

## Do's and Don'ts

### Do:
- **Do** keep the four-column shell (56 / 340 / fluid / 360px) and let each column scroll on its own.
- **Do** use Action Blue only for the one primary action, links, selection and focus.
- **Do** pair every risk color with an icon and a text label.
- **Do** write routine and OK states as muted text.
- **Do** separate surfaces with 1px hairlines and the gray-to-white step, at 4px radius.
- **Do** show the keyboard key on every action that has one.
- **Do** use monospace only for IDs, keys, tool names and step numbers.

### Don't:
- **Don't** use blue for information or status; neutral gray carries info.
- **Don't** use green pills or success badges for routine states.
- **Don't** use red for anything that is not risk, or amber for anything that is not "check this".
- **Don't** put shadows on panes, cards or messages.
- **Don't** give the human agent the teal; teal belongs to the product and the copilot.
- **Don't** add a second typeface, uppercase labels, gradients or decorative AI effects.
