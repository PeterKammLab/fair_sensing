import geopandas as gpd
import numpy as np
import pandas as pd


def clip_and_filter_cbs_by_city(cbs: gpd.GeoDataFrame, city: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    cbs = cbs.to_crs(epsg=28992)
    city = city.to_crs(epsg=28992)
    clipped = gpd.overlay(cbs, city, how='intersection')
    unique_vals = clipped['crs28992res100m'].unique()
    filtered = cbs[cbs['crs28992res100m'].isin(unique_vals)].copy()

    return filtered[[
        'crs28992res100m',
        'aantal_inwoners',
        'aantal_inwoners_0_tot_15_jaar',
        'aantal_inwoners_15_tot_25_jaar',
        'aantal_inwoners_25_tot_45_jaar',
        'aantal_inwoners_45_tot_65_jaar',
        'aantal_inwoners_65_jaar_en_ouder',
        'percentage_nederlandse_achtergrond',
        'percentage_westerse_migr_achtergr',
        'percentage_niet_westerse_migr_achtergr',
        'aantal_woningen',
        'gemiddelde_woz_waarde_woning',
        'geometry'
    ]]

def clean_cbs_nan(gdf: gpd.GeoDataFrame) -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
    nan_counts = (gdf == -99997).sum()
    nan_percentages = nan_counts / len(gdf) * 100
    nan_summary = pd.DataFrame({
        'NaN Count': nan_counts,
        'NaN Percentage (%)': nan_percentages
    })

    gdf.replace(-99997, np.nan, inplace=True)
    cleaned = gdf.dropna(subset=['aantal_inwoners']).copy()

    return nan_summary, cleaned

def rename_and_recalculate(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf.columns = [
        'crs28992', 'A_inhab', 'A_0_15', 'A_15_25', 'A_25_45',
        'A_45_65', 'A_65+', 'P_nederlan', 'P_west_mig', 'P_n_west_mig',
        'A_woning', 'G_woz_woning', 'geometry'
    ]

    gdf['A_nederlan'] = gdf['P_nederlan'] / 100 * gdf['A_inhab']
    gdf['A_west_mig'] = gdf['P_west_mig'] / 100 * gdf['A_inhab']
    gdf['A_n_west_mig'] = gdf['P_n_west_mig'] / 100 * gdf['A_inhab']

    gdf.drop(columns=[c for c in gdf.columns if c.startswith('P_')], inplace=True)
    cols = [c for c in gdf.columns if c != 'geometry'] + ['geometry']
    return gdf[cols].copy()

# FINAL FUNCTION 

def process_cbs_data(cbs: gpd.GeoDataFrame, city: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """
    1. clip_and_filter_cbs_by_city: clip CBS data to city boundary and select relevant columns  
    2. clean_cbs_nan: replace -99997 with NaN and drop rows with NaN in 'aantal_inwoners'  
    3. rename_and_recalculate: rename columns and recalculate A_nederlan, A_west_mig, A_n_west_mig  

    Returns:
    - Cleaned CBS GeoDataFrame
    - NaN summary DataFrame
    """
    filtered = clip_and_filter_cbs_by_city(cbs, city)
    nan_summary, cleaned = clean_cbs_nan(filtered)
    semi_cbs = rename_and_recalculate(cleaned)
    return semi_cbs, nan_summary
