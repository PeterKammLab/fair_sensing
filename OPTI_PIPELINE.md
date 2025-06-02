# Optimization Pipeline {Workflow 02}

This markdown file documents the end-to-end pipeline for optimizing public transport-based environmental sensing. It identifies best vehicles for different optmizations (spatial, temporal, fair) and visualises the outputs. Parameters such as start time, end time, agency, and bufferdistances are already set in the preprocessed data. 

---

## RAW/PREPROCESSED DATA & PARAMETERS

### 📊 Preprocessed Data: Sociodemographics (CBS)  
**File**: `data/temp/full_cbs.gpkg'  
**Note**: Contains 100×100m population grid, cleaned, wrangled, for specific city 

### 📊 Preprocessed Data: City Stats 
**File**: `data/city_stats_amsterdam.csv'  
**Note**: Contains staistics for the whole city, migration, WOZ value, age, etc. 

### 🗺️ Raw Data: City Border (Amsterdam)  
**File**: `data/Gemeente2.geojson`  
**Use**: Defines the administrative boundary of Amsterdam  

### 🚍 Preprocessed Data: Grouped GTFS Realtime Points with Intervals 
- **Realtime data**: `data/temp/grouped_by_points_GVB.gpkg'` # for specific timeframe (e.g. 1 day, 3 days, 1 week) 
- **Static GTFS**: `data/gtfs-nl.zip`  

### ⚙️ Parameters  
- **Number of vehicles**: e.g. 10 
- **Number of days**: e.g. 1, 3 or 7
---
