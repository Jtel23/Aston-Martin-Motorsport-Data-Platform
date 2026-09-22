import os
import time

import psycopg
import requests
from psycopg.types.json import Jsonb


# OpenF1 API endpoint
url = "https://api.openf1.org/v1/laps?session_key=9161"

# Fetch lap data from OpenF1 with retry logic
max_attempts = 3

for attempt in range(1, max_attempts + 1):
    try:
        print(f"Fetching OpenF1 data... Attempt {attempt}/{max_attempts}")

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        json_data = response.json()

        print(f"Successfully fetched {len(json_data)} laps from OpenF1.")

        # Stop retrying after a successful request
        break

    except requests.RequestException as error:
        print(f"OpenF1 request failed: {error}")

        # Stop the pipeline if all attempts have failed
        if attempt == max_attempts:
            print("Maximum number of attempts reached. Pipeline failed.")
            raise

        print("Waiting 5 seconds before retrying...")
        time.sleep(5)


# Load database configuration from environment variables
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")


# Connect to PostgreSQL
connection = psycopg.connect(
    host=db_host,
    port=db_port,
    dbname=db_name,
    user=db_user,
    password=db_password
)

print("Database connection established successfully!")

cursor = connection.cursor()


# Create the raw laps table if it does not exist
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS openf1_laps (
        id BIGSERIAL PRIMARY KEY,
        payload JSONB,
        ingested_at TIMESTAMPTZ DEFAULT NOW(),
        source TEXT
    )
    """
)


# Ensure the lap identification columns exist
cursor.execute(
    """
    ALTER TABLE openf1_laps
    ADD COLUMN IF NOT EXISTS session_key BIGINT
    """
)

cursor.execute(
    """
    ALTER TABLE openf1_laps
    ADD COLUMN IF NOT EXISTS driver_number INTEGER
    """
)

cursor.execute(
    """
    ALTER TABLE openf1_laps
    ADD COLUMN IF NOT EXISTS lap_number INTEGER
    """
)


# Prevent duplicate laps based on their natural key
cursor.execute(
    """
    CREATE UNIQUE INDEX IF NOT EXISTS unique_lap
    ON openf1_laps (session_key, driver_number, lap_number)
    """
)


# Initialize ingestion counters
inserted_count = 0
skipped_count = 0


# Insert each lap into the raw table
for lap in json_data:
    cursor.execute(
        """
        INSERT INTO openf1_laps (
            payload,
            source,
            session_key,
            driver_number,
            lap_number
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (session_key, driver_number, lap_number)
        DO NOTHING
        """,
        (
            Jsonb(lap),
            "openf1_ingestion.py",
            lap.get("session_key"),
            lap.get("driver_number"),
            lap.get("lap_number")
        )
    )

    if cursor.rowcount == 1:
        inserted_count += 1
    else:
        skipped_count += 1


# Commit all database changes
connection.commit()


# Print ingestion summary
print(f"Inserted {inserted_count} new laps into the database.")
print(f"Skipped {skipped_count} duplicate laps.")


# Close database resources
cursor.close()
connection.close()

print("OpenF1 ingestion completed successfully!")