import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

os.environ["DATA_SOURCE"] = "sample"

from integrations.common.reader import read_table  # noqa: E402
from integrations.dq_bot import bot  # noqa: E402
from integrations.dq_bot.report import TELEGRAM_LIMIT, format_summary, render_html  # noqa: E402
from integrations.dq_bot.suites import CheckResult, TableResult, run_checks, validate  # noqa: E402
from integrations.weather_sync import sync  # noqa: E402


# --- reader ---------------------------------------------------------------

def test_read_table_sample_since():
    everything = read_table("vw_weather_enriched", time_col="ts")
    cutoff = everything["ts"].sort_values().iloc[2]
    newer = read_table("vw_weather_enriched", since=cutoff, time_col="ts")
    assert (newer["ts"] > cutoff).all()
    assert len(newer) == len(everything) - 3


def test_read_table_rejects_unknown_name():
    with pytest.raises(ValueError):
        read_table("DimDate; DROP TABLE x")


# --- weather sync (needs the TimescaleDB container) -----------------------

@pytest.fixture
def pg():
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        pytest.skip("PG_DSN not set")
    import psycopg
    with psycopg.connect(dsn) as conn:
        conn.execute("TRUNCATE weather_enriched")
        conn.commit()
        yield conn
        conn.execute("TRUNCATE weather_enriched")
        conn.commit()


def count(conn):
    return conn.execute("SELECT count(*) FROM weather_enriched").fetchone()[0]


def test_sync_once_copies_everything_then_is_stable(pg):
    total = len(read_table("vw_weather_enriched"))
    assert sync.sync_once(pg) == total
    assert count(pg) == total
    sync.sync_once(pg)  # re-reads the lookback window
    assert count(pg) == total


def test_sync_once_reads_only_the_lookback_window(pg):
    sync.sync_once(pg)
    assert sync.sync_once(pg, lookback_days=1) == 24  # hourly rows of the last day


def test_sync_once_updates_changed_row(pg):
    sync.sync_once(pg)
    changed = read_table("vw_weather_enriched", time_col="ts")
    changed.loc[changed.index[-1], "pm25_day"] = 99.5
    with patch.object(sync, "read_table", return_value=changed):
        sync.sync_once(pg)
    assert count(pg) == len(changed)
    assert pg.execute("SELECT pm25_day FROM weather_enriched ORDER BY time DESC LIMIT 1").fetchone()[0] == 99.5


def test_sync_keeps_missing_values_as_null(pg):
    sync.sync_once(pg)  # the newest sample days have no taxi data yet
    assert pg.execute("SELECT count(*) FROM weather_enriched WHERE trips_day IS NULL").fetchone()[0] == 240


def test_run_survives_a_failed_cycle():
    connect = MagicMock(side_effect=[RuntimeError("warehouse unreachable"), RuntimeError("still down")])
    sleeps = []
    sync.run(connect=connect, sleep=sleeps.append, cycles=2)
    assert connect.call_count == 2 and len(sleeps) == 1


# --- data-quality suites --------------------------------------------------

def failed(result):
    return [c for c in result.checks if not c.success]


def test_all_suites_pass_on_sample():
    results = run_checks()
    assert len(results) == 7
    assert [r.table for r in results if not r.passed] == []


def test_null_key_fails():
    df = read_table("FactTaxiDaily").astype({"date_key": "float"})
    df.loc[0, "date_key"] = None
    result = validate("FactTaxiDaily", df)
    assert not result.passed
    assert any(c.column == "date_key" and "null" in c.expectation for c in failed(result))


def test_duplicate_key_fails():
    df = read_table("FactTaxiDaily")
    result = validate("FactTaxiDaily", pd.concat([df, df.head(1)]))
    assert any("unique" in c.expectation for c in failed(result))


def test_distribution_shift_fails():
    df = read_table("FactAirQualityDaily")
    df["avg_value"] = df["avg_value"] * 50
    result = validate("FactAirQualityDaily", df)
    assert any(c.column == "pm25_value" for c in failed(result))


def test_unknown_table_raises():
    with pytest.raises(ValueError):
        run_checks(["NoSuchTable"])


# --- report ---------------------------------------------------------------

def result_with_failures(n):
    checks = [CheckResult("expect_column_values_to_not_be_null", f"col_{i}", False, f"{i + 1} bad rows") for i in range(n)]
    return TableResult("FactTaxiDaily", 300, checks + [CheckResult("expect_table_row_count_to_be_between", None, True, "300")])


def test_summary_lists_failure_with_observed_value():
    text = format_summary([result_with_failures(1), TableResult("DimDate", 60, [CheckResult("x", "date_key", True, "ok")])])
    assert "1 of 2 tables have failures" in text
    assert "FactTaxiDaily.col_0 — expect_column_values_to_not_be_null — 1 bad rows" in text
    assert "✅ DimDate: 1/1 checks" in text


def test_summary_never_exceeds_telegram_limit():
    text = format_summary([result_with_failures(300)])
    assert len(text) <= TELEGRAM_LIMIT
    assert text.endswith("attached report.")


def test_render_html_contains_every_table_and_escapes():
    odd = TableResult("DimZone", 5, [CheckResult("x", "zone", False, "<script>")])
    html = render_html([result_with_failures(2), odd]).decode()
    assert "FactTaxiDaily" in html and "DimZone" in html
    assert "<script>" not in html


# --- bot ------------------------------------------------------------------

def make_update(chat_id):
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.message.reply_text = AsyncMock()
    update.message.reply_document = AsyncMock()
    return update


def test_unauthorised_chat_runs_nothing(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "111, 222")
    update, context = make_update(999), MagicMock(args=[])
    with patch.object(bot, "run_checks") as run:
        asyncio.run(bot.quality(update, context))
    run.assert_not_called()
    update.message.reply_text.assert_awaited_once_with("Not authorised")


def test_authorised_chat_gets_summary_and_report(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "111")
    update, context = make_update(111), MagicMock(args=["DimDate"])
    asyncio.run(bot.quality(update, context))
    assert "all checks passed" in update.message.reply_text.await_args_list[-1].args[0]
    assert update.message.reply_document.await_args.kwargs["filename"] == "quality_report.html"


def test_failure_replies_without_traceback(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "111")
    update, context = make_update(111), MagicMock(args=[])
    with patch.object(bot, "run_checks", side_effect=RuntimeError("secret connection string")):
        asyncio.run(bot.quality(update, context))
    last = update.message.reply_text.await_args_list[-1].args[0]
    assert "could not run" in last and "secret" not in last
    update.message.reply_document.assert_not_awaited()
