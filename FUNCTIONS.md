# 🛰️ Fair Sensing Workflow Pipeline

This markdown file documents the end-to-end pipeline for optimizing public transport-based environmental sensing coverage. It shows how we transform raw spatial and temporal data into a strategic deployment plan using modular Python functions.

---

## 1. `load_transport_data(df, crs)`

**Input**:  
- `df`: raw transport vehicle traces as GeoDataFrame  
- `crs`: string (e.g. `'EPSG:28992'`)  

**Output**:  
- Projected GeoDataFrame with standardized columns

```python
def load_transport_data(df, crs='EPSG:28992'):
    return df.to_crs(crs)

