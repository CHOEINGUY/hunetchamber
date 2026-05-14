#!/usr/bin/env python3
import os

import pymysql


DB_HOST = os.getenv("HUNET_DB_HOST", "49.247.214.116")
DB_PORT = int(os.getenv("HUNET_DB_PORT", "3306"))
DB_USER = os.getenv("HUNET_DB_USER", "smart_chamber")
DB_PASSWORD = os.getenv("HUNET_DB_PASSWORD", "smart_chamber")
DB_NAME = os.getenv("HUNET_DB_NAME", "smart_chamber")


DDL = """
CREATE TABLE IF NOT EXISTS fridge_readings (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    device_id VARCHAR(64) NOT NULL DEFAULT 'fridge-01',
    temp_c DECIMAL(6,2) NULL,
    humidity DECIMAL(6,2) NULL,
    target_c DECIMAL(6,2) NULL,
    band_c DECIMAL(4,2) NULL,
    fridge_on TINYINT NULL,
    armed TINYINT NULL,
    auto_mode TINYINT NULL,
    fan_percent TINYINT UNSIGNED NULL,
    led_percent TINYINT UNSIGNED NULL,
    min_off_s INT UNSIGNED NULL,
    wait_on_s INT UNSIGNED NULL,
    min_on_s INT UNSIGNED NULL,
    wait_off_s INT UNSIGNED NULL,
    state_elapsed_s INT UNSIGNED NULL,
    sensor_age_s INT NULL,
    reason VARCHAR(80) NULL,
    raw_json JSON NULL,
    PRIMARY KEY (id),
    KEY idx_created_at (created_at),
    KEY idx_device_created (device_id, created_at),
    KEY idx_device_temp (device_id, temp_c)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def main():
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        connect_timeout=8,
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(DDL)
            cur.execute("SHOW TABLES LIKE 'fridge_readings'")
            table = cur.fetchone()
            cur.execute("SHOW COLUMNS FROM fridge_readings")
            columns = cur.fetchall()
        print("Fridge DB setup OK")
        print("table:", table[0] if table else None)
        print("columns:", ", ".join(row[0] for row in columns))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
