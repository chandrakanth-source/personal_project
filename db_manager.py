"""
DuckDB Database Manager for Agri Oracle Platform
Provides high-performance SQL querying, analytics, and data management
"""

import os
import duckdb
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "agri_oracle.duckdb"))

def get_connection(read_only=True):
    """Returns a DuckDB connection. Uses read_only=True for concurrent web reads."""
    return duckdb.connect(DB_PATH, read_only=read_only)

def get_crops():
    """Fetches all registered crops."""
    con = get_connection(read_only=True)
    try:
        df = con.execute("SELECT crop_id, crop_name, category, icon FROM crops ORDER BY crop_id").fetchdf()
        return df.to_dict(orient="records")
    finally:
        con.close()

def get_markets(crop=None):
    """Fetches markets, optionally filtered by crop."""
    con = get_connection(read_only=True)
    try:
        if crop:
            df = con.execute("""
                SELECT crop, market_key, state_name, district_name, market_name, lat, lon, diesel_rate
                FROM markets
                WHERE crop = ?
                ORDER BY market_name
            """, [crop]).fetchdf()
        else:
            df = con.execute("""
                SELECT crop, market_key, state_name, district_name, market_name, lat, lon, diesel_rate
                FROM markets
                ORDER BY crop, market_name
            """).fetchdf()
        return df.to_dict(orient="records")
    finally:
        con.close()

def get_latest_prices(crop="mosambi"):
    """Fetches the latest recorded prices across all markets for a crop."""
    con = get_connection(read_only=True)
    try:
        df = con.execute("""
            SELECT v.*, m.lat, m.lon, m.diesel_rate
            FROM v_latest_mandi_prices v
            JOIN markets m ON v.crop = m.crop AND v.market_key = m.market_key
            WHERE v.crop = ?
            ORDER BY v.modal_price DESC
        """, [crop]).fetchdf()
        # Convert date to string for JSON serialization
        if "reported_date" in df.columns:
            df["reported_date"] = df["reported_date"].astype(str)
        return df.to_dict(orient="records")
    finally:
        con.close()

def get_market_history(crop, market_key, limit=365):
    """Fetches historical price and arrivals for a given market."""
    con = get_connection(read_only=True)
    try:
        df = con.execute("""
            SELECT reported_date, modal_price, min_price, max_price, arrivals_tonnes
            FROM mandi_prices
            WHERE crop = ? AND market_key = ?
            ORDER BY reported_date DESC
            LIMIT ?
        """, [crop, market_key, limit]).fetchdf()
        
        # Sort ascending for charts
        df = df.sort_values("reported_date").reset_index(drop=True)
        if "reported_date" in df.columns:
            df["reported_date"] = df["reported_date"].astype(str)
        return df.to_dict(orient="records")
    finally:
        con.close()

def get_market_forecasts(crop, market_key):
    """Fetches AI predictions across 7d, 14d, and 30d horizons."""
    con = get_connection(read_only=True)
    try:
        df = con.execute("""
            SELECT horizon, day_offset, target_date, predicted_price, lower_bound, upper_bound,
                   is_present_date, horizon_target
            FROM forecast_points
            WHERE crop = ? AND market_key = ?
            ORDER BY horizon, day_offset
        """, [crop, market_key]).fetchdf()

        if "target_date" in df.columns:
            df["target_date"] = df["target_date"].astype(str)

        # Group by horizon
        result = {}
        for h, grp in df.groupby("horizon"):
            result[f"horizon_{h}"] = grp.to_dict(orient="records")
        return result
    finally:
        con.close()

def get_arbitrage_analysis(crop="mosambi"):
    """
    Computes inter-mandi price spreads and arbitrage profit margins
    based on latest prices and regional transport costs.
    """
    con = get_connection(read_only=True)
    try:
        df = con.execute("""
            SELECT v.market_name, v.state_name, v.modal_price, v.arrivals_tonnes, m.diesel_rate, v.reported_date
            FROM v_latest_mandi_prices v
            JOIN markets m ON v.crop = m.crop AND v.market_key = m.market_key
            WHERE v.crop = ? AND v.modal_price > 0
            ORDER BY v.modal_price DESC
        """, [crop]).fetchdf()

        if len(df) < 2:
            return {"opportunities": [], "message": "Not enough active market price data."}

        highest = df.iloc[0]
        lowest = df.iloc[-1]
        spread = float(highest["modal_price"] - lowest["modal_price"])

        # Top 5 price comparison pairs
        opportunities = []
        for i in range(min(5, len(df))):
            top_m = df.iloc[i]
            for j in range(max(0, len(df) - 3), len(df)):
                low_m = df.iloc[j]
                if top_m["market_name"] == low_m["market_name"]:
                    continue
                diff = float(top_m["modal_price"] - low_m["modal_price"])
                if diff > 0:
                    opportunities.append({
                        "buy_market": low_m["market_name"],
                        "buy_state": low_m["state_name"],
                        "buy_price": float(low_m["modal_price"]),
                        "sell_market": top_m["market_name"],
                        "sell_state": top_m["state_name"],
                        "sell_price": float(top_m["modal_price"]),
                        "gross_margin_per_quintal": round(diff, 2),
                        "gross_margin_per_tonne": round(diff * 10, 2)
                    })

        # Sort by best margin
        opportunities = sorted(opportunities, key=lambda x: x["gross_margin_per_quintal"], reverse=True)[:5]

        return {
            "crop": crop,
            "national_highest": {
                "market": highest["market_name"],
                "state": highest["state_name"],
                "price": float(highest["modal_price"]),
                "date": str(highest["reported_date"])
            },
            "national_lowest": {
                "market": lowest["market_name"],
                "state": lowest["state_name"],
                "price": float(lowest["modal_price"]),
                "date": str(lowest["reported_date"])
            },
            "national_spread": round(spread, 2),
            "top_arbitrage_routes": opportunities
        }
    finally:
        con.close()

def run_analytics_query(sql_query, params=None):
    """Executes arbitrary read-only analytical SQL query on DuckDB."""
    con = get_connection(read_only=True)
    try:
        if params:
            df = con.execute(sql_query, params).fetchdf()
        else:
            df = con.execute(sql_query).fetchdf()
        # Convert any date columns to string
        for col in df.select_dtypes(include=["datetime", "datetimetz", "object"]).columns:
            df[col] = df[col].astype(str)
        return df.to_dict(orient="records")
    finally:
        con.close()

if __name__ == "__main__":
    print("Testing DuckDB Database Manager:")
    print("Crops:", get_crops())
    print("\nLatest Mosambi Prices Sample:")
    latest = get_latest_prices("mosambi")
    for r in latest[:3]:
        print(f"  {r['market_name']} ({r['state_name']}): Rs. {r['modal_price']}/quintal on {r['reported_date']}")

    print("\nArbitrage Analysis Sample:")
    arb = get_arbitrage_analysis("mosambi")
    print(f"  Highest: {arb['national_highest']['market']} @ Rs. {arb['national_highest']['price']}")
    print(f"  Lowest: {arb['national_lowest']['market']} @ Rs. {arb['national_lowest']['price']}")
    print(f"  Max Spread: Rs. {arb['national_spread']}/quintal")
