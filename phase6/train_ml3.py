# import json
# import os
# import joblib
# import numpy as np
# import pandas as pd
# from datetime import datetime, timedelta
# from sklearn.linear_model import LogisticRegression
# from sklearn.preprocessing import StandardScaler
# from sklearn.pipeline import Pipeline

# from sqlalchemy import create_engine
# from sklearn.metrics import (
#     accuracy_score,
#     precision_score,
#     recall_score,
#     f1_score,
#     roc_auc_score,
#     average_precision_score,
#     roc_curve,
#     precision_recall_curve

# )

# FEATURE_COLS = [
#     "avg_activity",
#     "activity_growth",
#     "active_hours",
#     "peak_ratio",
#     "variability",
#     "internet_share"
# ]

# DB_URL = "mysql+pymysql://root:root@localhost:3306/telecom_warehouse"
# engine = create_engine(DB_URL)

# def get_db_connection():
#     return engine.connect()

# def generate_multi_cutoff_dataset(num_cutoffs: int = 12) -> pd.DataFrame:
#     conn = get_db_connection()
    
#     time_df = pd.read_sql("SELECT timestamp FROM dim_time ORDER BY timestamp ASC;", conn)
#     all_timestamps = time_df["timestamp"].tolist()
    
#     if len(all_timestamps) < 48:
#         raise ValueError("Insufficient time history in warehouse to generate training slices.")

#     valid_cutoffs = all_timestamps[47:-1]
#     step = max(1, len(valid_cutoffs) // num_cutoffs)
#     selected_cutoffs = valid_cutoffs[::step][-num_cutoffs:]

#     print(f"Building temporal dataset across {len(selected_cutoffs)} distinct cutoff windows...")

#     dataset_records = []

#     for t_cutoff in selected_cutoffs:
#         t_future = t_cutoff + timedelta(hours=1)
#         recent_start = t_cutoff - timedelta(hours=23)
#         baseline_start = t_cutoff - timedelta(hours=47)
#         baseline_end = t_cutoff - timedelta(hours=24)

#         feat_query = """
#             SELECT 
#                 f.grid_id,
#                 AVG(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS recent_avg,
#                 MAX(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS recent_max,
#                 STDDEV_POP(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS recent_std,
#                 SUM(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE 0.0 END) AS recent_sum,
#                 SUM(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.internet_activity ELSE 0.0 END) AS recent_internet_sum,
#                 COUNT(DISTINCT CASE WHEN t.timestamp BETWEEN %s AND %s AND f.total_activity > 0 THEN t.hour ELSE NULL END) AS active_hours,
#                 AVG(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS baseline_avg
#             FROM fact_network_activity f
#             JOIN dim_time t ON f.time_key = t.time_key
#             WHERE t.timestamp BETWEEN %s AND %s
#             GROUP BY f.grid_id;
#         """
#         params = (
#             recent_start, t_cutoff,
#             recent_start, t_cutoff,
#             recent_start, t_cutoff,
#             recent_start, t_cutoff,
#             recent_start, t_cutoff,
#             recent_start, t_cutoff,
#             baseline_start, baseline_end,
#             baseline_start, t_cutoff
#         )
#         slice_df = pd.read_sql(feat_query, conn, params=params)

#         label_query = """
#             SELECT f.grid_id, f.total_activity AS future_activity
#             FROM fact_network_activity f
#             JOIN dim_time t ON f.time_key = t.time_key
#             WHERE t.timestamp = %s;
#         """
#         label_df = pd.read_sql(label_query, conn, params=(t_future,))

#         if slice_df.empty or label_df.empty:
#             continue

#         merged = pd.merge(slice_df, label_df, on="grid_id", how="inner")
        
#         # Exact ML2 Features (Unchanged)
#         merged["avg_activity"] = merged["recent_avg"].fillna(0.0).round(4)
#         growth = (merged["recent_avg"] - merged["baseline_avg"]) / (merged["baseline_avg"].fillna(0.0) + 1e-6)
#         merged["activity_growth"] = growth.fillna(0.0).clip(lower=-1.0, upper=10.0).round(4)
#         merged["active_hours"] = merged["active_hours"].fillna(0).astype(int)
#         peak = merged["recent_max"] / (merged["recent_avg"] + 1e-6)
#         merged["peak_ratio"] = peak.fillna(1.0).clip(lower=1.0).round(4)
#         var = merged["recent_std"] / (merged["recent_avg"] + 1e-6)
#         merged["variability"] = var.fillna(0.0).clip(lower=0.0).round(4)
#         net_share = merged["recent_internet_sum"] / (merged["recent_sum"] + 1e-6)
#         merged["internet_share"] = net_share.fillna(0.0).clip(lower=0.0, upper=1.0).round(4)

#         # TARGET: Relative surge of 35% above cell's own mean with baseline activity > 50 units
#         is_surge = (merged["future_activity"] >= (1.35 * merged["avg_activity"])) & (merged["future_activity"] >= 50.0)
#         merged["target_risk_t1"] = is_surge.astype(int)
#         merged["feature_timestamp"] = t_cutoff
#         merged["target_timestamp"] = t_future

#         dataset_records.append(merged)

#     conn.close()

#     if not dataset_records:
#         raise ValueError("Could not assemble training dataset from warehouse.")

#     full_df = pd.concat(dataset_records, ignore_index=True)
#     return full_df


# def run_training_experiment():
#     print("=" * 75)
#     print("ML3: RISK CLASSIFIER TRAINING & CHRONOLOGICAL EVALUATION")
#     print("=" * 75)

#     df = generate_multi_cutoff_dataset(num_cutoffs=10)
#     print(f"Total dataset size: {len(df):,} grid-interval samples.")

#     # 1. Chronological Split
#     unique_timestamps = sorted(df["feature_timestamp"].unique())
#     split_idx = int(len(unique_timestamps) * 0.70)
    
#     train_cutoffs = unique_timestamps[:split_idx]
#     test_cutoffs = unique_timestamps[split_idx:]

#     train_df = df[df["feature_timestamp"].isin(train_cutoffs)].copy()
#     test_df = df[df["feature_timestamp"].isin(test_cutoffs)].copy()

#     train_min_ts, train_max_ts = train_df["feature_timestamp"].min(), train_df["feature_timestamp"].max()
#     test_min_ts, test_max_ts = test_df["feature_timestamp"].min(), test_df["feature_timestamp"].max()

#     print("\n--- 1. Chronological Split Verification ---")
#     print(f"Train Window (70%): {train_min_ts}  -->  {train_max_ts}  ({len(train_df):,} samples)")
#     print(f"Test Window  (30%): {test_min_ts}  -->  {test_max_ts}  ({len(test_df):,} samples)")

#     assert train_max_ts < test_min_ts, "FATAL: Train and Test timestamps overlap! Data leakage detected."
#     print("Temporal Invariant (train_max_ts < test_min_ts): PASS (Zero Overlap)")

#     # 2. Class Balance & Base Rate
#     train_base_rate = float(train_df["target_risk_t1"].mean())
#     test_base_rate = float(test_df["target_risk_t1"].mean())

#     print("\n--- 2. Class Balance & Base Rate ---")
#     print(f"Train Base Rate (Positive Class %): {train_base_rate * 100:.2f}%")
#     print(f"Test Base Rate  (Positive Class %): {test_base_rate * 100:.2f}%")

#     X_train = train_df[FEATURE_COLS]
#     y_train = train_df["target_risk_t1"]
#     X_test = test_df[FEATURE_COLS]
#     y_test = test_df["target_risk_t1"]

#     # 3. Training Logistic Regression with Stronger L2 Regularization (C=0.001)
#     print("\n--- 3. Training Logistic Regression Baseline ---")
#     pipeline = Pipeline([
#         ("scaler", StandardScaler()),
#         ("classifier", LogisticRegression(
#             C=0.001,
#             class_weight="balanced",
#             random_state=42,
#             max_iter=1000
#         ))
#     ])

#     pipeline.fit(X_train, y_train)

#     y_pred = pipeline.predict(X_test)
#     y_prob = pipeline.predict_proba(X_test)[:, 1]

#     # Metrics
#     acc = accuracy_score(y_test, y_pred)
#     prec = precision_score(y_test, y_pred, zero_division=0)
#     rec = recall_score(y_test, y_pred, zero_division=0)
#     f1 = f1_score(y_test, y_pred, zero_division=0)

#     print("\n--- 4. Evaluation Report ---")
#     print(f"Base Rate (Majority Class Baseline): {((1 - test_base_rate) * 100):.2f}%")
#     print(f"Accuracy:                             {acc * 100:.2f}%")
#     print(f"Precision (True Positives / Flags):   {prec * 100:.2f}%")
#     print(f"Recall (Caught Risks / Total Risks): {rec * 100:.2f}%")
#     print(f"F1-Score:                             {f1:.4f}")
#     roc_auc = roc_auc_score(y_test, y_prob)
#     pr_auc = average_precision_score(y_test, y_prob)

#     print(f"ROC-AUC Score:                        {roc_auc:.4f}")
#     print(f"PR-AUC (Average Precision):           {pr_auc:.4f}  (Baseline is {test_base_rate:.4f})")

#     # 5. Feature Importances
#     print("\n--- 5. Logistic Regression Coefficients (Feature Weights) ---")
#     coefficients = pipeline.named_steps["classifier"].coef_[0]
#     coef_df = pd.DataFrame({
#         "Feature": FEATURE_COLS,
#         "Coefficient": coefficients,
#         "Absolute_Weight": np.abs(coefficients)
#     }).sort_values(by="Absolute_Weight", ascending=False)

#     for _, r in coef_df.iterrows():
#         sign = "+" if r["Coefficient"] > 0 else "-"
#         print(f"  {r['Feature']:<18} | Coef: {r['Coefficient']:>8.4f} ({sign} operational correlation)")

#     # 6. Save Model Artifact
#     os.makedirs("artifacts", exist_ok=True)
#     model_path = os.path.join("artifacts", "baseline_risk_model.joblib")
#     joblib.dump({
#         "model": pipeline,
#         "features": FEATURE_COLS,
#         "train_range": (str(train_min_ts), str(train_max_ts)),
#         "test_range": (str(test_min_ts), str(test_max_ts)),
#         "metrics": {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1}
#     }, model_path)
#     print(f"\nModel artifact saved successfully to: {model_path}")

#     os.makedirs("models", exist_ok=True)
#     with open(os.path.join("models", "feature_columns.json"), "w", encoding="utf-8") as f:
#         json.dump(FEATURE_COLS, f, indent=2)
#     print("Exported feature column definitions to models/feature_columns.json")

# if __name__ == "__main__":
#     run_training_experiment()


import os
import gc
import json
import joblib
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    precision_recall_curve
)

FEATURE_COLS = [
    "avg_activity",
    "activity_growth",
    "active_hours",
    "peak_ratio",
    "variability",
    "internet_share",
    "immediate_ratio",
    "hour_sin",
    "hour_cos",
    "dayofweek"
]

DB_URL = "mysql+pymysql://root:root@localhost:3306/telecom_warehouse"
engine = create_engine(
    DB_URL,
    connect_args={"connect_timeout": 60},
    pool_pre_ping=True
)


def fetch_full_raw_telemetry(chunk_size: int = 500_000) -> pd.DataFrame:
    """
    Retrieves the entire dataset across all available timestamps without date restrictions.
    Reads in stream chunks with optimized datatypes to prevent RAM exhaustion.
    """
    query = """
        SELECT 
            f.grid_id,
            t.timestamp,
            f.total_activity,
            f.internet_activity
        FROM fact_network_activity f
        JOIN dim_time t ON f.time_key = t.time_key
        ORDER BY f.grid_id ASC, t.timestamp ASC;
    """
    print("Executing full warehouse extraction (all timestamps, no date filtering)...")
    chunks = []
    total_rows = 0

    with engine.connect().execution_options(stream_results=True) as conn:
        for chunk in pd.read_sql(query, conn, chunksize=chunk_size):
            # Optimize data types to fit in client memory
            chunk["grid_id"] = chunk["grid_id"].astype(np.int32)
            chunk["total_activity"] = chunk["total_activity"].astype(np.float32)
            chunk["internet_activity"] = chunk["internet_activity"].astype(np.float32)
            chunk["timestamp"] = pd.to_datetime(chunk["timestamp"])
            chunks.append(chunk)
            total_rows += len(chunk)
            print(f"  Loaded {total_rows:,} rows...")

    print("Concatenating stream chunks into full memory buffer...")
    full_df = pd.concat(chunks, ignore_index=True)
    del chunks
    gc.collect()
    return full_df


def compute_row_level_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes 24h rolling feature dynamics, short-term momentum,
    diurnal cyclicity, and lookahead target (t+1) for each row.
    """
    print("Sorting full dataset by grid_id and timestamp...")
    df.sort_values(by=["grid_id", "timestamp"], ascending=True, inplace=True)
    df.reset_index(drop=True, inplace=True)

    print("Computing 24-hour rolling feature vectors and lookahead targets...")
    grouped = df.groupby("grid_id")

    rolling_24 = grouped["total_activity"].rolling(window=24, min_periods=24)
    df["avg_activity"] = rolling_24.mean().reset_index(level=0, drop=True).astype(np.float32)
    df["max_activity"] = rolling_24.max().reset_index(level=0, drop=True).astype(np.float32)
    df["std_activity"] = rolling_24.std().reset_index(level=0, drop=True).astype(np.float32)
    df["sum_activity"] = rolling_24.sum().reset_index(level=0, drop=True).astype(np.float32)

    rolling_internet = grouped["internet_activity"].rolling(window=24, min_periods=24)
    df["sum_internet"] = rolling_internet.sum().reset_index(level=0, drop=True).astype(np.float32)

    # Count active hours (> 0 activity) over the rolling 24-hour window
    is_active = (df["total_activity"] > 0).astype(np.float32)
    df["active_hours"] = is_active.groupby(df["grid_id"]).rolling(window=24, min_periods=24).sum().reset_index(level=0, drop=True).astype(np.float32)

    # Prior 24-hour baseline for momentum/growth comparison (offset 24 hours back)
    df["baseline_avg"] = grouped["total_activity"].shift(24).groupby(df["grid_id"]).rolling(window=24, min_periods=24).mean().reset_index(level=0, drop=True).astype(np.float32)

    # Lookahead target (t+1): Next immediate hour's total activity
    df["future_activity"] = grouped["total_activity"].shift(-1).astype(np.float32)

    print("Deriving operational, momentum, and cyclical features...")
    growth = (df["avg_activity"] - df["baseline_avg"]) / (df["baseline_avg"] + 1e-6)
    df["activity_growth"] = growth.clip(lower=-1.0, upper=10.0).round(4).astype(np.float32)

    peak = df["max_activity"] / (df["avg_activity"] + 1e-6)
    df["peak_ratio"] = peak.clip(lower=1.0).round(4).astype(np.float32)

    var = df["std_activity"] / (df["avg_activity"] + 1e-6)
    df["variability"] = var.clip(lower=0.0).round(4).astype(np.float32)

    net_share = df["sum_internet"] / (df["sum_activity"] + 1e-6)
    df["internet_share"] = net_share.clip(lower=0.0, upper=1.0).round(4).astype(np.float32)

    # Immediate Short-Term Momentum: current volume relative to 24h average
    imm_ratio = df["total_activity"] / (df["avg_activity"] + 1e-6)
    df["immediate_ratio"] = imm_ratio.clip(lower=0.0, upper=10.0).round(4).astype(np.float32)

    # Diurnal Cyclicity: capture 24-hour circadian rhythm without linear boundaries
    hours = df["timestamp"].dt.hour
    df["hour_sin"] = np.sin(2 * np.pi * hours / 24.0).astype(np.float32)
    df["hour_cos"] = np.cos(2 * np.pi * hours / 24.0).astype(np.float32)
    df["dayofweek"] = df["timestamp"].dt.dayofweek.astype(np.float32)

    # Target: 35%+ relative surge at t+1 with absolute minimum volume guard
    is_surge = (df["future_activity"] >= (1.35 * df["avg_activity"])) & (df["future_activity"] >= 50.0)
    df["target_risk_t1"] = is_surge.astype(np.int32)

    print(f"Total rows before dropping nulls: {len(df):,}")
    columns_to_check = FEATURE_COLS + ["target_risk_t1", "timestamp", "grid_id"]
    df.dropna(subset=columns_to_check, inplace=True)
    df.reset_index(drop=True, inplace=True)
    print(f"Total clean rows retained after dropping nulls: {len(df):,}")

    # Remove temporary helper columns to minimize RAM footprint
    drop_helpers = ["max_activity", "std_activity", "sum_activity", "sum_internet", "baseline_avg", "future_activity"]
    df.drop(columns=[col for col in drop_helpers if col in df.columns], inplace=True)
    gc.collect()

    return df


def find_optimal_threshold(y_true, y_probs):
    """
    Sweeps the precision-recall curve to determine the decision threshold
    that maximizes the operational F1-score.
    """
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_probs)
    f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-10)
    best_idx = np.argmax(f1_scores[:-1])
    return float(thresholds[best_idx]), float(f1_scores[best_idx])


def run_full_dataset_training():
    print("=" * 80)
    print("FULL-DATASET ROW-LEVEL MODEL TRAINING: HIST GRADIENT BOOSTED TREES")
    print("=" * 80)

    # Step 1: Retrieve all data and compute row-level features
    raw_df = fetch_full_raw_telemetry()
    df = compute_row_level_features(raw_df)
    del raw_df
    gc.collect()

    # Step 2: Chronological Train/Test Split (70/30)
    print("\n--- 1. Chronological Split (Zero Leakage) ---")
    unique_timestamps = sorted(df["timestamp"].unique())
    split_idx = int(len(unique_timestamps) * 0.70)
    split_cutoff = unique_timestamps[split_idx]

    train_mask = df["timestamp"] < split_cutoff
    test_mask = df["timestamp"] >= split_cutoff

    train_df = df[train_mask]
    test_df = df[test_mask]

    train_max_ts = train_df["timestamp"].max()
    test_min_ts = test_df["timestamp"].min()

    print(f"Train Records (70%): {len(train_df):,}  (Window: {train_df['timestamp'].min()} --> {train_max_ts})")
    print(f"Test Records  (30%): {len(test_df):,}   (Window: {test_min_ts} --> {test_df['timestamp'].max()})")
    assert train_max_ts < test_min_ts, "FATAL ERROR: Temporal overlap between train and test sets!"
    print("Temporal Invariant Verified: PASS (train_max_ts < test_min_ts)")

    # Step 3: Class Distribution
    train_base_rate = float(train_df["target_risk_t1"].mean())
    test_base_rate = float(test_df["target_risk_t1"].mean())
    print(f"\nPositive Surge Class Rate (Train): {train_base_rate * 100:.2f}%")
    print(f"Positive Surge Class Rate (Test):  {test_base_rate * 100:.2f}%")

    X_train = train_df[FEATURE_COLS]
    y_train = train_df["target_risk_t1"]
    X_test = test_df[FEATURE_COLS]
    y_test = test_df["target_risk_t1"]

    print("\n--- 2. Training Gradient Boosted Trees (HistGradientBoostingClassifier) ---")
    print("Hyperparameters: max_iter=250, learning_rate=0.08, max_leaf_nodes=45, class_weight='balanced'")
    
    # HistGradientBoosting operates directly on binned feature histograms (LightGBM design),
    # scaling effortlessly across 1,000,000+ rows without requiring feature standardizers.
    model = HistGradientBoostingClassifier(
        loss="log_loss",
        learning_rate=0.08,
        max_iter=250,
        max_leaf_nodes=45,
        min_samples_leaf=50,
        class_weight="balanced",
        random_state=42,
        early_stopping=True,
        validation_fraction=0.10,
        n_iter_no_change=15
    )

    model.fit(X_train, y_train)

    print("\n--- 3. Evaluation & Threshold Tuning ---")
    train_probs = model.predict_proba(X_train)[:, 1]
    test_probs = model.predict_proba(X_test)[:, 1]

    roc_auc = roc_auc_score(y_test, test_probs)
    pr_auc = average_precision_score(y_test, test_probs)

    optimal_threshold, train_opt_f1 = find_optimal_threshold(y_train, train_probs)

    pred_default = (test_probs >= 0.50).astype(int)
    pred_optimal = (test_probs >= optimal_threshold).astype(int)

    def format_metrics(label, preds):
        acc = accuracy_score(y_test, preds)
        prec = precision_score(y_test, preds, zero_division=0)
        rec = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)
        print(f"{label:<28} | Acc: {acc*100:>6.2f}% | Prec: {prec*100:>6.2f}% | Rec: {rec*100:>6.2f}% | F1: {f1:>6.4f}")

    print(f"ROC-AUC Score:                     {roc_auc:.4f}")
    print(f"PR-AUC (Average Precision):        {pr_auc:.4f}  (Random Baseline: {test_base_rate:.4f})")
    print(f"Learned Optimal Decision Cutoff:   {optimal_threshold:.4f}\n")
    print("-" * 80)
    format_metrics("Default Threshold (0.50)", pred_default)
    format_metrics(f"Optimal Threshold ({optimal_threshold:.2f})", pred_optimal)
    print("-" * 80)

    os.makedirs("artifacts", exist_ok=True)
    model_path = os.path.join("artifacts", "baseline_risk_model.joblib")
    joblib.dump({
        "model": model,
        "features": FEATURE_COLS,
        "optimal_threshold": optimal_threshold,
        "train_range": (str(train_df["timestamp"].min()), str(train_max_ts)),
        "test_range": (str(test_min_ts), str(test_df["timestamp"].max())),
        "metrics": {
            "roc_auc": roc_auc,
            "pr_auc": pr_auc,
            "optimal_threshold": optimal_threshold,
            "accuracy": accuracy_score(y_test, pred_optimal),
            "precision": precision_score(y_test, pred_optimal, zero_division=0),
            "recall": recall_score(y_test, pred_optimal, zero_division=0),
            "f1": f1_score(y_test, pred_optimal, zero_division=0)
        }
    }, model_path)
    print(f"\nTree-based model artifact + learned threshold saved successfully to: {model_path}")


if __name__ == "__main__":
    run_full_dataset_training()