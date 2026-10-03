// Keyboard-first review. J/K move through the queue, A sends, E edits, R rejects, Esc leaves the editor.
(function () {
  const $ = (s) => document.querySelector(s);

  function icons() { if (window.lucide) window.lucide.createIcons({ attrs: { class: "icon" } }); }
  document.addEventListener("DOMContentLoaded", icons);

  // Enviar is enabled only when sending makes sense: a blocked draft must be edited first,
  // a manual reply must not be empty. The server enforces the same rules.
  function guardSend() {
    const form = $("#review-form"), ta = $("#final_text"), send = $("#send-btn");
    if (!form || !ta || !send) return;
    const original = ta.value;
    const update = () => {
      if (form.dataset.manual === "true") send.disabled = !ta.value.trim();
      else if (form.dataset.blocking === "true") send.disabled = ta.value.trim() === original.trim();
    };
    ta.addEventListener("input", update);
    update();
  }
  document.addEventListener("DOMContentLoaded", guardSend);
  document.body.addEventListener("htmx:afterSwap", icons);

  function toggleEdit(force) {
    const draft = $(".draft");
    if (!draft) return;
    const editing = force ?? !draft.classList.contains("editing");
    draft.classList.toggle("editing", editing);
    const btn = $("#edit-btn");
    if (btn) btn.setAttribute("aria-pressed", String(editing));
    if (editing) {
      const ta = $("#final_text");
      ta.focus();
      ta.setSelectionRange(ta.value.length, ta.value.length);
    }
  }
  window.toggleEdit = toggleEdit;

  function submit(decision) {
    const form = $("#review-form");
    if (!form) return;
    const btn = form.querySelector(`button[value="${decision}"]`);
    if (btn && !btn.disabled) btn.click();
  }

  document.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit("send");  // send from inside the editor
      return;
    }
    const typing = ["TEXTAREA", "INPUT", "SELECT"].includes(document.activeElement?.tagName);
    if (typing) {
      if (e.key === "Escape") { document.activeElement.blur(); toggleEdit(false); }
      return;
    }
    const nav = document.body.dataset;
    switch (e.key.toLowerCase()) {
      case "j": if (nav.next) location.href = `/tickets/${nav.next}`; break;
      case "k": if (nav.prev) location.href = `/tickets/${nav.prev}`; break;
      case "a": submit("send"); break;
      case "e": e.preventDefault(); toggleEdit(true); break;
      case "r": submit("reject"); break;
      default: return;
    }
  });
})();
