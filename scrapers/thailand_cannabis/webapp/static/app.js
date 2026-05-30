// Outreach app — front-end glue.
//
// 1. Click-to-WhatsApp: fetch the wa.me URL from /api/whatsapp/<sid>,
//    open it in a new tab, then POST a log entry. Optional template picker.
// 2. tel: / mailto: link clicks just log the action; the browser handles
//    opening the dialer / mail client.
// 3. Edit form on /shop/<sid>: AJAX save against /api/shop/<sid>/update.

(function () {
  "use strict";

  let activeTemplateId = null; // overridden by clicking template-picker buttons

  function logAction(sid, action, detail) {
    return fetch(`/api/shop/${sid}/log`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({action, detail: detail || ""}),
    }).catch((e) => console.warn("log failed", e));
  }

  async function openWhatsApp(sid) {
    try {
      let url = `/api/whatsapp/${sid}`;
      if (activeTemplateId) url += `?template_id=${activeTemplateId}`;
      const res = await fetch(url);
      const data = await res.json();
      if (!res.ok) {
        alert("WhatsApp error: " + (data.error || res.statusText));
        return;
      }
      window.open(data.url, "_blank", "noopener");
      logAction(sid, "whatsapp_opened", `phone=${data.phone_used}`);
      // Visual hint: row briefly highlights
      const row = document.querySelector(`tr[data-sid="${sid}"], .shop-header[data-sid="${sid}"]`);
      if (row) {
        row.style.transition = "background-color .3s";
        row.style.backgroundColor = "#dcfce7";
        setTimeout(() => { row.style.backgroundColor = ""; }, 1200);
      }
    } catch (e) {
      console.error(e);
      alert("WhatsApp failed: " + e.message);
    }
  }

  // Wire up all action buttons (delegation: works for both list and detail pages)
  document.addEventListener("click", function (e) {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const row = btn.closest("[data-sid]");
    const sid = row && row.getAttribute("data-sid");
    if (!sid) return;

    const action = btn.getAttribute("data-action");
    if (action === "whatsapp") {
      e.preventDefault();
      openWhatsApp(sid);
    } else if (action === "call") {
      // browser handles tel: navigation; we just log it
      logAction(sid, "called");
    } else if (action === "email") {
      logAction(sid, "emailed");
    }
  });

  // Template picker on shop detail page
  document.addEventListener("click", function (e) {
    const btn = e.target.closest(".btn-template[data-tid]");
    if (!btn) return;
    activeTemplateId = btn.getAttribute("data-tid");
    document.querySelectorAll(".btn-template").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
  });

  // Outreach form save (shop detail page)
  const outreachForm = document.getElementById("outreach-form");
  if (outreachForm) {
    outreachForm.addEventListener("submit", async function (e) {
      e.preventDefault();
      const sid = outreachForm.getAttribute("data-sid");
      const fd = new FormData(outreachForm);
      const payload = {};
      for (const [k, v] of fd.entries()) payload[k] = v;
      const status = document.getElementById("save-status");
      status.textContent = "Saving...";
      status.classList.remove("error");
      try {
        const res = await fetch(`/api/shop/${sid}/update`, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || res.statusText);
        status.textContent = "Saved ✓";
        setTimeout(() => { status.textContent = ""; }, 2000);
      } catch (e) {
        status.textContent = "Error: " + e.message;
        status.classList.add("error");
      }
    });
  }
})();
