"""Great Expectations data-quality checks for the gold tables."""
import os
from dataclasses import dataclass, field
from datetime import date, timedelta

import great_expectations as gx
import great_expectations.expectations as gxe

from integrations.common.reader import TABLES, read_table


@dataclass
class CheckResult:
    expectation: str
    column: str | None
    success: bool
    observed: str


@dataclass
class TableResult:
    table: str
    rows: int
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self):
        return all(c.success for c in self.checks)


def _keys(*columns):
    """Key columns must be present and, together, unique."""
    unique = (
        gxe.ExpectColumnValuesToBeUnique(column=columns[0]) if len(columns) == 1
        else gxe.ExpectCompoundColumnsToBeUnique(column_list=list(columns))
    )
    return [gxe.ExpectTableRowCountToBeBetween(min_value=1), unique] + [
        gxe.ExpectColumnValuesToNotBeNull(column=c) for c in columns
    ]


def _fresh(column, max_age_days):
    """The newest date_key must be recent. Skipped for the static sample files."""
    if os.environ.get("DATA_SOURCE", "sample") == "sample":
        return []
    oldest_allowed = int((date.today() - timedelta(days=max_age_days)).strftime("%Y%m%d"))
    return [gxe.ExpectColumnMaxToBeBetween(column=column, min_value=oldest_allowed)]


def build_suites():
    return {
        "DimDate": _keys("date_key") + [
            gxe.ExpectColumnValuesToBeBetween(column="weekday", min_value=1, max_value=7),
            gxe.ExpectColumnValuesToBeBetween(column="month", min_value=1, max_value=12),
        ],
        "DimZone": _keys("zone_key") + [
            gxe.ExpectColumnValuesToNotBeNull(column="borough"),
        ],
        "DimFX": _keys("date_key") + [
            gxe.ExpectColumnValuesToBeBetween(column="usd_per_eur", min_value=0.8, max_value=1.6),
            gxe.ExpectColumnStdevToBeBetween(column="usd_per_eur", min_value=0, strict_min=True),
        ],
        "DimGDP": _keys("country_code", "year") + [
            gxe.ExpectColumnValuesToBeBetween(column="gdp_usd", min_value=0, strict_min=True),
        ],
        "FactTaxiDaily": _keys("date_key", "zone_key") + [
            gxe.ExpectColumnValuesToBeBetween(column="trips", min_value=1),
            gxe.ExpectColumnValuesToBeBetween(column="fare_amount", min_value=0),
            gxe.ExpectColumnValuesToBeBetween(column="total_amount", min_value=0),
            # Distribution: revenue per trip and trips per zone-day stay in their usual bands.
            gxe.ExpectColumnMeanToBeBetween(column="revenue_per_trip", min_value=5, max_value=150),
            gxe.ExpectColumnMedianToBeBetween(column="trips", min_value=1, max_value=20000),
        ] + _fresh("date_key", 120),
        "FactAirQualityDaily": _keys("date_key", "location_id", "pollutant") + [
            gxe.ExpectColumnValuesToBeInSet(column="pollutant", value_set=["pm25", "no2", "o3"]),
            gxe.ExpectColumnValuesToBeBetween(column="avg_value", min_value=0, max_value=500),
            # Distribution of PM2.5 only (column pm25_value is empty for other pollutants).
            gxe.ExpectColumnMeanToBeBetween(column="pm25_value", min_value=2, max_value=35),
            gxe.ExpectColumnQuantileValuesToBeBetween(
                column="pm25_value",
                quantile_ranges={"quantiles": [0.95], "value_ranges": [[None, 100]]},
            ),
        ] + _fresh("date_key", 14),
        "vw_weather_enriched": _keys("ts") + [
            gxe.ExpectColumnValuesToBeBetween(column="temperature_c", min_value=-40, max_value=50),
            gxe.ExpectColumnValuesToBeBetween(column="precipitation_mm", min_value=0, max_value=200),
            gxe.ExpectColumnValuesToBeBetween(column="relative_humidity_pct", min_value=0, max_value=100),
            gxe.ExpectColumnMeanToBeBetween(column="temperature_c", min_value=-10, max_value=35),
        ],
    }


def _prepare(table, df):
    """Adds the derived columns that the distribution checks look at."""
    if table == "FactTaxiDaily":
        df = df.assign(revenue_per_trip=df["total_amount"] / df["trips"])
    if table == "FactAirQualityDaily":
        df = df.assign(pm25_value=df["avg_value"].where(df["pollutant"] == "pm25"))
    return df


def _observed(result):
    """The most telling number GE reports for a check, as short text."""
    r = result.result or {}
    if r.get("unexpected_count"):
        sample = ", ".join(str(v) for v in (r.get("partial_unexpected_list") or [])[:3])
        return f"{r['unexpected_count']} bad rows ({r.get('unexpected_percent', 0):.2f}%)" + (f", e.g. {sample}" if sample else "")
    if "observed_value" in r:
        value = r["observed_value"]
        if isinstance(value, dict):  # quantile checks report {"quantiles": [...], "values": [...]}
            value = value.get("values", value)
        return str(round(value, 4) if isinstance(value, float) else value)
    return "ok" if result.success else "failed"


def validate(table, df):
    """Runs the table's suite on a DataFrame. Separate from run_checks so it can be tested with bad data."""
    context = gx.get_context(mode="ephemeral")
    batch = (
        context.data_sources.add_pandas(table).add_dataframe_asset(table)
        .add_batch_definition_whole_dataframe(table)
        .get_batch(batch_parameters={"dataframe": _prepare(table, df)})
    )
    outcome = batch.validate(gx.ExpectationSuite(name=table, expectations=build_suites()[table]))
    checks = [
        CheckResult(
            expectation=r.expectation_config.type,
            column=r.expectation_config.kwargs.get("column") or ", ".join(r.expectation_config.kwargs.get("column_list", [])) or None,
            success=bool(r.success),
            observed=_observed(r),
        )
        for r in outcome.results
    ]
    return TableResult(table=table, rows=len(df), checks=checks)


def run_checks(tables=None):
    """Validates the given gold tables (all of them by default) against their suites."""
    tables = list(tables) if tables else sorted(TABLES)
    unknown = [t for t in tables if t not in TABLES]
    if unknown:
        raise ValueError(f"Unknown table: {', '.join(unknown)}. Known tables: {', '.join(sorted(TABLES))}")
    return [validate(t, read_table(t)) for t in tables]
