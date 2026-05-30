"""Final aggregation step: join scraped emails into the country dataset,
recompute reachability (phone OR email OR contactable URL), and regenerate
the final HTML report.

Produces:
  data/hospitality_country_final.csv  — full dataset + scraped_emails column
  data/reachable_country_final.csv    — only rows with at least one contact
  data/report_country_final.html      — top-N HTML for the user
  data/contact_list_country.csv       — slim CSV: name,city,phone,email,website,
                                         fb_url,maps_url,score — the outreach list
"""

import argparse
import csv
import html
import os
import re
import sys
from collections import Counter
from datetime import datetime
from urllib.parse import quote


def wa_format(phone: str) -> str:
    """Convert a Thai phone string to wa.me-compatible international form.

    Thai mobiles are 10 digits starting with 0; landlines are 9 digits starting with 0.
    Strip non-digits, drop the leading 0, prepend 66 (Thailand country code).
    Already-international (+66xxx) numbers pass through.
    """
    if not phone:
        return ""
    digits = re.sub(r"[^\d+]", "", phone)
    if digits.startswith("+"):
        digits = digits[1:]
    if digits.startswith("66"):
        return digits
    if digits.startswith("0"):
        return "66" + digits[1:]
    return digits

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def load_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def has_contact(r: dict) -> bool:
    return bool(
        (r.get("phone") or "").strip()
        or (r.get("scraped_emails") or r.get("email") or "").strip()
        or (r.get("website") or "").strip()
        or (r.get("fb_search_url") or "").strip()
        or (r.get("detail_url") or "").strip()
    )


def gmaps_url(name: str, city: str) -> str:
    return f"https://www.google.com/maps/search/{quote(name + ' ' + city)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--top", type=int, default=300, help="Top-N in HTML report")
    args = parser.parse_args()

    country = load_csv(os.path.join(DATA_DIR, "hospitality_country.csv"))
    emails = load_csv(os.path.join(DATA_DIR, "emails_country.csv"))
    print(f"[final] {len(country):,} country rows  |  {len(emails):,} email lookups")

    # Join emails by src_id
    emails_by_sid = {e["src_id"]: e for e in emails if e.get("src_id")}
    matched = 0
    for r in country:
        sid = r.get("src_id")
        if sid in emails_by_sid:
            r["scraped_emails"] = emails_by_sid[sid].get("scraped_emails", "")
            if r["scraped_emails"]:
                matched += 1
        else:
            r["scraped_emails"] = ""
    print(f"[final] {matched:,} country rows now have scraped emails")

    # Update score: +1 if has scraped_emails
    for r in country:
        if r.get("scraped_emails"):
            try:
                raw = int(r.get("lead_raw") or 0)
                r["lead_raw"] = str(raw + 1)
                r["lead_quality"] = str(min(10, round((raw + 1) * 10 / 14)))
                r["score_factors"] = (r.get("score_factors") or "") + " ; +1 scraped email"
            except (ValueError, TypeError):
                pass

    # Re-sort
    country.sort(key=lambda r: -int(r.get("lead_raw") or 0))

    # Write enriched country CSV
    if country:
        fields = list(country[0].keys())
        if "scraped_emails" not in fields:
            fields.append("scraped_emails")
        out = os.path.join(DATA_DIR, "hospitality_country_final.csv")
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in country:
                w.writerow({k: r.get(k, "") for k in fields})
        print(f"[final] wrote {out}")

    # Reachable subset
    reachable = [r for r in country if has_contact(r)]
    out_reach = os.path.join(DATA_DIR, "reachable_country_final.csv")
    if reachable:
        with open(out_reach, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in reachable:
                w.writerow({k: r.get(k, "") for k in fields})
        print(f"[final] wrote {out_reach} ({len(reachable):,} rows)")

    # Slim contact list — the actual outreach CSV
    contact_fields = ["rank", "name", "category", "city", "phone", "emails",
                      "website", "fb_search_url", "maps_url", "score", "lat", "lng"]
    out_contact = os.path.join(DATA_DIR, "contact_list_country.csv")
    with open(out_contact, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=contact_fields)
        w.writeheader()
        for i, r in enumerate(reachable, 1):
            name = r.get("name", "")
            city = r.get("_city_slug", "")
            w.writerow({
                "rank": i,
                "name": name,
                "category": r.get("category_raw") or r.get("subcategory") or "",
                "city": city,
                "phone": r.get("phone", ""),
                "emails": r.get("scraped_emails", ""),
                "website": r.get("website", ""),
                "fb_search_url": r.get("fb_search_url", ""),
                "maps_url": gmaps_url(name, city) if name else "",
                "score": r.get("lead_quality", ""),
                "lat": r.get("lat", ""),
                "lng": r.get("lng", ""),
            })
    print(f"[final] wrote {out_contact}")

    # Stats
    print(f"\n=== SUMMARY ===")
    print(f"Total unique businesses:  {len(country):,}")
    print(f"Reachable (any channel):  {len(reachable):,}")
    print(f"With phone:               {sum(1 for r in reachable if (r.get('phone') or '').strip()):,}")
    print(f"With scraped email:       {sum(1 for r in reachable if (r.get('scraped_emails') or '').strip()):,}")
    print(f"With real website:        {sum(1 for r in reachable if (r.get('website') or '').strip() and not 'facebook' in (r.get('website') or '').lower()):,}")
    print(f"Score 5+:                 {sum(1 for r in reachable if r.get('lead_quality') and int(r['lead_quality']) >= 5):,}")
    print(f"Score 7+:                 {sum(1 for r in reachable if r.get('lead_quality') and int(r['lead_quality']) >= 7):,}")
    cities = Counter(r.get("_city_slug", "?") for r in reachable)
    print(f"\nPer-city reachable:")
    for c, n in cities.most_common():
        print(f"  {n:>5}  {c}")

    # HTML report
    top = reachable[: args.top]
    rows_html = ""
    for i, r in enumerate(top, 1):
        sid = esc(r.get("src_id") or f"row-{i}")
        raw_name = r.get("name", "?")
        name = esc(raw_name)
        cat = esc(r.get("category_raw") or r.get("subcategory") or "?")
        city = esc(r.get("_city_slug", ""))
        raw_phone = r.get("phone", "")
        phone = esc(raw_phone) or "&mdash;"
        wa_num = wa_format(raw_phone)
        wa_btn = ""
        if wa_num:
            wa_btn = (f'<button type="button" class="btn-wa" data-action="whatsapp" '
                      f'data-sid="{sid}" data-wa="{esc(wa_num)}" '
                      f'data-name="{name}" data-city="{city}" '
                      f'title="Open WhatsApp Web with pre-filled message">WA</button>')
        emails_raw = r.get("scraped_emails", "") or ""
        emails_html = ""
        if emails_raw:
            first_email = emails_raw.split(";")[0].strip()
            emails_html = (f'<a href="mailto:{esc(first_email)}" title="{esc(emails_raw)}">'
                           f'{esc(first_email[:30])}</a>')
        else:
            emails_html = "&mdash;"
        website = r.get("website") or ""
        website_html = (f'<a href="{esc(website)}" target="_blank" rel="noopener">'
                        f'{esc(website[:35])}{"..." if len(website) > 35 else ""}</a>'
                        if website else "&mdash;")
        try:
            q = int(r.get("lead_quality", "0"))
        except ValueError:
            q = 0
        q_cls = "hi" if q >= 5 else "mid" if q >= 3 else "lo"
        maps_url_str = gmaps_url(r.get("name", ""), city)
        gmaps_html = f'<a href="{esc(maps_url_str)}" target="_blank" rel="noopener">Maps</a>'
        fb_html = ""
        fb_url = r.get("fb_search_url") or ""
        if fb_url:
            fb_html = f' &middot; <a href="{esc(fb_url)}" target="_blank" rel="noopener">FB</a>'
        detail_html = ""
        detail_url = r.get("detail_url") or ""
        if detail_url:
            detail_html = f' &middot; <a href="{esc(detail_url)}" target="_blank" rel="noopener">Wongnai</a>'
        rows_html += f"""
        <tr data-sid="{sid}" data-name="{name}" data-city="{city}">
          <td class="rank">{i}</td>
          <td><span class="qbadge q-{q_cls}">{q}</span></td>
          <td><strong>{name}</strong><div class="meta">{cat}</div></td>
          <td>{city}</td>
          <td class="nowrap">{phone} {wa_btn}</td>
          <td class="nowrap">{emails_html}</td>
          <td>{website_html}</td>
          <td class="nowrap">{gmaps_html}{fb_html}{detail_html}</td>
          <td class="notes-cell">
            <span class="status-badge" data-sid="{sid}"></span>
            <textarea class="note-input" data-sid="{sid}" rows="1"
                      placeholder="add note..."></textarea>
          </td>
        </tr>
        """

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    out_html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<title>Thailand hospitality — final country contact list</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; margin: 0;
         background: #f5f7f5; color: #1a1a2e; font-size: 14px; line-height: 1.5; }}
  .header {{ background: #0d2818; color: #e6f4ec; padding: 22px 28px; }}
  .header h1 {{ margin: 0 0 4px; color: white; font-size: 22px; }}
  .header p  {{ margin: 0; opacity: 0.85; font-size: 13px; }}
  .page {{ padding: 22px 24px; max-width: 1700px; margin: 0 auto; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 12px; margin-bottom: 18px; }}
  .stat {{ background: white; padding: 12px 16px; border-radius: 8px;
           box-shadow: 0 1px 2px rgba(0,0,0,.05); border-left: 4px solid #22c55e; }}
  .stat-val {{ font-size: 1.8em; font-weight: 700; line-height: 1; color: #0d2818; }}
  .stat-lbl {{ font-size: 11px; color: #555; text-transform: uppercase;
               letter-spacing: 0.8px; margin-top: 4px; }}
  .stat.warn {{ border-left-color: #f59e0b; }}
  .stat.dim  {{ border-left-color: #94a3b8; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px;
           overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,.05); }}
  th, td {{ padding: 8px 11px; text-align: left; border-bottom: 1px solid #eaeaea; }}
  th {{ background: #f3f4f6; font-weight: 600; font-size: 11px;
        text-transform: uppercase; letter-spacing: 0.5px; color: #4b5563; }}
  tr:hover {{ background: #fafafa; }}
  td.rank {{ font-weight: 700; color: #94a3b8; }}
  td.nowrap {{ white-space: nowrap; }}
  .qbadge {{ display: inline-block; width: 28px; text-align: center;
             padding: 2px 0; border-radius: 4px; font-weight: 700; font-size: 13px; }}
  .q-hi {{ background: #dcfce7; color: #14532d; }}
  .q-mid {{ background: #fef3c7; color: #78350f; }}
  .q-lo {{ background: #f1f5f9; color: #64748b; }}
  .meta {{ font-size: 11px; color: #64748b; margin-top: 2px; }}
  a {{ color: #15803d; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .callout {{ background: #eff6ff; border: 1px solid #93c5fd; border-radius: 6px;
              padding: 10px 14px; margin-bottom: 18px; font-size: 13px; }}

  /* === Interactive: WhatsApp + notes === */
  .toolbar {{ background: white; padding: 12px 16px; border-radius: 8px;
              box-shadow: 0 1px 2px rgba(0,0,0,.05); margin-bottom: 16px;
              display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
  .toolbar label {{ font-size: 12px; color: #555; font-weight: 600;
                    text-transform: uppercase; letter-spacing: 0.5px; }}
  .toolbar textarea {{ flex: 1; min-width: 300px; padding: 6px 10px;
                       border: 1px solid #cbd5e1; border-radius: 5px;
                       font-family: inherit; font-size: 13px; resize: vertical; min-height: 32px; }}
  .toolbar .btn {{ padding: 6px 14px; border-radius: 5px; font-size: 12px;
                   font-weight: 600; cursor: pointer; border: 1px solid #cbd5e1;
                   background: white; color: #475569; }}
  .toolbar .btn:hover {{ background: #f1f5f9; }}
  .toolbar .btn-primary {{ background: #15803d; color: white; border-color: #15803d; }}
  .toolbar .btn-primary:hover {{ background: #166534; }}
  .toolbar .saved-count {{ font-size: 12px; color: #64748b; margin-left: auto; }}

  .btn-wa {{ background: #25d366; color: white; border: none; border-radius: 4px;
             padding: 3px 9px; font-size: 11px; font-weight: 700; cursor: pointer;
             margin-left: 6px; line-height: 1.4; }}
  .btn-wa:hover {{ background: #128c7e; }}

  td.notes-cell {{ min-width: 200px; max-width: 260px; }}
  td.notes-cell textarea.note-input {{ width: 100%; padding: 4px 8px;
                                       border: 1px solid #e5e7eb; border-radius: 4px;
                                       font-family: inherit; font-size: 12px;
                                       resize: vertical; min-height: 28px;
                                       background: #fafafa; color: #1a1a2e; }}
  td.notes-cell textarea.note-input:focus {{ outline: none;
                                             border-color: #15803d; background: white;
                                             box-shadow: 0 0 0 2px rgba(21,128,61,0.1); }}
  td.notes-cell textarea.note-input.has-note {{ background: #fef9c3;
                                                border-color: #fde68a; }}
  .status-badge {{ display: inline-block; font-size: 10px; font-weight: 700;
                   padding: 1px 6px; border-radius: 3px; margin-bottom: 2px;
                   color: #15803d; background: #dcfce7; }}
  .status-badge:empty {{ display: none; }}
  .row-contacted {{ background: #f0fdf4 !important; }}
</style>
</head><body>
  <div class="header">
    <h1>Thailand hospitality &mdash; country contact list</h1>
    <p>{len(reachable):,} reachable businesses across {len(cities)} cities.
       Top {len(top)} shown. Generated {generated}.</p>
  </div>
  <div class="page">
    <div class="callout">
      Files: <code>hospitality_country_final.csv</code> ({len(country):,} all rows),
      <code>reachable_country_final.csv</code> ({len(reachable):,} reachable),
      <code>contact_list_country.csv</code> (slim outreach CSV).
    </div>
    <div class="stats">
      <div class="stat"><div class="stat-val">{len(country):,}</div><div class="stat-lbl">Total unique</div></div>
      <div class="stat"><div class="stat-val">{len(reachable):,}</div><div class="stat-lbl">Reachable</div></div>
      <div class="stat"><div class="stat-val">{sum(1 for r in reachable if (r.get('phone') or '').strip()):,}</div><div class="stat-lbl">With phone</div></div>
      <div class="stat"><div class="stat-val">{sum(1 for r in reachable if (r.get('scraped_emails') or '').strip()):,}</div><div class="stat-lbl">With email</div></div>
      <div class="stat warn"><div class="stat-val">{sum(1 for r in reachable if r.get('lead_quality') and int(r['lead_quality']) >= 5):,}</div><div class="stat-lbl">Score 5+</div></div>
      <div class="stat dim"><div class="stat-val">{len(cities)}</div><div class="stat-lbl">Cities</div></div>
    </div>
    <div class="toolbar">
      <label for="wa-template">WhatsApp message template:</label>
      <textarea id="wa-template" rows="1">Hi {{shop_name}}, hope you're doing well — I'd like to share something that may be useful for your business. Do you have a moment to chat?</textarea>
      <button type="button" class="btn btn-primary" id="save-template">Save template</button>
      <button type="button" class="btn" id="export-notes">Export notes (CSV)</button>
      <button type="button" class="btn" id="import-notes-btn">Import notes</button>
      <input type="file" id="import-notes-file" accept=".csv" style="display:none">
      <button type="button" class="btn" id="clear-notes">Clear all notes</button>
      <span class="saved-count" id="saved-count">0 notes saved</span>
    </div>
    <p style="font-size:12px;color:#64748b;margin:0 0 14px">
      Use <code>{{{{shop_name}}}}</code> in the template; it auto-substitutes per shop.
      Notes save to this browser's localStorage. Export to back them up.
    </p>
    <table>
      <thead><tr>
        <th>#</th><th>Score</th><th>Shop</th><th>City</th>
        <th>Phone</th><th>Email</th><th>Website</th><th>Verify</th><th>Notes</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>

<script>
(function() {{
  "use strict";
  const STORAGE_KEY = "tha_hospitality_country_v1";

  function load() {{
    try {{
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {{template: null, notes: {{}}}};
    }} catch (e) {{ return {{template: null, notes: {{}}}}; }}
  }}
  function save(data) {{
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  }}
  const state = load();

  // --- Template ---
  const tplInput = document.getElementById("wa-template");
  if (state.template) tplInput.value = state.template;
  document.getElementById("save-template").addEventListener("click", () => {{
    state.template = tplInput.value;
    save(state);
    flash("Template saved");
  }});

  // --- Notes: load + bind ---
  function applyNote(sid, note) {{
    const ta = document.querySelector(`textarea.note-input[data-sid="${{sid}}"]`);
    if (!ta) return;
    ta.value = note || "";
    ta.classList.toggle("has-note", !!(note && note.trim()));
    const tr = ta.closest("tr");
    if (tr) tr.classList.toggle("row-contacted", !!(note && note.trim()));
  }}
  Object.entries(state.notes || {{}}).forEach(([sid, note]) => applyNote(sid, note));

  // Save on blur / Ctrl+Enter
  document.querySelectorAll("textarea.note-input").forEach(ta => {{
    ta.addEventListener("blur", () => {{
      const sid = ta.dataset.sid;
      const v = ta.value.trim();
      if (v) state.notes[sid] = v; else delete state.notes[sid];
      save(state);
      ta.classList.toggle("has-note", !!v);
      ta.closest("tr").classList.toggle("row-contacted", !!v);
      updateCount();
    }});
    ta.addEventListener("keydown", (e) => {{
      if (e.ctrlKey && e.key === "Enter") {{ ta.blur(); }}
    }});
  }});

  function updateCount() {{
    const n = Object.keys(state.notes || {{}}).length;
    document.getElementById("saved-count").textContent = `${{n}} note${{n === 1 ? "" : "s"}} saved`;
  }}
  updateCount();

  // --- WhatsApp button ---
  document.body.addEventListener("click", (e) => {{
    const btn = e.target.closest("button[data-action='whatsapp']");
    if (!btn) return;
    const wa = btn.dataset.wa;
    const name = btn.dataset.name || "";
    const tpl = (state.template || tplInput.value || "Hi {{shop_name}}").replace(/\\{{shop_name\\}}/g, name);
    const url = `https://wa.me/${{wa}}?text=${{encodeURIComponent(tpl)}}`;
    window.open(url, "_blank", "noopener");
    // Mark this shop as contacted in notes if no note exists
    const sid = btn.dataset.sid;
    if (sid && !(state.notes[sid] || "").trim()) {{
      const ts = new Date().toISOString().slice(0, 16).replace("T", " ");
      state.notes[sid] = `WA sent ${{ts}}`;
      save(state);
      applyNote(sid, state.notes[sid]);
      updateCount();
    }}
  }});

  // --- Export notes to CSV ---
  document.getElementById("export-notes").addEventListener("click", () => {{
    const entries = Object.entries(state.notes || {{}});
    if (entries.length === 0) {{ flash("No notes to export"); return; }}
    const lines = ["src_id,name,city,note"];
    entries.forEach(([sid, note]) => {{
      const tr = document.querySelector(`tr[data-sid="${{sid}}"]`);
      const name = tr ? tr.dataset.name : "";
      const city = tr ? tr.dataset.city : "";
      const esc = s => '"' + (s || "").replace(/"/g, '""') + '"';
      lines.push([esc(sid), esc(name), esc(city), esc(note)].join(","));
    }});
    const blob = new Blob([lines.join("\\n")], {{type: "text/csv;charset=utf-8"}});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `hospitality_notes_${{new Date().toISOString().slice(0, 10)}}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }});

  // --- Import notes from CSV ---
  document.getElementById("import-notes-btn").addEventListener("click", () =>
    document.getElementById("import-notes-file").click());
  document.getElementById("import-notes-file").addEventListener("change", (e) => {{
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {{
      const text = reader.result;
      const lines = text.split(/\\r?\\n/);
      let imported = 0;
      // Skip header
      for (let i = 1; i < lines.length; i++) {{
        const cols = parseCsvLine(lines[i]);
        if (cols.length < 4 || !cols[0]) continue;
        state.notes[cols[0]] = cols[3];
        applyNote(cols[0], cols[3]);
        imported++;
      }}
      save(state);
      updateCount();
      flash(`Imported ${{imported}} notes`);
    }};
    reader.readAsText(file);
  }});

  function parseCsvLine(line) {{
    const out = []; let cur = ""; let inQuotes = false;
    for (let i = 0; i < line.length; i++) {{
      const c = line[i];
      if (inQuotes) {{
        if (c === '"' && line[i + 1] === '"') {{ cur += '"'; i++; }}
        else if (c === '"') {{ inQuotes = false; }}
        else cur += c;
      }} else {{
        if (c === ',') {{ out.push(cur); cur = ""; }}
        else if (c === '"') {{ inQuotes = true; }}
        else cur += c;
      }}
    }}
    out.push(cur);
    return out;
  }}

  // --- Clear all notes ---
  document.getElementById("clear-notes").addEventListener("click", () => {{
    if (!confirm("Clear all saved notes? This cannot be undone (export first to back them up).")) return;
    state.notes = {{}};
    save(state);
    document.querySelectorAll("textarea.note-input").forEach(ta => {{
      ta.value = "";
      ta.classList.remove("has-note");
      ta.closest("tr").classList.remove("row-contacted");
    }});
    updateCount();
  }});

  function flash(msg) {{
    const el = document.getElementById("saved-count");
    const orig = el.textContent;
    el.textContent = msg;
    el.style.color = "#15803d";
    setTimeout(() => {{ el.textContent = orig; el.style.color = ""; }}, 1500);
  }}
}})();
</script>
</body></html>
"""

    out_html_path = os.path.join(DATA_DIR, "report_country_final.html")
    with open(out_html_path, "w", encoding="utf-8") as f:
        f.write(out_html)
    print(f"\n[final] wrote {out_html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
