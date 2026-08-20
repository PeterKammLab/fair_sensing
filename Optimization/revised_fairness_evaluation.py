import numpy as np
import pandas as pd

from .optimization_big_merge_stats_VIZ_points import (
    calculate_percentages_from_vehicles,
    create_combined_vehicle_df,
    extract_string_lists,
    extract_unique_crs_codes,
    vehicle_optimization_stats_pipeline,
)
from .optimization_vehicles_fairness import (
    FAIRNESS_FEATURES,
    REPORT_FEATURES,
    compute_fairness_scales,
    mahalanobis_distance,
    standardized_euclidean_distance,
)


def _city_series(city_stats):
    if isinstance(city_stats, pd.DataFrame):
        return city_stats.iloc[0]
    return city_stats


def _scale_vector(scales):
    return np.array([float(scales[f]) for f in FAIRNESS_FEATURES], dtype=float)


def _city_reduced_vector(city_stats):
    city = _city_series(city_stats)
    return np.array([float(city[f]) for f in FAIRNESS_FEATURES], dtype=float)


def _ensure_vehicle_percentages(vehicles_gdf):
    """Return vehicle-level data with the percentage fields used by fairness."""
    return calculate_percentages_from_vehicles(vehicles_gdf.copy())


def _cumulative_composition(selected_vehicles):
    """
    Compute the composition matching the relative fairness optimizer.

    The relative optimizer works with one percentage vector per selected vehicle,
    then accumulates those vectors across vehicles. Therefore this post-hoc
    cumulative/overlap-weighted composition is the arithmetic mean of the
    selected vehicle percentage vectors. WOZ is likewise averaged across
    selected vehicles.
    """
    if selected_vehicles.empty:
        return {feature: np.nan for feature in REPORT_FEATURES}

    values = {}
    for feature in REPORT_FEATURES:
        values[feature] = float(
            pd.to_numeric(selected_vehicles[feature], errors="coerce").mean()
        )
    return values


def _unique_composition(selected_vehicles, cbs_gdf, vehicle_crs_col="crs28922_list", cbs_crs_col="crs28992"):
    """Compute sociodemographic composition over the union of uniquely covered CBS cells."""
    if selected_vehicles.empty:
        return {feature: np.nan for feature in REPORT_FEATURES}, 0, 0.0

    codes = extract_unique_crs_codes(selected_vehicles, column=vehicle_crs_col)
    covered = cbs_gdf[cbs_gdf[cbs_crs_col].isin(codes)].copy()

    if covered.empty:
        return {feature: np.nan for feature in REPORT_FEATURES}, 0, 0.0

    pop = pd.to_numeric(covered["A_inhab"], errors="coerce").sum()
    if not np.isfinite(pop) or pop <= 0:
        return {feature: np.nan for feature in REPORT_FEATURES}, len(covered), 0.0

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

    values = {}
    for pct_col, count_col in mappings.items():
        count = pd.to_numeric(covered[count_col], errors="coerce").sum()
        values[pct_col] = float(count / pop * 100)

    values["G_woz_woni"] = float(
        pd.to_numeric(covered["G_woz_woni"], errors="coerce").mean()
    )
    return values, len(covered), float(pop)


def _diagnostics_for_composition(composition, city_stats, scales, cbs_gdf):
    city = _city_series(city_stats)
    scale_values = _scale_vector(scales)

    sensed_reduced = np.array(
        [float(composition[f]) for f in FAIRNESS_FEATURES], dtype=float
    )
    city_reduced = _city_reduced_vector(city_stats)

    result = {
        "Distance_standardized": standardized_euclidean_distance(
            sensed_reduced, city_reduced, scale_values
        ),
        "Distance_mahalanobis": mahalanobis_distance(
            sensed_reduced, city_reduced, cbs_gdf
        ),
        "WOZ_difference": float(composition["G_woz_woni"]) - float(city["G_woz_woni"]),
    }

    ratios = []
    for feature in REPORT_FEATURES:
        if feature == "G_woz_woni":
            continue
        sensed = float(composition[feature])
        reference = float(city[feature])
        result[f"PPDev_{feature}"] = sensed - reference
        ratio = np.nan if reference == 0 else sensed / reference
        result[f"Ratio_{feature}"] = ratio
        ratios.append(ratio)

    finite_ratios = [r for r in ratios if np.isfinite(r)]
    result["Worst_representation_ratio"] = (
        min(finite_ratios) if finite_ratios else np.nan
    )
    return result


def build_revised_fairness_diagnostics(
    vehicles_gdf,
    cbs_gdf,
    city_stats,
    strategy_tables,
    city_name="Amsterdam",
):
    """
    Evaluate every strategy using both fairness objects requested in revision.

    Returns one row per strategy with:
      - cumulative/overlap-weighted standardized Euclidean and Mahalanobis;
      - unique-coverage standardized Euclidean and Mahalanobis;
      - per-group percentage-point deviations and representation ratios for both;
      - worst representation ratio for both;
      - unique cells, unique population, and unique population coverage (%).

    The cumulative definition matches the relative optimizer's arithmetic mean
    of selected vehicle demographic percentage vectors. The unique definition
    evaluates the union of covered CBS cells, counting each cell once.
    """
    vehicles_p = _ensure_vehicle_percentages(vehicles_gdf)
    scales = compute_fairness_scales(cbs_gdf)

    combined = create_combined_vehicle_df(*strategy_tables)
    lists_dict = extract_string_lists(combined)

    total_city_pop = float(pd.to_numeric(cbs_gdf["A_inhab"], errors="coerce").sum())
    records = []

    for strategy, ids in lists_dict.items():
        selected = vehicles_p[vehicles_p["uni_id"].astype(str).isin(ids)].copy()

        cumulative = _cumulative_composition(selected)
        unique, n_unique_cells, unique_pop = _unique_composition(selected, cbs_gdf)

        cumulative_diag = _diagnostics_for_composition(
            cumulative, city_stats, scales, cbs_gdf
        )
        unique_diag = _diagnostics_for_composition(
            unique, city_stats, scales, cbs_gdf
        )

        record = {
            "Strategy": strategy,
            "Unique_cells": n_unique_cells,
            "Unique_population": unique_pop,
            "Unique_population_coverage_pct": (
                np.nan if total_city_pop <= 0 else unique_pop / total_city_pop * 100
            ),
        }

        for key, value in cumulative_diag.items():
            record[f"Cumulative_{key}"] = value
        for key, value in unique_diag.items():
            record[f"Unique_{key}"] = value

        records.append(record)

    diagnostics = pd.DataFrame(records).set_index("Strategy")
    diagnostics.attrs["fairness_scales"] = scales.to_dict()
    diagnostics.attrs["fairness_features"] = list(FAIRNESS_FEATURES)
    diagnostics.attrs["fairness_object_cumulative"] = (
        "Arithmetic mean of selected vehicle sociodemographic percentage vectors; "
        "overlapping CBS cells can therefore contribute through multiple vehicles."
    )
    diagnostics.attrs["fairness_object_unique"] = (
        "Union of covered CBS cells; each covered cell contributes once."
    )
    diagnostics.attrs["city_name"] = city_name
    return diagnostics


def _append_diagnostic_rows(master_df, diagnostics, city_name="Amsterdam"):
    """Append revision metrics to the existing strategy-as-columns master table."""
    out = master_df.copy()

    # Remove the obsolete raw Euclidean row so it is not confused with the
    # corrected standardized metric.
    if "euclidean_distance" in out.index:
        out = out.drop(index="euclidean_distance")

    simple_rows = {
        "distance_cumulative_standardized": "Cumulative_Distance_standardized",
        "distance_cumulative_mahalanobis": "Cumulative_Distance_mahalanobis",
        "distance_unique_standardized": "Unique_Distance_standardized",
        "distance_unique_mahalanobis": "Unique_Distance_mahalanobis",
        "worst_representation_ratio_cumulative": "Cumulative_Worst_representation_ratio",
        "worst_representation_ratio_unique": "Unique_Worst_representation_ratio",
        "population_coverage_unique_pct": "Unique_population_coverage_pct",
        "woz_difference_cumulative": "Cumulative_WOZ_difference",
        "woz_difference_unique": "Unique_WOZ_difference",
    }

    for output_row, diagnostic_col in simple_rows.items():
        values = {
            strategy: diagnostics.loc[strategy, diagnostic_col]
            for strategy in diagnostics.index
            if strategy in out.columns
        }
        out.loc[output_row] = pd.Series(values)

    # Add per-group diagnostics for transparent reporting.
    demographic_features = [f for f in REPORT_FEATURES if f != "G_woz_woni"]
    for feature in demographic_features:
        for prefix, readable in (("Cumulative", "cumulative"), ("Unique", "unique")):
            pp_col = f"{prefix}_PPDev_{feature}"
            ratio_col = f"{prefix}_Ratio_{feature}"

            pp_values = {
                strategy: diagnostics.loc[strategy, pp_col]
                for strategy in diagnostics.index
                if strategy in out.columns
            }
            ratio_values = {
                strategy: diagnostics.loc[strategy, ratio_col]
                for strategy in diagnostics.index
                if strategy in out.columns
            }
            out.loc[f"ppdev_{readable}_{feature}"] = pd.Series(pp_values)
            out.loc[f"ratio_{readable}_{feature}"] = pd.Series(ratio_values)

    # City/reference values for new rows.
    if city_name in out.columns:
        for row in [
            "distance_cumulative_standardized",
            "distance_cumulative_mahalanobis",
            "distance_unique_standardized",
            "distance_unique_mahalanobis",
            "woz_difference_cumulative",
            "woz_difference_unique",
        ]:
            out.at[row, city_name] = 0.0

        out.at["worst_representation_ratio_cumulative", city_name] = 1.0
        out.at["worst_representation_ratio_unique", city_name] = 1.0
        out.at["population_coverage_unique_pct", city_name] = 100.0

        for feature in demographic_features:
            out.at[f"ppdev_cumulative_{feature}", city_name] = 0.0
            out.at[f"ppdev_unique_{feature}", city_name] = 0.0
            out.at[f"ratio_cumulative_{feature}", city_name] = 1.0
            out.at[f"ratio_unique_{feature}", city_name] = 1.0

    return out


def vehicle_optimization_stats_pipeline_revised(
    gdf,
    cbs,
    ams_stats,
    max_space_vehicles,
    max_temp_vehicles,
    max_pop_vehicles,
    fair_vehicles,
    combined_vehicles,
    random_vehicles,
    all_vehicles,
    city_name="Amsterdam",
    return_diagnostics=False,
):
    """
    Revision-safe wrapper around the original master statistics pipeline.

    The original coverage/transport summaries are retained. The obsolete raw
    Euclidean row is removed and replaced by standardized cumulative and unique
    fairness evaluations plus Mahalanobis robustness and per-group diagnostics.
    """
    master = vehicle_optimization_stats_pipeline(
        gdf,
        cbs,
        ams_stats,
        max_space_vehicles,
        max_temp_vehicles,
        max_pop_vehicles,
        fair_vehicles,
        combined_vehicles,
        random_vehicles,
        all_vehicles,
    )

    strategy_tables = (
        max_space_vehicles,
        max_temp_vehicles,
        max_pop_vehicles,
        fair_vehicles,
        combined_vehicles,
        random_vehicles,
        all_vehicles,
    )

    diagnostics = build_revised_fairness_diagnostics(
        gdf,
        cbs,
        ams_stats,
        strategy_tables,
        city_name=city_name,
    )
    revised = _append_diagnostic_rows(master, diagnostics, city_name=city_name)

    if return_diagnostics:
        return revised, diagnostics
    return revised
