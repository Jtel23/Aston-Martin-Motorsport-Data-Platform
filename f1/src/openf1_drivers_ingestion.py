import os
import time

import psycopg
import requests
from psycopg.types.json import Jsonb


# --------------------------------------------------
# OPENF1 API ENDPOINTS
# --------------------------------------------------

sessions_url = "https://api.openf1.org/v1/sessions"
drivers_url = "https://api.openf1.org/v1/drivers"


# --------------------------------------------------
# REQUEST CONFIGURATION
# --------------------------------------------------

max_attempts = 3
retry_delay = 5


def fetch_openf1_data(url, params=None):
    """
    Fetch data from OpenF1 with retry logic.
    """

    for attempt in range(1, max_attempts + 1):
        try:
            print(
                f"Fetching OpenF1 data... "
                f"Attempt {attempt}/{max_attempts}"
            )

            response = requests.get(
                url,
                params=params,
                timeout=30
            )

            if response.status_code == 404:
                print(
                    "No data available for this request. "
                    "Skipping..."
                )
                return []

            response.raise_for_status()

            data = response.json()

            print(
                f"Successfully fetched "
                f"{len(data)} records from OpenF1."
            )

            return data

        except requests.RequestException as error:
            print(f"OpenF1 request failed: {error}")

            if attempt == max_attempts:
                print(
                    "Maximum number of attempts reached. "
                    "Skipping this request."
                )
                return []

            wait_time = retry_delay * (2 ** (attempt - 1))

            print(
                f"Waiting {wait_time} seconds "
                f"before retrying..."
            )

            time.sleep(wait_time)


# --------------------------------------------------
# 1. FETCH AVAILABLE SESSIONS
# --------------------------------------------------

sessions = fetch_openf1_data(sessions_url)

print(
    f"\n{len(sessions)} sessions "
    f"available for driver ingestion."
)


# --------------------------------------------------
# 2. LOAD DATABASE CONFIGURATION
# --------------------------------------------------

db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")


# --------------------------------------------------
# 3. CONNECT TO POSTGRESQL
# --------------------------------------------------

connection = psycopg.connect(
    host=db_host,
    port=db_port,
    dbname=db_name,
    user=db_user,
    password=db_password
)

print("\nDatabase connection established successfully!")

cursor = connection.cursor()


# --------------------------------------------------
# 4. CREATE RAW DRIVERS TABLE
# --------------------------------------------------

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS openf1_drivers (
        id BIGSERIAL PRIMARY KEY,
        payload JSONB NOT NULL,
        ingested_at TIMESTAMPTZ DEFAULT NOW(),
        source TEXT,
        session_key BIGINT,
        meeting_key BIGINT,
        driver_number INTEGER
    )
    """
)


# --------------------------------------------------
# 5. CREATE NATURAL-KEY UNIQUE INDEX
# --------------------------------------------------

cursor.execute(
    """
    CREATE UNIQUE INDEX IF NOT EXISTS unique_driver_session
    ON openf1_drivers (
        session_key,
        driver_number
    )
    """
)

connection.commit()


# --------------------------------------------------
# 6. INITIALIZE INGESTION COUNTERS
# --------------------------------------------------

total_inserted = 0
total_skipped = 0
processed_sessions = 0


# --------------------------------------------------
# 7. PROCESS EACH SESSION
# --------------------------------------------------

for session in sessions:

    session_key = session.get("session_key")

    if session_key is None:
        print(
            "Skipping session because "
            "session_key is missing."
        )
        continue

    print(
        f"\nProcessing session "
        f"{session_key}..."
    )


    # ----------------------------------------------
    # 8. FETCH DRIVERS FOR CURRENT SESSION
    # ----------------------------------------------

    drivers = fetch_openf1_data(
        drivers_url,
        params={
            "session_key": session_key
        }
    )

    print(
        f"Session {session_key}: "
        f"{len(drivers)} drivers received."
    )


    # ----------------------------------------------
    # 9. INSERT DRIVERS INTO RAW TABLE
    # ----------------------------------------------

    session_inserted = 0
    session_skipped = 0

    for driver in drivers:

        cursor.execute(
            """
            INSERT INTO openf1_drivers (
                payload,
                source,
                session_key,
                meeting_key,
                driver_number
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s
            )
            ON CONFLICT (
                session_key,
                driver_number
            )
            DO NOTHING
            """,
            (
                Jsonb(driver),
                "openf1_drivers_ingestion.py",
                driver.get("session_key"),
                driver.get("meeting_key"),
                driver.get("driver_number")
            )
        )

        if cursor.rowcount == 1:
            session_inserted += 1
        else:
            session_skipped += 1


    # ----------------------------------------------
    # 10. COMMIT CURRENT SESSION
    # ----------------------------------------------

    connection.commit()

    total_inserted += session_inserted
    total_skipped += session_skipped
    processed_sessions += 1

    print(
        f"Session {session_key}: "
        f"{session_inserted} inserted, "
        f"{session_skipped} skipped."
    )


# --------------------------------------------------
# 11. PRINT FINAL INGESTION SUMMARY
# --------------------------------------------------

print("\n======================================")
print("OPENF1 DRIVERS INGESTION SUMMARY")
print("======================================")

print(
    f"Sessions processed: "
    f"{processed_sessions}"
)

print(
    f"New drivers inserted: "
    f"{total_inserted}"
)

print(
    f"Duplicate drivers skipped: "
    f"{total_skipped}"
)


# --------------------------------------------------
# 12. CLOSE DATABASE RESOURCES
# --------------------------------------------------

cursor.close()
connection.close()

print(
    "\nOpenF1 drivers ingestion "
    "completed successfully!"
)