# KrobJob — CRM + marketing/analytics for the company directory

A stdlib-only Python + SQLite system that turns the scraped hospitality directory
into a managed pipeline: **list every company → control comms & contracts →
promote registered ones to clients → enrich their socials → log their sales &
expenses → run the agent for revenue/performance recommendations.**

This is the back office for the **KrobJob app**, which collects sales and employee
expenses from restaurant & bar owners; those feeds land in the `sales` /
`expenses` tables and drive the recommendation agent.

## Quick start

```bash
export KROBJOB_DB=krobjob/krobjob.db        # optional; this is the default location

python -m krobjob init                       # create the SQLite schema
python -m krobjob seed-udon                  # import Udon Thani companies + enriched contacts
python -m krobjob stats
```

## Pipeline

| Stage | Command |
|-------|---------|
| Browse directory | `company list [--status prospect\|client] [--venue-type bar] [--missing-contact]` |
| Inspect one | `company show "Irish Clock"` |
| Add manually | `company add "New Bar" --province "Udon Thani" --venue-type bar --phone ...` |
| **Becomes a client** | `promote "Irish Clock" --plan growth --manager Nok --fee 8000` |
| Communications | `comm log "Irish Clock" --channel email --direction out --subject ... --body ...` / `comm list ...` |
| Contracts | `contract add "Irish Clock" --title "Retainer" --status active --value 96000 --start 2026-06-01 --end 2027-06-01` / `contract list` |
| Social (for marketing) | `social add "Irish Clock" --platform instagram --url ... --followers 1200` / `social scan "Irish Clock"` |
| Sales / expenses feed | `sale log "Irish Clock" --amount 12000 --category drinks --date 2026-05-30`<br>`expense log "Irish Clock" --amount 4000 --category "staff wages"` |
| **Performance report** | `report "Irish Clock" --days 30 --html` |
| **Market trends** | `trends --province "Udon Thani" --html` |

## The agent (recommendations)

`agent.py` is **heuristics-first, Claude-optional**:

- **Offline (default):** rule-based analysis of the client's sales/expenses
  (revenue, margin, growth vs previous period, category concentration, average
  ticket) and of the directory (contactability, social coverage, segment
  clusters). Runs with no network.
- **Claude upgrade:** if `ANTHROPIC_API_KEY` is set and the `anthropic` SDK +
  network are available, `narrative()` calls Claude (model `claude-opus-4-8`,
  prompt-cached system prompt) to turn the metrics into nuanced prose. It falls
  back silently to the heuristic summary otherwise — so the same command works
  on a plane or in production. Pass `--no-claude` to force heuristics.

A specialised per-market view (e.g. the Udon Thani agent discovering trends) is
`trends --province "Udon Thani"`, which scans the whole directory for that market.

## Data model (SQLite)

`companies` (master directory; `status` = prospect→client→lost) · `clients`
(plan/manager/fee, created on promote) · `social_profiles` · `communications` ·
`contracts` · `sales` · `expenses` · `reports`. See `db.py` for the schema.

## Seeding

`seed-udon` imports `scrapers/thailand_hospitality/data/hospitality_udonthani.csv`
(~3,600 companies) as prospects, derives `venue_type` from the subcategory, and
overlays the manually-enriched `udon_barshow_contacts.csv` (phone/email/website/
facebook). To extend to other provinces, point `seed.py` at the other
`hospitality_*.csv` files.

## Notes

- The DB (`krobjob/*.db`) and rendered reports (`krobjob/reports/`) are
  git-ignored — regenerate with `init` + `seed-udon`.
- `social scan` consolidates known handles and flags missing platforms; live
  follower/post scraping is a separate network-enabled job that writes back via
  `social add`.
