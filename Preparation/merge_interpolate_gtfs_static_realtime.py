
import numpy as np
from scipy.interpolate import interp1d
import time
import pandas as pd
from zipfile import ZipFile
import geopandas as gpd
from scipy import stats
import time
from datetime import datetime
import pandas as pd
import geopandas as gpd


def filter_gtfs_realtime(gtfs_realtime_df: pd.DataFrame, start_timestamp: pd.Timestamp, end_timestamp: pd.Timestamp) -> pd.DataFrame:
    """
    Load GTFS real-time for Netherlands and clean it for specific data and Amsterdam purpose.

    Parameters:
    - gtfs_realtime_df : GTFS real-time DataFrame with 'timestamp' column (UNIX seconds)
    - start_timestamp : pd.Timestamp, e.g. '2024-03-15 05:30:00'
    - end_timestamp   : pd.Timestamp, e.g. '2024-03-16 05:29:59'

    Returns:
    - Filtered GTFS real-time DataFrame
    """

    # check the min and max time stamp in our timeformat    
    gtfs_realtime_df['timestamp_date'] = pd.to_datetime(gtfs_realtime_df['timestamp'], unit='s')
    print(gtfs_realtime_df['timestamp_date'].min(), gtfs_realtime_df['timestamp_date'].max())

    # make a new column 'day' to get the exact date from the time stamp
    gtfs_realtime_df['day'] = gtfs_realtime_df['timestamp_date'].dt.date
    unique_day = gtfs_realtime_df['day'].unique()  # check the unique days in the data set
    points_per_day = (gtfs_realtime_df['day'].value_counts())  # check the value count per day

    # and now for each day, I want to see min and max time stamp # but print per day 
    min_max_per_day = gtfs_realtime_df['timestamp_date'].groupby(gtfs_realtime_df['day']).agg(['min', 'max'])  # check the min and max time stamp per day

    # add new column day of the week here (optional)
    gtfs_realtime_df['day_of_week'] = gtfs_realtime_df['timestamp_date'].dt.day_name()

    """ Setting frame, bbox and date """ 
    # start_timestamp is 2024-03-15 Friday - around 250.000 counts!
    # end time is 2024-03-16 05.29.59 - 24 hours later
    # this is only one day

    filtered_df = gtfs_realtime_df[
        (gtfs_realtime_df['timestamp'] >= start_timestamp.value / 10 ** 9) &
        (gtfs_realtime_df['timestamp'] < end_timestamp.value / 10 ** 9)
    ]

    # Assuming your DataFrame is named df
    min_timestamp = filtered_df['timestamp'].min()
    max_timestamp = filtered_df['timestamp'].max()

    # Convert to human-readable format (assuming UNIX timestamp)
    min_time = datetime.utcfromtimestamp(min_timestamp).strftime('%Y-%m-%d %H:%M:%S')
    max_time = datetime.utcfromtimestamp(max_timestamp).strftime('%Y-%m-%d %H:%M:%S')

    print(min_time, max_time)

    return unique_day,  points_per_day,  min_max_per_day,  filtered_df


from zipfile import ZipFile
import geopandas as gpd
import pandas as pd

def enrich_and_filter_gtfs_data(filtered_realtime: pd.DataFrame, gtfs_zip_path: str, agency_id_filter: str = 'GVB') -> gpd.GeoDataFrame:
    """
    Merge real-time GTFS data with static GTFS routes.txt and filter for specific agency and route types (0 and 3).

    Parameters:
    - filtered_realtime : pd.DataFrame, cleaned GTFS real-time data (must include lat/lon, label, route_id, agency_id)
    - gtfs_zip_path     : str, path to GTFS zip (e.g., 'gtfs-nl.zip')
    - agency_id_filter  : str, agency ID to include (e.g., 'GVB')

    Returns:
    - GeoDataFrame filtered by agency and valid route types with spatial geometry and metadata
    """

    """ Load Routes again """ 
    # Reading the data from the zip file
    with ZipFile(gtfs_zip_path) as myzip:
        routes_df = pd.read_csv(myzip.open("routes.txt"), dtype={
            'route_id': 'str',
            'agency_id': 'str',
            'route_short_name': 'str',
            'route_long_name': 'str',
            'route_desc': 'str',
            'route_type': 'Int64',
            'route_color': 'str',
            'route_text_color': 'str',
            'exact_times': 'bool'
        })

    filtered_realtime = filtered_realtime[filtered_realtime['label'].notna()]  # remove NaN
    filtered_realtime['label'] = filtered_realtime['label'].astype(int)

    # Filter out rows where latitude or longitude is 0
    filtered_realtime = filtered_realtime[(filtered_realtime['latitude'] != 0) & (filtered_realtime['longitude'] != 0)]

    # "Specify the geometry column using the latitude and longitude columns"
    filtered_realtime['geometry'] = gpd.points_from_xy(filtered_realtime.longitude, filtered_realtime.latitude)
    gdf = gpd.GeoDataFrame(filtered_realtime, geometry='geometry')
    gdf.crs = "EPSG:4326"

    # Set route_id in both Dataframes to same data type and merge  
    # Cast 'route_id' to int64 to match the data type in routes_df
    gdf['route_id'] = gdf['route_id'].astype('int64')
    routes_df['route_id'] = routes_df['route_id'].astype('int64')
    routes_df['route_type'] = routes_df['route_type'].astype('int64')

    # Merge the DataFrames
    merged_df = gdf.merge(routes_df, on='route_id', how='left')

    # Create a new column by concatenating 'label' and 'agency_id' LABEL is a vehicle
    merged_df['label'] = merged_df['label'].astype('str')
    merged_df['agency_id'] = merged_df['agency_id'].astype('str')
    merged_df['uni_id'] = merged_df['label'] + '_' + merged_df['agency_id']

    """ Sorting and cleaning the dataset """
    merged_df.sort_values(by=['uni_id', 'timestamp'], inplace=True)
    merged_df = merged_df[merged_df['route_type'].isin([0, 3])]  # only buses 3 and trams 0

    gdf_gvb = merged_df[merged_df['agency_id'] == agency_id_filter]

    # df to shape file 
    gdf_gvb = gpd.GeoDataFrame(gdf_gvb, geometry=gpd.points_from_xy(gdf_gvb.longitude, gdf_gvb.latitude))
  

    # Find unique values of agency_id
    print(gdf_gvb['agency_id'].unique())  # GVB only
    print(gdf_gvb['route_type'].unique())  # buses and trams
    print(gdf_gvb['uni_id'].nunique())  # circa 250
    print(gdf_gvb['start_date'].unique())  # 13.03.2024

    return gdf_gvb


def apply_split_and_count_route_types(gdf_gvb: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Splits each uni_id group based on large jumps in GPS coordinates and prints route_type counts.

    Parameters:
    - gdf_gvb : GeoDataFrame with 'uni_id', 'latitude', 'longitude', and 'route_type' columns

    Returns:
    - Concatenated GeoDataFrame after group-wise splitting with new 'uni_id_2' assigned
    """

    # Function to split the group and assign unique identifiers
    def split_group(group_data):
        # Calculate differences between consecutive latitudes and longitudes
        lat_diff = group_data['latitude'].diff().dropna()  # Difference in latitudes
        lon_diff = group_data['longitude'].diff().dropna()  # Difference in longitudes

        # Identify points where lat difference > 0.01 or lon difference > 0.01
        split_indices = (abs(lat_diff) > 0.01) | (abs(lon_diff) > 0.01)

        # Initialize variables for split groups and identifiers
        split_groups = []
        identifier = 1
        start_index = 0

        # Iterate over the group and split it into smaller groups
        for end_index, split_point in enumerate(split_indices):
            if split_point:
                split_groups.append(group_data.iloc[start_index:end_index + 1].copy())
                split_groups[-1]['uni_id_2'] = f"{group_data['uni_id'].iloc[0]}_{identifier}"
                start_index = end_index + 1
                identifier += 1

        # Add the remaining part of the group as a split group
        split_groups.append(group_data.iloc[start_index:].copy())
        split_groups[-1]['uni_id_2'] = f"{group_data['uni_id'].iloc[0]}_{identifier}"

        return pd.concat(split_groups)

    # Apply the split function to each group
    gdf_gvb = gdf_gvb.groupby('uni_id').apply(split_group).reset_index(drop=True)

    # Count occurrences of each route_type
    route_type_counts = gdf_gvb['route_type'].value_counts()
    print(route_type_counts)

    return gdf_gvb

def run_interpolation_on_traces(gdf_gvb: pd.DataFrame, interval: int = 5) -> gpd.GeoDataFrame:
    """
    Create a GeoDataFrame from interpolation results.

    This function:
    - Interpolates GPS traces for each vehicle segment (uni_id_2)
    - Adds route/trip metadata
    - Returns GeoDataFrame in EPSG:28992 (Amersfoort / RD New)

    Parameters:
    - gdf_gvb : DataFrame with real-time GTFS grouped by 'uni_id_2'
    - interval: int, interpolation interval in seconds (default = 5)

    Returns:
    - GeoDataFrame of all interpolated traces
    """
    interpolated_dfs = []

    for uni_id, group_df in gdf_gvb.groupby('uni_id_2'):
        if len(group_df) > 1:
            timestamps = np.array(group_df['timestamp'])
            latitudes = np.array(group_df['latitude'])
            longitudes = np.array(group_df['longitude'])

            # === Interpolation logic ===
            from scipy.interpolate import interp1d
            interp_func_lat = interp1d(timestamps, latitudes, kind='linear', fill_value='extrapolate')
            interp_func_lon = interp1d(timestamps, longitudes, kind='linear', fill_value='extrapolate')
            new_timestamps_sec = np.arange(timestamps[0], timestamps[-1], interval)
            new_latitudes = interp_func_lat(new_timestamps_sec)
            new_longitudes = interp_func_lon(new_timestamps_sec)

            interpolated_df = pd.DataFrame({
                'new_timestamp': new_timestamps_sec,
                'new_lat': new_latitudes,
                'new_lon': new_longitudes
            })

            # Add metadata
            interpolated_df['uni_id'] = uni_id
            interpolated_df['route_id'] = group_df['route_id'].iloc[0]
            interpolated_df['trip_id'] = group_df['trip_id'].iloc[0]
            interpolated_df['route_type'] = group_df['route_type'].iloc[0]

            interpolated_dfs.append(interpolated_df)

    """ Create a single DataFrame """
    combined_df = pd.concat(interpolated_dfs, ignore_index=True)

    """ Create a GeoDataFrame, set projection """
    geometry = gpd.points_from_xy(combined_df['new_lon'], combined_df['new_lat'])
    gdf = gpd.GeoDataFrame(combined_df, geometry=geometry)
    gdf.set_crs(epsg=4326, inplace=True)

    gdf = gdf.to_crs("EPSG:28992")  # Amersfoort / RD New projection

    # Method: Split on 'GVB' and keep the first part + 'GVB'
    gdf['uni_id'] = gdf['uni_id'].str.split('GVB').str[0] + 'GVB'

    return gdf


# FINAL FUNCTION 

def process_gtfs_pipeline(gtfs_realtime_df: pd.DataFrame, gtfs_zip_path: str,
                                    start_timestamp: pd.Timestamp, end_timestamp: pd.Timestamp,
                                    agency_id: str = 'GVB') -> tuple[gpd.GeoDataFrame, pd.DataFrame, pd.Series, pd.DataFrame]:
    """
    Complete in-memory GTFS pipeline:
    1. Filter GTFS real-time to one day and print stats
    2. Merge real-time GTFS with static routes.txt
    3. Filter by agency and route_type
    4. Split on GPS jumps
    5. Interpolate GPS traces


    Parameters:
    - gtfs_realtime_df : full GTFS real-time DataFrame
    - gtfs_zip_path    : static GTFS zip file path
    - start_timestamp  : e.g. pd.Timestamp('2024-03-15 05:30:00')
    - end_timestamp    : e.g. pd.Timestamp('2024-03-16 05:29:59')
    - agency_id        : GTFS agency_id to include (default 'GVB')

    Returns:
    - final_gdf        : GeoDataFrame in EPSG:28992
    - unique_day       : np.ndarray of dates
    - points_per_day   : pd.Series of counts per date
    - min_max_per_day  : pd.DataFrame with min/max per date
    """
    # 1. Filter real-time GTFS and print date info
    unique_day, points_per_day, min_max_per_day, filtered_realtime = filter_gtfs_realtime(
        gtfs_realtime_df, start_timestamp, end_timestamp
    )

    # 2. Merge with static and filter agency/route_type
    gdf_gvb = enrich_and_filter_gtfs_data(filtered_realtime, gtfs_zip_path, agency_id_filter=agency_id)

    # 3. Split traces by GPS jumps
    gdf_gvb = apply_split_and_count_route_types(gdf_gvb)

    # 4. Interpolate traces
    interpolated_df = run_interpolation_on_traces(gdf_gvb)

    final_gdf = interpolated_df.copy() 

    return final_gdf, unique_day, points_per_day, min_max_per_day
