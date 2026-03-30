#!/usr/bin/env python3
"""
Nord-Norge Travel Database — HTML Dashboard Builder
====================================================
Reads nordnorge_travel.db and generates a searchable, filterable HTML dashboard:
  - Summary statistics cards
  - Interactive table with live search + column filters
  - Export to CSV button (client-side)
  - Links to run the compliance scanner on any subset

Output: nordnorge_travel_dashboard.html  (fully self-contained, no server needed)

Usage:
    python build_travel_dashboard.py
    python build_travel_dashboard.py --db nordnorge_travel.db --output dashboard.html
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime

DEFAULT_DB  = "nordnorge_travel.db"
DEFAULT_OUT = "nordnorge_travel_dashboard.html"


def open_db(path: str) -> sqlite3.Connection:
    if not os.path.exists(path):
        print(f"Database ikke funnet: {path}")
        print("Kjør først: python fetch_nordnorge_travel.py")
        sys.exit(1)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def load_companies(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT
            org_nr, name, org_form, nace_code, nace_description,
            status, employees, street_address, postal_code, postal_place,
            municipality, county, founded_year,
            website, proff_url, phone, email, is_sub_unit, fetched_at
        FROM companies
        ORDER BY county, municipality, name
    """).fetchall()
    return [dict(r) for r in rows]


def load_stats(conn: sqlite3.Connection) -> dict:
    total   = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    active  = conn.execute("SELECT COUNT(*) FROM companies WHERE status='active'").fetchone()[0]
    web     = conn.execute("SELECT COUNT(*) FROM companies WHERE website!='' AND website IS NOT NULL").fetchone()[0]
    svalbard = conn.execute(
        "SELECT COUNT(*) FROM companies WHERE county LIKE '%Svalbard%' OR postal_place LIKE 'LONGYEARBYEN'"
    ).fetchone()[0]
    no_web  = conn.execute(
        "SELECT COUNT(*) FROM companies WHERE (website='' OR website IS NULL) AND status='active'"
    ).fetchone()[0]
    counties = [dict(r) for r in conn.execute("SELECT * FROM summary_by_county")]
    nace_groups = [dict(r) for r in conn.execute("SELECT * FROM summary_by_nace")]
    return {
        "total": total, "active": active, "web": web,
        "svalbard": svalbard, "no_web": no_web,
        "counties": counties, "nace_groups": nace_groups,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def build_html(companies: list[dict], stats: dict) -> str:
    # Serialise company data for JS
    companies_json = json.dumps(companies, ensure_ascii=False)

    # County filter options
    county_opts = "".join(
        f'<option value="{c["county"]}">{c["county"]} ({c["total"]})</option>'
        for c in stats["counties"]
    )

    # NACE filter options (group by 2-digit prefix)
    nace_seen = {}
    for ng in stats["nace_groups"]:
        prefix = ng["nace_code"][:2]
        label  = ng["nace_description"]
        nace_seen.setdefault(prefix, {"label": label, "total": 0})
        nace_seen[prefix]["total"] += ng["total"]
    nace_opts = "".join(
        f'<option value="{k}">{k} — {v["label"][:38]} ({v["total"]})</option>'
        for k, v in sorted(nace_seen.items())
    )

    # County summary cards
    county_cards = ""
    for c in stats["counties"]:
        pct_web = int(c["has_website"] * 100 / max(c["total"], 1))
        county_cards += f"""
        <div class="county-card">
            <div class="cc-name">{c["county"]}</div>
            <div class="cc-stats">
                <span class="cc-num">{c["total"]}</span><span class="cc-lbl">totalt</span>
                <span class="cc-num">{c["active"]}</span><span class="cc-lbl">aktive</span>
                <span class="cc-num">{pct_web}%</span><span class="cc-lbl">m/nettsted</span>
            </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="no">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nord-Norge Reiselivsregister</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    margin: 0; background: #f0f4f8; color: #222;
  }}
  .topbar {{
    background: linear-gradient(135deg, #0d2b45, #0e5f8a);
    color: #fff; padding: 20px 28px;
    display: flex; align-items: center; justify-content: space-between;
  }}
  .topbar h1 {{ margin: 0; font-size: 1.35em; }}
  .topbar .meta {{ font-size: 0.82em; opacity: 0.75; margin-top: 4px; }}
  .topbar .actions {{ display: flex; gap: 10px; }}
  .btn {{
    padding: 8px 16px; border-radius: 6px; border: none; cursor: pointer;
    font-size: 0.88em; font-weight: 600; text-decoration: none; display: inline-block;
  }}
  .btn-primary {{ background: #fff; color: #0d2b45; }}
  .btn-outline {{ background: transparent; color: #fff; border: 1.5px solid rgba(255,255,255,0.5); }}
  .btn-outline:hover {{ background: rgba(255,255,255,0.12); }}

  .summary {{
    display: flex; gap: 14px; padding: 18px 28px; flex-wrap: wrap;
    background: #fff; border-bottom: 1px solid #dde3ea;
  }}
  .stat-card {{
    background: #f8fafc; border-radius: 8px; padding: 14px 20px;
    text-align: center; min-width: 100px;
  }}
  .stat-card .sv {{ font-size: 2em; font-weight: 700; color: #0d2b45; }}
  .stat-card .sl {{ font-size: 0.78em; color: #666; margin-top: 2px; }}
  .stat-card.warn .sv {{ color: #b85000; }}
  .stat-card.good .sv {{ color: #1a7a3c; }}

  .county-row {{
    display: flex; gap: 10px; padding: 12px 28px; flex-wrap: wrap;
    background: #fff; border-bottom: 1px solid #dde3ea;
  }}
  .county-card {{
    background: #f0f4f8; border-radius: 6px; padding: 10px 14px; font-size: 0.85em;
  }}
  .cc-name {{ font-weight: 700; color: #0d2b45; margin-bottom: 4px; }}
  .cc-stats {{ display: flex; gap: 10px; }}
  .cc-num {{ font-weight: 700; font-size: 1.05em; }}
  .cc-lbl {{ color: #888; font-size: 0.82em; margin-left: 1px; }}

  .controls {{
    display: flex; gap: 10px; padding: 14px 28px; flex-wrap: wrap;
    background: #fff; border-bottom: 1px solid #dde3ea; align-items: center;
  }}
  .controls input, .controls select {{
    padding: 8px 12px; border: 1.5px solid #cdd5de; border-radius: 6px;
    font-size: 0.9em; background: #fff; color: #222;
  }}
  .controls input {{ min-width: 260px; }}
  .controls select {{ min-width: 160px; }}
  .controls input:focus, .controls select:focus {{
    outline: none; border-color: #0e5f8a;
  }}
  .filter-badge {{
    background: #e8f0fe; color: #0d2b45; padding: 4px 10px; border-radius: 20px;
    font-size: 0.82em; font-weight: 600; cursor: pointer;
  }}
  .filter-badge:hover {{ background: #c8dafb; }}
  #result-count {{
    margin-left: auto; font-size: 0.88em; color: #555;
  }}

  .table-wrap {{
    padding: 0 28px 40px; overflow-x: auto;
  }}
  table {{
    width: 100%; border-collapse: collapse; background: #fff;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07); border-radius: 8px;
    overflow: hidden; font-size: 0.875em; margin-top: 16px;
  }}
  thead th {{
    background: #0d2b45; color: #fff; padding: 11px 13px;
    text-align: left; white-space: nowrap; cursor: pointer; user-select: none;
  }}
  thead th:hover {{ background: #163c5e; }}
  thead th .sort-icon {{ opacity: 0.5; margin-left: 4px; }}
  thead th.sorted .sort-icon {{ opacity: 1; }}
  tbody tr {{ border-bottom: 1px solid #edf0f4; }}
  tbody tr:hover {{ background: #f5f8fc; }}
  tbody td {{ padding: 9px 13px; vertical-align: top; }}
  .td-name {{ font-weight: 600; max-width: 260px; }}
  .td-orgnr {{ font-family: monospace; font-size: 0.9em; color: #555; }}
  .td-nace  {{ font-size: 0.82em; color: #555; }}
  .td-mun   {{ max-width: 130px; }}
  .td-county {{ max-width: 160px; }}
  .td-web   {{ max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .td-web a {{ color: #0e5f8a; text-decoration: none; font-size: 0.88em; }}
  .td-web a:hover {{ text-decoration: underline; }}
  .badge {{
    display: inline-block; padding: 2px 7px; border-radius: 4px;
    font-size: 0.78em; font-weight: 600; white-space: nowrap;
  }}
  .badge-active   {{ background: #d4edda; color: #155724; }}
  .badge-dissolved{{ background: #e2e3e5; color: #383d41; }}
  .badge-bankrupt {{ background: #f8d7da; color: #721c24; }}
  .badge-winding  {{ background: #fff3cd; color: #856404; }}
  .no-web {{ color: #aaa; font-style: italic; font-size: 0.82em; }}

  .pagination {{
    display: flex; gap: 8px; align-items: center;
    padding: 0 28px 20px; justify-content: flex-end;
  }}
  .page-btn {{
    padding: 6px 12px; border: 1.5px solid #cdd5de; border-radius: 5px;
    background: #fff; cursor: pointer; font-size: 0.85em;
  }}
  .page-btn.active {{ background: #0d2b45; color: #fff; border-color: #0d2b45; }}
  .page-btn:hover:not(.active) {{ background: #f0f4f8; }}
  #page-info {{ font-size: 0.85em; color: #555; padding: 0 4px; }}
</style>
</head>
<body>

<div class="topbar">
  <div>
    <h1>Nord-Norge Reiselivsregister</h1>
    <div class="meta">
      Nordland · Troms · Finnmark · Svalbard &nbsp;|&nbsp;
      Generert: {stats["generated"]} &nbsp;|&nbsp;
      Kilde: Brønnøysundregistrene + proff.no
    </div>
  </div>
  <div class="actions">
    <button class="btn btn-outline" onclick="exportCSV()">Eksporter CSV</button>
    <button class="btn btn-primary" onclick="exportScanCSV()">Lag skanner-CSV</button>
  </div>
</div>

<div class="summary">
  <div class="stat-card">
    <div class="sv">{stats["total"]}</div>
    <div class="sl">Virksomheter totalt</div>
  </div>
  <div class="stat-card good">
    <div class="sv">{stats["active"]}</div>
    <div class="sl">Aktive</div>
  </div>
  <div class="stat-card good">
    <div class="sv">{stats["web"]}</div>
    <div class="sl">Har nettsted</div>
  </div>
  <div class="stat-card warn">
    <div class="sv">{stats["no_web"]}</div>
    <div class="sl">Mangler nettsted (aktive)</div>
  </div>
  <div class="stat-card">
    <div class="sv">{stats["svalbard"]}</div>
    <div class="sl">Svalbard</div>
  </div>
  <div class="stat-card">
    <div class="sv">{len(stats["counties"])}</div>
    <div class="sl">Fylker</div>
  </div>
</div>

<div class="county-row">
  {county_cards}
</div>

<div class="controls">
  <input type="search" id="search-box" placeholder="Søk på navn, kommune, nettsted…" oninput="applyFilters()">
  <select id="filter-county" onchange="applyFilters()">
    <option value="">Alle fylker</option>
    {county_opts}
  </select>
  <select id="filter-nace" onchange="applyFilters()">
    <option value="">Alle NACE</option>
    {nace_opts}
  </select>
  <select id="filter-status" onchange="applyFilters()">
    <option value="active">Aktive</option>
    <option value="">Alle statuser</option>
    <option value="dissolved">Opphørt</option>
    <option value="bankrupt">Konkurs</option>
  </select>
  <select id="filter-website" onchange="applyFilters()">
    <option value="">Alle</option>
    <option value="yes">Har nettsted</option>
    <option value="no">Mangler nettsted</option>
  </select>
  <span class="filter-badge" onclick="clearFilters()">✕ Nullstill</span>
  <span id="result-count"></span>
</div>

<div class="table-wrap">
  <table id="main-table">
    <thead>
      <tr>
        <th onclick="sortBy('name')">Navn <span class="sort-icon">↕</span></th>
        <th onclick="sortBy('org_nr')">Org.nr <span class="sort-icon">↕</span></th>
        <th onclick="sortBy('nace_code')">NACE <span class="sort-icon">↕</span></th>
        <th onclick="sortBy('municipality')">Kommune <span class="sort-icon">↕</span></th>
        <th onclick="sortBy('county')">Fylke <span class="sort-icon">↕</span></th>
        <th onclick="sortBy('employees')">Ansatte <span class="sort-icon">↕</span></th>
        <th onclick="sortBy('status')">Status <span class="sort-icon">↕</span></th>
        <th onclick="sortBy('website')">Nettsted <span class="sort-icon">↕</span></th>
      </tr>
    </thead>
    <tbody id="table-body"></tbody>
  </table>
</div>

<div class="pagination" id="pagination"></div>

<script>
const RAW = {companies_json};

let filtered = [];
let sortCol  = 'name';
let sortAsc  = true;
let page     = 1;
const PAGE_SIZE = 50;

function esc(s) {{
  if (!s) return '';
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

function statusBadge(s) {{
  const map = {{
    active:     ['badge-active',   'Aktiv'],
    dissolved:  ['badge-dissolved','Opphørt'],
    bankrupt:   ['badge-bankrupt', 'Konkurs'],
    winding_down:['badge-winding','Avvikling'],
  }};
  const [cls, label] = map[s] || ['badge-dissolved', s];
  return `<span class="badge ${{cls}}">${{label}}</span>`;
}}

function webCell(url, proff) {{
  if (url) {{
    const short = url.replace(/^https?:\\/\\//, '').replace(/\\/$/, '').substring(0,38);
    return `<a href="${{esc(url)}}" target="_blank" title="${{esc(url)}}">${{esc(short)}}</a>`;
  }}
  if (proff) {{
    return `<a href="${{esc(proff)}}" target="_blank" class="no-web">proff.no →</a>`;
  }}
  return '<span class="no-web">ikke oppgitt</span>';
}}

function applyFilters() {{
  const q    = document.getElementById('search-box').value.toLowerCase();
  const cty  = document.getElementById('filter-county').value;
  const nace = document.getElementById('filter-nace').value;
  const stat = document.getElementById('filter-status').value;
  const web  = document.getElementById('filter-website').value;

  filtered = RAW.filter(r => {{
    if (q && !['name','municipality','county','website','org_nr','nace_description','street_address']
               .some(k => (r[k]||'').toLowerCase().includes(q))) return false;
    if (cty  && r.county !== cty) return false;
    if (nace && !(r.nace_code||'').startsWith(nace)) return false;
    if (stat && r.status !== stat) return false;
    if (web === 'yes' && !r.website) return false;
    if (web === 'no'  &&  r.website) return false;
    return true;
  }});

  // Sort
  filtered.sort((a, b) => {{
    const va = (a[sortCol] || '').toString().toLowerCase();
    const vb = (b[sortCol] || '').toString().toLowerCase();
    return sortAsc ? va.localeCompare(vb, 'nb') : vb.localeCompare(va, 'nb');
  }});

  page = 1;
  renderTable();
}}

function sortBy(col) {{
  if (sortCol === col) sortAsc = !sortAsc;
  else {{ sortCol = col; sortAsc = true; }}
  // Update header icons
  document.querySelectorAll('thead th').forEach(th => th.classList.remove('sorted'));
  applyFilters();
}}

function renderTable() {{
  const total  = filtered.length;
  const start  = (page - 1) * PAGE_SIZE;
  const end    = Math.min(start + PAGE_SIZE, total);
  const slice  = filtered.slice(start, end);

  document.getElementById('result-count').textContent =
    `${{total.toLocaleString('nb')}} treff`;

  const tbody = document.getElementById('table-body');
  tbody.innerHTML = slice.map(r => `
    <tr>
      <td class="td-name">${{esc(r.name)}}</td>
      <td class="td-orgnr">${{esc(r.org_nr)}}</td>
      <td class="td-nace" title="${{esc(r.nace_description)}}">${{esc(r.nace_code)}}</td>
      <td class="td-mun">${{esc(r.municipality)}}</td>
      <td class="td-county">${{esc(r.county)}}</td>
      <td>${{esc(r.employees)}}</td>
      <td>${{statusBadge(r.status)}}</td>
      <td class="td-web">${{webCell(r.website, r.proff_url)}}</td>
    </tr>`).join('');

  renderPagination(total);
}}

function renderPagination(total) {{
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const el = document.getElementById('pagination');
  if (totalPages <= 1) {{ el.innerHTML = ''; return; }}

  let html = `<span id="page-info">Side ${{page}} av ${{totalPages}}</span>`;
  const makeBtn = (n, label) =>
    `<button class="page-btn${{n===page?' active':''}}" onclick="goPage(${{n}})">${{label}}</button>`;

  html += makeBtn(1, '«');
  if (page > 2) html += makeBtn(page-1, page-1);
  html += makeBtn(page, page);
  if (page < totalPages - 1) html += makeBtn(page+1, page+1);
  html += makeBtn(totalPages, '»');
  el.innerHTML = html;
}}

function goPage(n) {{ page = n; renderTable(); window.scrollTo(0,0); }}

function clearFilters() {{
  document.getElementById('search-box').value = '';
  document.getElementById('filter-county').value = '';
  document.getElementById('filter-nace').value = '';
  document.getElementById('filter-status').value = 'active';
  document.getElementById('filter-website').value = '';
  applyFilters();
}}

function exportCSV() {{
  const cols = ['org_nr','name','nace_code','nace_description','status',
                'employees','street_address','postal_code','postal_place',
                'municipality','county','founded_year','website','phone','email'];
  const header = cols.join(',');
  const rows = filtered.map(r =>
    cols.map(c => '"' + (r[c]||'').toString().replace(/"/g,'""') + '"').join(',')
  );
  const blob = new Blob([header + '\\n' + rows.join('\\n')], {{type:'text/csv;charset=utf-8;'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'nordnorge_reiselivs_' + new Date().toISOString().slice(0,10) + '.csv';
  a.click();
}}

function exportScanCSV() {{
  const scannable = filtered.filter(r => r.website);
  if (!scannable.length) {{ alert('Ingen virksomheter med nettsted i valget.'); return; }}
  const cols = ['nace_code','nace_description','org_nr','name','website','municipality','county'];
  const header = 'category_id,category_name,company_id,company_name,url,org_nr,municipality,region,notes';
  const rows = scannable.map((r, i) =>
    [r.nace_code, r.nace_description, String(i+1).padStart(4,'0'),
     r.name, r.website, r.org_nr, r.municipality, r.county,
     `Ansatte: ${{r.employees||'?'}} | Grunnlagt: ${{r.founded_year||'?'}}`
    ].map(v => '"' + (v||'').toString().replace(/"/g,'""') + '"').join(',')
  );
  const blob = new Blob([header + '\\n' + rows.join('\\n')], {{type:'text/csv;charset=utf-8;'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'scan_ready_' + new Date().toISOString().slice(0,10) + '.csv';
  a.click();
  alert(`${{scannable.length}} virksomheter eksportert. ${{filtered.length - scannable.length}} mangler nettsted og er utelatt.`);
}}

// Init
applyFilters();
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(
        description="Build an HTML dashboard from the travel companies database"
    )
    parser.add_argument("--db",     default=DEFAULT_DB,  help=f"Database path (default: {DEFAULT_DB})")
    parser.add_argument("--output", default=DEFAULT_OUT, help=f"Output HTML path (default: {DEFAULT_OUT})")
    args = parser.parse_args()

    conn = open_db(args.db)
    print(f"Laster virksomheter fra {args.db}...")
    companies = load_companies(conn)
    stats     = load_stats(conn)
    conn.close()

    print(f"Bygger dashboard for {len(companies)} virksomheter...")
    html = build_html(companies, stats)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(args.output) // 1024
    print(f"Dashboard lagret: {args.output} ({size_kb} KB)")
    print(f"Åpne i nettleseren for å søke og utforske registeret.")


if __name__ == "__main__":
    main()
