# import libraries
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import geopandas as gpd

# FINAL FUNCTION 

def snap_interpolated_points_to_routes(routes_gdf: gpd.GeoDataFrame, interpolated_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Snap interpolated GTFS points (buses and trams) to their nearest GVB route lines in Amsterdam.

    Parameters:
    - routes_gdf         : GeoDataFrame of public transport routes (must include 'route_type')
    - interpolated_gdf   : GeoDataFrame of interpolated GTFS points (must include 'route_type', 'geometry')

    Returns:
    - GeoDataFrame of snapped GTFS points (deduplicated), projected in same CRS as routes_gdf
    """

    # Reproject interpolated data to match routes CRS
    interpolated_gdf = interpolated_gdf.to_crs(routes_gdf.crs)

    # Split by mode
    interpolated_trams = interpolated_gdf[interpolated_gdf['route_type'] == 0]
    interpolated_buses = interpolated_gdf[interpolated_gdf['route_type'] == 3]

    routes_trams = routes_gdf[routes_gdf['route_type'] == 0]
    routes_buses = routes_gdf[routes_gdf['route_type'] == 3]

    # Plot raw data
    fig, ax = plt.subplots(figsize=(10, 10))
    routes_gdf.plot(ax=ax, color='black', linewidth=0.5)
    interpolated_gdf.plot(ax=ax, color='red', linewidth=0.5, markersize=0.2)
    plt.title('Routes and Interpolated GTFS Points')

    def snap_points(points_gdf, lines_gdf):
        joined = gpd.sjoin_nearest(points_gdf, lines_gdf, how="inner", distance_col="dist")
        snapped = []
        for i, row in joined.iterrows():
            if (i + 1) % 1000 == 0:
                print(f"Processed {i + 1} values")
            road = lines_gdf.loc[int(row['index_right'])].geometry
            proj = road.project(row.geometry)
            snapped_point = road.interpolate(proj)
            snapped.append(snapped_point)
        joined['geometry'] = snapped
        return joined.drop(columns=['index_right', 'dist'])

    # Snap trams
    final_trams = snap_points(interpolated_trams, routes_trams)
    final_trams = final_trams[['new_timestamp', 'new_lat', 'new_lon', 'uni_id', 'route_id_left', 'trip_id', 'route_type_left', 'geometry']]

    # Snap buses
    final_buses = snap_points(interpolated_buses, routes_buses)
    final_buses = final_buses[['new_timestamp', 'new_lat', 'new_lon', 'uni_id', 'route_id_left', 'trip_id', 'route_type_left', 'geometry']]

    # Combine
    snapped = gpd.GeoDataFrame(pd.concat([final_buses, final_trams], ignore_index=True), crs=routes_gdf.crs)

    # Drop duplicates
    snapped = snapped.drop_duplicates(subset=['new_lat', 'new_lon', 'new_timestamp', 'uni_id'], keep='first')

    # Plot snapped
    fig, ax = plt.subplots(figsize=(10, 10))
    routes_gdf.plot(ax=ax, color='black', linewidth=0.5)
    snapped.plot(ax=ax, color='red', linewidth=0.5, markersize=0.2)
    plt.title('Roads and Snapped GTFS Points')

    return snapped