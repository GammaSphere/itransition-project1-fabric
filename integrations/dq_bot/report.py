"""Turns validation results into a Telegram message and an HTML report."""
from datetime import datetime, timezone
from html import escape

TELEGRAM_LIMIT = 4096
TAIL = "\n… more failures in the attached report."


def format_summary(results):
    """Plain-text summary: one line per table, then every failed check with what was observed."""
    failed_tables = [r for r in results if not r.passed]
    lines = [
        "Data quality: all checks passed ✅" if not failed_tables
        else f"Data quality: {len(failed_tables)} of {len(results)} tables have failures ❌",
        "",
    ]
    for r in results:
        ok = sum(c.success for c in r.checks)
        lines.append(f"{'✅' if r.passed else '❌'} {r.table}: {ok}/{len(r.checks)} checks, {r.rows:,} rows")
    failures = [
        f"• {r.table}.{c.column or '(table)'} — {c.expectation} — {c.observed}"
        for r in failed_tables for c in r.checks if not c.success
    ]
    if failures:
        lines += ["", "Failures:"] + failures
    text = "\n".join(lines)
    if len(text) > TELEGRAM_LIMIT:
        text = text[: TELEGRAM_LIMIT - len(TAIL)].rsplit("\n", 1)[0] + TAIL
    return text


def render_html(results):
    """One self-contained HTML file with every check of every table."""
    # shortcut: own HTML instead of GE Data Docs (a multi-file site that cannot be sent as one
    # Telegram attachment), upgrade if a hosted report is wanted.
    sections = []
    for r in results:
        rows = "".join(
            f"<tr class='{'ok' if c.success else 'bad'}'><td>{'PASS' if c.success else 'FAIL'}</td>"
            f"<td>{escape(c.column or '(table)')}</td><td>{escape(c.expectation)}</td><td>{escape(c.observed)}</td></tr>"
            for c in r.checks
        )
        sections.append(
            f"<h2>{escape(r.table)} — {'passed' if r.passed else 'FAILED'} ({r.rows:,} rows)</h2>"
            f"<table><tr><th>Result</th><th>Column</th><th>Expectation</th><th>Observed</th></tr>{rows}</table>"
        )
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Data quality report</title><style>"
        "body{font-family:system-ui,sans-serif;margin:2rem;color:#222}table{border-collapse:collapse;width:100%;margin-bottom:2rem}"
        "th,td{border:1px solid #ccc;padding:.35rem .6rem;text-align:left}th{background:#f3f3f3}"
        ".ok td:first-child{color:#0a6b2d;font-weight:600}.bad{background:#fdecec}.bad td:first-child{color:#a40000;font-weight:600}"
        f"</style></head><body><h1>Data quality report</h1><p>Generated {generated} with Great Expectations.</p>"
        + "".join(sections) + "</body></html>"
    )
    return html.encode("utf-8")
