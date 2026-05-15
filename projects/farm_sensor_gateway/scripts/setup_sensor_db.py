import os

import pymysql


DB_HOST = os.getenv("HUNET_DB_HOST", "49.247.214.116")
DB_PORT = int(os.getenv("HUNET_DB_PORT", "3306"))
DB_USER = os.getenv("HUNET_DB_USER", "smart_chamber")
DB_PASSWORD = os.getenv("HUNET_DB_PASSWORD", "smart_chamber")
DB_NAME = os.getenv("HUNET_DB_NAME", "smart_chamber")


DDL = """
CREATE TABLE IF NOT EXISTS sensor_readings (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    device_id VARCHAR(64) NOT NULL DEFAULT 'pico-w5500-01',
    air_temp DECIMAL(6,2) NULL,
    humidity DECIMAL(6,2) NULL,
    moisture DECIMAL(6,2) NULL,
    soil_temp DECIMAL(6,2) NULL,
    ec INT NULL,
    ph DECIMAL(5,2) NULL,
    n INT NULL,
    p INT NULL,
    k INT NULL,
    solar INT NULL,
    co2 INT NULL,
    nutri_ph DECIMAL(5,2) NULL,
    nutri_temp DECIMAL(5,2) NULL,
    nutri_ec INT NULL,
    nutri_tds INT NULL,
    nutri_salinity INT NULL,
    nutri_orp INT NULL,
    nutri_turbidity DECIMAL(6,2) NULL,
    nutri_do DECIMAL(5,2) NULL,
    relay TINYINT NULL,
    raw_json JSON NULL,
    PRIMARY KEY (id),
    KEY idx_created_at (created_at),
    KEY idx_device_created (device_id, created_at)
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
            cur.execute("SHOW TABLES LIKE 'sensor_readings'")
            table = cur.fetchone()
            cur.execute("SHOW COLUMNS FROM sensor_readings")
            columns = cur.fetchall()
        print("DB setup OK")
        print("table:", table[0] if table else None)
        print("columns:", ", ".join(row[0] for row in columns))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
