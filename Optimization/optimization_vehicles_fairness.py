import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.spatial.distance import euclidean
import numpy as np


# ---------------------------------------------------------------------
# Fairness metric configuration
# ---------------------------------------------------------------------
# One reference category is omitted from each compositional block because
# age shares and migration shares each sum to 100%.
#
# Omitted reference categories:
# - Migration: P_n_west_m
# - Age: P_65+
#
# All categories remain available for descriptive reporting.
FAIRNESS_FEATURES = [
    "P_nederlan",
    "P_west_mig",
    "P_0_15",
    "P_15_25",
    "P_25_45",
    "P_45_65",
    "G_woz_woni",
]

REPORT_FEATURES = [
    "P_nederlan",
    "P_west_mig",
    "P_n_west_m",
    "P_0_15",
    "P_15_25",
    "P_25_45",
    "P_45_65",
    "P_65+",
    "G_woz_woni",
]

REFERENCE_CATEGORIES = {
    "migration": "P_n_west_m",
    "age": "P_65+",
}


def calculate_percentages(gdf):
    """
    Calculate age-group and migration-background percentages.

    All categories are retained for descriptive reporting. The reduced
    FAIRNESS_FEATURES vector is used only when calculating the composite
    fairness distance.
    """
    gdf = gdf.copy()

    age_cols = ["A_0_15", "A_15_25", "A_25_45", "A_45_65", "A_65+"]
    for col in age_cols:
        pct_col = f"P_{col.split('_')[1]}" if col != "A_65+" else "P_65+"
        gdf[pct_col] = (gdf[col] / gdf["A_inhab"] * 100).round(2)

    mig_map = {
        "A_nederlan": "P_nederlan",
        "A_west_mig": "P_west_mig",
        "A_n_west_m": "P_n_west_m",
    }
    for a_col, p_col in mig_map.items():
        gdf[p_col] = (gdf[a_col] / gdf["A_inhab"] * 100).round(2)

    gdf.rename(
        columns={
            "P_0": "P_0_15",
            "P_15": "P_15_25",
            "P_25": "P_25_45",
            "P_45": "P_45_65",
            "P_65+": "P_65+",
        },
        inplace=True,
    )

    if "geometry" in gdf.columns:
        cols = [c for c in gdf.columns if c != "geometry"] + ["geometry"]
        gdf = gdf[cols]

    return gdf


def prepare_cbs_fairness_features(cbs_gdf):
    """
    Create cell-level fairness features from the CBS grid.

    The standard deviations and covariance used by the fairness metrics must
    be estimated over city CBS cells rather than over candidate vehicles.
    Percentages are calculated per populated CBS cell; WOZ remains in its
    original unit because the subsequent standardization removes scale effects.
    """
    required = [
        "A_inhab",
        "A_nederlan",
        "A_west_mig",
        "A_n_west_m",
        "A_0_15",
        "A_15_25",
        "A_25_45",
        "A_45_65",
        "A_65+",
        "G_woz_woni",
    ]
    missing = [c for c in required if c not in cbs_gdf.columns]
    if missing:
        raise ValueError(f"CBS data are missing required fairness columns: {missing}")

    cbs = cbs_gdf[required].copy()
    cbs = cbs[pd.to_numeric(cbs["A_inhab"], errors="coerce") > 0].copy()

    mappings = {
        "P_nederlan": "A_nederlan",
        "P_west_mig": "A_west_mig",
        "P_n_west_m": "A_n_west_m",
        "P_0_15": "A_0_15",
        "P_15_25": "A_15_25",
        "P_25_45": "A_25_45",
        "P_45_65": "A_45_65",
        "P_65+": "A_65+",
    }
    for p_col, a_col in mappings.items():
        cbs[p_col] = (
            pd.to_numeric(cbs[a_col], errors="coerce")
            / pd.to_numeric(cbs["A_inhab"], errors="coerce")
            * 100
        )

    cbs["G_woz_woni"] = pd.to_numeric(cbs["G_woz_woni"], errors="coerce")
    feature_df = cbs[REPORT_FEATURES].replace([np.inf, -np.inf], np.nan)
    return feature_df


def compute_fairness_scales(cbs_gdf):
    """
    Estimate city-wide standard deviations for the reduced fairness vector.

    These scales define standardized Euclidean distance:
        sqrt(sum(((x_j - city_j) / sd_j)^2))
    """
    cell_features = prepare_cbs_fairness_features(cbs_gdf)
    scales = cell_features[FAIRNESS_FEATURES].std(axis=0, ddof=1)

    invalid = scales[(~np.isfinite(scales)) | (scales <= 0)]
    if not invalid.empty:
        raise ValueError(
            "Cannot standardize fairness features with zero/non-finite SD: "
            + ", ".join(invalid.index)
        )
    return scales


def standardized_euclidean_distance(x, y, scales):
    """Calculate standardized Euclidean distance for FAIRNESS_FEATURES."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    s = np.asarray(scales, dtype=float)

    if len(x) != len(FAIRNESS_FEATURES) or len(y) != len(FAIRNESS_FEATURES):
        raise ValueError(
            f"Expected {len(FAIRNESS_FEATURES)} fairness features, "
            f"received {len(x)} and {len(y)}."
        )
    if len(s) != len(FAIRNESS_FEATURES):
        raise ValueError(
            f"Expected {len(FAIRNESS_FEATURES)} scale values, received {len(s)}."
        )
    if np.any(~np.isfinite(s)) or np.any(s <= 0):
        raise ValueError("All fairness scales must be finite and > 0.")

    return float(np.sqrt(np.sum(((x - y) / s) ** 2)))


def mahalanobis_distance(x, y, cbs_gdf, regularization=1e-9):
    """
    Post-hoc robustness metric that accounts for covariance among features.

    A pseudo-inverse is used so the function remains stable when the covariance
    matrix is near-singular. Reference categories have already been removed via
    FAIRNESS_FEATURES.
    """
    cell_features = prepare_cbs_fairness_features(cbs_gdf)
    complete = cell_features[FAIRNESS_FEATURES].dropna()

    if len(complete) < 2:
        return np.nan

    covariance = np.cov(complete.to_numpy(dtype=float), rowvar=False)
    covariance = covariance + np.eye(covariance.shape[0]) * regularization
    inverse_covariance = np.linalg.pinv(covariance)

    delta = np.asarray(x, dtype=float) - np.asarray(y, dtype=float)
    return float(np.sqrt(delta.T @ inverse_covariance @ delta))


def representation_ratios(sensed_values, city_values):
    """
    Return sensed-share / city-share ratios for all demographic share variables.

    A ratio of 1 means proportional representation, <1 under-representation,
    and >1 over-representation. WOZ is excluded because it is not a population
    share.
    """
    ratios = {}
    for feature in REPORT_FEATURES:
        if feature == "G_woz_woni":
            continue
        city_value = float(city_values[feature])
        sensed_value = float(sensed_values[feature])
        ratios[feature] = (
            np.nan if city_value == 0 else sensed_value / city_value
        )
    return ratios


def _fairness_scale_vector(fairness_scales):
    """Coerce a scale Series/dict/array to FAIRNESS_FEATURES order."""
    if isinstance(fairness_scales, pd.Series):
        return fairness_scales[FAIRNESS_FEATURES].to_numpy(dtype=float)
    if isinstance(fairness_scales, dict):
        return np.array([fairness_scales[f] for f in FAIRNESS_FEATURES], dtype=float)
    return np.asarray(fairness_scales, dtype=float)


def _city_vector(ams_gdf):
    return ams_gdf[FAIRNESS_FEATURES].iloc[0].to_numpy(dtype=float)


def calculate_closest_vehicle(gdf, ams_gdf, fairness_scales):
    """
    Calculate standardized Euclidean distance from each vehicle to the city.

    Raw Euclidean is retained temporarily as a diagnostic column so old and
    revised values can be compared during the revision.
    """
    gdf = gdf.copy()
    city_values = _city_vector(ams_gdf)
    vehicle_values = gdf[FAIRNESS_FEATURES].to_numpy(dtype=float)
    scale_values = _fairness_scale_vector(fairness_scales)

    gdf["distance_raw_reduced"] = [
        euclidean(city_values, row) for row in vehicle_values
    ]
    gdf["distance"] = [
        standardized_euclidean_distance(city_values, row, scale_values)
        for row in vehicle_values
    ]
    return gdf


def select_top_n_vehicles(gdf_closest, n=10):
    vehicles_simplest = (
        gdf_closest.sort_values("distance", ascending=True)
        .head(n)["uni_id"]
        .values
        .tolist()
    )
    closest_vehicle_closest_df = (
        gdf_closest.sort_values("distance", ascending=True).head(n)
    )
    return closest_vehicle_closest_df, vehicles_simplest


def iterative_closest_vehicles(
    gdf_closest, ams_gdf, fairness_scales, target_n=10
):
    """
    Relative iterative fairness optimization using standardized Euclidean distance.

    The original cumulative/overlap-weighted vehicle-selection logic is
    preserved; only the distance definition is corrected.
    """
    i = 2
    gdf_closest = gdf_closest.copy()
    city_values = _city_vector(ams_gdf)
    scale_values = _fairness_scale_vector(fairness_scales)

    vehicle_values = gdf_closest[FAIRNESS_FEATURES].to_numpy(dtype=float)
    gdf_closest["distance"] = [
        standardized_euclidean_distance(city_values, row, scale_values)
        for row in vehicle_values
    ]

    closest_vehicle_df = gdf_closest.loc[
        [gdf_closest["distance"].idxmin()]
    ].reset_index(drop=True)

    while len(closest_vehicle_df) < target_n:
        n_selected = len(closest_vehicle_df)
        target_values = (
            city_values * (n_selected + 1)
            - closest_vehicle_df[FAIRNESS_FEATURES].sum().to_numpy(dtype=float)
        )

        candidate_values = gdf_closest[FAIRNESS_FEATURES].to_numpy(dtype=float)
        distances = [
            standardized_euclidean_distance(target_values, row, scale_values)
            for row in candidate_values
        ]
        distance_col = f"distance_{i}"
        gdf_closest[distance_col] = distances

        existing_vehicle_ids = closest_vehicle_df["uni_id"].values
        filtered_gdf = gdf_closest[
            ~gdf_closest["uni_id"].isin(existing_vehicle_ids)
        ]

        if filtered_gdf.empty:
            break

        closest_row = filtered_gdf.loc[filtered_gdf[distance_col].idxmin()]
        closest_row_df = closest_row.to_frame().T
        closest_row_df["target_values"] = [
            np.round(target_values, 2).tolist()
        ]
        closest_vehicle_df = pd.concat(
            [closest_vehicle_df, closest_row_df], ignore_index=True
        )
        i += 1

    vehicles_relative = closest_vehicle_df["uni_id"].tolist()[:target_n]
    return closest_vehicle_df, vehicles_relative


def iterative_closest_vehicles_absolute(
    gdf, ams_gdf, fairness_scales, target_n=10
):
    """
    Absolute/population-weighted exploratory fairness method using the same
    standardized distance definition as the primary method.
    """
    gdf = gdf.copy()
    metrics = FAIRNESS_FEATURES
    city_values = _city_vector(ams_gdf)
    scale_values = _fairness_scale_vector(fairness_scales)

    gdf["distance_1"] = [
        standardized_euclidean_distance(city_values, row, scale_values)
        for row in gdf[metrics].to_numpy(dtype=float)
    ]
    closest_vehicle_df = gdf.loc[[gdf["distance_1"].idxmin()]].copy()

    i = 2
    while len(closest_vehicle_df) < target_n:
        total_pop = closest_vehicle_df["A_inhab"].sum()
        if total_pop <= 0:
            break

        real_values = []
        for metric in metrics:
            if metric == "G_woz_woni":
                real_values.append(
                    pd.to_numeric(
                        closest_vehicle_df["G_woz_woni"], errors="coerce"
                    ).mean()
                )
            else:
                real_values.append(
                    (
                        pd.to_numeric(
                            closest_vehicle_df[metric], errors="coerce"
                        )
                        * pd.to_numeric(
                            closest_vehicle_df["A_inhab"], errors="coerce"
                        )
                    ).sum()
                    / total_pop
                )

        target = city_values * 2 - np.asarray(real_values, dtype=float)

        dist_col = f"distance_{i}"
        gdf[dist_col] = [
            standardized_euclidean_distance(target, row, scale_values)
            for row in gdf[metrics].to_numpy(dtype=float)
        ]

        remaining = gdf[
            ~gdf["uni_id"].isin(closest_vehicle_df["uni_id"])
        ]
        if remaining.empty:
            break

        next_row = remaining.loc[remaining[dist_col].idxmin()].copy()
        next_row["target_values"] = [np.round(target, 2).tolist()]
        closest_vehicle_df = pd.concat(
            [closest_vehicle_df, next_row.to_frame().T],
            ignore_index=True,
        )
        i += 1

    vehicles_absolute = closest_vehicle_df["uni_id"].tolist()[:target_n]
    return closest_vehicle_df, vehicles_absolute


def create_area_comparison_statistics(
    ams_gdf,
    df_closest,
    df_rel,
    df_abs,
    fairness_scales,
    cbs_gdf=None,
):
    """
    Compare city values with the three fairness-selection variants.

    Outputs include:
    - all demographic shares and WOZ for interpretation;
    - standardized Euclidean distance on the reduced vector;
    - raw reduced Euclidean distance as a revision diagnostic;
    - percentage-point deviations for all demographic shares;
    - representation ratios for all demographic shares;
    - optional post-hoc Mahalanobis distance.
    """

    def calculate_percentages2(gdf):
        sums = gdf[
            [
                "A_inhab",
                "A_nederlan",
                "A_west_mig",
                "A_n_west_m",
                "A_0_15",
                "A_15_25",
                "A_25_45",
                "A_45_65",
                "A_65+",
            ]
        ].sum()

        woz = pd.to_numeric(gdf["G_woz_woni"], errors="coerce").mean()

        return {
            "P_nederlan": float(sums["A_nederlan"] / sums["A_inhab"] * 100),
            "P_west_mig": float(sums["A_west_mig"] / sums["A_inhab"] * 100),
            "P_n_west_m": float(sums["A_n_west_m"] / sums["A_inhab"] * 100),
            "P_0_15": float(sums["A_0_15"] / sums["A_inhab"] * 100),
            "P_15_25": float(sums["A_15_25"] / sums["A_inhab"] * 100),
            "P_25_45": float(sums["A_25_45"] / sums["A_inhab"] * 100),
            "P_45_65": float(sums["A_45_65"] / sums["A_inhab"] * 100),
            "P_65+": float(sums["A_65+"] / sums["A_inhab"] * 100),
            "G_woz_woni": float(woz),
        }

    scenarios = {
        "Amsterdam_Average": {
            feature: float(ams_gdf[feature].iloc[0])
            for feature in REPORT_FEATURES
        },
        "percentages_abs": calculate_percentages2(df_abs),
        "percentages_rel": calculate_percentages2(df_rel),
        "percentages_closest": calculate_percentages2(df_closest),
    }

    out = pd.DataFrame.from_dict(scenarios, orient="index")
    out.index.name = "Area"
    out.reset_index(inplace=True)

    city_reduced = out.loc[
        out["Area"] == "Amsterdam_Average", FAIRNESS_FEATURES
    ].iloc[0].to_numpy(dtype=float)
    scale_values = _fairness_scale_vector(fairness_scales)

    standardized = []
    raw_reduced = []
    mahalanobis = []

    for _, row in out.iterrows():
        values = row[FAIRNESS_FEATURES].to_numpy(dtype=float)
        standardized.append(
            standardized_euclidean_distance(
                city_reduced, values, scale_values
            )
        )
        raw_reduced.append(euclidean(city_reduced, values))
        if cbs_gdf is not None:
            mahalanobis.append(
                mahalanobis_distance(values, city_reduced, cbs_gdf)
            )
        else:
            mahalanobis.append(np.nan)

    out["Distance_standardized"] = standardized
    out["Distance_raw_reduced"] = raw_reduced
    out["Distance_mahalanobis"] = mahalanobis

    city_report = {
        feature: float(
            out.loc[out["Area"] == "Amsterdam_Average", feature].iloc[0]
        )
        for feature in REPORT_FEATURES
    }

    for feature in REPORT_FEATURES:
        if feature == "G_woz_woni":
            out["WOZ_difference"] = out[feature] - city_report[feature]
            continue

        out[f"PPDev_{feature}"] = out[feature] - city_report[feature]
        out[f"Ratio_{feature}"] = np.where(
            city_report[feature] == 0,
            np.nan,
            out[feature] / city_report[feature],
        )

    ratio_cols = [
        c for c in out.columns if c.startswith("Ratio_")
    ]
    out["Worst_representation_ratio"] = out[ratio_cols].min(axis=1)

    # Backward-compatible alias. This now refers to STANDARDIZED Euclidean.
    out["Distance"] = out["Distance_standardized"]

    return out.round(4)


def generate_optimization_vehicle_table(
    closest_absolute, closest_relative, closest_closest, n
):
    """Create vehicle-ID tables for the three fairness variants."""
    df_optimizations = pd.DataFrame(
        {
            "optimization": [
                "fair_absolute",
                "fair_relative",
                "fair_closest",
            ],
            "vehicles": [
                closest_absolute["uni_id"].tolist(),
                closest_relative["uni_id"].tolist(),
                closest_closest["uni_id"].tolist(),
            ],
        }
    )

    df_vehicle_ids = pd.DataFrame(
        {
            "closest_absolute": closest_absolute["uni_id"].tolist()[:n],
            "closest_relative": closest_relative["uni_id"].tolist()[:n],
            "closest_simple": closest_closest["uni_id"].tolist()[:n],
        }
    )
    return df_optimizations, df_vehicle_ids


# FINAL FUNCTION
def run_fairness_pipeline(gdf, ams_gdf, cbs_gdf, n=10):
    """
    Run the fairness workflow with standardized Euclidean distance.

    Parameters
    ----------
    gdf : GeoDataFrame
        Vehicle-level data containing population counts and WOZ.
    ams_gdf : DataFrame/GeoDataFrame
        City-wide reference shares and WOZ.
    cbs_gdf : GeoDataFrame
        Full city CBS grid. Used to estimate city-wide feature standard
        deviations for standardized Euclidean distance and covariance for the
        post-hoc Mahalanobis robustness metric.
    n : int
        Number of vehicles to select.

    Returns
    -------
    closest_simple, closest_relative, closest_absolute,
    df_area_statistics, df_optimizations, df_vehicle_ids
    """
    # 1) Compute vehicle percentages.
    gdf_p = calculate_percentages(gdf)

    # 2) Ensure city reference values are numeric.
    ams_gdf = ams_gdf.copy()
    for feature in REPORT_FEATURES:
        ams_gdf[feature] = pd.to_numeric(
            ams_gdf[feature], errors="raise"
        )

    # 3) Estimate city-wide scales from CBS cells.
    fairness_scales = compute_fairness_scales(cbs_gdf)

    # 4) Compute standardized distances.
    gdf_closest = calculate_closest_vehicle(
        gdf_p, ams_gdf, fairness_scales
    )

    # 5) Simple closest vehicles.
    closest_simple, _ = select_top_n_vehicles(gdf_closest, n=n)

    # 6) Relative iterative method (primary fairness optimization).
    closest_relative, _ = iterative_closest_vehicles(
        gdf_closest,
        ams_gdf,
        fairness_scales,
        target_n=n,
    )

    # 7) Absolute exploratory method.
    closest_absolute, _ = iterative_closest_vehicles_absolute(
        gdf_p,
        ams_gdf,
        fairness_scales,
        target_n=n,
    )

    # 8) Area-level comparison, including post-hoc Mahalanobis.
    df_area_statistics = create_area_comparison_statistics(
        ams_gdf,
        closest_simple,
        closest_relative,
        closest_absolute,
        fairness_scales,
        cbs_gdf=cbs_gdf,
    )

    # 9) Compile vehicle ID tables.
    df_optimizations, df_vehicle_ids = generate_optimization_vehicle_table(
        closest_absolute,
        closest_relative,
        closest_simple,
        n,
    )

    return (
        closest_simple,
        closest_relative,
        closest_absolute,
        df_area_statistics,
        df_optimizations,
        df_vehicle_ids,
    )
