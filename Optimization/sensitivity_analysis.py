import ast
import numpy as np
import pandas as pd

from .optimization_vehicles_fairness import FAIRNESS_FEATURES


def _as_list(value):
    if isinstance(value, list):
        return value
    if pd.isna(value):
        return []
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return [v.strip(" '\"") for v in value.strip("[]").split(",") if v.strip(" '\"")]
    return [value]


def _city_row(city_stats):
    return city_stats.iloc[0] if isinstance(city_stats, pd.DataFrame) else city_stats


def _vehicle_percentage_columns(vehicles):
    out = vehicles.copy()
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
    for pct, absolute in mappings.items():
        if pct not in out.columns and absolute in out.columns:
            out[pct] = pd.to_numeric(out[absolute], errors="coerce") / pd.to_numeric(
                out["A_inhab"], errors="coerce"
            ) * 100
    return out


def woz_imputation_sensitivity(
    cbs_gdf,
    vehicles_gdf,
    selected_vehicle_ids,
    city_stats,
    vehicle_id_col="uni_id",
    vehicle_crs_col="crs28922_list",
    cbs_crs_col="crs28992",
    imputation_flag_col="WOZ_imputed",
):
    """
    Post-hoc sensitivity of the cumulative relative fairness result to WOZ imputation.

    The selected vehicle set is kept fixed. Demographic components are unchanged.
    Only the WOZ component is recomputed using observed-WOZ CBS cells, and its
    citywide SD/reference mean are recomputed on observed-WOZ cells.

    Returns
    -------
    summary : one-row DataFrame with main vs observed-WOZ-only distance and
              exposure to imputation.
    vehicle_woz : per-selected-vehicle WOZ diagnostics.
    """
    if imputation_flag_col not in cbs_gdf.columns:
        raise ValueError(
            f"{imputation_flag_col!r} is missing. Re-run final_cbs_pipeline after "
            "the revision update so WOZ provenance is retained."
        )

    vehicles = _vehicle_percentage_columns(vehicles_gdf)
    ids = pd.Series(selected_vehicle_ids).dropna().astype(str).tolist()
    selected = vehicles[vehicles[vehicle_id_col].astype(str).isin(ids)].copy()
    if selected.empty:
        raise ValueError("No selected vehicle IDs were found in vehicles_gdf.")

    cbs = cbs_gdf.copy()
    observed = cbs[~cbs[imputation_flag_col].astype(bool)].copy()
    observed = observed[pd.to_numeric(observed["G_woz_woni"], errors="coerce").notna()].copy()
    if observed.empty:
        raise ValueError("No observed WOZ cells are available for sensitivity analysis.")

    # Main standardized metric uses citywide SDs of the reduced fairness vector.
    main_scales = {}
    for f in FAIRNESS_FEATURES:
        if f == "G_woz_woni":
            vals = pd.to_numeric(cbs[f], errors="coerce")
        else:
            vals = pd.to_numeric(cbs[f], errors="coerce")
        main_scales[f] = vals.std(ddof=1)

    # Main cumulative composition: mean selected vehicle percentage vectors.
    main_composition = {f: pd.to_numeric(selected[f], errors="coerce").mean() for f in FAIRNESS_FEATURES}
    city = _city_row(city_stats)
    main_city = np.array([float(city[f]) for f in FAIRNESS_FEATURES], dtype=float)
    main_vec = np.array([float(main_composition[f]) for f in FAIRNESS_FEATURES], dtype=float)
    main_sd = np.array([float(main_scales[f]) for f in FAIRNESS_FEATURES], dtype=float)
    main_distance = float(np.sqrt(np.sum(((main_vec - main_city) / main_sd) ** 2)))

    # Recompute observed-only WOZ for each selected vehicle from its CBS cell list.
    cbs_codes = cbs[cbs_crs_col].astype(str)
    rows = []
    observed_vehicle_woz = []
    for _, vehicle in selected.iterrows():
        codes = {str(x) for x in _as_list(vehicle[vehicle_crs_col])}
        covered_all = cbs[cbs_codes.isin(codes)]
        covered_obs = covered_all[~covered_all[imputation_flag_col].astype(bool)]

        main_woz = pd.to_numeric(covered_all["G_woz_woni"], errors="coerce").mean()
        obs_woz = pd.to_numeric(covered_obs["G_woz_woni"], errors="coerce").mean()
        if np.isfinite(obs_woz):
            observed_vehicle_woz.append(float(obs_woz))

        rows.append({
            vehicle_id_col: vehicle[vehicle_id_col],
            "covered_cells": len(covered_all),
            "observed_woz_cells": len(covered_obs),
            "imputed_woz_cells": int(covered_all[imputation_flag_col].astype(bool).sum()),
            "WOZ_main": main_woz,
            "WOZ_observed_only": obs_woz,
        })

    if not observed_vehicle_woz:
        raise ValueError("Selected vehicles cover no CBS cells with observed WOZ values.")

    sensitivity_vec = main_vec.copy()
    woz_index = FAIRNESS_FEATURES.index("G_woz_woni")
    sensitivity_vec[woz_index] = float(np.mean(observed_vehicle_woz))

    observed_city_woz = float(pd.to_numeric(observed["G_woz_woni"], errors="coerce").mean())
    observed_woz_sd = float(pd.to_numeric(observed["G_woz_woni"], errors="coerce").std(ddof=1))
    sensitivity_city = main_city.copy()
    sensitivity_city[woz_index] = observed_city_woz
    sensitivity_sd = main_sd.copy()
    sensitivity_sd[woz_index] = observed_woz_sd

    observed_only_distance = float(
        np.sqrt(np.sum(((sensitivity_vec - sensitivity_city) / sensitivity_sd) ** 2))
    )

    # Unique-footprint exposure to imputation.
    all_codes = set()
    for value in selected[vehicle_crs_col]:
        all_codes.update(str(x) for x in _as_list(value))
    covered_unique = cbs[cbs_codes.isin(all_codes)].copy()

    city_populated = cbs[pd.to_numeric(cbs["A_inhab"], errors="coerce") > 0]
    city_imputed_pct = 100 * city_populated[imputation_flag_col].astype(bool).mean()
    footprint_imputed_pct = (
        100 * covered_unique[imputation_flag_col].astype(bool).mean()
        if len(covered_unique) else np.nan
    )

    summary = pd.DataFrame([{
        "n_selected_vehicles": len(selected),
        "city_imputed_WOZ_cells_pct": city_imputed_pct,
        "selected_unique_imputed_WOZ_cells_pct": footprint_imputed_pct,
        "main_city_WOZ": float(city["G_woz_woni"]),
        "observed_only_city_WOZ": observed_city_woz,
        "main_selected_WOZ": float(main_vec[woz_index]),
        "observed_only_selected_WOZ": float(sensitivity_vec[woz_index]),
        "main_standardized_distance": main_distance,
        "observed_WOZ_only_standardized_distance": observed_only_distance,
        "distance_change": observed_only_distance - main_distance,
    }])

    return summary, pd.DataFrame(rows)


def measurement_frequency_sensitivity(
    cbs_interval_counts,
    threshold_per_hour=12,
    min_hours=1,
    cbs_id_col="crs28992",
):
    """
    Classify CBS cells by repeated measurement frequency.

    Uses the existing hourly count columns created by
    group_points_by_cbs_and_intervals(). A cell is `meaningfully_sensed` when
    at least `min_hours` hourly intervals contain >= `threshold_per_hour`
    measurements.

    This is a post-hoc coverage sensitivity, not a new optimization objective.

    Returns
    -------
    classified : original CBS-frequency table plus max_hourly_count,
                 hours_meeting_threshold and meaningfully_sensed.
    summary    : one-row overview of all sensed vs threshold-meeting cells.
    """
    df = cbs_interval_counts.copy()
    excluded = {cbs_id_col, "count", "geometry"}
    hour_cols = []
    for col in df.columns:
        if col in excluded:
            continue
        values = pd.to_numeric(df[col], errors="coerce")
        # Hour columns generated by the existing pipeline look like 5-6, 23-0, etc.
        if isinstance(col, str) and "-" in col and values.notna().any():
            hour_cols.append(col)

    if not hour_cols:
        raise ValueError("No hourly count columns were found in cbs_interval_counts.")

    hourly = df[hour_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    df["max_hourly_count"] = hourly.max(axis=1)
    df["hours_meeting_threshold"] = (hourly >= threshold_per_hour).sum(axis=1)
    df["meaningfully_sensed"] = df["hours_meeting_threshold"] >= min_hours

    if "count" in df.columns:
        total_count = pd.to_numeric(df["count"], errors="coerce").fillna(0)
    else:
        total_count = hourly.sum(axis=1)
    df["sensed_any"] = total_count > 0

    sensed = df["sensed_any"]
    meaningful = df["meaningfully_sensed"]
    summary = pd.DataFrame([{
        "threshold_per_hour": threshold_per_hour,
        "min_hours": min_hours,
        "cells_total": len(df),
        "cells_sensed_any": int(sensed.sum()),
        "cells_meaningfully_sensed": int(meaningful.sum()),
        "meaningful_share_of_sensed_pct": (
            np.nan if sensed.sum() == 0 else 100 * meaningful.sum() / sensed.sum()
        ),
    }])

    return df, summary


def compare_frequency_demographics(
    classified_cbs,
    population_col="A_inhab",
):
    """
    Optional demographic comparison of all sensed vs meaningfully sensed cells.

    This is deliberately separate from measurement_frequency_sensitivity so the
    frequency map/count result can be used without making a fairness claim.
    """
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
    required = [population_col, "sensed_any", "meaningfully_sensed"] + list(mappings.values())
    missing = [c for c in required if c not in classified_cbs.columns]
    if missing:
        raise ValueError(f"Missing demographic columns: {missing}")

    records = []
    for label, mask in {
        "all_sensed_cells": classified_cbs["sensed_any"],
        "meaningfully_sensed_cells": classified_cbs["meaningfully_sensed"],
    }.items():
        subset = classified_cbs[mask].copy()
        pop = pd.to_numeric(subset[population_col], errors="coerce").sum()
        record = {"Area": label, "cells": len(subset), "A_inhab": pop}
        for pct, absolute in mappings.items():
            value = pd.to_numeric(subset[absolute], errors="coerce").sum()
            record[pct] = np.nan if pop <= 0 else value / pop * 100
        if "G_woz_woni" in subset.columns:
            record["G_woz_woni"] = pd.to_numeric(subset["G_woz_woni"], errors="coerce").mean()
        records.append(record)
    return pd.DataFrame(records)
