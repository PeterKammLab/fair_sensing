import pandas as pd

def combine_optimized_dfs(spatial_df, pop_df, fair_df):
    df = pd.concat([spatial_df, pop_df, fair_df], axis=1)
    return df