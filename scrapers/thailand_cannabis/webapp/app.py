"""Flask app for B2B outreach to Thai cannabis shops.

Run with:
  python -m scrapers.thailand_cannabis.webapp.app

Opens http://localhost:8000.

Routes:
  /                       — cities sidebar + landing
  /city/<canon>           — shop table for one province, with filters
  /shop/<source_id>       — shop detail + edit form (modal-style page)
  /api/shop/<sid>/update  — POST: save manual phone/email/notes/status
  /api/shop/<sid>/log     — POST: append outreach_log entry
  /api/whatsapp/<sid>     — GET:  build wa.me URL with template merged
  /templates              — GET/POST: manage message templates
  /search?q=...           — search across all shops
"""

import os
import re
import sys
from urllib.parse import quote

from flask import Flask, abort, g, jsonify, redirect, render_template, request, url_for

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from scrapers.thailand_cannabis.webapp import db as dbmod  # noqa: E402


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )
    # Don't cache static files in dev — CSS/JS edits must be picked up on refresh
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    # Reload Jinja templates when their source files change (so template edits
    # are visible after just refreshing the browser — no server restart needed).
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True
    app.teardown_appcontext(dbmod.close_db)

    # Helpers --------------------------------------------------------------

    def shop_phone(shop: dict) -> str:
        """Best available phone: manual override > google."""
        return (shop.get("manual_phone") or shop.get("google_phone") or "").strip()

    def shop_email(shop: dict) -> str:
        return (shop.get("manual_email") or shop.get("scraped_email") or "").strip()

    def wa_format(phone: str) -> str:
        """Convert a Thai phone to international format for wa.me.

        Thai mobile numbers are 10 digits starting with 0 (e.g. 091 725 4800).
        wa.me wants country code + national number with leading 0 dropped:
        091 725 4800 -> 66917254800 (Thailand country code 66).
        Already-international (+66xxx) numbers pass through.
        """
        if not phone:
            return ""
        digits = re.sub(r"[^\d+]", "", phone)
        if digits.startswith("+"):
            return digits[1:]
        if digits.startswith("66"):
            return digits
        if digits.startswith("0"):
            return "66" + digits[1:]
        # fall-through: assume already correct
        return digits

    app.jinja_env.globals.update(
        wa_format=wa_format,
        shop_phone=shop_phone,
        shop_email=shop_email,
    )

    # Routes ---------------------------------------------------------------

    @app.route("/")
    def index():
        db = dbmod.get_db()
        cities = db.execute(
            """
            SELECT
              canonical_city AS city,
              COUNT(*) AS shop_count,
              SUM(CASE WHEN COALESCE(o.manual_phone, s.google_phone) IS NOT NULL
                          AND COALESCE(o.manual_phone, s.google_phone) != '' THEN 1 ELSE 0 END) AS phone_count,
              SUM(CASE WHEN s.lead_score >= 8 THEN 1 ELSE 0 END) AS high_quality,
              SUM(CASE WHEN o.status = 'messaged' THEN 1 ELSE 0 END) AS messaged_count,
              SUM(CASE WHEN o.status = 'replied' THEN 1 ELSE 0 END) AS replied_count
            FROM shops s
            LEFT JOIN outreach o ON o.source_id = s.source_id
            WHERE s.canonical_city IS NOT NULL
            GROUP BY canonical_city
            ORDER BY shop_count DESC
            """
        ).fetchall()
        totals = db.execute(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN lead_score >= 8 THEN 1 ELSE 0 END) AS high_total FROM shops"
        ).fetchone()
        return render_template("index.html", cities=cities, totals=totals)

    @app.route("/city/<path:canon>")
    def city(canon: str):
        # Decode + normalize (URL may be lowercased/underscored)
        canon_lookup = canon.replace("_", " ")
        db = dbmod.get_db()
        # Find the exact canonical_city value (case-insensitive)
        row = db.execute(
            "SELECT DISTINCT canonical_city FROM shops WHERE LOWER(canonical_city) = LOWER(?)",
            (canon_lookup,),
        ).fetchone()
        if not row:
            abort(404, f"No city matching {canon_lookup!r}")
        canonical = row[0]

        status_filter = request.args.get("status", "")
        min_score = int(request.args.get("min_score", 0))
        sort = request.args.get("sort", "score")
        # New filters — default ON so Bangkok-style pages are usable on first load.
        # Pass ?hide_low=0 or ?group_phones=0 to disable.
        hide_low = request.args.get("hide_low", "1") == "1"
        group_phones = request.args.get("group_phones", "1") == "1"

        where = ["s.canonical_city = ?"]
        params: list = [canonical]
        if status_filter:
            where.append("COALESCE(o.status, 'new') = ?")
            params.append(status_filter)
        if min_score > 0:
            where.append("COALESCE(s.lead_score, 0) >= ?")
            params.append(min_score)
        if hide_low:
            # Drop Google-low-confidence matches AND no-result. Keeps high, medium,
            # and rows with no confidence value (e.g. weed.th-only data).
            where.append("(s.google_match_confidence IS NULL "
                         "OR s.google_match_confidence NOT IN ('low', 'no_result'))")

        order = {
            "score": "s.lead_score DESC NULLS LAST, s.google_user_ratings DESC NULLS LAST",
            "reviews": "s.google_user_ratings DESC NULLS LAST",
            "name": "s.name COLLATE NOCASE ASC",
            "status_changed": "o.updated_at DESC NULLS LAST",
        }.get(sort, "s.lead_score DESC NULLS LAST")

        # Phone-group sizes (per phone, in this city). Joined into the main query
        # so each row knows how many duplicate listings share its phone.
        # Manual phone overrides Google phone for grouping purposes.
        phone_group_sql = """
            WITH eff AS (
              SELECT s.source_id,
                     COALESCE(o.manual_phone, s.google_phone) AS eff_phone
              FROM shops s LEFT JOIN outreach o ON o.source_id = s.source_id
              WHERE s.canonical_city = ?
            )
            SELECT eff_phone, COUNT(*) AS cnt,
                   MAX(source_id) AS dummy  -- forces aggregation
            FROM eff
            WHERE eff_phone IS NOT NULL AND eff_phone != ''
            GROUP BY eff_phone
        """
        phone_counts = {r["eff_phone"]: r["cnt"]
                        for r in db.execute(phone_group_sql, (canonical,)).fetchall()}

        if group_phones:
            # For each phone group, pick the single row with the highest lead_score
            # (ties broken by source_id for determinism). Show ALL rows that have no phone.
            where.append("""
                (COALESCE(o.manual_phone, s.google_phone) IS NULL
                 OR COALESCE(o.manual_phone, s.google_phone) = ''
                 OR s.source_id = (
                    SELECT s2.source_id FROM shops s2
                    LEFT JOIN outreach o2 ON o2.source_id = s2.source_id
                    WHERE s2.canonical_city = s.canonical_city
                      AND COALESCE(o2.manual_phone, s2.google_phone)
                          = COALESCE(o.manual_phone, s.google_phone)
                    ORDER BY s2.lead_score DESC NULLS LAST, s2.source_id ASC
                    LIMIT 1
                 ))
            """)

        rows = db.execute(
            f"""
            SELECT
              s.*,
              COALESCE(o.status, 'new') AS status,
              o.manual_phone, o.manual_email, o.notes, o.updated_at AS outreach_updated_at
            FROM shops s
            LEFT JOIN outreach o ON o.source_id = s.source_id
            WHERE {' AND '.join(where)}
            ORDER BY {order}
            """,
            params,
        ).fetchall()

        # Attach phone_group_size to each row (Row objects are read-only; use dicts).
        rows_out = []
        for r in rows:
            d = dict(r)
            eff_phone = d.get("manual_phone") or d.get("google_phone") or ""
            d["phone_group_size"] = phone_counts.get(eff_phone, 1) if eff_phone else 1
            rows_out.append(d)

        # Status counts respect ALL active filters EXCEPT status itself (so the
        # chip labels show "what would I see if I clicked this status?").
        status_where = ["s.canonical_city = ?"]
        status_params: list = [canonical]
        if min_score > 0:
            status_where.append("COALESCE(s.lead_score, 0) >= ?")
            status_params.append(min_score)
        if hide_low:
            status_where.append("(s.google_match_confidence IS NULL "
                                "OR s.google_match_confidence NOT IN ('low', 'no_result'))")
        if group_phones:
            status_where.append("""
                (COALESCE(o.manual_phone, s.google_phone) IS NULL
                 OR COALESCE(o.manual_phone, s.google_phone) = ''
                 OR s.source_id = (
                    SELECT s2.source_id FROM shops s2
                    LEFT JOIN outreach o2 ON o2.source_id = s2.source_id
                    WHERE s2.canonical_city = s.canonical_city
                      AND COALESCE(o2.manual_phone, s2.google_phone)
                          = COALESCE(o.manual_phone, s.google_phone)
                    ORDER BY s2.lead_score DESC NULLS LAST, s2.source_id ASC
                    LIMIT 1
                 ))
            """)
        status_counts = {
            r["status"]: r["c"]
            for r in db.execute(
                f"""
                SELECT COALESCE(o.status, 'new') AS status, COUNT(*) AS c
                FROM shops s LEFT JOIN outreach o ON o.source_id = s.source_id
                WHERE {' AND '.join(status_where)}
                GROUP BY status
                """,
                status_params,
            ).fetchall()
        }
        # Default template for the WhatsApp button (first default; fall back to first)
        tpl = db.execute(
            "SELECT * FROM templates WHERE channel='whatsapp' ORDER BY is_default DESC, id ASC LIMIT 1"
        ).fetchone()
        all_templates = db.execute(
            "SELECT * FROM templates WHERE channel='whatsapp' ORDER BY is_default DESC, name"
        ).fetchall()

        return render_template(
            "city.html",
            city=canonical,
            shops=rows_out,
            status_counts=status_counts,
            current_status=status_filter,
            current_min_score=min_score,
            current_sort=sort,
            current_hide_low=hide_low,
            current_group_phones=group_phones,
            default_template=tpl,
            all_templates=all_templates,
        )

    @app.route("/shop/<sid>")
    def shop(sid: str):
        db = dbmod.get_db()
        row = db.execute(
            """
            SELECT s.*, COALESCE(o.status, 'new') AS status,
                   o.manual_phone, o.manual_email, o.notes, o.updated_at AS outreach_updated_at
            FROM shops s LEFT JOIN outreach o ON o.source_id = s.source_id
            WHERE s.source_id = ?
            """,
            (sid,),
        ).fetchone()
        if not row:
            abort(404)
        log = db.execute(
            "SELECT * FROM outreach_log WHERE source_id = ? ORDER BY created_at DESC LIMIT 50",
            (sid,),
        ).fetchall()
        templates = db.execute(
            "SELECT * FROM templates WHERE channel='whatsapp' ORDER BY is_default DESC, name"
        ).fetchall()
        return render_template("shop.html", shop=row, log=log, templates=templates)

    @app.post("/api/shop/<sid>/update")
    def api_update(sid: str):
        data = request.get_json(silent=True) or request.form
        db = dbmod.get_db()
        if not db.execute("SELECT 1 FROM shops WHERE source_id = ?", (sid,)).fetchone():
            return jsonify({"error": "shop not found"}), 404
        dbmod.ensure_outreach_row(sid)

        fields = {}
        for k in ("status", "manual_phone", "manual_email", "notes"):
            if k in data:
                v = data.get(k)
                if isinstance(v, str):
                    v = v.strip()
                fields[k] = v or None
        if not fields:
            return jsonify({"error": "no fields to update"}), 400

        # Build dynamic UPDATE
        sets = ", ".join(f"{k} = ?" for k in fields.keys())
        params = list(fields.values()) + [dbmod.now_iso(), sid]
        db.execute(
            f"UPDATE outreach SET {sets}, updated_at = ? WHERE source_id = ?",
            params,
        )
        db.commit()
        dbmod.log_action(sid, "edited", "; ".join(f"{k}={v!r}" for k, v in fields.items()))
        return jsonify({"ok": True})

    @app.post("/api/shop/<sid>/log")
    def api_log(sid: str):
        data = request.get_json(silent=True) or request.form
        action = (data.get("action") or "").strip()
        detail = (data.get("detail") or "").strip()
        if not action:
            return jsonify({"error": "action required"}), 400
        dbmod.ensure_outreach_row(sid)
        dbmod.log_action(sid, action, detail)
        # If they actually opened WhatsApp/called, auto-bump status to messaged
        # ONLY if currently 'new' (don't downgrade a higher status).
        if action in ("whatsapp_opened", "called", "emailed"):
            db = dbmod.get_db()
            db.execute(
                "UPDATE outreach SET status='messaged', updated_at=? WHERE source_id=? AND status='new'",
                (dbmod.now_iso(), sid),
            )
            db.commit()
        return jsonify({"ok": True})

    @app.get("/api/whatsapp/<sid>")
    def api_whatsapp(sid: str):
        """Return {url, message} ready to open. Does not auto-open — caller does it."""
        db = dbmod.get_db()
        shop = db.execute(
            """
            SELECT s.*, o.manual_phone
            FROM shops s LEFT JOIN outreach o ON o.source_id = s.source_id
            WHERE s.source_id = ?
            """,
            (sid,),
        ).fetchone()
        if not shop:
            return jsonify({"error": "shop not found"}), 404
        tpl_id = request.args.get("template_id")
        if tpl_id:
            tpl = db.execute("SELECT * FROM templates WHERE id = ?", (tpl_id,)).fetchone()
        else:
            tpl = db.execute(
                "SELECT * FROM templates WHERE channel='whatsapp' "
                "ORDER BY is_default DESC, id ASC LIMIT 1"
            ).fetchone()
        if not tpl:
            return jsonify({"error": "no templates defined"}), 400

        message = tpl["body"]
        message = message.replace("{shop_name}", shop["name"] or "")
        message = message.replace("{city}", shop["canonical_city"] or "")

        phone = shop_phone(dict(shop))
        wa_num = wa_format(phone)
        if not wa_num:
            return jsonify({"error": "no phone number on file for this shop"}), 400
        url = f"https://wa.me/{wa_num}?text={quote(message)}"
        return jsonify({"url": url, "message": message, "phone_used": phone})

    @app.route("/templates", methods=["GET", "POST"])
    def templates_page():
        db = dbmod.get_db()
        if request.method == "POST":
            tid = request.form.get("id")
            name = (request.form.get("name") or "").strip()
            body = (request.form.get("body") or "").strip()
            channel = request.form.get("channel") or "whatsapp"
            is_default = 1 if request.form.get("is_default") else 0
            if not name or not body:
                abort(400, "name and body are required")
            if is_default:
                db.execute("UPDATE templates SET is_default = 0 WHERE channel = ?", (channel,))
            if tid:
                db.execute(
                    "UPDATE templates SET name=?, body=?, channel=?, is_default=? WHERE id=?",
                    (name, body, channel, is_default, tid),
                )
            else:
                db.execute(
                    "INSERT INTO templates (name, body, channel, is_default, created_at) VALUES (?, ?, ?, ?, ?)",
                    (name, body, channel, is_default, dbmod.now_iso()),
                )
            db.commit()
            return redirect(url_for("templates_page"))
        templates = db.execute(
            "SELECT * FROM templates ORDER BY channel, is_default DESC, name"
        ).fetchall()
        return render_template("templates.html", templates=templates)

    @app.post("/templates/<int:tid>/delete")
    def template_delete(tid: int):
        db = dbmod.get_db()
        db.execute("DELETE FROM templates WHERE id = ?", (tid,))
        db.commit()
        return redirect(url_for("templates_page"))

    @app.get("/search")
    def search():
        q = (request.args.get("q") or "").strip()
        rows = []
        if q:
            db = dbmod.get_db()
            like = f"%{q}%"
            rows = db.execute(
                """
                SELECT s.*, COALESCE(o.status, 'new') AS status,
                       o.manual_phone, o.manual_email
                FROM shops s LEFT JOIN outreach o ON o.source_id = s.source_id
                WHERE s.name LIKE ?
                   OR s.address LIKE ?
                   OR s.canonical_city LIKE ?
                   OR COALESCE(o.manual_phone, s.google_phone) LIKE ?
                ORDER BY s.lead_score DESC NULLS LAST
                LIMIT 200
                """,
                (like, like, like, like),
            ).fetchall()
        return render_template("search.html", q=q, rows=rows)

    return app


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    # Auto-initialize DB if missing
    if not os.path.exists(dbmod.DB_PATH):
        print(f"[app] DB not found at {dbmod.DB_PATH}, initializing...")
        dbmod.init_db()
        print("[app] Run 'python -m scrapers.thailand_cannabis.webapp.import_csvs' to load shop data.")
    else:
        # Still call init_db to apply any schema additions (idempotent)
        dbmod.init_db()

    app = create_app()
    print(f"[app] starting on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
