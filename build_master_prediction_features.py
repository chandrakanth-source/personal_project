import os
import glob
import argparse
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DATASETS_DIR = os.environ.get("DATASETS_DIR", os.path.join(BASE_DIR, "datasets"))

def discover_crops():
    if not os.path.exists(BASE_DATASETS_DIR):
        return []
    items = os.listdir(BASE_DATASETS_DIR)
    crops = []
    for item in items:
        item_path = os.path.join(BASE_DATASETS_DIR, item)
        if os.path.isdir(item_path):
            # Check if it contains master_ml_datasets or selected_prediction_markets
            if os.path.exists(os.path.join(item_path, "selected_prediction_markets")) or os.path.exists(os.path.join(item_path, "master_ml_datasets")):
                crops.append(item)
    return sorted(crops) if crops else ["mosambi"]

def build_master_ml_datasets(crop_name="mosambi"):
    crop_dir = os.path.join(BASE_DATASETS_DIR, crop_name)
    if not os.path.exists(crop_dir):
        # Fallback to root if not structured yet
        crop_dir = BASE_DATASETS_DIR

    price_dir = os.path.join(crop_dir, "selected_prediction_markets")
    weather_dir = os.path.join(crop_dir, "weather")
    nasa_dir = os.path.join(crop_dir, "real_nasa_agronomic")
    season_dir = os.path.join(crop_dir, "seasonality")
    out_dir = os.path.join(crop_dir, "master_ml_datasets")
    
    os.makedirs(out_dir, exist_ok=True)

    # Load Seasonality
    season_files = glob.glob(os.path.join(season_dir, "*.csv"))
    df_season = None
    if season_files:
        df_season = pd.read_csv(season_files[0])
        df_season["date"] = pd.to_datetime(df_season["date"], format="mixed", errors="coerce")

    # Price files
    price_files = glob.glob(os.path.join(price_dir, "*.csv"))
    price_files = [f for f in price_files if "selected_markets_index" not in f]

    summary = []
    print(f"\n==================================================")
    print(f" BUILDING MASTER ML DATASETS FOR CROP: {crop_name.upper()}")
    print(f"==================================================")

    for p_file in sorted(price_files):
        filename = os.path.basename(p_file)
        clean_name = filename.replace(".csv", "")
        
        # Load Price Data
        df_price = pd.read_csv(p_file)
        df_price.columns = [c.strip().lower().replace(" ", "_") for c in df_price.columns]
        df_price["date"] = pd.to_datetime(df_price["reported_date"], format="mixed", dayfirst=True, errors="coerce")
        if "reported_date_dt" in df_price.columns:
            df_price["date"] = pd.to_datetime(df_price["reported_date_dt"], format="mixed", errors="coerce").fillna(df_price["date"])

        df_price = df_price.sort_values(by="date").copy()

        # Find matching weather file
        w_files = glob.glob(os.path.join(weather_dir, "*.csv"))
        matched_w = [w for w in w_files if any(part.lower() in os.path.basename(w).lower() for part in clean_name.split("_") if len(part) > 4)]
        
        df_weather = None
        if matched_w:
            df_weather = pd.read_csv(matched_w[0])
            df_weather["date"] = pd.to_datetime(df_weather["date"], format="mixed", errors="coerce")

        # Find matching NASA file
        n_files = glob.glob(os.path.join(nasa_dir, "*.csv"))
        matched_n = [n for n in n_files if any(part.lower() in os.path.basename(n).lower() for part in clean_name.split("_") if len(part) > 4)]
        
        df_nasa = None
        if matched_n:
            df_nasa = pd.read_csv(matched_n[0])
            df_nasa["date"] = pd.to_datetime(df_nasa["date"], format="mixed", errors="coerce")

        # Merge step-by-step
        df_master = df_price.copy()
        if df_season is not None:
            df_master = df_master.merge(df_season, on="date", how="left")
        if df_weather is not None:
            df_master = df_master.merge(df_weather, on="date", how="left")
        if df_nasa is not None:
            df_master = df_master.merge(df_nasa, on="date", how="left")

        # Feature Engineering: Lagged Features (3-day, 7-day, 14-day, 30-day price & supply lags)
        modal_cols = [c for c in df_master.columns if "modal" in c]
        arr_cols = [c for c in df_master.columns if "arrival" in c]

        if modal_cols and arr_cols:
            modal_col = modal_cols[0]
            arr_col = arr_cols[0]

            df_master["modal_price_lag_7d"] = df_master[modal_col].shift(7)
            df_master["modal_price_lag_14d"] = df_master[modal_col].shift(14)
            df_master["modal_price_lag_30d"] = df_master[modal_col].shift(30)

            df_master["arrivals_lag_7d"] = df_master[arr_col].shift(7)
            df_master["arrivals_rolling_mean_7d"] = df_master[arr_col].rolling(window=7, min_periods=1).mean()
            df_master["price_rolling_mean_7d"] = df_master[modal_col].rolling(window=7, min_periods=1).mean()

        out_path = os.path.join(out_dir, f"master_{clean_name}.csv")
        df_master.to_csv(out_path, index=False)

        summary.append({
            "Crop": crop_name,
            "Market_Dataset": clean_name,
            "Total_Records": len(df_master),
            "Total_Features": len(df_master.columns),
            "Start_Date": df_master["date"].min().strftime("%Y-%m-%d") if len(df_master)>0 and pd.notnull(df_master["date"].min()) else "N/A",
            "End_Date": df_master["date"].max().strftime("%Y-%m-%d") if len(df_master)>0 and pd.notnull(df_master["date"].max()) else "N/A",
            "File_Name": f"master_{clean_name}.csv"
        })

    sum_df = pd.DataFrame(summary)
    sum_df.to_csv(os.path.join(out_dir, "master_datasets_index.csv"), index=False)

    print(sum_df.to_string())
    print(f"\nSaved all master files for crop '{crop_name}' to: {out_dir}")

def main():
    parser = argparse.ArgumentParser(description="Multi-Crop Master ML Dataset Feature Builder")
    parser.add_argument("--crop", type=str, default="all", help="Crop folder name (e.g. mosambi, tomato, apple, or all)")
    args = parser.parse_args()

    available_crops = discover_crops()
    if args.crop == "all":
        for c in available_crops:
            build_master_ml_datasets(c)
    else:
        build_master_ml_datasets(args.crop)

if __name__ == "__main__":
    main()
