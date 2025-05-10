# import libraries
import geopandas as gpd
import numpy as np
import random
from sklearn.linear_model import LinearRegression
import pandas as pd

def clean_and_adjust_cbs(cbs: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Clean and adjust CBS population data so that age and migration columns
    sum exactly to A_inhab (total inhabitants).

    Steps:
    1. Drop irrelevant columns
    2. Fill NaNs and replace inf values
    3. Round to integers
    4. Adjust group counts to match A_inhab exactly
    5. Recalculate and verify sums

    Parameters:
    - cbs : GeoDataFrame with CBS columns

    Returns:
    - Cleaned and corrected GeoDataFrame
    """
    # rename columns in cbs migration
    cbs = cbs.rename(columns={
        'G_woz_woning': 'G_woz_woni',
        'A_nederlan': 'A_nederlan',
        'A_west_mig': 'A_west_mig',
        'A_n_west_mig': 'A_n_west_m',
    }) 			

    # drop housing column if present
    if 'A_woning' in cbs.columns:
        cbs = cbs.drop(columns=['A_woning'])

    # define groups
    age_cols = ['A_0_15', 'A_15_25', 'A_25_45', 'A_45_65', 'A_65+']
    mig_cols = ['A_nederlan', 'A_west_mig', 'A_n_west_m']

    # fill missing and inf values
    cbs[age_cols + mig_cols + ['A_inhab']] = cbs[age_cols + mig_cols + ['A_inhab']].fillna(0)
    cbs = cbs.replace([np.inf, -np.inf], 0)

    # round to whole persons
    cbs[age_cols + mig_cols] = cbs[age_cols + mig_cols].round(0)

    # adjust totals
    def adjust_columns_to_target(row, target_col, columns):
        target = int(row[target_col])
        for col in columns:
            row[col] = int(row[col])
        current_sum = sum(row[col] for col in columns)
        diff = target - current_sum
        if diff > 0:
            while current_sum < target:
                col = random.choice(columns)
                row[col] += 1
                current_sum += 1
        elif diff < 0:
            total = -diff
            base, rem = divmod(total, len(columns))
            for i, col in enumerate(columns):
                row[col] -= base + (1 if i < rem else 0)
        return row

    cbs = cbs.apply(lambda r: adjust_columns_to_target(r, 'A_inhab', age_cols), axis=1)
    cbs = cbs.apply(lambda r: adjust_columns_to_target(r, 'A_inhab', mig_cols), axis=1)

    # recompute and enforce integer type
    cbs['age_sum'] = cbs[age_cols].sum(axis=1)
    cbs['migration_sum'] = cbs[mig_cols].sum(axis=1)
    for col in age_cols + mig_cols + ['age_sum', 'migration_sum']:
        cbs[col] = cbs[col].astype(int)

    # validation
    assert (cbs['age_sum'] == cbs['A_inhab']).all()
    assert (cbs['migration_sum'] == cbs['A_inhab']).all()

    return cbs




def impute_woz_with_regression(cbs_full: pd.DataFrame) -> pd.DataFrame:
    """
    Use linear regression to impute missing or invalid (negative) G_woz_woni values in CBS data.

    Parameters:
    - cbs_full : DataFrame with population and housing attributes

    Returns:
    - Updated DataFrame with G_woz_woni imputed and cleaned
    """
    features = ['A_inhab', 'A_0_15', 'A_15_25', 'A_25_45', 'A_45_65', 'A_65+',
                'A_nederlan', 'A_west_mig', 'A_n_west_m']
    target = 'G_woz_woni'

    # Split known and missing target values
    known = cbs_full[cbs_full[target].notna()]
    missing = cbs_full[cbs_full[target].isna()]

    # Train regression model
    model = LinearRegression()
    model.fit(known[features], known[target])

    # Predict missing
    if not missing.empty:
        preds = model.predict(missing[features])
        cbs_full.loc[cbs_full[target].isna(), target] = preds

    # Replace negative values with mean of non-negative entries
    mean_woz = cbs_full[cbs_full[target] >= 0][target].mean()
    cbs_full.loc[cbs_full[target] < 0, target] = mean_woz

    return cbs_full

def adjust_negative_values(cbs_full: pd.DataFrame) -> pd.DataFrame:
    """
    Detect and correct negative values in age and migration columns while preserving total group sums.
    Negative values are set to 0 and their deficit is redistributed across the remaining positive columns.

    Parameters:
    - cbs_full : DataFrame with population columns

    Returns:
    - Cleaned DataFrame with non-negative age/migration columns and preserved group totals
    """

    # Define column groups
    age_cols = ['A_0_15', 'A_15_25', 'A_25_45', 'A_45_65', 'A_65+']
    mig_cols = ['A_nederlan', 'A_west_mig', 'A_n_west_m']

    def adjust_negatives(row, cols):
        deficit = sum(-row[col] for col in cols if row[col] < 0)
        original_sum = sum(row[col] for col in cols)
        for col in cols:
            if row[col] < 0:
                row[col] = 0
        while deficit > 0:
            positive_cols = [col for col in cols if row[col] > 0]
            if not positive_cols:
                break
            chosen_col = random.choice(positive_cols)
            row[chosen_col] -= 1
            deficit -= 1
        return row

    # Apply to migration and age columns
    cbs_full = cbs_full.apply(lambda row: adjust_negatives(row, mig_cols), axis=1)
    cbs_full = cbs_full.apply(lambda row: adjust_negatives(row, age_cols), axis=1)

    # Recompute and verify
    cbs_full['migration_sum'] = cbs_full[mig_cols].sum(axis=1)
    cbs_full['age_sum'] = cbs_full[age_cols].sum(axis=1)
    print(cbs_full[['A_inhab', 'migration_sum', 'age_sum']].head())

    return cbs_full



# FINAL FUNCTION 1 

def final_cbs_pipeline(cbs: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Pipeline to process CBS data:
    1. Clean and adjust population groups
    2. Impute missing G_woz_woni values
    3. Adjust any remaining negative values
    """
    cbs_clean = clean_and_adjust_cbs(cbs)
    cbs_imputed = impute_woz_with_regression(cbs_clean)
    cbs_full = adjust_negative_values(cbs_imputed)
    return cbs_full

# FINAL FUNCTION 2


def compute_city_stats(cbs_city):
    """
    Compute city-level demographic and housing statistics from CBS data.

    Outputs:
    - Total inhabitants
    - Mean G_woz_woni (property value)
    - Absolute sums for age and migration groups
    - Relative percentages for age and migration groups
    - Returns result as a one-row DataFrame
    """
    total_inhab = cbs_city['A_inhab'].sum()
    mean_woz = round(cbs_city['G_woz_woni'].mean(), 2)

    # absolute sums
    age_cols = ['A_0_15', 'A_15_25', 'A_25_45', 'A_45_65', 'A_65+']
    mig_cols = ['A_nederlan', 'A_west_mig', 'A_n_west_m']
    age_sums = cbs_city[age_cols].sum()
    mig_sums = cbs_city[mig_cols].sum()

    # calculate and round percentages
    pct_age = (age_sums / total_inhab * 100).round(2)
    pct_mig = (mig_sums / total_inhab * 100).round(2)

    stats = pd.DataFrame([{
        'Area': 'Amsterdam',
        'A_inhab': total_inhab,
        'G_woz_woni': mean_woz,
        **age_sums.to_dict(),
        **mig_sums.to_dict(),
        'P_0_15': pct_age['A_0_15'],
        'P_15_25': pct_age['A_15_25'],
        'P_25_45': pct_age['A_25_45'],
        'P_45_65': pct_age['A_45_65'],
        'P_65+': pct_age['A_65+'],
        'P_nederlan': pct_mig['A_nederlan'],
        'P_west_mig': pct_mig['A_west_mig'],
        'P_n_west_m': pct_mig['A_n_west_m'],
    }])

    return stats
