# Setup

How to get this project running in your own Microsoft Fabric workspace.

## 1. Connect the workspace to the repository

**Prerequisites**

- A Fabric workspace on a Fabric capacity (F2 or larger, or a trial). You must be a workspace **Admin**.
- In the Fabric admin portal, tenant settings: *Users can synchronize workspace items with their
  Git repositories* and *Users can sync workspace items with GitHub repositories* are enabled.
- A GitHub personal access token for this repository: fine-grained with **Contents: Read and
  write**, or classic with the `repo` scope.

**Steps**

1. Open the workspace → **Workspace settings** → **Git integration**.
2. Choose **GitHub**, add an account with the token, then select this repository, the `main`
   branch, and the Git folder `fabric`.
3. Select **Connect and sync**. Fabric creates every item found in the `fabric/` folder.

**Expected result:** every item in the `fabric/` folder appears in the workspace.

| Item | Type | Purpose |
|---|---|---|
| `lh_bronze`, `lh_silver` | Lakehouse | Raw and cleaned layers |
| `wh_gold` | Warehouse | Star schema (6 tables, 2 views) |
| `pl_ingest_taxi`, `pl_master` | Data pipeline | Taxi file ingestion; end-to-end orchestration |
| `df_ecb_fx`, `df_worldbank_gdp`, `df_openaq` | Dataflow Gen2 | API data into bronze tables |
| `nb_taxi_months`, `nb_openaq_raw` | Notebook | Helpers for bronze ingestion |
| `nb_silver_taxi`, `nb_silver_air_quality`, `nb_silver_economy` | Notebook | Bronze → silver |
| `nb_gold_load` | Notebook | Silver → gold |
| `nb_dashboards` | Notebook | The four dashboards |

Only item definitions are stored in Git. Lakehouse files and tables are created when the
pipelines run.

## 2. One-time configuration

Some settings cannot be stored in Git and are set once in the workspace.

### 2.1 OpenAQ API key

1. Register at <https://explore.openaq.org/register> and copy the API key from your account page.
2. Save the key in a text file named `openaq_api_key.txt` (the key only, nothing else).
3. Open `lh_bronze` → **Files** → create a folder `config` → upload the file into it.

The key stays in OneLake. It is never written to Git, to a notebook, or to a dataflow.

### 2.2 Dataflow connections

Open `df_ecb_fx` and `df_worldbank_gdp` in turn. If a banner asks for credentials, choose
**Configure connection**, keep authentication **Anonymous**, and connect. Then **Save**.

`df_openaq` only reads from `lh_bronze` and needs no web connection.

### 2.3 If you use a different workspace

The repository was built in one workspace, and three kinds of reference are specific to it:

- **Dataflow destinations** (`mashup.pq` of each dataflow) contain the workspace ID and the
  `lh_bronze` lakehouse ID. Open each dataflow, re-select the destination table in `lh_bronze`,
  and save.
- **The HTTP connection** used by `pl_ingest_taxi`. Create an anonymous HTTP connection to
  `https://d37ci6vzurychx.cloudfront.net` and select it in both Copy activities.
- **The schedule** of `pl_master` (daily, 06:00) can be changed under **Schedule**.

Commit the workspace changes afterwards (**Source control → Commit**). Pipeline → notebook,
pipeline → dataflow and pipeline → lakehouse references use logical IDs and need no changes.

## 3. Run

Run `pl_master`. It takes the parameter `start_month` (default `2024-01`), the first taxi month to
load. On a small capacity keep the default; an earlier month loads more history.

Order of execution:

1. `pl_ingest_taxi` copies the missing monthly Parquet files and the zone lookup into
   `lh_bronze/Files/taxi`.
2. `nb_openaq_raw` lands the OpenAQ API responses; the three dataflows fill the bronze tables.
3. The silver notebooks clean and conform the data into `lh_silver`.
4. `nb_gold_load` loads the star schema in `wh_gold`.

Notebooks run one after another, because a small capacity cannot run several Spark sessions at once.

**Expected result of the first run**

| Where | What |
|---|---|
| `lh_bronze/Files/taxi` | One Parquet file per published month since `start_month`, plus `taxi_zone_lookup.csv` |
| `lh_bronze` tables | `ecb_fx_raw` (about 7,000 rows), `worldbank_gdp_raw` (about 65), `openaq_raw_json`, `openaq_locations_raw`, `openaq_daily_raw` |
| `lh_silver` tables | `taxi_trips` (roughly 3 million rows per month), `taxi_daily_zone`, `taxi_zones` (265), `air_quality_daily`, `fx_daily`, `gdp_yearly` |
| `wh_gold` | All six tables populated; `vw_city_daily` and `vw_revenue_usd_eur` return rows |

Every notebook ends with checks (row counts, unique keys, no null keys) and fails loudly if one
does not hold. A second run copies no taxi files and produces the same row counts.

Then open `nb_dashboards` and choose **Run all**.
