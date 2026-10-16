import ast
import numpy as np
import pandas as pd

from .optimization_vehicles_spatial import spatial_optimization_pipeline
from .optimization_vehicles_temporal import temporal_optimization_pipeline
from .optimization_vehicles_fairness import (
    FAIRNESS_FEATURES,
    calculate_percentages,
    compute_fairness_scales,
    mahalanobis_distance,
    run_fairness_pipeline,
    standardized_euclidean_distance,
)


DEFAULT_SAMPLES = [
    2, 4, 6, 8, 10,
    15, 20, 25, 30, 35,
    40, 45, 50, 60, 70,
    80, 90, 100,
]


def _parse_cell_list(value):
    """Return a vehicle's CBS-cell list as ordinary strings."""
    if isinstance(value, (list, tuple, set, np.ndarray)):
        return [str(v) for v in value]
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    try:
        parsed = ast.literal_eval(str(value))
        if isinstance(parsed, (list, tuple, set)):
            return [str(v) for v in parsed]
    except (ValueError, SyntaxError):
        pass
    return [
        x.strip(" '\"")
        for x in str(value).strip("[]").split(",")
        if x.strip(" '\"")
    ]


def _selected_vehicle_frame(vehicles_stats, selected_ids):
    ids = set(map(str, selected_ids))
    selected = vehicles_stats[
        vehicles_stats["uni_id"].astype(str).isin(ids)
    ].copy()
    if selected.empty:
        raise ValueError("The selected vehicle list did not match any rows in vehicles_stats.")
    return selected


def _evaluate_selection(
    vehicles_stats,
    selected_ids,
    city_stats,
    cbs_full,
    fairness_scales,
    vehicle_crs_col="crs28922_list",
):
    """Evaluate coverage, frequency, standardized Euclidean, and Mahalanobis."""
    selected = _selected_vehicle_frame(vehicles_stats, selected_ids)

    if vehicle_crs_col not in selected.columns:
        raise KeyError(
            f"'{vehicle_crs_col}' is missing from vehicles_stats; "
            f"available columns include: {list(selected.columns)}"
        )

    # Unique union coverage.
    unique_cells = set()
    for value in selected[vehicle_crs_col]:
        unique_cells.update(_parse_cell_list(value))
    n_unique_cells = len(unique_cells)

    # Frequency: total selected measurements / unique CBS cells.
    if "count" not in selected.columns:
        raise KeyError("'count' is missing from vehicles_stats.")
    total_measurements = pd.to_numeric(selected["count"], errors="coerce").fillna(0).sum()
    avg_points_per_cell = (
        float(total_measurements) / n_unique_cells
        if n_unique_cells > 0 else np.nan
    )

    # IMPORTANT: vehicles_stats normally contains A_* counts, not P_* shares.
    # Create the exact percentage columns used by the revised fairness metric
    # before selecting FAIRNESS_FEATURES. This fixes the previous KeyError.
    selected_pct = calculate_percentages(selected)

    missing_features = [f for f in FAIRNESS_FEATURES if f not in selected_pct.columns]
    if missing_features:
        raise KeyError(
            "Fairness percentage preparation did not create required columns: "
            + ", ".join(missing_features)
        )

    # Revised cumulative fleet profile: equal-weight arithmetic mean of the
    # selected vehicle profiles (overlap is intentionally allowed here).
    selected_profile = (
        selected_pct[FAIRNESS_FEATURES]
        .apply(pd.to_numeric, errors="coerce")
        .mean(axis=0)
    )

    city_row = city_stats.iloc[0] if isinstance(city_stats, pd.DataFrame) else city_stats
    city_profile = pd.Series({
        feature: float(city_row[feature])
        for feature in FAIRNESS_FEATURES
    })

    scales = fairness_scales[FAIRNESS_FEATURES].to_numpy(dtype=float)
    selected_vector = selected_profile[FAIRNESS_FEATURES].to_numpy(dtype=float)
    city_vector = city_profile[FAIRNESS_FEATURES].to_numpy(dtype=float)

    standardized_distance = standardized_euclidean_distance(
        selected_vector,
        city_vector,
        scales,
    )
    maha_distance = mahalanobis_distance(
        selected_vector,
        city_vector,
        cbs_full,
    )

    return {
        "unique": int(n_unique_cells),
        "total_measurements": float(total_measurements),
        "avg_point": float(avg_points_per_cell),
        "fairness": float(standardized_distance),
        "mahalanobis": float(maha_distance),
    }


def filter_weekly_candidate_pool(
    points_gdf,
    vehicles_stats,
    min_active_days=6,
    day_col="n_unique_days",
):
    """
    Restrict both weekly points and vehicle statistics to the same candidate pool.

    For the revised 7-day comparison use min_active_days=6, so spatial,
    temporal, and fairness all optimize over vehicles active on at least 6 days.
    """
    if day_col not in vehicles_stats.columns:
        raise KeyError(
            f"'{day_col}' is missing from vehicles_stats. "
            "Create n_unique_days before applying the weekly candidate filter."
        )

    eligible_vehicles = vehicles_stats[
        pd.to_numeric(vehicles_stats[day_col], errors="coerce") >= min_active_days
    ].copy()

    eligible_ids = set(eligible_vehicles["uni_id"].astype(str))
    eligible_points = points_gdf[
        points_gdf["uni_id"].astype(str).isin(eligible_ids)
    ].copy()

    return eligible_points, eligible_vehicles


def create_intransit_summary(
    points_gdf,
    vehicles_stats,
    cbs_full,
    city_stats,
    samples=None,
    coverage_threshold=2,
    verbose=True,
):
    """
    Create the R-ready optimization trade-off summary.

    Spatial optimization is run once up to max(samples), because its greedy
    output is an ordered sequence and each N uses its prefix.

    Temporal and fairness optimizations are rerun for every N. The fairness
    strategy exported here is closest_relative.

    The Eucl_* columns contain the revised standardized Euclidean distance.
    Maha_* columns contain the corresponding Mahalanobis robustness metric.
    """
    if samples is None:
        samples = DEFAULT_SAMPLES
    samples = list(samples)
    if not samples:
        raise ValueError("samples cannot be empty")

    max_n = max(samples)
    if max_n > vehicles_stats["uni_id"].astype(str).nunique():
        raise ValueError(
            f"max sample size ({max_n}) exceeds candidate vehicles "
            f"({vehicles_stats['uni_id'].astype(str).nunique()})."
        )

    fairness_scales = compute_fairness_scales(cbs_full)

    if verbose:
        print("Candidate vehicles:", vehicles_stats["uni_id"].astype(str).nunique())
        print("Running spatial optimization once to N =", max_n)

    _, _, spatial_full = spatial_optimization_pipeline(
        points_gdf,
        cbs_full,
        vehicles_stats,
        coverage_threshold=coverage_threshold,
        top_n=max_n,
    )
    spatial_order = (
        spatial_full["max_spatial"].dropna().astype(str).tolist()
    )

    rows = []

    for n in samples:
        if verbose:
            print(f"Running N = {n}")

        # Spatial: ordered prefix from the single greedy run.
        spatial_ids = spatial_order[:n]

        # Temporal: rerun at this exact N.
        _, _, temporal_df = temporal_optimization_pipeline(
            vehicles_stats,
            top_n=n,
        )
        temporal_ids = (
            temporal_df["max_temporal"].dropna().astype(str).tolist()
        )

        # Fairness: rerun at this exact N and keep primary relative strategy.
        _, _, _, _, _, fair_vehicles = run_fairness_pipeline(
            vehicles_stats,
            city_stats,
            cbs_full,
            n=n,
        )
        fairness_ids = (
            fair_vehicles["closest_relative"].dropna().astype(str).tolist()
        )

        spatial_stats = _evaluate_selection(
            vehicles_stats, spatial_ids, city_stats, cbs_full, fairness_scales
        )
        temporal_stats = _evaluate_selection(
            vehicles_stats, temporal_ids, city_stats, cbs_full, fairness_scales
        )
        fairness_stats = _evaluate_selection(
            vehicles_stats, fairness_ids, city_stats, cbs_full, fairness_scales
        )

        rows.append({
            "Sample": n,
            "avg_point_spatial": spatial_stats["avg_point"],
            "Eucl_spatial": spatial_stats["fairness"],
            "Maha_spatial": spatial_stats["mahalanobis"],
            "unique_spatial": spatial_stats["unique"],
            "avg_point_temp": temporal_stats["avg_point"],
            "Eucl_temp": temporal_stats["fairness"],
            "Maha_temp": temporal_stats["mahalanobis"],
            "unique_temp": temporal_stats["unique"],
            "avg_point_fair": fairness_stats["avg_point"],
            "Eucl_fair": fairness_stats["fairness"],
            "Maha_fair": fairness_stats["mahalanobis"],
            "unique_fair": fairness_stats["unique"],
        })

    return pd.DataFrame(rows)
