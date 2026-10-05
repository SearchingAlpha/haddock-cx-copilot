// Code tour at /codigo: colour code and draw Mermaid diagrams when a stop becomes visible.
// Navigation is story.js. Spec: docs/specs/tour.md
import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";

mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "strict",
  fontFamily: getComputedStyle(document.body).fontFamily });

let n = 0;
async function draw(stop) {
  if (stop.hidden || stop.dataset.drawn) return;
  stop.dataset.drawn = "1";
  stop.querySelectorAll("pre code").forEach((el) => window.hljs && window.hljs.highlightElement(el));
  for (const src of stop.querySelectorAll(".mermaid-src")) {
    const { svg } = await mermaid.render(`tour-diagram-${++n}`, src.textContent);
    src.nextElementSibling.innerHTML = svg;
  }
}

const stops = [...document.querySelectorAll(".tour-stop")];
const watch = new MutationObserver((changes) => changes.forEach((c) => draw(c.target)));
stops.forEach((s) => watch.observe(s, { attributes: true, attributeFilter: ["hidden"] }));
window.addEventListener("load", () => stops.forEach(draw));
