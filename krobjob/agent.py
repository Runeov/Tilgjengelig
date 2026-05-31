"""Recommendation agent — heuristics now, Claude API when available.

Two products:
  performance_report(company_id, days)  -> revenue/cost/profit analysis + advice
  market_trends(province)               -> directory-level opportunity scan

Both return a dict with a heuristic `recommendations` list. `narrative()` upgrades
the prose with Claude if ANTHROPIC_API_KEY + the `anthropic` SDK + network are
present; otherwise it falls back to a heuristic summary (fully offline).
"""

import os
from collections import Counter, defaultdict
from datetime import date, timedelta

from . import db


# ----------------------------- performance ---------------------------------

def performance_report(company_id: int, days: int = 30) -> dict:
    conn = db.connect()
    today = date.today()
    cur_start = today - timedelta(days=days)
    prev_start = today - timedelta(days=2 * days)

    def _sum(table, start, end):
        rows = conn.execute(
            f"SELECT occurred_on, amount, category FROM {table} "
            "WHERE company_id=? AND occurred_on>=? AND occurred_on<?",
            (company_id, start.isoformat(), end.isoformat()),
        ).fetchall()
        return rows

    sales_cur = _sum("sales", cur_start, today + timedelta(days=1))
    sales_prev = _sum("sales", prev_start, cur_start)
    exp_cur = _sum("expenses", cur_start, today + timedelta(days=1))
    name = conn.execute("SELECT name FROM companies WHERE id=?", (company_id,)).fetchone()
    conn.close()

    rev = sum(r["amount"] for r in sales_cur)
    rev_prev = sum(r["amount"] for r in sales_prev)
    cost = sum(r["amount"] for r in exp_cur)
    profit = rev - cost
    margin = (profit / rev * 100) if rev else 0.0
    growth = ((rev - rev_prev) / rev_prev * 100) if rev_prev else None

    by_sales_cat = Counter()
    for r in sales_cur:
        by_sales_cat[r["category"] or "uncategorized"] += r["amount"]
    by_exp_cat = Counter()
    for r in exp_cur:
        by_exp_cat[r["category"] or "uncategorized"] += r["amount"]

    recs = _performance_recs(rev, rev_prev, cost, margin, growth,
                             by_sales_cat, by_exp_cat, len(sales_cur))

    return {
        "kind": "performance",
        "company": name["name"] if name else f"#{company_id}",
        "company_id": company_id,
        "period_days": days,
        "period_start": cur_start.isoformat(),
        "period_end": today.isoformat(),
        "revenue": round(rev, 2),
        "revenue_prev": round(rev_prev, 2),
        "cost": round(cost, 2),
        "profit": round(profit, 2),
        "margin_pct": round(margin, 1),
        "growth_pct": round(growth, 1) if growth is not None else None,
        "sales_count": len(sales_cur),
        "top_sales_categories": by_sales_cat.most_common(5),
        "top_expense_categories": by_exp_cat.most_common(5),
        "recommendations": recs,
    }


def _performance_recs(rev, rev_prev, cost, margin, growth, sales_cat, exp_cat, n_sales):
    recs = []
    if rev == 0:
        recs.append("No sales logged this period — start logging daily sales so the "
                    "agent can spot trends and benchmark against the market.")
        return recs
    if growth is not None:
        if growth <= -10:
            recs.append(f"Revenue is down {abs(growth):.0f}% vs the previous period — "
                        "run a promotion on your best category and post it to social.")
        elif growth >= 15:
            recs.append(f"Revenue is up {growth:.0f}% — double down: feature the winning "
                        "items and capture reviews while momentum is high.")
    if margin < 15:
        biggest = exp_cat.most_common(1)
        extra = f" Your largest cost is '{biggest[0][0]}'." if biggest else ""
        recs.append(f"Margin is thin ({margin:.0f}%).{extra} Review pricing or trim the "
                    "top expense category.")
    elif margin > 60:
        recs.append(f"Healthy {margin:.0f}% margin — there's room to reinvest in marketing "
                    "to grow volume.")
    if sales_cat:
        top = sales_cat.most_common(1)[0]
        share = top[1] / rev * 100
        if share > 60:
            recs.append(f"'{top[0]}' drives {share:.0f}% of revenue — concentration risk; "
                        "promote a second category to diversify.")
        else:
            recs.append(f"Lead with '{top[0]}' in marketing — it's your top revenue category.")
    if n_sales and rev / n_sales:
        recs.append(f"Average ticket is {rev / n_sales:,.0f} THB — test an upsell/combo to "
                    "lift it.")
    return recs


# ------------------------------ market trends -------------------------------

def market_trends(province: str = "Udon Thani") -> dict:
    conn = db.connect()
    rows = conn.execute(
        "SELECT venue_type, phone, email, website, facebook, status "
        "FROM companies WHERE province=?", (province,)
    ).fetchall()
    conn.close()

    total = len(rows)
    by_type = Counter((r["venue_type"] or "unknown") for r in rows)
    contactable = sum(1 for r in rows if r["phone"] or r["email"])
    with_social = sum(1 for r in rows if r["facebook"])
    clients = sum(1 for r in rows if r["status"] == "client")

    recs = []
    if total:
        social_pct = with_social / total * 100
        contact_pct = contactable / total * 100
        recs.append(f"{contact_pct:.0f}% of {province} venues are contactable — "
                    f"{total - contactable} have no phone/email to chase or enrich.")
        recs.append(f"Only {social_pct:.1f}% have a social profile on file — biggest "
                    "marketing-onboarding gap and the easiest upsell.")
        bars = by_type.get("bar", 0)
        shows = by_type.get("show", 0)
        if bars or shows:
            recs.append(f"Nightlife segment: {bars} bars + {shows} show venues — a natural "
                        "cluster for a bundled 'Udon nightlife' marketing package.")
        if clients < total * 0.05:
            recs.append(f"Only {clients} are clients ({clients / total * 100:.1f}%) — large "
                        "prospect pool; prioritise the enriched, contactable bars first.")

    return {
        "kind": "market_trend",
        "province": province,
        "total_companies": total,
        "by_venue_type": by_type.most_common(),
        "contactable": contactable,
        "with_social": with_social,
        "clients": clients,
        "recommendations": recs,
    }


# ------------------------------ Claude hook ---------------------------------

def narrative(report: dict) -> str:
    """Return a prose summary. Uses Claude when available, else a heuristic blurb."""
    claude = _claude_narrative(report)
    if claude:
        return claude
    return _heuristic_narrative(report)


def _heuristic_narrative(report: dict) -> str:
    recs = report.get("recommendations", [])
    if report["kind"] == "performance":
        head = (f"{report['company']} — last {report['period_days']} days: revenue "
                f"{report['revenue']:,.0f} THB, profit {report['profit']:,.0f} THB "
                f"({report['margin_pct']}% margin).")
    else:
        head = (f"{report['province']}: {report['total_companies']} companies, "
                f"{report['clients']} clients, {report['with_social']} with social on file.")
    bullets = "\n".join(f"  - {r}" for r in recs)
    return head + "\nRecommended steps:\n" + bullets


def _claude_narrative(report: dict) -> str | None:
    """Best-effort Claude call; returns None if unavailable (no key/SDK/network)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    try:
        client = anthropic.Anthropic()
        kind = report["kind"]
        sys = ("You are a hospitality business advisor for KrobJob clients in Thailand. "
               "Given a JSON metrics report, write a concise, concrete set of "
               "recommended steps to improve revenue and performance. Be specific and "
               "actionable; 4-6 bullets max.")
        import json as _json
        msg = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=600,
            system=[{"type": "text", "text": sys,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user",
                       "content": f"Report kind: {kind}\nMetrics:\n{_json.dumps(report, ensure_ascii=False)}"}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    except Exception:
        return None
