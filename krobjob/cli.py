"""KrobJob command-line interface.

  python -m krobjob init
  python -m krobjob seed-udon
  python -m krobjob company list [--status prospect|client|lost] [--province P]
                                 [--venue-type bar] [--missing-contact] [--limit N]
  python -m krobjob company show <id|name>
  python -m krobjob company add "Name" [--province ... --venue-type ... --phone ...]
  python -m krobjob promote <id|name> [--plan ... --manager ... --fee 5000]
  python -m krobjob comm log <company> --channel email --direction out --subject ... --body ...
  python -m krobjob comm list <company>
  python -m krobjob contract add <company> --title ... [--value 50000 --start 2026-06-01 --end 2027-06-01 --status active]
  python -m krobjob contract list [<company>]
  python -m krobjob social add <company> --platform facebook --url ... [--followers 1200]
  python -m krobjob social scan <company>
  python -m krobjob sale log <company> --amount 12000 [--date 2026-05-30 --category drinks --desc ...]
  python -m krobjob expense log <company> --amount 4000 [--date ... --category rent --desc ...]
  python -m krobjob report <company> [--days 30] [--html] [--no-claude]
  python -m krobjob trends [--province "Udon Thani"] [--html]
  python -m krobjob stats
"""

import argparse
import sys
from datetime import date

from . import db, seed as seedmod, agent, report as reportmod


def _resolve(conn, ident):
    try:
        row = db.find_company(conn, ident)
    except LookupError as e:
        sys.exit(f"error: {e}")
    if not row:
        sys.exit(f"error: no company matching {ident!r}")
    return row


# --------------------------------- commands ---------------------------------

def cmd_init(a):
    print("[init] schema ready at", db.init_db())


def cmd_seed_udon(a):
    db.init_db()
    seedmod.seed_udon()


def cmd_seed_city(a):
    db.init_db()
    seedmod.seed_city(a.slug, a.province)


def cmd_company_list(a):
    conn = db.connect()
    q = "SELECT id,name,venue_type,status,phone,facebook FROM companies WHERE 1=1"
    p = []
    if a.status:      q += " AND status=?";       p.append(a.status)
    if a.province:    q += " AND province=?";     p.append(a.province)
    if a.venue_type:  q += " AND venue_type=?";   p.append(a.venue_type)
    if a.missing_contact:
        q += " AND COALESCE(phone,'')='' AND COALESCE(email,'')='' AND COALESCE(website,'')=''"
    q += " ORDER BY (status='client') DESC, name LIMIT ?"
    p.append(a.limit)
    rows = conn.execute(q, p).fetchall()
    conn.close()
    for r in rows:
        flag = "★" if r["status"] == "client" else " "
        fb = "fb" if r["facebook"] else "  "
        print(f"{flag}[{r['id']:>5}] {(r['name'] or '')[:38]:40} {(r['venue_type'] or ''):10} "
              f"{r['status']:8} {fb} {r['phone'] or ''}")
    print(f"\n{len(rows)} shown")


def cmd_company_show(a):
    conn = db.connect()
    c = _resolve(conn, a.ident)
    print(f"[{c['id']}] {c['name']}  ({c['status']})")
    for k in ("name_thai", "province", "city", "venue_type", "subcategory", "phone",
              "email", "website", "facebook", "instagram", "line_id", "address", "source"):
        if c[k]:
            print(f"  {k:12}: {c[k]}")
    socials = conn.execute("SELECT platform,url,followers FROM social_profiles WHERE company_id=?",
                           (c["id"],)).fetchall()
    for s in socials:
        print(f"  social      : {s['platform']} {s['url'] or ''} {s['followers'] or ''}")
    if c["status"] == "client":
        cl = conn.execute("SELECT * FROM clients WHERE company_id=?", (c["id"],)).fetchone()
        if cl:
            print(f"  client      : plan={cl['plan']} manager={cl['account_manager']} "
                  f"fee={cl['monthly_fee']} since {cl['registered_at']}")
    nc = conn.execute("SELECT COUNT(*) n FROM communications WHERE company_id=?", (c["id"],)).fetchone()["n"]
    nk = conn.execute("SELECT COUNT(*) n FROM contracts WHERE company_id=?", (c["id"],)).fetchone()["n"]
    print(f"  comms={nc}  contracts={nk}")
    conn.close()


def cmd_company_add(a):
    conn = db.connect()
    with conn:
        cur = conn.execute(
            """INSERT INTO companies(name,province,city,venue_type,phone,email,website,
                                     facebook,address,source,status,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?, 'manual', 'prospect', ?, ?)""",
            (a.name, a.province, a.city, a.venue_type, a.phone, a.email, a.website,
             a.facebook, a.address, db.now(), db.now()))
    print(f"[add] company #{cur.lastrowid}: {a.name}")
    conn.close()


def cmd_promote(a):
    conn = db.connect()
    c = _resolve(conn, a.ident)
    with conn:
        conn.execute("UPDATE companies SET status='client', updated_at=? WHERE id=?",
                     (db.now(), c["id"]))
        conn.execute(
            """INSERT INTO clients(company_id,krobjob_account,plan,account_manager,
                                   monthly_fee,registered_at,status)
               VALUES (?,?,?,?,?,?, 'active')
               ON CONFLICT(company_id) DO UPDATE SET
                 plan=excluded.plan, account_manager=excluded.account_manager,
                 monthly_fee=excluded.monthly_fee""",
            (c["id"], a.account, a.plan, a.manager, a.fee, db.now()))
    print(f"[promote] {c['name']} → CLIENT (plan={a.plan}, manager={a.manager})")
    conn.close()


def cmd_comm_log(a):
    conn = db.connect()
    c = _resolve(conn, a.company)
    with conn:
        conn.execute(
            """INSERT INTO communications(company_id,channel,direction,subject,body,
                                          occurred_at,operator,created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (c["id"], a.channel, a.direction, a.subject, a.body,
             a.at or db.now(), a.operator, db.now()))
    print(f"[comm] logged {a.direction} {a.channel} for {c['name']}")
    conn.close()


def cmd_comm_list(a):
    conn = db.connect()
    c = _resolve(conn, a.company)
    rows = conn.execute(
        "SELECT occurred_at,channel,direction,subject FROM communications "
        "WHERE company_id=? ORDER BY occurred_at DESC LIMIT 50", (c["id"],)).fetchall()
    conn.close()
    print(f"# communications — {c['name']}")
    for r in rows:
        print(f"  {r['occurred_at'][:16]}  {r['direction']:3} {r['channel']:8} {r['subject'] or ''}")


def cmd_contract_add(a):
    conn = db.connect()
    c = _resolve(conn, a.company)
    with conn:
        cur = conn.execute(
            """INSERT INTO contracts(company_id,title,status,value,start_date,end_date,
                                     signed_at,notes,created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (c["id"], a.title, a.status, a.value, a.start, a.end,
             db.now() if a.status in ("signed", "active") else None, a.notes, db.now()))
    print(f"[contract] #{cur.lastrowid} '{a.title}' ({a.status}) for {c['name']}")
    conn.close()


def cmd_contract_list(a):
    conn = db.connect()
    if a.company:
        c = _resolve(conn, a.company)
        rows = conn.execute("SELECT * FROM contracts WHERE company_id=? ORDER BY created_at DESC",
                            (c["id"],)).fetchall()
    else:
        rows = conn.execute(
            "SELECT ct.*, co.name FROM contracts ct JOIN companies co ON co.id=ct.company_id "
            "ORDER BY ct.created_at DESC LIMIT 100").fetchall()
    conn.close()
    for r in rows:
        nm = r["name"] if "name" in r.keys() else ""
        print(f"  #{r['id']:>4} {r['status']:8} {str(r['value'] or '—'):>10} THB  "
              f"{r['start_date'] or '?'}→{r['end_date'] or '?'}  {r['title']}  {nm}")


def cmd_social_add(a):
    conn = db.connect()
    c = _resolve(conn, a.company)
    with conn:
        conn.execute(
            """INSERT INTO social_profiles(company_id,platform,handle,url,followers,last_checked)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(company_id,platform) DO UPDATE SET
                 handle=excluded.handle, url=excluded.url, followers=excluded.followers,
                 last_checked=excluded.last_checked""",
            (c["id"], a.platform, a.handle, a.url, a.followers, db.now()))
        if a.platform == "facebook" and a.url:
            conn.execute("UPDATE companies SET facebook=? WHERE id=?", (a.url, c["id"]))
        if a.platform == "instagram" and a.url:
            conn.execute("UPDATE companies SET instagram=? WHERE id=?", (a.url, c["id"]))
    print(f"[social] {a.platform} set for {c['name']}")
    conn.close()


def cmd_social_scan(a):
    """Offline 'scan': surface social handles already known + where to look.

    Network scraping is a separate networked job; here we consolidate what's on
    file and flag platforms still missing so they can be added manually.
    """
    conn = db.connect()
    c = _resolve(conn, a.company)
    have = {s["platform"] for s in conn.execute(
        "SELECT platform FROM social_profiles WHERE company_id=?", (c["id"],)).fetchall()}
    if c["facebook"]:
        have.add("facebook")
    conn.close()
    want = {"facebook", "instagram", "tiktok", "line"}
    print(f"# social scan — {c['name']}")
    print(f"  on file : {', '.join(sorted(have)) or 'none'}")
    print(f"  missing : {', '.join(sorted(want - have)) or 'none'}")
    if c["facebook"]:
        print(f"  facebook: {c['facebook']}")
    print("  (live follower/post scraping runs in a network-enabled job; "
          "use `social add` to record findings)")


def cmd_money_log(a, table):
    conn = db.connect()
    c = _resolve(conn, a.company)
    if c["status"] != "client":
        print(f"  note: {c['name']} is a {c['status']}, not a client — logging anyway")
    with conn:
        conn.execute(
            f"""INSERT INTO {table}(company_id,occurred_on,amount,category,description,created_at)
                VALUES (?,?,?,?,?,?)""",
            (c["id"], a.date or date.today().isoformat(), a.amount, a.category,
             a.desc, db.now()))
    print(f"[{table[:-1]}] {a.amount:,.0f} THB for {c['name']} on {a.date or date.today().isoformat()}")
    conn.close()


def cmd_report(a):
    conn = db.connect()
    c = _resolve(conn, a.company)
    conn.close()
    rep = agent.performance_report(c["id"], days=a.days)
    narrative = agent._heuristic_narrative(rep) if a.no_claude else agent.narrative(rep)
    print(narrative)
    if a.html:
        path = reportmod.render(rep, narrative)
        _save_report(c["id"], rep, narrative, path)
        print(f"\n[html] {path}")


def cmd_trends(a):
    rep = agent.market_trends(province=a.province)
    narrative = agent._heuristic_narrative(rep) if a.no_claude else agent.narrative(rep)
    print(narrative)
    print("\nby venue type:", ", ".join(f"{k}={v}" for k, v in rep["by_venue_type"]))
    if a.html:
        path = reportmod.render(rep, narrative)
        _save_report(None, rep, narrative, path)
        print(f"\n[html] {path}")


def _save_report(company_id, rep, narrative, path):
    import json
    conn = db.connect()
    with conn:
        conn.execute(
            """INSERT INTO reports(company_id,kind,period_start,period_end,summary,
                                   payload_json,html_path,generated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (company_id, rep["kind"], rep.get("period_start"), rep.get("period_end"),
             narrative[:500], json.dumps(rep, ensure_ascii=False), path, db.now()))
    conn.close()


def cmd_stats(a):
    conn = db.connect()
    g = lambda q, *p: conn.execute(q, p).fetchone()[0]
    contactable_q = ("SELECT COUNT(*) FROM companies "
                     "WHERE COALESCE(phone,'')<>'' OR COALESCE(email,'')<>''")
    social_q = "SELECT COUNT(*) FROM companies WHERE COALESCE(facebook,'')<>''"
    print("KrobJob directory")
    print(f"  companies  : {g('SELECT COUNT(*) FROM companies')}")
    print(f"  prospects  : {g('SELECT COUNT(*) FROM companies WHERE status=?', 'prospect')}")
    print(f"  clients    : {g('SELECT COUNT(*) FROM companies WHERE status=?', 'client')}")
    print(f"  contactable: {g(contactable_q)}")
    print(f"  w/ social  : {g(social_q)}")
    print(f"  comms      : {g('SELECT COUNT(*) FROM communications')}")
    print(f"  contracts  : {g('SELECT COUNT(*) FROM contracts')}")
    print(f"  sales rows : {g('SELECT COUNT(*) FROM sales')}   expenses: {g('SELECT COUNT(*) FROM expenses')}")
    conn.close()


# --------------------------------- parser -----------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="krobjob", description="KrobJob CRM + agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(fn=cmd_init)
    sub.add_parser("seed-udon").set_defaults(fn=cmd_seed_udon)
    sc = sub.add_parser("seed-city"); sc.add_argument("slug")
    sc.add_argument("--province", required=True); sc.set_defaults(fn=cmd_seed_city)
    sub.add_parser("stats").set_defaults(fn=cmd_stats)

    co = sub.add_parser("company").add_subparsers(dest="sub", required=True)
    cl = co.add_parser("list"); cl.set_defaults(fn=cmd_company_list)
    cl.add_argument("--status"); cl.add_argument("--province"); cl.add_argument("--venue-type")
    cl.add_argument("--missing-contact", action="store_true"); cl.add_argument("--limit", type=int, default=40)
    cs = co.add_parser("show"); cs.add_argument("ident"); cs.set_defaults(fn=cmd_company_show)
    ca = co.add_parser("add"); ca.add_argument("name")
    for opt in ("province", "city", "venue-type", "phone", "email", "website", "facebook", "address"):
        ca.add_argument("--" + opt)
    ca.set_defaults(fn=cmd_company_add)

    pr = sub.add_parser("promote"); pr.add_argument("ident")
    pr.add_argument("--plan"); pr.add_argument("--manager"); pr.add_argument("--account")
    pr.add_argument("--fee", type=float); pr.set_defaults(fn=cmd_promote)

    cm = sub.add_parser("comm").add_subparsers(dest="sub", required=True)
    cml = cm.add_parser("log"); cml.add_argument("company")
    cml.add_argument("--channel", required=True); cml.add_argument("--direction", default="out")
    cml.add_argument("--subject"); cml.add_argument("--body"); cml.add_argument("--at")
    cml.add_argument("--operator"); cml.set_defaults(fn=cmd_comm_log)
    cmls = cm.add_parser("list"); cmls.add_argument("company"); cmls.set_defaults(fn=cmd_comm_list)

    ct = sub.add_parser("contract").add_subparsers(dest="sub", required=True)
    cta = ct.add_parser("add"); cta.add_argument("company"); cta.add_argument("--title", required=True)
    cta.add_argument("--status", default="draft"); cta.add_argument("--value", type=float)
    cta.add_argument("--start"); cta.add_argument("--end"); cta.add_argument("--notes")
    cta.set_defaults(fn=cmd_contract_add)
    ctl = ct.add_parser("list"); ctl.add_argument("company", nargs="?"); ctl.set_defaults(fn=cmd_contract_list)

    so = sub.add_parser("social").add_subparsers(dest="sub", required=True)
    soa = so.add_parser("add"); soa.add_argument("company"); soa.add_argument("--platform", required=True)
    soa.add_argument("--handle"); soa.add_argument("--url"); soa.add_argument("--followers", type=int)
    soa.set_defaults(fn=cmd_social_add)
    sos = so.add_parser("scan"); sos.add_argument("company"); sos.set_defaults(fn=cmd_social_scan)

    sa = sub.add_parser("sale").add_subparsers(dest="sub", required=True)
    sal = sa.add_parser("log"); sal.add_argument("company"); sal.add_argument("--amount", type=float, required=True)
    sal.add_argument("--date"); sal.add_argument("--category"); sal.add_argument("--desc")
    sal.set_defaults(fn=lambda a: cmd_money_log(a, "sales"))

    ex = sub.add_parser("expense").add_subparsers(dest="sub", required=True)
    exl = ex.add_parser("log"); exl.add_argument("company"); exl.add_argument("--amount", type=float, required=True)
    exl.add_argument("--date"); exl.add_argument("--category"); exl.add_argument("--desc")
    exl.set_defaults(fn=lambda a: cmd_money_log(a, "expenses"))

    rp = sub.add_parser("report"); rp.add_argument("company"); rp.add_argument("--days", type=int, default=30)
    rp.add_argument("--html", action="store_true"); rp.add_argument("--no-claude", action="store_true")
    rp.set_defaults(fn=cmd_report)

    tr = sub.add_parser("trends"); tr.add_argument("--province", default="Udon Thani")
    tr.add_argument("--html", action="store_true"); tr.add_argument("--no-claude", action="store_true")
    tr.set_defaults(fn=cmd_trends)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
