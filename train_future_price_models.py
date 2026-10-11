import os
import glob
import json
import argparse
import joblib
import pandas as pd
import numpy as np
from datetime import timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb
import lightgbm as lgb
import warnings

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DATASETS_DIR = os.environ.get("DATASETS_DIR", os.path.join(BASE_DIR, "datasets"))
MODELS_DIR = os.environ.get("MODELS_DIR", os.path.join(BASE_DIR, "models"))
OUTPUT_DIR = os.environ.get("PREDICTIONS_DIR", os.path.join(BASE_DIR, "predictions"))

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def discover_crops():
    if not os.path.exists(BASE_DATASETS_DIR):
        return ["mosambi"]
    items = os.listdir(BASE_DATASETS_DIR)
    crops = []
    for item in items:
        item_path = os.path.join(BASE_DATASETS_DIR, item)
        if os.path.isdir(item_path):
            if os.path.exists(os.path.join(item_path, "master_ml_datasets")) or os.path.exists(os.path.join(item_path, "selected_prediction_markets")):
                crops.append(item)
    return sorted(crops) if crops else ["mosambi"]

def calculate_mape(y_true, y_pred):
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    non_zero = y_true != 0
    if not np.any(non_zero):
        return 0.0
    return np.mean(np.abs((y_true[non_zero] - y_pred[non_zero]) / y_true[non_zero])) * 100.0

def build_advanced_features(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    modal_cols = [c for c in df.columns if "modal_price" in c and "lag" not in c and "rolling" not in c]
    arr_cols = [c for c in df.columns if "arrivals" in c and "lag" not in c and "rolling" not in c]
    min_cols = [c for c in df.columns if "min_price" in c]
    max_cols = [c for c in df.columns if "max_price" in c]

    modal_col = modal_cols[0] if modal_cols else df.columns[5]
    arr_col = arr_cols[0] if arr_cols else df.columns[6]
    min_col = min_cols[0] if min_cols else modal_col
    max_col = max_cols[0] if max_cols else modal_col

    # Target price column
    df["price"] = pd.to_numeric(df[modal_col], errors="coerce").fillna(1000.0)
    df["arrivals"] = pd.to_numeric(df[arr_col], errors="coerce").fillna(10.0)
    df["min_price"] = pd.to_numeric(df[min_col], errors="coerce").fillna(df["price"])
    df["max_price"] = pd.to_numeric(df[max_col], errors="coerce").fillna(df["price"])
    df["price_spread"] = df["max_price"] - df["min_price"]

    # Historical price lags
    for lag in [1, 2, 3, 5, 7, 10, 14, 21, 30]:
        df[f"price_lag_{lag}d"] = df["price"].shift(lag)
        df[f"arrivals_lag_{lag}d"] = df["arrivals"].shift(lag)

    # Rolling price statistics
    for w in [3, 7, 14, 30]:
        df[f"price_rolling_mean_{w}d"] = df["price"].rolling(window=w, min_periods=1).mean()
        df[f"price_rolling_std_{w}d"] = df["price"].rolling(window=w, min_periods=1).std().fillna(0)
        df[f"price_rolling_min_{w}d"] = df["price"].rolling(window=w, min_periods=1).min()
        df[f"price_rolling_max_{w}d"] = df["price"].rolling(window=w, min_periods=1).max()
        df[f"arrivals_rolling_mean_{w}d"] = df["arrivals"].rolling(window=w, min_periods=1).mean()

    # Price momentum and percentage changes
    df["price_pct_change_1d"] = df["price"].pct_change(1).replace([np.inf, -np.inf], np.nan).fillna(0).clip(-1.0, 5.0)
    df["price_pct_change_7d"] = df["price"].pct_change(7).replace([np.inf, -np.inf], np.nan).fillna(0).clip(-1.0, 5.0)
    df["price_pct_change_14d"] = df["price"].pct_change(14).replace([np.inf, -np.inf], np.nan).fillna(0).clip(-1.0, 5.0)
    df["price_pct_change_30d"] = df["price"].pct_change(30).replace([np.inf, -np.inf], np.nan).fillna(0).clip(-1.0, 5.0)

    # Calendar features
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"] = df["date"].dt.day
    df["day_of_week"] = df["date"].dt.dayofweek
    df["day_of_year"] = df["date"].dt.dayofyear
    df["quarter"] = df["date"].dt.quarter
    df["sin_month"] = np.sin(2 * np.pi * df["month"] / 12.0)
    df["cos_month"] = np.cos(2 * np.pi * df["month"] / 12.0)
    df["sin_dayofyear"] = np.sin(2 * np.pi * df["day_of_year"] / 365.25)
    df["cos_dayofyear"] = np.cos(2 * np.pi * df["day_of_year"] / 365.25)

    # Weather and NASA Agronomic features handling
    agronomic_cols = [
        "temp_max_c", "temp_min_c", "temp_mean_c", "precipitation_mm", "rain_mm", 
        "humidity_pct", "wind_speed_max_kmh", "real_surface_soil_moisture_index", 
        "real_rootzone_soil_moisture_index", "real_precipitation_mm", 
        "real_earth_surface_temp_c", "real_air_temp_2m_c", "real_relative_humidity_pct"
    ]
    for c in agronomic_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").ffill().bfill().fillna(0)
        else:
            df[c] = 0.0

    # Categorical seasonality features
    cat_cols = ["harvest_season", "supply_phase", "seasonal_price_trend"]
    for c in cat_cols:
        if c in df.columns:
            df[c] = df[c].fillna("Unknown").astype(str)
            dummies = pd.get_dummies(df[c], prefix=c, drop_first=False)
            df = pd.concat([df, dummies], axis=1)

    if "relative_demand_index" in df.columns:
        df["relative_demand_index"] = pd.to_numeric(df["relative_demand_index"], errors="coerce").fillna(1.0)

    # Future targets creation
    df["target_7d"] = df["price"].shift(-7)
    df["target_14d"] = df["price"].shift(-14)
    df["target_30d"] = df["price"].shift(-30)

    # Replace any remaining inf / -inf across dataframe
    df = df.replace([np.inf, -np.inf], np.nan)

    return df

def train_and_evaluate_market(file_path, crop_name="mosambi"):
    market_name = os.path.basename(file_path).replace("master_", "").replace(".csv", "")
    print(f"\n==================================================")
    print(f" TRAINING [{crop_name.upper()}] MODELS FOR MARKET: {market_name}")
    print(f"==================================================")

    df_raw = pd.read_csv(file_path)
    df = build_advanced_features(df_raw)

    exclude_cols = [
        "state_name", "district_name", "market_name", "variety", "group",
        "reported_date", "reported_date_dt", "date", "harvest_season", "supply_phase",
        "seasonal_price_trend", "target_7d", "target_14d", "target_30d"
    ]
    feature_cols = [c for c in df.columns if c not in exclude_cols and not c.startswith("modal_price") and not c.startswith("min_price") and not c.startswith("max_price") and not c.startswith("arrivals_(")]
    
    for col in feature_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0)

    market_models_dir = os.path.join(MODELS_DIR, crop_name, market_name)
    os.makedirs(market_models_dir, exist_ok=True)

    horizons = [7, 14, 30]
    market_metrics = {}
    horizon_forecasts = {}

    for h in horizons:
        target_col = f"target_{h}d"
        valid_df = df.dropna(subset=[target_col]).copy()
        
        split_idx = int(len(valid_df) * 0.8)
        train_df = valid_df.iloc[:split_idx]
        test_df = valid_df.iloc[split_idx:]

        X_train, y_train = train_df[feature_cols], train_df[target_col]
        X_test, y_test = test_df[feature_cols], test_df[target_col]

        model_xgb = xgb.XGBRegressor(n_estimators=150, learning_rate=0.04, max_depth=6, subsample=0.8, colsample_bytree=0.8, random_state=42)
        model_xgb.fit(X_train, y_train)

        model_lgb = lgb.LGBMRegressor(n_estimators=150, learning_rate=0.04, max_depth=6, subsample=0.8, colsample_bytree=0.8, random_state=42, verbose=-1)
        model_lgb.fit(X_train, y_train)

        model_rf = RandomForestRegressor(n_estimators=100, max_depth=12, random_state=42, n_jobs=-1)
        model_rf.fit(X_train, y_train)

        pred_xgb = model_xgb.predict(X_test)
        pred_lgb = model_lgb.predict(X_test)
        pred_rf = model_rf.predict(X_test)
        pred_ensemble = (pred_xgb * 0.4) + (pred_lgb * 0.4) + (pred_rf * 0.2)

        mae = mean_absolute_error(y_test, pred_ensemble)
        rmse = np.sqrt(mean_squared_error(y_test, pred_ensemble))
        mape = calculate_mape(y_test, pred_ensemble)
        r2 = r2_score(y_test, pred_ensemble)
        accuracy = max(0.0, round(100.0 - mape, 2))

        print(f"Horizon T+{h:02d}d | MAE: {mae:.2f} Rs/q | RMSE: {rmse:.2f} | MAPE: {mape:.2f}% | Acc: {accuracy:.2f}% | R2: {r2:.4f}")

        joblib.dump(model_xgb, os.path.join(market_models_dir, f"xgb_model_{h}d.joblib"))
        joblib.dump(model_lgb, os.path.join(market_models_dir, f"lgb_model_{h}d.joblib"))
        joblib.dump(model_rf, os.path.join(market_models_dir, f"rf_model_{h}d.joblib"))

        with open(os.path.join(market_models_dir, "features.json"), "w") as f:
            json.dump(feature_cols, f)

        market_metrics[f"T+{h}d"] = {
            "MAE": round(float(mae), 2),
            "RMSE": round(float(rmse), 2),
            "MAPE": round(float(mape), 2),
            "Accuracy": accuracy,
            "R2": round(float(r2), 4),
            "XGB_MAE": round(float(mean_absolute_error(y_test, pred_xgb)), 2),
            "LGB_MAE": round(float(mean_absolute_error(y_test, pred_lgb)), 2),
            "RF_MAE": round(float(mean_absolute_error(y_test, pred_rf)), 2)
        }

        PRESENT_DATE = pd.to_datetime("2026-10-07")
        last_known_row = df.iloc[-1]
        latest_date = pd.to_datetime(last_known_row["date"])

        gap_days = (PRESENT_DATE - latest_date).days
        black_box_info = {
            "start_date": (latest_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "end_date": (PRESENT_DATE - timedelta(days=1)).strftime("%Y-%m-%d"),
            "gap_days": max(0, gap_days - 1),
            "status": "UNREPORTED_DATA_BLACK_BOX",
            "message": "Black Box: Unreported Data Gap (Data Not Available - No Graph Plotted)"
        }
        
        future_dates = [PRESENT_DATE + timedelta(days=i) for i in range(0, 31)]
        future_preds = []
        current_features = df.iloc[[-1]][feature_cols].copy()

        for i, f_date in enumerate(future_dates):
            predicted_price = model_xgb.predict(current_features)[0] * 0.4 + model_lgb.predict(current_features)[0] * 0.4 + model_rf.predict(current_features)[0] * 0.2
            std_err = mae * (1 + (i / 30.0) * 0.5)
            lower_bound = max(0, predicted_price - 1.96 * std_err)
            upper_bound = predicted_price + 1.96 * std_err

            future_preds.append({
                "day": i,
                "date": f_date.strftime("%Y-%m-%d"),
                "predicted_price": round(float(predicted_price), 2),
                "lower_bound": round(float(lower_bound), 2),
                "upper_bound": round(float(upper_bound), 2),
                "is_present_date": (i == 0),
                "horizon_target": f"T+{h}d" if i == h else None
            })

        horizon_forecasts[f"horizon_{h}d"] = future_preds

    lgb_7d = joblib.load(os.path.join(market_models_dir, "lgb_model_7d.joblib"))
    importances = lgb_7d.feature_importances_
    feat_imp = sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True)[:10]
    top_features = [{"feature": k, "importance": int(v)} for k, v in feat_imp]

    hist_90 = df.iloc[-90:][["date", "price", "arrivals", "min_price", "max_price"]].copy()
    hist_90["date"] = hist_90["date"].dt.strftime("%Y-%m-%d")
    historical_data = hist_90.to_dict(orient="records")

    last_row = df.iloc[-1]
    raw_last = df_raw.iloc[-1] if len(df_raw) > 0 else {}

    detailed_factors = {
        "date": last_row["date"].strftime("%Y-%m-%d"),
        "city_town": market_name.split("_")[-1],
        "state": market_name.split("_")[0],
        "crop": crop_name,
        "real_price": {
            "modal_price": round(float(last_row["price"]), 2),
            "min_price": round(float(last_row["min_price"]), 2),
            "max_price": round(float(last_row["max_price"]), 2),
            "price_spread": round(float(last_row["price_spread"]), 2),
            "price_lag_7d": round(float(last_row.get("price_lag_7d", last_row["price"])), 2),
            "price_rolling_mean_7d": round(float(last_row.get("price_rolling_mean_7d", last_row["price"])), 2),
            "price_pct_change_7d": round(float(last_row.get("price_pct_change_7d", 0)) * 100, 2)
        },
        "climate_weather": {
            "temp_max_c": round(float(last_row.get("temp_max_c", 0)), 1),
            "temp_min_c": round(float(last_row.get("temp_min_c", 0)), 1),
            "temp_mean_c": round(float(last_row.get("temp_mean_c", 0)), 1),
            "precipitation_mm": round(float(last_row.get("precipitation_mm", 0)), 2),
            "rain_mm": round(float(last_row.get("rain_mm", 0)), 2),
            "humidity_pct": round(float(last_row.get("humidity_pct", 0)), 1),
            "wind_speed_max_kmh": round(float(last_row.get("wind_speed_max_kmh", 0)), 1)
        },
        "supply_chain": {
            "arrivals_tonnes": round(float(last_row["arrivals"]), 2),
            "arrivals_lag_7d": round(float(last_row.get("arrivals_lag_7d", last_row["arrivals"])), 2),
            "arrivals_rolling_mean_7d": round(float(last_row.get("arrivals_rolling_mean_7d", last_row["arrivals"])), 2)
        },
        "real_nasa_agronomic": {
            "surface_soil_moisture_index": round(float(last_row.get("real_surface_soil_moisture_index", 0)), 3),
            "rootzone_soil_moisture_index": round(float(last_row.get("real_rootzone_soil_moisture_index", 0)), 3),
            "precipitation_mm": round(float(last_row.get("real_precipitation_mm", 0)), 2),
            "earth_surface_temp_c": round(float(last_row.get("real_earth_surface_temp_c", 0)), 1),
            "air_temp_2m_c": round(float(last_row.get("real_air_temp_2m_c", 0)), 1),
            "relative_humidity_pct": round(float(last_row.get("real_relative_humidity_pct", 0)), 1)
        },
        "seasonality": {
            "harvest_season": str(raw_last.get("harvest_season", "Peak Harvest")),
            "supply_phase": str(raw_last.get("supply_phase", "Active Supply")),
            "relative_demand_index": round(float(last_row.get("relative_demand_index", 1.0)), 2),
            "seasonal_price_trend": str(raw_last.get("seasonal_price_trend", "Stable")),
            "month_name": last_row["date"].strftime("%B"),
            "day_of_year": int(last_row["date"].dayofyear)
        }
    }

    return {
        "market_name": market_name,
        "crop": crop_name,
        "metrics": market_metrics,
        "forecasts": horizon_forecasts,
        "top_features": top_features,
        "historical_recent": historical_data,
        "detailed_factors": detailed_factors,
        "black_box_gap": black_box_info,
        "present_date": PRESENT_DATE.strftime("%Y-%m-%d"),
        "latest_recorded_price": round(float(df["price"].iloc[-1]), 2),
        "latest_recorded_date": df["date"].iloc[-1].strftime("%Y-%m-%d")
    }

def train_crop(crop_name="mosambi"):
    crop_dir = os.path.join(BASE_DATASETS_DIR, crop_name, "master_ml_datasets")
    if not os.path.exists(crop_dir):
        crop_dir = os.path.join(BASE_DATASETS_DIR, "master_ml_datasets")

    files = sorted(glob.glob(os.path.join(crop_dir, "master_*.csv")))
    files = [f for f in files if "index" not in f]

    if not files:
        print(f"No master ML datasets found in: {crop_dir}")
        return {}

    all_market_results = {}
    summary_metrics = []

    for file_path in files:
        m_res = train_and_evaluate_market(file_path, crop_name=crop_name)
        market_key = m_res["market_name"]
        all_market_results[market_key] = m_res

        summary_metrics.append({
            "Crop": crop_name,
            "Market": market_key,
            "Latest_Price": m_res["latest_recorded_price"],
            "T+7d_Accuracy": m_res["metrics"]["T+7d"]["Accuracy"],
            "T+7d_MAE": m_res["metrics"]["T+7d"]["MAE"],
            "T+14d_Accuracy": m_res["metrics"]["T+14d"]["Accuracy"],
            "T+14d_MAE": m_res["metrics"]["T+14d"]["MAE"],
            "T+30d_Accuracy": m_res["metrics"]["T+30d"]["Accuracy"],
            "T+30d_MAE": m_res["metrics"]["T+30d"]["MAE"]
        })

    # Save crop-specific forecast output JSON
    crop_out_dir = os.path.join(OUTPUT_DIR, crop_name)
    os.makedirs(crop_out_dir, exist_ok=True)
    with open(os.path.join(crop_out_dir, "all_market_forecasts.json"), "w") as f:
        json.dump(all_market_results, f, indent=2)

    # Also save to root predictions for default viewing
    with open(os.path.join(OUTPUT_DIR, "all_market_forecasts.json"), "w") as f:
        json.dump(all_market_results, f, indent=2)

    summary_df = pd.DataFrame(summary_metrics)
    summary_df.to_csv(os.path.join(crop_out_dir, "market_model_performance.csv"), index=False)

    return all_market_results

def main():
    parser = argparse.ArgumentParser(description="Multi-Crop Model Trainer")
    parser.add_argument("--crop", type=str, default="all", help="Crop folder name (e.g. mosambi, tomato, or all)")
    args = parser.parse_args()

    crops = discover_crops()
    all_crops_data = {}

    if args.crop == "all":
        for c in crops:
            res = train_crop(c)
            all_crops_data[c] = res
    else:
        res = train_crop(args.crop)
        all_crops_data[args.crop] = res

    # Save root multi-crop registry
    with open(os.path.join(OUTPUT_DIR, "all_crops_forecasts.json"), "w") as f:
        json.dump(all_crops_data, f, indent=2)

    print("\n==================================================")
    print(" ALL CROP MODELS TRAINED & EVALUATED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    main()
