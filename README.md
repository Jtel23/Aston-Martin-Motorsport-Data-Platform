# Aston Martin Motorsport Data Platform 🏎️

An educational Data Engineering project focused on building a motorsport data platform using real-world racing data.

The project is being developed incrementally, with each version introducing new Data Engineering concepts and technologies.

> **Disclaimer:** This is an unofficial educational project and is not affiliated with Aston Martin, Aston Martin Racing, Formula 1, or OpenF1.

## V1 — OpenF1 Data Ingestion Pipeline

The first version implements a containerized ingestion pipeline that retrieves Formula 1 lap data from the OpenF1 API and stores the raw data in PostgreSQL.

The main goal of V1 is to establish a reliable and reproducible ingestion layer before introducing transformations, orchestration, cloud infrastructure, and additional motorsport data sources.

## Architecture

```text
OpenF1 API
    │
    │ HTTP GET
    ▼
Python Ingestion
    │
    │ JSON
    ▼
PostgreSQL
    │
    ├── Raw JSONB payload
    ├── Ingestion metadata
    └── Natural key
    │
    ▼
Docker Volume
```

The application and database run as separate Docker containers managed by Docker Compose.

## Tech Stack

* Python 3.12
* PostgreSQL 17
* Docker
* Docker Compose
* Requests
* Psycopg 3
* OpenF1 API

## Data Flow

The V1 pipeline follows these steps:

1. Request lap data from the OpenF1 API.
2. Validate the HTTP response.
3. Convert the response into Python objects.
4. Connect to PostgreSQL.
5. Preserve the complete source object as `JSONB`.
6. Store identifying metadata for each lap.
7. Prevent duplicate records using a natural key.
8. Commit the ingestion batch.
9. Report inserted and skipped records.

## Raw Data Model

Each OpenF1 lap is stored as one row in the `openf1_laps` table.

The original API object is preserved in the `payload` column as `JSONB`.

Additional metadata includes:

* `id`
* `session_key`
* `driver_number`
* `lap_number`
* `source`
* `ingested_at`

The combination below represents the natural key used by V1:

```text
session_key + driver_number + lap_number
```

A unique PostgreSQL index prevents multiple rows representing the same lap.

## Idempotency

The ingestion process is designed to be idempotent.

PostgreSQL enforces uniqueness on:

```sql
(session_key, driver_number, lap_number)
```

The ingestion uses:

```sql
ON CONFLICT (session_key, driver_number, lap_number)
DO NOTHING
```

This allows the same session to be processed multiple times without duplicating existing laps.

During testing, the first ingestion stored **297 lap records**. Running the same ingestion again resulted in:

```text
Inserted 0 new laps into the database.
Skipped 297 duplicate laps.
```

## Reliability

The OpenF1 request includes basic failure handling.

V1 implements:

* HTTP status validation
* Request timeout
* Up to three request attempts
* Delay between retries
* Controlled pipeline failure after the maximum number of attempts

A failure scenario was tested by intentionally using an invalid API hostname. The pipeline retried the request three times and then terminated with a non-zero exit code.

This behavior makes failures visible to future orchestration tools instead of silently reporting a successful execution.

## Observability

The ingestion job reports basic execution metrics:

```text
Inserted X new laps into the database.
Skipped Y duplicate laps.
```

These counters provide a simple way to understand the result of each ingestion run.

More advanced logging and monitoring will be introduced in future versions.

## Project Structure

```text
.
├── .gitignore
├── compose.yaml
├── README.md
└── f1/
    ├── Dockerfile
    ├── requirements.txt
    └── src/
        └── openf1_ingestion.py
```

## Running the Project

### Requirements

You need:

* Docker
* Docker Compose

### Start the pipeline

From the project root:

```bash
docker compose up --build
```

Docker Compose builds the Python ingestion image, starts PostgreSQL, executes the ingestion job, and persists PostgreSQL data using a Docker volume.

## Current Scope

V1 intentionally focuses on the ingestion layer.

It does **not** yet implement:

* Data transformation layers
* Analytical models
* Workflow orchestration
* Cloud deployment
* Automated scheduling
* GT3 or endurance ingestion

These capabilities are planned as later stages of the project.

## Roadmap

Future versions may introduce:

```text
OpenF1 / GT3 / Endurance
          │
          ▼
       Ingestion
          │
          ▼
      Raw Storage
          │
          ▼
    Transformation
          │
          ▼
   Analytical Models
          │
          ▼
 Analytics / Motorsport Insights
```

Technologies explored throughout the project may include Airflow, AWS, dbt, Snowflake, Spark, Terraform, and CI/CD as the platform evolves.

## Engineering Goals

This project is designed to practice Data Engineering concepts through an evolving real-world system, including:

* API ingestion
* Raw data preservation
* Data modeling
* Idempotency
* Data quality
* Failure handling
* Observability
* Containerization
* Orchestration
* Cloud architecture
* Incremental processing

---

**Version:** V1
**Status:** Functional ingestion pipeline

