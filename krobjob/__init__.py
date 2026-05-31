"""KrobJob — CRM + marketing/analytics layer over the company directory.

Pipeline: every company is listed as a *prospect*; when they register on the
KrobJob app they're *promoted* to *client*, at which point we enrich their social
profiles, log communications/contracts, record their sales & expenses, and run
the recommendation agent to advise on revenue/performance.

CLI + SQLite, stdlib-only. See README.md.
"""

__version__ = "0.1.0"
