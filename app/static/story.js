// Scene engine for /intro and /presentacion. Spec: docs/specs/story.md
(function () {
  const SEEN = "haddock-cx-intro";
  const scenes = [...document.querySelectorAll(".scene")];
  const dots = [...document.querySelectorAll(".dots button")];
  const kickers = JSON.parse(document.getElementById("kickers").textContent);
  const total = scenes.length;
  const prev = document.getElementById("prev");
  const next = document.getElementById("next");
  const kicker = document.getElementById("kicker");

  const clamp = (n) => Math.min(Math.max(n || 1, 1), total);
  let step = clamp(parseInt(new URLSearchParams(location.search).get("paso"), 10));

  function markSeen() {
    try { localStorage.setItem(SEEN, "1"); } catch (e) { /* storage blocked: skip still works */ }
  }

  function show(n) {
    step = clamp(n);
    scenes.forEach((s, i) => { s.hidden = i !== step - 1; });
    dots.forEach((d, i) => {
      d.classList.toggle("done", i < step - 1);
      if (i === step - 1) d.setAttribute("aria-current", "step"); else d.removeAttribute("aria-current");
    });
    prev.style.visibility = step === 1 ? "hidden" : "visible";
    next.style.visibility = step === total ? "hidden" : "visible";
    kicker.textContent = kickers[step - 1];
    const url = new URL(location.href);
    url.searchParams.set("paso", step);
    history.replaceState(null, "", url);
    if (window.lucide) window.lucide.createIcons({ attrs: { class: "icon" } });
  }

  function finish() { markSeen(); location.href = "/"; }

  prev.addEventListener("click", () => show(step - 1));
  next.addEventListener("click", () => show(step + 1));
  dots.forEach((d) => d.addEventListener("click", () => show(parseInt(d.dataset.go, 10))));
  document.querySelectorAll("[data-finish]").forEach((a) => a.addEventListener("click", markSeen));

  document.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.target instanceof HTMLButtonElement && e.key === "Enter") return;
    if (e.key === "Escape") finish();
    else if (e.key === "ArrowLeft" || e.key === "Backspace") { e.preventDefault(); show(step - 1); }
    else if (e.key === "ArrowRight" || e.key === " " || e.key === "Enter") {
      e.preventDefault();
      if (step === total) finish(); else show(step + 1);
    }
  });

  document.addEventListener("DOMContentLoaded", () => show(step));
  if (document.readyState !== "loading") show(step);
})();
