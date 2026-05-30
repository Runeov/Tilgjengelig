"""Generate a single-page HTML directory for one city's shops.

Reads data/weed_th_<city>_google.csv if it exists (enriched with Google Places
phone/website/hours), otherwise falls back to data/weed_th_<city>.csv (addresses
and ratings only). Output: data/report_<city>.html.

The report has a manual editor for phone/email/notes:
  - <select> at top + Edit button opens an inline form
  - Each row also has a pencil icon for direct edit
  - Edits persist in browser localStorage (keyed per city)
  - Export edits as CSV; import a previously-exported CSV to restore

Usage:
  python report_city.py "Udon Thani"
"""

import argparse
import csv
import html
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.thailand_cannabis.common import DATA_DIR  # noqa: E402
from scrapers.thailand_cannabis.city_normalize import canonical_city  # noqa: E402


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def load_city_csv(city: str) -> tuple[list[dict], bool, bool, str]:
    """Return (rows, enriched, has_weed_contacts, source_path).

    Source-file lookup, in priority order:
      1. weed_th_<city>_google.csv  — per-city scrape + Google (highest quality)
      2. weed_th_<city>.csv          — per-city scrape, addresses only, no phone
      3. weed_th_google.csv          — country-wide Google enrichment, filtered by city
                                       (used when you ran the country scrape but no
                                       per-city detail scrape; lower match confidence
                                       since queries lack street addresses)

    If weed_th_contacts_<city>.csv exists, merges its weed_* fields into each
    row by source_id. Cell precedence at render time:
      manual (localStorage) > weed_<method> > google_<field> > empty
    """
    safe = city.lower().replace(" ", "_")
    enriched_path = os.path.join(DATA_DIR, f"weed_th_{safe}_google.csv")
    basic_path = os.path.join(DATA_DIR, f"weed_th_{safe}.csv")
    country_path = os.path.join(DATA_DIR, "weed_th_google.csv")
    contacts_path = os.path.join(DATA_DIR, f"weed_th_contacts_{safe}.csv")
    if os.path.exists(enriched_path):
        path = enriched_path
        enriched = True
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    elif os.path.exists(basic_path):
        path = basic_path
        enriched = False
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    elif os.path.exists(country_path):
        path = country_path
        enriched = True
        # Match by canonical name so `report_city.py "Phang Nga"` picks up rows
        # whose raw city is Phangnga, Chang Wat Phang Nga, Nga, or พังงา.
        target_canon = canonical_city(city).lower()
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            rows = [r for r in csv.DictReader(f)
                    if canonical_city(r.get("city", "")).lower() == target_canon]
        if not rows:
            raise FileNotFoundError(
                f"No rows for city={city!r} (canonical={canonical_city(city)!r}) "
                f"in country file {path}. Try a different spelling or run "
                f"summary_country.py to see all available city names."
            )
    else:
        raise FileNotFoundError(
            f"No data file found for {city!r}. Looked for {enriched_path}, "
            f"{basic_path}, and {country_path}. "
            f"Run scrape_weed_th_detail.py {city!r} or enrich_google_places.py on "
            f"weed_th.csv first."
        )

    has_weed_contacts = os.path.exists(contacts_path)
    if has_weed_contacts:
        with open(contacts_path, "r", encoding="utf-8-sig", newline="") as f:
            contacts = {c["source_id"]: c for c in csv.DictReader(f) if c.get("source_id")}
        for row in rows:
            c = contacts.get(row.get("source_id"))
            if not c:
                continue
            for k, v in c.items():
                if k.startswith("weed_") and v:
                    row[k] = v

    # Optionally merge lead-qualification fields (scraped_email + lead_quality + lead_score)
    leads_path = os.path.join(DATA_DIR, f"leads_{safe}.csv")
    if os.path.exists(leads_path):
        with open(leads_path, "r", encoding="utf-8-sig", newline="") as f:
            leads = {r["source_id"]: r for r in csv.DictReader(f) if r.get("source_id")}
        for row in rows:
            l = leads.get(row.get("source_id"))
            if not l:
                continue
            for k in ("scraped_email", "lead_quality", "lead_score"):
                v = l.get(k, "")
                if v:
                    row[k] = v
    return rows, enriched, has_weed_contacts, path


def stats(rows: list[dict], enriched: bool, has_weed_contacts: bool) -> dict:
    total = len(rows)
    with_address = sum(1 for r in rows if r.get("address"))
    with_rating = sum(1 for r in rows if r.get("rating"))
    # Any source of phone counts: weed.th-auth, Google, or manual is applied at render time
    def phone_for(r):
        return r.get("weed_phone") or (r.get("google_phone") if enriched else "")
    def website_for(r):
        return r.get("weed_website") or (r.get("google_website") if enriched else "")
    with_phone = sum(1 for r in rows if phone_for(r))
    with_website = sum(1 for r in rows if website_for(r))
    high_conf = sum(1 for r in rows if r.get("google_match_confidence") == "high") if enriched else 0
    with_weed_phone = sum(1 for r in rows if r.get("weed_phone")) if has_weed_contacts else 0
    with_weed_line = sum(1 for r in rows if r.get("weed_line")) if has_weed_contacts else 0
    return {
        "total": total,
        "with_address": with_address,
        "with_rating": with_rating,
        "with_phone": with_phone,
        "with_website": with_website,
        "high_conf": high_conf,
        "with_weed_phone": with_weed_phone,
        "with_weed_line": with_weed_line,
    }


def _channel_link(value: str, kind: str) -> str:
    """Render a chip-like link for a weed.th-sourced channel value."""
    if not value:
        return ""
    v = value.strip()
    href = ""
    if kind == "line":
        # Many LINE IDs come as @id; the public URL pattern is line.me/ti/p/@id or /R/ti/...
        line_id = v.lstrip("@")
        href = f"https://line.me/R/ti/p/@{line_id}"
        label = f"@{line_id}"
    elif kind == "facebook":
        href = v if v.startswith("http") else f"https://facebook.com/{v.lstrip('@')}"
        label = "FB"
    elif kind == "instagram":
        href = v if v.startswith("http") else f"https://instagram.com/{v.lstrip('@')}"
        label = "IG"
    elif kind == "whatsapp":
        digits = "".join(ch for ch in v if ch.isdigit() or ch == "+")
        href = f"https://wa.me/{digits.lstrip('+')}"
        label = "WA"
    elif kind == "google_url":
        href = v
        label = "Maps"
    else:
        return f'<span class="chip">{esc(v)[:30]}</span>'
    return (f'<a class="chip chip-{esc(kind)}" href="{esc(href)}" target="_blank" '
            f'rel="noopener" title="{esc(v)}">{esc(label)}</a>')


def _score_cell(r: dict) -> str:
    """Render a small badge with the lead-quality score. Empty cell if no score."""
    q = r.get("lead_quality")
    if not q:
        return '<td class="nowrap">&mdash;</td>'
    try:
        qn = int(q)
    except (ValueError, TypeError):
        return f'<td class="nowrap">{esc(q)}</td>'
    cls = "score-high" if qn >= 8 else ("score-mid" if qn >= 5 else "score-low")
    return f'<td class="nowrap"><span class="score-badge {cls}">{qn}</span></td>'


def render_row(r: dict, enriched: bool, has_weed_contacts: bool, has_leads: bool = False) -> str:
    sid = esc(r.get("source_id") or "")
    name = esc(r.get("name"))
    addr = esc(r.get("address")) or "&mdash;"
    rating = r.get("rating") or ""
    reviews = r.get("review_count") or ""
    rating_cell = (
        f"{esc(rating)} <span class='dim'>({esc(reviews)})</span>"
        if rating else "&mdash;"
    )
    detail_url = esc(r.get("detail_url"))
    detail_link = (
        f'<a href="{detail_url}" target="_blank" rel="noopener">weed.th &rarr;</a>'
        if detail_url else "&mdash;"
    )

    # Source-of-truth phone: weed.th-auth value preferred, then Google.
    weed_phone = r.get("weed_phone") or ""
    google_phone = r.get("google_phone") if enriched else ""
    src_phone = weed_phone or google_phone
    src_phone_origin = "weed.th" if weed_phone else ("google" if google_phone else "")
    phone_cell_inner = esc(src_phone) if src_phone else "&mdash;"

    # Source email: weed.th-auth preferred, then scraped-from-website fallback.
    # (Google Places does not return emails.)
    weed_email = r.get("weed_email") or ""
    scraped_email = r.get("scraped_email") or ""
    src_email = weed_email or scraped_email
    src_email_origin = "weed.th" if weed_email else ("scraped" if scraped_email else "")
    email_cell_inner = esc(src_email) if src_email else "&mdash;"

    edit_btn = (
        f'<button type="button" class="row-edit" data-edit-sid="{sid}" '
        f'title="Edit phone/email/notes">&#9998;</button>'
    )

    common = f"""
        <td><strong>{name}</strong></td>
        <td class="addr">{addr}</td>
        <td class="nowrap">{rating_cell}</td>
        <td class="nowrap phone-cell"
            data-src-phone="{esc(src_phone)}"
            data-src-phone-origin="{esc(src_phone_origin)}">
          <span class="cell-value" data-cell="phone" data-sid="{sid}">{phone_cell_inner}</span>
        </td>
        <td class="nowrap email-cell"
            data-src-email="{esc(src_email)}"
            data-src-email-origin="{esc(src_email_origin)}">
          <span class="cell-value" data-cell="email" data-sid="{sid}">{email_cell_inner}</span>
        </td>
        <td class="notes-cell">
          <span class="cell-value notes-text" data-cell="notes" data-sid="{sid}"></span>
        </td>
        <td class="nowrap">{edit_btn}</td>
    """

    if has_weed_contacts:
        chips = " ".join(filter(None, [
            _channel_link(r.get("weed_line", ""), "line"),
            _channel_link(r.get("weed_facebook", ""), "facebook"),
            _channel_link(r.get("weed_instagram", ""), "instagram"),
            _channel_link(r.get("weed_whatsapp", ""), "whatsapp"),
            _channel_link(r.get("weed_google_url", ""), "google_url"),
        ]))
        channels_cell = f'<td class="channels-cell">{chips or "&mdash;"}</td>'
    else:
        channels_cell = ""

    # Website preference: weed.th value beats Google value
    weed_website = r.get("weed_website") or ""
    if enriched:
        google_website = r.get("google_website") or ""
        website = weed_website or google_website
        website_cell = (
            f'<a href="{esc(website)}" target="_blank" rel="noopener">{esc(website[:40])}{"..." if len(website) > 40 else ""}</a>'
            if website else "&mdash;"
        )
        hours = esc(r.get("google_hours")) or "&mdash;"
        maps_uri = r.get("google_maps_uri") or ""
        maps_link = (
            f'<a href="{esc(maps_uri)}" target="_blank" rel="noopener">Maps</a>'
            if maps_uri else "&mdash;"
        )
        conf = r.get("google_match_confidence") or ""
        conf_class = {
            "high": "badge-ok",
            "medium": "badge-mid",
            "low": "badge-warn",
            "no_result": "badge-dim",
        }.get(conf, "badge-dim")
        conf_cell = f'<span class="badge {conf_class}">{esc(conf) or "&mdash;"}</span>'
        extras = f"""
        <td>{website_cell}</td>
        <td class="hours">{hours}</td>
        <td class="nowrap">{maps_link}</td>
        <td class="nowrap">{detail_link}</td>
        <td class="nowrap">{conf_cell}</td>
        """
    elif weed_website:
        website_cell = (
            f'<a href="{esc(weed_website)}" target="_blank" rel="noopener">{esc(weed_website[:40])}{"..." if len(weed_website) > 40 else ""}</a>'
        )
        extras = f"""
        <td>{website_cell}</td>
        <td class="nowrap">{detail_link}</td>
        """
    else:
        extras = f"""
        <td class="nowrap">{detail_link}</td>
        """

    score_cell = _score_cell(r) if has_leads else ""
    return f'<tr data-sid="{sid}" data-name="{name}">{common}{channels_cell}{score_cell}{extras}</tr>\n'


def render_select_options(rows: list[dict]) -> str:
    """Build <option>s for the editor select. Sorted alphabetically by name."""
    sorted_rows = sorted(rows, key=lambda r: (r.get("name") or "").lower())
    parts = ['<option value="">&mdash; Select a shop &mdash;</option>']
    for r in sorted_rows:
        sid = esc(r.get("source_id") or "")
        name = esc(r.get("name") or "(unnamed)")
        city = esc(r.get("city") or "")
        parts.append(f'<option value="{sid}">{name} &middot; {city}</option>')
    return "\n".join(parts)


def build(city: str) -> tuple[str, str]:
    rows, enriched, has_weed_contacts, source_path = load_city_csv(city)

    # Sort: rows with address first (descending review count as tiebreaker), then no-address rows
    def sort_key(r: dict):
        has_addr = bool(r.get("address"))
        try:
            rc = int(r.get("review_count") or 0)
        except ValueError:
            rc = 0
        return (0 if has_addr else 1, -rc, r.get("name", ""))

    rows.sort(key=sort_key)

    has_leads = any(r.get("lead_quality") for r in rows)
    s = stats(rows, enriched, has_weed_contacts)
    rows_html = "".join(render_row(r, enriched, has_weed_contacts, has_leads) for r in rows)
    select_options = render_select_options(rows)

    safe_city = city.lower().replace(" ", "_")
    storage_key = f"tha_cannabis_overrides_{safe_city}"

    common_cols = (
        "<th>Name</th><th>Address</th><th>Rating</th>"
        "<th>Phone</th><th>Email</th><th>Notes</th><th></th>"
    )
    channels_col = "<th>Channels</th>" if has_weed_contacts else ""
    score_col = "<th title='Lead-quality score 0-10'>Score</th>" if has_leads else ""
    if enriched:
        header_cells = (
            common_cols + channels_col + score_col
            + "<th>Website</th><th>Hours</th><th>Maps</th><th>weed.th</th><th>Match</th>"
        )
    elif any(r.get("weed_website") for r in rows):
        header_cells = common_cols + channels_col + score_col + "<th>Website</th><th>weed.th</th>"
    else:
        header_cells = common_cols + channels_col + score_col + "<th>weed.th</th>"

    if has_weed_contacts:
        banner = (
            f"""
            <div class="callout callout-info">
              <strong>Sources merged in this report:</strong>
              weed.th (authenticated fetch &mdash; {s['with_weed_phone']} phones, {s['with_weed_line']} LINE IDs),
              {("Google Places, " if enriched else "")}and your manual overrides.
              Cell precedence: <em>manual &rsaquo; weed.th &rsaquo; Google &rsaquo; empty</em>.
            </div>
            """
        )
    elif enriched:
        banner = ""
    else:
        banner = (
            f"""
            <div class="callout">
              <strong>No phone numbers from sources yet.</strong> weed.th does not expose phones
              on its public pages. To populate the Phone column automatically, you can either:
              <br><br>
              <strong>Option A &mdash; Google Places ($, easy):</strong>
              <code>python scrapers/thailand_cannabis/enrich_google_places.py data/weed_th_{safe_city}.csv</code>
              <br>
              <strong>Option B &mdash; weed.th authenticated fetch (free, ToS risk):</strong>
              run <code>weed_th_auth_login.py</code> then
              <code>weed_th_auth_fetch_contacts.py "{esc(city)}"</code>
              <br><br>
              Manual entries via the editor below always take precedence.
            </div>
            """
        )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    enriched_stat_html = ""
    if enriched:
        enriched_stat_html += f"""
        <div class="stat">
          <div class="stat-value">{s['with_phone']}</div>
          <div class="stat-label">With phone</div>
        </div>
        <div class="stat">
          <div class="stat-value">{s['with_website']}</div>
          <div class="stat-label">With website</div>
        </div>
        <div class="stat">
          <div class="stat-value">{s['high_conf']}</div>
          <div class="stat-label">High-confidence (Google)</div>
        </div>
        """
    if has_weed_contacts:
        enriched_stat_html += f"""
        <div class="stat" style="border-left-color:#3b82f6">
          <div class="stat-value">{s['with_weed_phone']}</div>
          <div class="stat-label">Phone (weed.th auth)</div>
        </div>
        <div class="stat" style="border-left-color:#3b82f6">
          <div class="stat-value">{s['with_weed_line']}</div>
          <div class="stat-label">LINE (weed.th auth)</div>
        </div>
        """
    if has_leads:
        high_leads = sum(1 for r in rows if (r.get("lead_quality") or "").isdigit() and int(r["lead_quality"]) >= 8)
        with_email = sum(1 for r in rows if r.get("scraped_email") or r.get("weed_email"))
        enriched_stat_html += f"""
        <div class="stat" style="border-left-color:#84cc16">
          <div class="stat-value">{high_leads}</div>
          <div class="stat-label">High-quality leads (8+)</div>
        </div>
        <div class="stat" style="border-left-color:#84cc16">
          <div class="stat-value">{with_email}</div>
          <div class="stat-label">With email (any source)</div>
        </div>
        """

    # JS reads storage_key from a meta tag so we don't have to escape it inside a JS literal.
    out_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{esc(city)} cannabis shops &mdash; full directory</title>
<meta name="tha-storage-key" content="{esc(storage_key)}">
<meta name="tha-city" content="{esc(city)}">
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
         line-height: 1.5; max-width: 1640px; margin: 0 auto; padding: 24px;
         background: #f7f7f8; color: #1a1a2e; }}
  h1, h2 {{ color: #0d2818; }}
  h1 {{ margin: 0 0 6px; }}
  .header {{ background: #0d2818; color: #e6f4ec; padding: 24px 28px;
             border-radius: 10px; margin-bottom: 20px; }}
  .header h1 {{ color: white; }}
  .header p {{ margin: 0; opacity: 0.85; font-size: 14px; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 12px; margin: 0 0 22px; }}
  .stat {{ background: white; padding: 14px 16px; border-radius: 8px;
           box-shadow: 0 1px 2px rgba(0,0,0,.05); border-left: 4px solid #22c55e; }}
  .stat-value {{ font-size: 1.9em; font-weight: 700; line-height: 1; color: #0d2818; }}
  .stat-label {{ font-size: 11px; color: #555; text-transform: uppercase;
                 letter-spacing: 0.8px; margin-top: 5px; }}
  .callout {{ background: #fef3c7; border: 1px solid #f59e0b;
              border-radius: 8px; padding: 12px 16px; margin: 12px 0 22px;
              font-size: 13px; line-height: 1.6; }}
  .callout code {{ background: rgba(0,0,0,.08); padding: 1px 6px;
                   border-radius: 3px; font-size: 12px; word-break: break-all; }}

  /* ===== Editor panel ===== */
  .editor {{ background: white; border-radius: 10px; padding: 16px 20px;
             margin-bottom: 22px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }}
  .editor h2 {{ margin: 0 0 12px; font-size: 15px;
                text-transform: uppercase; letter-spacing: 0.8px; color: #4b5563; }}
  .editor-bar {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
  .editor-bar select {{ flex: 1 1 320px; min-width: 220px; padding: 8px 10px;
                        border: 1px solid #cbd5e1; border-radius: 6px;
                        font-size: 14px; background: white; }}
  .editor-bar button, .form-actions button {{
    padding: 8px 14px; border: 1px solid transparent; border-radius: 6px;
    font-size: 13px; font-weight: 600; cursor: pointer; background: #15803d;
    color: white; transition: background .15s;
  }}
  .editor-bar button:hover, .form-actions button:hover {{ background: #166534; }}
  .editor-bar button.secondary, .form-actions button.secondary {{
    background: white; color: #15803d; border-color: #15803d;
  }}
  .editor-bar button.secondary:hover {{ background: #f0fdf4; }}
  .editor-bar button.danger, .form-actions button.danger {{
    background: white; color: #991b1b; border-color: #fecaca;
  }}
  .editor-bar button.danger:hover {{ background: #fef2f2; }}
  .editor-bar .count {{ margin-left: auto; font-size: 12px; color: #64748b; }}
  .editor-form {{ display: none; margin-top: 16px; padding-top: 16px;
                  border-top: 1px solid #e5e7eb; }}
  .editor-form.open {{ display: block; }}
  .editor-form .selected-name {{ font-weight: 700; font-size: 15px;
                                 margin-bottom: 4px; color: #0d2818; }}
  .editor-form .selected-meta {{ font-size: 12px; color: #64748b;
                                 margin-bottom: 14px; }}
  .form-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .form-grid .full {{ grid-column: 1 / -1; }}
  .form-grid label {{ display: block; font-size: 11px; font-weight: 600;
                      text-transform: uppercase; letter-spacing: 0.5px;
                      color: #4b5563; margin-bottom: 4px; }}
  .form-grid input, .form-grid textarea {{
    width: 100%; padding: 8px 10px; border: 1px solid #cbd5e1;
    border-radius: 6px; font-size: 14px; font-family: inherit;
  }}
  .form-grid input:focus, .form-grid textarea:focus {{
    outline: none; border-color: #15803d; box-shadow: 0 0 0 3px rgba(21,128,61,.12);
  }}
  .form-grid textarea {{ resize: vertical; min-height: 60px; }}
  .form-grid .source-hint {{ font-size: 11px; color: #64748b; margin-top: 4px; }}
  .form-actions {{ margin-top: 14px; display: flex; gap: 8px; }}
  .save-status {{ margin-left: auto; align-self: center; font-size: 12px;
                  color: #15803d; opacity: 0; transition: opacity .25s; }}
  .save-status.visible {{ opacity: 1; }}

  /* ===== Table ===== */
  table {{ width: 100%; border-collapse: collapse; background: white;
           border-radius: 8px; overflow: hidden;
           box-shadow: 0 1px 2px rgba(0,0,0,.05);
           font-size: 13px; }}
  th, td {{ padding: 9px 11px; text-align: left;
            border-bottom: 1px solid #eaeaea; vertical-align: top; }}
  th {{ background: #f3f4f6; font-weight: 600; font-size: 11px;
        text-transform: uppercase; letter-spacing: 0.5px; color: #4b5563;
        position: sticky; top: 0; z-index: 2; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover {{ background: #fafafa; }}
  tr.highlighted {{ background: #fef9c3 !important; }}
  td.addr {{ max-width: 320px; }}
  td.hours {{ max-width: 200px; font-size: 12px; }}
  td.nowrap {{ white-space: nowrap; }}
  td.notes-cell {{ max-width: 180px; font-size: 12px; color: #475569; font-style: italic; }}
  td.channels-cell {{ white-space: nowrap; font-size: 11px; }}
  .chip {{ display: inline-block; padding: 2px 8px; border-radius: 11px;
           font-size: 11px; font-weight: 600; margin-right: 3px;
           text-decoration: none; line-height: 1.4; border: 1px solid transparent; }}
  .chip-line {{ background: #ecfdf5; color: #047857; border-color: #a7f3d0; }}
  .chip-facebook {{ background: #eff6ff; color: #1d4ed8; border-color: #bfdbfe; }}
  .chip-instagram {{ background: #fdf2f8; color: #be185d; border-color: #fbcfe8; }}
  .chip-whatsapp {{ background: #ecfdf5; color: #047857; border-color: #a7f3d0; }}
  .chip-google_url {{ background: #f3f4f6; color: #374151; border-color: #d1d5db; }}
  .chip:hover {{ text-decoration: none; opacity: 0.85; }}
  .callout-info {{ background: #eff6ff; border-color: #3b82f6; color: #1e3a8a; }}
  .callout-info code {{ background: rgba(30,58,138,0.08); }}
  .score-badge {{ display: inline-block; width: 26px; text-align: center;
                  padding: 2px 0; border-radius: 4px; font-weight: 700; font-size: 12px; }}
  .score-high {{ background: #dcfce7; color: #14532d; }}
  .score-mid {{ background: #fef3c7; color: #78350f; }}
  .score-low {{ background: #f1f5f9; color: #64748b; }}
  .dim {{ color: #94a3b8; font-size: 12px; }}
  a {{ color: #15803d; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px;
            font-size: 11px; font-weight: 600; }}
  .badge-ok {{ background: #dcfce7; color: #166534; }}
  .badge-mid {{ background: #fef3c7; color: #92400e; }}
  .badge-warn {{ background: #fee2e2; color: #991b1b; }}
  .badge-dim {{ background: #f1f5f9; color: #64748b; }}
  .cell-value.manual {{
    background: #fef9c3; padding: 1px 6px; border-radius: 3px;
    border: 1px solid #fde68a;
  }}
  .cell-value.manual::after {{
    content: " \\270E"; color: #a16207; font-size: 10px; margin-left: 2px;
  }}
  button.row-edit {{
    background: transparent; border: 1px solid transparent;
    color: #64748b; cursor: pointer; font-size: 14px; padding: 2px 6px;
    border-radius: 4px;
  }}
  button.row-edit:hover {{ background: #e2e8f0; color: #15803d; }}

  footer {{ margin-top: 28px; padding-top: 16px; border-top: 1px solid #ddd;
            font-size: 12px; color: #666; }}
</style>
</head>
<body>
  <div class="header">
    <h1>{esc(city)} &mdash; cannabis shop directory</h1>
    <p>Source: <a href="https://weed.th" style="color:#86efac" target="_blank" rel="noopener">weed.th</a>{(" + Google Places" if enriched else "")}. Generated {generated_at}.</p>
  </div>

  {banner}

  <div class="stats">
    <div class="stat">
      <div class="stat-value">{s['total']}</div>
      <div class="stat-label">Total shops</div>
    </div>
    <div class="stat">
      <div class="stat-value">{s['with_address']}</div>
      <div class="stat-label">With address</div>
    </div>
    <div class="stat">
      <div class="stat-value">{s['with_rating']}</div>
      <div class="stat-label">With rating</div>
    </div>
    {enriched_stat_html}
    <div class="stat" style="border-left-color:#f59e0b">
      <div class="stat-value" id="override-count">0</div>
      <div class="stat-label">Manual overrides</div>
    </div>
  </div>

  <div class="editor">
    <h2>Edit shop contact info</h2>
    <div class="editor-bar">
      <select id="shop-select">{select_options}</select>
      <button type="button" id="edit-btn">Edit</button>
      <button type="button" class="secondary" id="export-btn">Export edits (CSV)</button>
      <button type="button" class="secondary" id="import-btn">Import edits</button>
      <input type="file" id="import-file" accept=".csv,.json" style="display:none">
      <button type="button" class="danger" id="clear-all-btn">Clear all</button>
      <span class="count" id="storage-note"></span>
    </div>
    <div class="editor-form" id="editor-form">
      <div class="selected-name" id="selected-name"></div>
      <div class="selected-meta" id="selected-meta"></div>
      <div class="form-grid">
        <div>
          <label for="input-phone">Phone</label>
          <input type="tel" id="input-phone" placeholder="e.g. +66 81 234 5678">
          <div class="source-hint" id="phone-hint"></div>
        </div>
        <div>
          <label for="input-email">Email</label>
          <input type="email" id="input-email" placeholder="shop@example.com">
        </div>
        <div class="full">
          <label for="input-notes">Notes</label>
          <textarea id="input-notes" placeholder="Free text &mdash; visit notes, contact attempts, anything"></textarea>
        </div>
      </div>
      <div class="form-actions">
        <button type="button" id="save-btn">Save</button>
        <button type="button" class="secondary" id="cancel-btn">Cancel</button>
        <button type="button" class="danger" id="reset-btn">Clear this shop's override</button>
        <span class="save-status" id="save-status">Saved</span>
      </div>
    </div>
  </div>

  <table id="shop-table">
    <thead><tr>{header_cells}</tr></thead>
    <tbody>{rows_html}</tbody>
  </table>

  <footer>
    Source CSV: <code>{esc(os.path.relpath(source_path))}</code> &middot;
    Edits are stored in your browser only (<code>localStorage</code>, key
    <code>{esc(storage_key)}</code>). Use <strong>Export edits</strong> to back them
    up or share with another machine.
  </footer>

<script>
(function() {{
  "use strict";
  var STORAGE_KEY = document.querySelector('meta[name="tha-storage-key"]').content;
  var CITY = document.querySelector('meta[name="tha-city"]').content;

  function loadStore() {{
    try {{
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return {{}};
      var parsed = JSON.parse(raw);
      return (parsed && parsed.overrides) || {{}};
    }} catch (e) {{
      console.error("Failed to load overrides", e);
      return {{}};
    }}
  }}

  function saveStore(overrides) {{
    var payload = {{
      schema_version: 1,
      city: CITY,
      saved_at: new Date().toISOString(),
      overrides: overrides
    }};
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  }}

  function applyOverrideToRow(sid, ov) {{
    var fields = ["phone", "email", "notes"];
    fields.forEach(function(field) {{
      var cell = document.querySelector('.cell-value[data-cell="' + field + '"][data-sid="' + sid + '"]');
      if (!cell) return;
      var manualVal = ov && ov[field];
      var srcAttr = null;
      if (field === "phone") {{
        var td = cell.closest('td');
        srcAttr = td && td.getAttribute('data-src-phone');
      }} else if (field === "email") {{
        var td = cell.closest('td');
        srcAttr = td && td.getAttribute('data-src-email');
      }}
      if (manualVal) {{
        cell.textContent = manualVal;
        cell.classList.add("manual");
      }} else {{
        cell.classList.remove("manual");
        if (field === "phone" || field === "email") {{
          cell.textContent = srcAttr || "\\u2014";
        }} else {{
          cell.textContent = "";
        }}
      }}
    }});
  }}

  function refreshAll() {{
    var store = loadStore();
    document.querySelectorAll('tr[data-sid]').forEach(function(tr) {{
      var sid = tr.getAttribute('data-sid');
      applyOverrideToRow(sid, store[sid]);
    }});
    updateCount(store);
  }}

  function updateCount(store) {{
    var count = Object.keys(store || loadStore()).length;
    document.getElementById('override-count').textContent = count;
    document.getElementById('storage-note').textContent =
      count > 0 ? (count + " saved in this browser") : "No edits saved yet";
  }}

  // ----- Editor form wiring -----
  var sel = document.getElementById('shop-select');
  var form = document.getElementById('editor-form');
  var nameEl = document.getElementById('selected-name');
  var metaEl = document.getElementById('selected-meta');
  var phoneInput = document.getElementById('input-phone');
  var emailInput = document.getElementById('input-email');
  var notesInput = document.getElementById('input-notes');
  var phoneHint = document.getElementById('phone-hint');
  var status = document.getElementById('save-status');

  function openForm(sid) {{
    if (!sid) return;
    var tr = document.querySelector('tr[data-sid="' + sid + '"]');
    if (!tr) return;
    sel.value = sid;
    var store = loadStore();
    var ov = store[sid] || {{}};
    nameEl.textContent = tr.getAttribute('data-name') || '(unnamed)';
    var addrCell = tr.querySelector('td.addr');
    metaEl.textContent = addrCell ? addrCell.textContent.trim() : '';
    phoneInput.value = ov.phone || '';
    emailInput.value = ov.email || '';
    notesInput.value = ov.notes || '';
    var srcPhone = tr.querySelector('td.phone-cell');
    var srcPhoneVal = srcPhone && srcPhone.getAttribute('data-src-phone');
    var srcPhoneOrigin = srcPhone && srcPhone.getAttribute('data-src-phone-origin');
    phoneHint.textContent = srcPhoneVal
      ? ('Source value: ' + srcPhoneVal +
         (srcPhoneOrigin ? ' (from ' + srcPhoneOrigin + ')' : '') +
         ' — manual entry will override')
      : 'No source value — enter manually';
    form.classList.add('open');
    // Scroll the highlighted row into view
    document.querySelectorAll('tr.highlighted').forEach(function(r) {{
      r.classList.remove('highlighted');
    }});
    tr.classList.add('highlighted');
    phoneInput.focus();
  }}

  function closeForm() {{
    form.classList.remove('open');
    sel.value = '';
    document.querySelectorAll('tr.highlighted').forEach(function(r) {{
      r.classList.remove('highlighted');
    }});
  }}

  function flashStatus(text) {{
    status.textContent = text;
    status.classList.add('visible');
    setTimeout(function() {{ status.classList.remove('visible'); }}, 1500);
  }}

  document.getElementById('edit-btn').addEventListener('click', function() {{
    openForm(sel.value);
  }});
  sel.addEventListener('change', function() {{
    if (sel.value) openForm(sel.value);
  }});
  document.querySelectorAll('button.row-edit').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      openForm(btn.getAttribute('data-edit-sid'));
    }});
  }});

  document.getElementById('save-btn').addEventListener('click', function() {{
    var sid = sel.value;
    if (!sid) return;
    var store = loadStore();
    var rec = {{
      phone: phoneInput.value.trim(),
      email: emailInput.value.trim(),
      notes: notesInput.value.trim(),
      updated_at: new Date().toISOString()
    }};
    // If everything blank, remove the override entirely
    if (!rec.phone && !rec.email && !rec.notes) {{
      delete store[sid];
    }} else {{
      store[sid] = rec;
    }}
    saveStore(store);
    applyOverrideToRow(sid, store[sid]);
    updateCount(store);
    flashStatus('Saved');
  }});

  document.getElementById('cancel-btn').addEventListener('click', closeForm);

  document.getElementById('reset-btn').addEventListener('click', function() {{
    var sid = sel.value;
    if (!sid) return;
    if (!confirm('Clear manual override for this shop?')) return;
    var store = loadStore();
    delete store[sid];
    saveStore(store);
    applyOverrideToRow(sid, null);
    updateCount(store);
    phoneInput.value = '';
    emailInput.value = '';
    notesInput.value = '';
    flashStatus('Cleared');
  }});

  document.getElementById('clear-all-btn').addEventListener('click', function() {{
    var count = Object.keys(loadStore()).length;
    if (count === 0) return alert('No overrides to clear.');
    if (!confirm('Clear all ' + count + ' manual overrides for ' + CITY + '? This cannot be undone unless you exported first.')) return;
    localStorage.removeItem(STORAGE_KEY);
    refreshAll();
    closeForm();
  }});

  // ----- CSV export / import -----
  function csvEscape(s) {{
    if (s == null) return '';
    s = String(s);
    if (/[",\\n\\r]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
    return s;
  }}

  function downloadFile(filename, text, mime) {{
    var blob = new Blob([text], {{type: mime || 'text/plain;charset=utf-8'}});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    setTimeout(function() {{ URL.revokeObjectURL(url); document.body.removeChild(a); }}, 0);
  }}

  document.getElementById('export-btn').addEventListener('click', function() {{
    var store = loadStore();
    var entries = Object.keys(store);
    if (entries.length === 0) {{
      alert('No edits to export.');
      return;
    }}
    var header = ['source_id', 'name', 'city', 'phone', 'email', 'notes', 'updated_at'];
    var lines = [header.join(',')];
    entries.forEach(function(sid) {{
      var tr = document.querySelector('tr[data-sid="' + sid + '"]');
      var name = tr ? tr.getAttribute('data-name') : '';
      var ov = store[sid];
      lines.push([
        csvEscape(sid), csvEscape(name), csvEscape(CITY),
        csvEscape(ov.phone || ''), csvEscape(ov.email || ''),
        csvEscape(ov.notes || ''), csvEscape(ov.updated_at || '')
      ].join(','));
    }});
    var stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    downloadFile('overrides_' + CITY.toLowerCase().replace(/\\s+/g, '_') + '_' + stamp + '.csv',
                 lines.join('\\n'), 'text/csv;charset=utf-8');
  }});

  document.getElementById('import-btn').addEventListener('click', function() {{
    document.getElementById('import-file').click();
  }});

  // Minimal CSV parser: handles quoted fields, escaped quotes, commas, newlines inside quotes.
  function parseCSV(text) {{
    var rows = [], row = [], field = '', inQuotes = false;
    for (var i = 0; i < text.length; i++) {{
      var c = text[i];
      if (inQuotes) {{
        if (c === '"') {{
          if (text[i+1] === '"') {{ field += '"'; i++; }}
          else {{ inQuotes = false; }}
        }} else {{ field += c; }}
      }} else {{
        if (c === '"') inQuotes = true;
        else if (c === ',') {{ row.push(field); field = ''; }}
        else if (c === '\\n' || c === '\\r') {{
          if (c === '\\r' && text[i+1] === '\\n') i++;
          row.push(field); field = '';
          if (row.length > 1 || row[0] !== '') rows.push(row);
          row = [];
        }} else {{ field += c; }}
      }}
    }}
    if (field || row.length) {{ row.push(field); rows.push(row); }}
    return rows;
  }}

  document.getElementById('import-file').addEventListener('change', function(e) {{
    var file = e.target.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function() {{
      var text = reader.result;
      var imported = {{}};
      try {{
        if (file.name.endsWith('.json')) {{
          var parsed = JSON.parse(text);
          imported = parsed.overrides || parsed;
        }} else {{
          var rows = parseCSV(text);
          if (rows.length < 2) throw new Error('Empty CSV');
          var header = rows[0].map(function(h) {{ return h.trim().toLowerCase(); }});
          var idx = {{
            source_id: header.indexOf('source_id'),
            phone: header.indexOf('phone'),
            email: header.indexOf('email'),
            notes: header.indexOf('notes'),
            updated_at: header.indexOf('updated_at')
          }};
          if (idx.source_id < 0) throw new Error('Missing source_id column');
          for (var i = 1; i < rows.length; i++) {{
            var r = rows[i];
            var sid = r[idx.source_id];
            if (!sid) continue;
            imported[sid] = {{
              phone: idx.phone >= 0 ? (r[idx.phone] || '') : '',
              email: idx.email >= 0 ? (r[idx.email] || '') : '',
              notes: idx.notes >= 0 ? (r[idx.notes] || '') : '',
              updated_at: idx.updated_at >= 0 ? (r[idx.updated_at] || '') : new Date().toISOString()
            }};
          }}
        }}
      }} catch (err) {{
        alert('Import failed: ' + err.message);
        e.target.value = '';
        return;
      }}
      var existing = loadStore();
      var added = 0, updated = 0;
      Object.keys(imported).forEach(function(sid) {{
        if (existing[sid]) updated++; else added++;
        existing[sid] = imported[sid];
      }});
      saveStore(existing);
      refreshAll();
      alert('Imported ' + Object.keys(imported).length + ' overrides (' + added + ' new, ' + updated + ' updated).');
      e.target.value = '';
    }};
    reader.readAsText(file);
  }});

  // Initial render
  refreshAll();
}})();
</script>
</body>
</html>
"""

    safe = city.lower().replace(" ", "_")
    out_path = os.path.join(DATA_DIR, f"report_{safe}.html")
    return out_html, out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("city", help="City to report on (e.g. 'Udon Thani')")
    args = parser.parse_args()

    out_html, out_path = build(args.city)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out_html)
    print(f"[report_city] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
