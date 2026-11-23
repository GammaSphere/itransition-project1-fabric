# Governance policies

## Ownership

| Asset | Owner | Responsibility |
|---|---|---|
| Workspace and capacity | Workspace admin | Access, capacity monitoring, Git connection |
| Bronze layer | Data engineer | Ingestion keeps running; raw data is never edited |
| Silver and gold layers | Data engineer | Cleaning rules, schema, data-quality checks |
| Dashboards | Analyst | Correct interpretation of the measures |

## Access

Access is granted through Fabric workspace roles. Nobody receives more than the role they need.

| Role | Who | Can do |
|---|---|---|
| Admin | Workspace owner | Everything, including Git integration and role assignment |
| Member / Contributor | Data engineers | Create and edit items, run pipelines |
| Viewer | Analysts and report readers | Read `wh_gold` through the SQL endpoint; no access to bronze or silver files |

- Readers consume **gold only**. Bronze and silver are working layers.
- Automated readers (for example an external job) use a **service principal** with read access to
  `wh_gold` only, not a personal account.
- Row-level security is optional in the assignment and is not configured: the data is public and
  contains no personal information.

## Secrets

- The OpenAQ API key is stored only as a file in `lh_bronze/Files/config/`. Lakehouse files are not
  part of Git integration.
- No key, token or password is written in a notebook, dataflow, pipeline or this repository.
- Local configuration for the integrations lives in `.env`, which is git-ignored;
  `.env.example` lists the variable names without values.
- A leaked key is rotated at the provider and the file is replaced; no code change is needed.

## Data classification and privacy

All four sources are open data. Taxi trip records contain no passenger or driver identifiers;
locations are taxi zones, not addresses. No personal data is stored in any layer.

## Data quality rules

Applied when bronze is turned into silver:

| Dataset | Rule |
|---|---|
| Taxi trips | Pickup inside the file's month; drop-off after pickup; distance > 0; fare > 0; duration ≤ 12 h; pickup zone present; exact duplicates removed |
| Air quality | Only PM2.5, NO2 and O3; non-null, non-negative values; units converted to µg/m³; stations outside New York City removed |
| FX | Positive rates only; one row per calendar day, gaps carried forward and flagged |
| GDP | Years without a published value removed; one row per country and year |

Every notebook ends with checks that fail the run when they do not hold: tables are not empty,
keys are unique and not null, time bands add up to the trip count, the FX calendar has no gaps,
and every fact key exists in its dimension. A failed check stops `pl_master` before gold is
reloaded.

## Retention

| Layer | Retention |
|---|---|
| Bronze files | Kept indefinitely; they are the replayable source of truth |
| Bronze API tables | Replaced on every run; the source APIs hold the history |
| Silver | Rebuilt from bronze; Delta history kept for the default 7 days |
| Gold | Fully reloaded on every run |

## Change management

- Every Fabric item is versioned in Git. Changes are made in the repository or committed from
  the workspace, so each change has an author, a date and a diff.
- A change is released by syncing the workspace from the `main` branch.
- Schema changes to gold tables are made in the warehouse SQL files and described in the data
  dictionary in the same commit.

## Monitoring

- `pl_master` runs daily at 06:00. Run history and failures are visible in the Fabric
  **Monitoring hub**; a failure notification can be added on the pipeline schedule.
- Taxi files are published about two months late. The pipeline picks up a new month on the
  first run after it appears.

## Source licences and attribution

| Source | Terms |
|---|---|
| NYC Taxi & Limousine Commission trip records | NYC Open Data terms of use; attribution to NYC TLC |
| OpenAQ | Data from many providers under their own open licences (mostly CC BY 4.0); attribution to OpenAQ and the original provider (for New York, US EPA AirNow) |
| World Bank Open Data | CC BY 4.0; attribution to the World Bank |
| European Central Bank reference rates | Free reuse with the source acknowledged; rates are for information only |
