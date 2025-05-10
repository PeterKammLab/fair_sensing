import pandas as pd
import geopandas as gpd
from zipfile import ZipFile
from shapely.geometry import LineString


# FINAL FUNCTION

def extract_public_lines(gtfs_zip_path: str, agency_id: str = 'GVB'):
    # 1) Read GTFS static files from zip
    with ZipFile(gtfs_zip_path) as z:
        df_shapes = pd.read_csv(z.open("shapes.txt"), dtype={
            'shape_id': 'str',
            'shape_pt_lat': 'float',
            'shape_pt_lon': 'float',
            'shape_pt_sequence': 'Int64',
            'shape_dist_traveled': 'float',
        })
        df_routes = pd.read_csv(z.open("routes.txt"), dtype={
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
        df_trips = pd.read_csv(z.open("trips.txt"), dtype={
            'route_id': 'str',
            'service_id': 'str',
            'trip_id': 'str',
            'shape_id': 'str',
            'trip_headsign': 'str',
            'direction_id': 'str',
            'block_id': 'str',
            'wheelchair_accessible': 'str',
            'route_direction': 'str',
            'trip_note': 'str',
            'bikes_allowed': 'str'
        })

    # 2) Build GeoDataFrame of shapes
    df_shapes['geometry'] = gpd.points_from_xy(df_shapes['shape_pt_lon'], df_shapes['shape_pt_lat'])
    # group into LineStrings per shape_id
    grouped = df_shapes.groupby('shape_id')['geometry'].agg(list)
    grouped = grouped[grouped.map(len) > 1].to_frame()
    grouped['geometry'] = grouped['geometry'].apply(LineString)
    gdf_shapes = gpd.GeoDataFrame(grouped, geometry='geometry', crs="EPSG:4326")
    # reproject to RD New
    gdf_shapes = gdf_shapes.to_crs("EPSG:28992")

    # 3) Prepare route info
    df_route_meta = df_routes[['route_id','route_type','route_short_name','agency_id']].drop_duplicates()
    df_trip_meta = df_trips[['route_id','shape_id']].drop_duplicates()
    df_trip_meta = df_trip_meta.merge(df_route_meta, on='route_id', how='left')

    # 4) Merge shapes with trip metadata
    gdf = gdf_shapes.merge(df_trip_meta, left_index=True, right_on='shape_id', how='left')

    # 5) Filter for agency and modes
    gdf_agency = gdf[gdf['agency_id'] == agency_id]

    # tram: route_type == 0
    tram_gdf = gdf_agency[gdf_agency['route_type'] == 0]
    tram_unique = tram_gdf.drop_duplicates(subset='route_short_name').reset_index(drop=True)

    # bus: route_type == 3
    bus_gdf = gdf_agency[gdf_agency['route_type'] == 3]
    bus_unique = bus_gdf.drop_duplicates(subset='route_short_name').reset_index(drop=True)

    # night bus: short_name startswith 'N'
    bus_night_unique = bus_unique[bus_unique['route_short_name'].str.startswith('N')].reset_index(drop=True)

    # day bus: the rest
    bus_day_unique = bus_unique[~bus_unique['route_short_name'].str.startswith('N')].reset_index(drop=True)

    # public transport = trams + all buses
    public_transport = pd.concat([tram_unique, bus_unique], ignore_index=True)

    return public_transport, tram_unique, bus_unique, bus_day_unique, bus_night_unique
