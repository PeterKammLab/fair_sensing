
import os
import sys
import time
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import random
import geopandas as gpd
import shapely
from sklearn.linear_model import LinearRegression
from sklearn.impute import SimpleImputer
from shapely import wkt

def prepare_points_for_join(gdf_cbs: gpd.GeoDataFrame, points_realtime: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Prepare snapped points for spatial join with CBS data:
    - Reproject points to match CBS CRS (EPSG:28992)
    - Add unique 7-digit ID
    - Place ID as the first column
    """
    # Reproject points if needed
    if gdf_cbs.crs != points_realtime.crs:
        points_realtime = points_realtime.to_crs(gdf_cbs.crs)

    # Rename column new_timestamp to new_timest
    points_realtime.rename(columns={"new_timestamp": "new_timest"}, inplace=True)
    
    # Add unique ID
    points_realtime["id"] = (points_realtime.index + 1).astype(str).str.zfill(7)
    
    # Reorder columns: ID first
    points_realtime = points_realtime[["id"] + [col for col in points_realtime.columns if col != "id"]]
    
    return points_realtime


def create_buffer(points_realtime: gpd.GeoDataFrame, buffer_distance: float = 50) -> gpd.GeoDataFrame:
    """
    Create buffer zones around snapped points.

    Parameters:
    - points_realtime : GeoDataFrame of snapped points
    - buffer_distance : buffer size in meters (default 50)

    Returns:
    - GeoDataFrame with buffer geometries
    """
    buffered = points_realtime.copy()
    buffered["geometry"] = buffered.geometry.buffer(buffer_distance)
    return buffered


def spatial_join_intersections(buffer_points: gpd.GeoDataFrame, gdf_cbs: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Perform spatial join between buffered points and CBS areas.
    Adds list of intersecting 'crs28992' values and their count per point.

    Parameters:
    - buffer_points : buffered points GeoDataFrame
    - gdf_cbs : CBS GeoDataFrame with 'crs28992' and 'geometry'

    Returns:
    - DataFrame with 'id', 'crs28992_list', and 'count_crs28992' (no geometry)

    """
   
    # Perform spatial join to find intersections with CBS cells
    joined = gpd.sjoin(buffer_points, gdf_cbs[['crs28992', 'geometry']], how="left", predicate="intersects")

    crs_lists = joined.groupby('id')['crs28992']\
        .apply(lambda x: list(x.dropna()) if not x.isna().all() else np.nan)\
        .reset_index()\
        .rename(columns={'crs28992': 'crs28992_list'})

    intersected_points = buffer_points.merge(crs_lists, on='id', how='left')
    intersected_points['count_crs28992'] = intersected_points['crs28992_list'].apply(lambda x: len(x) if isinstance(x, list) else 0)
    intersected_points = intersected_points.drop(columns=['geometry'])
    
    return intersected_points

def finalize_intersections(intersected_points: pd.DataFrame, points: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Finalize intersected points:
    - Add geometry back from original points using 'id'
    - Filter out non-intersecting points (count_crs28992 > 0)
    - Convert 'new_timest' to datetime and create hourly intervals

    Parameters:
    - intersected_points : DataFrame with intersected results
    - points : original points GeoDataFrame (with 'id' and 'geometry')

    Returns:
    - Cleaned DataFrame with geometry, intervals, and filtered rows
    """
    # Add geometry
    intersected_points = intersected_points.merge(points[['id', 'geometry']], on='id', how='left', suffixes=('', '_points'))

    # Reorder columns
    grouped_by_points = intersected_points[['id', 'uni_id', 'route_id_left', 'new_timest', 'trip_id', 'route_type_left',
                                            'crs28992_list', 'count_crs28992', 'geometry']]

    # Filter only points with intersections
    grouped_by_points = grouped_by_points[grouped_by_points['count_crs28992'] > 0]

    # Convert timestamp and create interval column
    grouped_by_points['timestamp'] = pd.to_datetime(grouped_by_points['new_timest'], unit='s')
    grouped_by_points['interval'] = grouped_by_points['timestamp'].apply(lambda dt: f"{dt.hour}-{(dt.hour + 1) % 24}")

    # put geometry in the last column
    grouped_by_points = grouped_by_points[['id', 'uni_id', 'route_id_left', 'new_timest', 'trip_id', 'route_type_left',
                                            'crs28992_list', 'count_crs28992', 'interval', 'geometry']]

    # transform grouped_by_points to gdf
    grouped_by_points = gpd.GeoDataFrame(grouped_by_points, geometry='geometry', crs=points.crs)
    # set amersfoort as crs
    grouped_by_points.crs = "EPSG:28992"

    return grouped_by_points

def group_points_by_cbs_and_intervals(intersected_points: gpd.GeoDataFrame,
                                      gdf_cbs: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # Convert Unix timestamp → datetime
    intersected_points['timestamp'] = pd.to_datetime(intersected_points['new_timest'], unit='s')
    # Create hourly interval “H-H+1”
    intersected_points['interval'] = (
        intersected_points['timestamp'].dt.hour.astype(str)
        + '-'
        + ((intersected_points['timestamp'].dt.hour + 1) % 24).astype(str)
    )

    # 1. Explode list → one row per CBS cell
    df = (
        intersected_points
        .dropna(subset=['crs28992_list'])
        .explode('crs28992_list')
        .rename(columns={'crs28992_list': 'crs28992'})
    )

    # 2. Count per cell & interval
    counts = (
        df
        .groupby(['crs28992', 'interval'])
        .size()
        .reset_index(name='count')
    )

    # 3. Pivot wide, fill & sum
    pivot = (
        counts
        .pivot(index='crs28992', columns='interval', values='count')
        .fillna(0)
        .astype(int)
    )
    pivot['count'] = pivot.sum(axis=1)

    # 4. Merge back to CBS grid
    result = gdf_cbs.merge(pivot, on='crs28992', how='left').fillna(0)

    # 5. Reorder columns (5‑6 → 4‑5), then total & geometry
    hour_cols = [
        "5-6","6-7","7-8","8-9","9-10","10-11","11-12","12-13",
        "13-14","14-15","15-16","16-17","17-18","18-19","19-20",
        "20-21","21-22","22-23","23-0","0-1","1-2","2-3","3-4","4-5"
    ]
    cols = ['crs28992'] + [h for h in hour_cols if h in result.columns] + ['count', 'geometry']
    return result[cols]


# FINAL FUNCTION 

def process_realtime_with_cbs(gdf_cbs: gpd.GeoDataFrame, points_realtime: gpd.GeoDataFrame, buffer_size: float = 50):
    """
    Full in-memory pipeline to process realtime snapped points to CBS aggregation.

    Steps:
    1. Prepare points and assign IDs.
    2. Create buffer around points.
    3. Perform spatial join to find intersections with CBS cells.
    4. Finalize intersections (add geometry, intervals).
    5. Group by CBS cells and intervals.

    Parameters:
    - gdf_cbs : GeoDataFrame of CBS cells with 'crs28992' and 'geometry'
    - points_realtime : GeoDataFrame of snapped points
    - buffer_size : buffer distance in meters (default 50)

    Returns:
    - grouped_by_points : DataFrame with intersected points, intervals, geometry
    - cbs_interval_counts : GeoDataFrame with counts per CBS cell and intervals
    """

    points_prepared = prepare_points_for_join(gdf_cbs, points_realtime)
    buffer = create_buffer(points_prepared, buffer_size)
    intersected_points = spatial_join_intersections(buffer, gdf_cbs)
    grouped_by_points = finalize_intersections(intersected_points, points_prepared)
    cbs_interval_counts = group_points_by_cbs_and_intervals(intersected_points, gdf_cbs)

    return grouped_by_points, cbs_interval_counts

