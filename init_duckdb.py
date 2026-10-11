"""
DuckDB Database Initialization & Migration Script for Agri Oracle
Migrates all historical Mandi Prices, Weather, NASA Agronomics, Model Metrics, and Forecasts
into a high-performance local DuckDB database: agri_oracle.duckdb
"""

import os
import glob
import json
import duckdb
import pandas as pd
import numpy as np
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "agri_oracle.duckdb"))
BASE_DATASETS = os.environ.get("DATASETS_DIR", os.path.join(BASE_DIR, "datasets"))
PREDICTIONS_DIR = os.environ.get("PREDICTIONS_DIR", os.path.join(BASE_DIR, "predictions"))

# Mandi Coordinate Metadata
MARKET_COORDS = {
    # Mosambi
    "Anantapur": {"lat": 14.6819, "lon": 77.6006, "state": "Andhra Pradesh", "diesel": 96.4},
    "Bangalore": {"lat": 12.9716, "lon": 77.5946, "state": "Karnataka", "diesel": 89.2},
    "Nagpur": {"lat": 21.1458, "lon": 79.0882, "state": "Maharashtra", "diesel": 92.5},
    "Aurangabad": {"lat": 19.8762, "lon": 75.3433, "state": "Maharashtra", "diesel": 92.5},
    "Hyderabad": {"lat": 17.3850, "lon": 78.4867, "state": "Telangana", "diesel": 95.8},
    "Azadpur": {"lat": 28.7041, "lon": 77.1025, "state": "NCT of Delhi", "diesel": 87.6},
    "Jodhpur": {"lat": 26.2389, "lon": 73.0243, "state": "Rajasthan", "diesel": 93.7},
    "Lucknow": {"lat": 26.8467, "lon": 80.9462, "state": "Uttar Pradesh", "diesel": 89.7},
    "Sultanpur": {"lat": 26.2648, "lon": 82.0727, "state": "Uttar Pradesh", "diesel": 89.7},
    "Mechua": {"lat": 22.5726, "lon": 88.3639, "state": "West Bengal", "diesel": 92.8},
    # Rice - Telangana
    "Suryapeta": {"lat": 17.1439, "lon": 79.6239, "state": "Telangana", "diesel": 95.8},
    "Nizamabad": {"lat": 18.6725, "lon": 78.0941, "state": "Telangana", "diesel": 95.8},
    "Karimnagar": {"lat": 18.4386, "lon": 79.1288, "state": "Telangana", "diesel": 95.8},
    "Warangal": {"lat": 17.9689, "lon": 79.5941, "state": "Telangana", "diesel": 95.8},
    "Miryalaguda": {"lat": 16.8724, "lon": 79.5647, "state": "Telangana", "diesel": 95.8},
    "Badepalli": {"lat": 16.7450, "lon": 78.1400, "state": "Telangana", "diesel": 95.8},
    "Siddipet": {"lat": 18.1018, "lon": 78.8520, "state": "Telangana", "diesel": 95.8},
    "Choppadandi": {"lat": 18.5772, "lon": 79.1764, "state": "Telangana", "diesel": 95.8},
    # Rice - Andhra Pradesh
    "Tadepalligudem": {"lat": 16.8142, "lon": 81.5268, "state": "Andhra Pradesh", "diesel": 96.4},
    "Rajahmundry": {"lat": 17.0005, "lon": 81.8040, "state": "Andhra Pradesh", "diesel": 96.4},
    "Repalli": {"lat": 16.0200, "lon": 80.8500, "state": "Andhra Pradesh", "diesel": 96.4},
    "Narasaraopet": {"lat": 16.2344, "lon": 80.0469, "state": "Andhra Pradesh", "diesel": 96.4},
    "Nandyal": {"lat": 15.4800, "lon": 78.4800, "state": "Andhra Pradesh", "diesel": 96.4},
    "Ongole": {"lat": 15.5057, "lon": 80.0499, "state": "Andhra Pradesh", "diesel": 96.4},
    "Chirala": {"lat": 15.8246, "lon": 80.3522, "state": "Andhra Pradesh", "diesel": 96.4},
    "Divi": {"lat": 16.0500, "lon": 80.9500, "state": "Andhra Pradesh", "diesel": 96.4},
    # Rice - National
    "Burdwan": {"lat": 23.2324, "lon": 87.8615, "state": "West Bengal", "diesel": 92.8},
    "Shimoga": {"lat": 13.9299, "lon": 75.5681, "state": "Karnataka", "diesel": 89.2},
    "Basti": {"lat": 26.8000, "lon": 82.7600, "state": "Uttar Pradesh", "diesel": 89.7},
    "Dahod": {"lat": 22.8333, "lon": 74.2500, "state": "Gujarat", "diesel": 92.4},
    "Narela": {"lat": 28.8527, "lon": 77.0931, "state": "NCT of Delhi", "diesel": 87.6}
}

def init_duckdb():
    print(f"==================================================")
    print(f" INITIALIZING DUCKDB DATABASE AT: {DB_PATH}")
    print(f"==================================================")

    # Connect to persistent DuckDB database
    con = duckdb.connect(DB_PATH)

    # 1. Create Schema
    con.execute("""
    CREATE OR REPLACE TABLE crops (
        crop_id VARCHAR PRIMARY KEY,
        crop_name VARCHAR,
        category VARCHAR,
        icon VARCHAR
    );
    """)

    con.execute("""
    CREATE OR REPLACE TABLE markets (
        crop VARCHAR,
        market_key VARCHAR,
        state_name VARCHAR,
        district_name VARCHAR,
        market_name VARCHAR,
        lat DOUBLE,
        lon DOUBLE,
        diesel_rate DOUBLE,
        PRIMARY KEY (crop, market_key)
    );
    """)

    con.execute("""
    CREATE OR REPLACE TABLE mandi_prices (
        crop VARCHAR,
        market_key VARCHAR,
        state_name VARCHAR,
        district_name VARCHAR,
        market_name VARCHAR,
        variety VARCHAR,
        arrivals_tonnes DOUBLE,
        min_price DOUBLE,
        max_price DOUBLE,
        modal_price DOUBLE,
        reported_date DATE
    );
    """)

    con.execute("""
    CREATE OR REPLACE TABLE weather_observations (
        crop VARCHAR,
        market_key VARCHAR,
        record_date DATE,
        temp_max_c DOUBLE,
        temp_min_c DOUBLE,
        temp_mean_c DOUBLE,
        precipitation_mm DOUBLE,
        rain_mm DOUBLE,
        humidity_pct DOUBLE,
        wind_speed_max_kmh DOUBLE
    );
    """)

    con.execute("""
    CREATE OR REPLACE TABLE nasa_agronomic (
        crop VARCHAR,
        market_key VARCHAR,
        record_date DATE,
        surface_soil_moisture DOUBLE,
        rootzone_soil_moisture DOUBLE,
        surface_temp_c DOUBLE,
        air_temp_2m_c DOUBLE,
        relative_humidity_pct DOUBLE,
        precipitation_mm DOUBLE
    );
    """)

    con.execute("""
    CREATE OR REPLACE TABLE forecast_points (
        crop VARCHAR,
        market_key VARCHAR,
        horizon VARCHAR,
        day_offset INTEGER,
        target_date DATE,
        predicted_price DOUBLE,
        lower_bound DOUBLE,
        upper_bound DOUBLE,
        is_present_date BOOLEAN,
        horizon_target VARCHAR
    );
    """)

    con.execute("""
    CREATE OR REPLACE TABLE market_metrics (
        crop VARCHAR,
        market_key VARCHAR,
        t1_mae DOUBLE,
        t1_mape DOUBLE,
        t7_mae DOUBLE,
        t7_mape DOUBLE,
        t30_mae DOUBLE,
        t30_mape DOUBLE
    );
    """)

    # Populate Crops Table
    crops_data = [
        ("mosambi", "Mosambi (Sweet Lime)", "Fruit", "Mosambi"),
        ("rice", "Rice (Paddy)", "Grain / Cereal", "Rice")
    ]
    con.executemany("INSERT INTO crops VALUES (?, ?, ?, ?)", crops_data)
    print("[OK] Inserted Crops table.")

    # Populate Markets & Mandi Prices
    crops = ["mosambi", "rice"]
    for crop in crops:
        price_files = glob.glob(os.path.join(BASE_DATASETS, crop, "selected_prediction_markets", "*.csv"))
        price_files = [f for f in price_files if "selected_markets_index" not in f]

        for p_file in price_files:
            m_key = os.path.basename(p_file).replace(".csv", "")
            df = pd.read_csv(p_file)
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

            # Resolve coordinates from MARKET_COORDS
            m_city = m_key.split("_")[-1]
            coords = MARKET_COORDS.get(m_city, {"lat": 20.5937, "lon": 78.9629, "state": "India", "diesel": 92.5})
            state_val = str(df["state_name"].iloc[0]) if "state_name" in df.columns and len(df) > 0 else coords["state"]
            dist_val = str(df["district_name"].iloc[0]) if "district_name" in df.columns and len(df) > 0 else m_city
            mkt_val = str(df["market_name"].iloc[0]) if "market_name" in df.columns and len(df) > 0 else m_city

            # Insert into markets table
            con.execute("""
                INSERT OR REPLACE INTO markets VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (crop, m_key, state_val, dist_val, mkt_val, coords["lat"], coords["lon"], coords["diesel"]))

            # Clean prices
            arr_col = [c for c in df.columns if "arrival" in c][0] if any("arrival" in c for c in df.columns) else None
            min_col = [c for c in df.columns if "min" in c][0] if any("min" in c for c in df.columns) else None
            max_col = [c for c in df.columns if "max" in c][0] if any("max" in c for c in df.columns) else None
            mod_col = [c for c in df.columns if "modal" in c][0] if any("modal" in c for c in df.columns) else None

            # Date parsing
            date_col = "reported_date_dt" if "reported_date_dt" in df.columns else "reported_date"
            df["parsed_date"] = pd.to_datetime(df[date_col], format="mixed", errors="coerce").dt.date

            clean_df = pd.DataFrame({
                "crop": crop,
                "market_key": m_key,
                "state_name": state_val,
                "district_name": dist_val,
                "market_name": mkt_val,
                "variety": df["variety"] if "variety" in df.columns else "Common",
                "arrivals_tonnes": pd.to_numeric(df[arr_col], errors="coerce").fillna(0.0) if arr_col else 0.0,
                "min_price": pd.to_numeric(df[min_col], errors="coerce").fillna(0.0) if min_col else 0.0,
                "max_price": pd.to_numeric(df[max_col], errors="coerce").fillna(0.0) if max_col else 0.0,
                "modal_price": pd.to_numeric(df[mod_col], errors="coerce").fillna(0.0) if mod_col else 0.0,
                "reported_date": df["parsed_date"]
            }).dropna(subset=["reported_date"])

            con.register("tmp_clean_prices", clean_df)
            con.execute("INSERT INTO mandi_prices SELECT * FROM tmp_clean_prices")
            con.unregister("tmp_clean_prices")

        print(f"[OK] Migrated all Mandi Prices for crop: {crop} ({len(price_files)} markets)")

        # Weather observations
        weather_files = glob.glob(os.path.join(BASE_DATASETS, crop, "weather", "*.csv"))
        weather_files = [f for f in weather_files if "summary" not in f.lower() and "index" not in f.lower()]
        for w_file in weather_files:
            m_key = os.path.basename(w_file).replace("weather_", "").replace(".csv", "")
            dfw = pd.read_csv(w_file)
            if "date" not in dfw.columns:
                continue
            dfw["parsed_date"] = pd.to_datetime(dfw["date"], format="mixed", errors="coerce").dt.date
            
            clean_w = pd.DataFrame({
                "crop": crop,
                "market_key": m_key,
                "record_date": dfw["parsed_date"],
                "temp_max_c": pd.to_numeric(dfw.get("temp_max_c", 0.0), errors="coerce").fillna(0.0),
                "temp_min_c": pd.to_numeric(dfw.get("temp_min_c", 0.0), errors="coerce").fillna(0.0),
                "temp_mean_c": pd.to_numeric(dfw.get("temp_mean_c", 0.0), errors="coerce").fillna(0.0),
                "precipitation_mm": pd.to_numeric(dfw.get("precipitation_mm", 0.0), errors="coerce").fillna(0.0),
                "rain_mm": pd.to_numeric(dfw.get("rain_mm", 0.0), errors="coerce").fillna(0.0),
                "humidity_pct": pd.to_numeric(dfw.get("humidity_pct", 0.0), errors="coerce").fillna(0.0),
                "wind_speed_max_kmh": pd.to_numeric(dfw.get("wind_speed_max_kmh", 0.0), errors="coerce").fillna(0.0)
            }).dropna(subset=["record_date"])

            con.register("tmp_weather", clean_w)
            con.execute("INSERT INTO weather_observations SELECT * FROM tmp_weather")
            con.unregister("tmp_weather")

        print(f"[OK] Migrated Weather records for crop: {crop} ({len(weather_files)} files)")

        # NASA Agronomic
        nasa_files = glob.glob(os.path.join(BASE_DATASETS, crop, "real_nasa_agronomic", "*.csv"))
        nasa_files = [f for f in nasa_files if "summary" not in f.lower() and "index" not in f.lower()]
        for n_file in nasa_files:
            m_key = os.path.basename(n_file).replace("nasa_agronomic_", "").replace(".csv", "")
            dfn = pd.read_csv(n_file)
            if "date" not in dfn.columns:
                continue
            dfn["parsed_date"] = pd.to_datetime(dfn["date"], format="mixed", errors="coerce").dt.date

            # Extract soil moisture column variations
            surf_col = "real_surface_soil_moisture_index" if "real_surface_soil_moisture_index" in dfn.columns else "surface_soil_moisture_index"
            root_col = "real_rootzone_soil_moisture_index" if "real_rootzone_soil_moisture_index" in dfn.columns else "rootzone_soil_moisture_index"
            temp_col = "real_earth_surface_temp_c" if "real_earth_surface_temp_c" in dfn.columns else "earth_surface_temp_c"
            air_col = "real_air_temp_2m_c" if "real_air_temp_2m_c" in dfn.columns else "air_temp_2m_c"
            hum_col = "real_relative_humidity_pct" if "real_relative_humidity_pct" in dfn.columns else "relative_humidity_pct"
            prec_col = "real_precipitation_mm" if "real_precipitation_mm" in dfn.columns else "precipitation_mm"

            clean_n = pd.DataFrame({
                "crop": crop,
                "market_key": m_key,
                "record_date": dfn["parsed_date"],
                "surface_soil_moisture": pd.to_numeric(dfn.get(surf_col, 0.5), errors="coerce").fillna(0.5),
                "rootzone_soil_moisture": pd.to_numeric(dfn.get(root_col, 0.5), errors="coerce").fillna(0.5),
                "surface_temp_c": pd.to_numeric(dfn.get(temp_col, 25.0), errors="coerce").fillna(25.0),
                "air_temp_2m_c": pd.to_numeric(dfn.get(air_col, 25.0), errors="coerce").fillna(25.0),
                "relative_humidity_pct": pd.to_numeric(dfn.get(hum_col, 60.0), errors="coerce").fillna(60.0),
                "precipitation_mm": pd.to_numeric(dfn.get(prec_col, 0.0), errors="coerce").fillna(0.0)
            }).dropna(subset=["record_date"])

            con.register("tmp_nasa", clean_n)
            con.execute("INSERT INTO nasa_agronomic SELECT * FROM tmp_nasa")
            con.unregister("tmp_nasa")

        print(f"[OK] Migrated NASA Agronomics for crop: {crop}")

    # Forecasts and Metrics
    forecasts_file = os.path.join(PREDICTIONS_DIR, "all_crops_forecasts.json")
    if os.path.exists(forecasts_file):
        with open(forecasts_file, "r") as f:
            all_fc = json.load(f)

        points = []
        metrics = []
        for crop, m_dict in all_fc.items():
            for m_key, m_info in m_dict.items():
                m_mets = m_info.get("metrics", {})
                metrics.append((
                    crop,
                    m_key,
                    float(m_mets.get("T+1d", {}).get("MAE", 0.0)),
                    float(m_mets.get("T+1d", {}).get("MAPE_%", 0.0)),
                    float(m_mets.get("T+7d", {}).get("MAE", 0.0)),
                    float(m_mets.get("T+7d", {}).get("MAPE_%", 0.0)),
                    float(m_mets.get("T+30d", {}).get("MAE", 0.0)),
                    float(m_mets.get("T+30d", {}).get("MAPE_%", 0.0))
                ))

                fc_dict = m_info.get("forecasts", {})
                if isinstance(fc_dict, dict):
                    for h_name, f_list in fc_dict.items():
                        h_code = h_name.replace("horizon_", "")
                        if isinstance(f_list, list):
                            for pt in f_list:
                                if isinstance(pt, dict):
                                    points.append((
                                        crop,
                                        m_key,
                                        h_code,
                                        int(pt.get("day", 0)),
                                        datetime.strptime(pt.get("date"), "%Y-%m-%d").date() if pt.get("date") else None,
                                        float(pt.get("predicted_price", 0.0)),
                                        float(pt.get("lower_bound", 0.0)),
                                        float(pt.get("upper_bound", 0.0)),
                                        bool(pt.get("is_present_date", False)),
                                        str(pt.get("horizon_target")) if pt.get("horizon_target") is not None else None
                                    ))

        if metrics:
            con.executemany("INSERT INTO market_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?)", metrics)
            print(f"[OK] Migrated {len(metrics)} Model Performance Metrics.")

        if points:
            con.executemany("INSERT INTO forecast_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", points)
            print(f"[OK] Migrated {len(points)} Forecast Points.")

    # 4. Create Analytical Views for Instant Analytics
    con.execute("""
    CREATE OR REPLACE VIEW v_latest_mandi_prices AS
    WITH ranked AS (
        SELECT *,
               ROW_NUMBER() OVER (PARTITION BY crop, market_key ORDER BY reported_date DESC) as rn
        FROM mandi_prices
    )
    SELECT crop, market_key, state_name, district_name, market_name, variety,
           arrivals_tonnes, min_price, max_price, modal_price, reported_date
    FROM ranked
    WHERE rn = 1;
    """)

    con.execute("""
    CREATE OR REPLACE VIEW v_market_summary AS
    SELECT crop,
           market_key,
           COUNT(*) as total_days_recorded,
           MIN(reported_date) as start_date,
           MAX(reported_date) as end_date,
           ROUND(AVG(modal_price), 2) as avg_price,
           MIN(modal_price) as min_historical_price,
           MAX(modal_price) as max_historical_price,
           ROUND(AVG(arrivals_tonnes), 2) as avg_arrivals
    FROM mandi_prices
    GROUP BY crop, market_key;
    """)

    print(f"\n==================================================")
    print(f" DUCKDB SUMMARY OF POPULATED TABLES:")
    print(f"==================================================")
    tables = con.execute("SHOW TABLES").fetchall()
    for t in tables:
        tname = t[0]
        cnt = con.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
        print(f"  * {tname:<25}: {cnt:>6} rows")

    con.close()
    print("\nSUCCESS: DuckDB database creation & migration completed successfully!")

if __name__ == "__main__":
    init_duckdb()
