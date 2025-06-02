# Optimization Pipeline {Workflow 02}

This markdown file documents the end-to-end pipeline for optimizing public transport-based environmental sensing. It identifies the best vehicles for different optimization goals (spatial, temporal, fairness, etc.) and visualizes the outputs. Parameters such as start time, end time, agency, and buffer distances are already set in the preprocessed data.

---

## RAW / PREPROCESSED DATA & PARAMETERS

### 📊 Preprocessed Data: Sociodemographics (CBS)  
**File**: `data/temp/full_cbs.gpkg`  
**Note**: Contains 100×100m population grid, cleaned and filtered for Amsterdam  

### 📊 Preprocessed Data: City Stats  
**File**: `data/city_stats_amsterdam.csv`  
**Note**: Aggregated indicators for the whole city (migration, WOZ, age, etc.)  

### 🗺️ Raw Data: City Border (Amsterdam)  
**File**: `data/Gemeente2.geojson`  
**Use**: Defines the administrative boundary of Amsterdam  

### 🚍 Preprocessed Data: Grouped GTFS Realtime Points  
- **File**: `data/temp/grouped_by_points_GVB.gpkg`  
- **Note**: GTFS points grouped with CBS cells, for 1/3/7 day intervals  

### ⚙️ Parameters  
- **Number of vehicles**: e.g. 10  
- **Analysis duration**: 1 / 3 / 7 days  

---

# PROCESS

## 🧠 Create Vehicles with Sociodemographic Stats

- Combine CBS data with grouped realtime points  
- Calculate per-vehicle statistics for population, housing, and migration  

#### 📥 INPUT DATA: Grouped GTFS Points, CBS Full  
#### 📤 OUTPUT DATA: GeoDataFrame of Vehicles with Statistics  

---

## 🌍 Spatial Optimization

- Select vehicles that **cover the most unique CBS cells**  
- Prioritize spatial diversity (heuristic-based selection)

#### 📥 INPUT DATA: Grouped Points with CBS, CBS Full, Vehicle Stats  
#### 📤 OUTPUT DATA: Optimized Spatial Vehicle List & GDF  

---

## ⏱️ Temporal Optimization

- Maximize **average frequency** (measurements per CBS cell per 24h)  

#### 📥 INPUT DATA: Vehicles Stats  
#### 📤 OUTPUT DATA: Optimized Temporal Vehicle List & GDF  

---

## ⚖️ Fairness Optimization

- Select vehicles whose stats are **closest to the city average**  
- Optimize for:  
  - Absolute difference  
  - Relative difference  
  - Weighted/combined score  

#### 📥 INPUT DATA: City Stats, Vehicles Stats  
#### 📤 OUTPUT DATA:  
- Fairness DataFrame (absolute/relative/combined)  
- Optimized Fairness Vehicle List  
- Fairness Subset GDF  

---

## 👥 Population-Specific Optimizations

- Optimize vehicles based on demographic coverage

### 📊 Types of Population Prioritization:
- Max **Total Population** (unique)
- Max **Elderly (Age > 65)**  
- Max **Young (Age < 15)**  
- Max **Dutch population**  
- Max **Non-Western migrants**  
- Max **Non-Western %**  
- Max **Old Age %**  
- Max **Measurement Counts**

#### 📥 INPUT DATA: CBS Full, Vehicle Stats  
#### 📤 OUTPUT DATA:  
- Optimized Vehicle Lists per Category  
- Vehicle Subsets per Optimization  
- Unique counts per group (e.g. `A_inhab`, `P_65+`)

---

## 🔀 Merge All Optimizations

- Combine all optimization types into a **single overview DataFrame**  
- Compare selected vehicles to the entire dataset and city-wide averages  

#### 📥 INPUT DATA:  
- CBS Full  
- Vehicle Stats  
- Amsterdam City Stats  
- Selected Vehicles from all Optimizations  

#### 📤 OUTPUT DATA: Combined Stats Comparison Table  

---

## 🚍 Prepare Optimized Vehicles for Visualization

- Build one GeoDataFrame for selected vehicles across all optimization strategies  
- Attach optimization labels for final visual analysis  

#### 📥 INPUT DATA: Optimized Vehicle Lists, Vehicles Stats GDF  
#### 📤 OUTPUT DATA: Final GDF for Visualisation  

---

## 📸 Quick Visual Insights

- Generate visual snapshots of optimized vehicles per strategy  
- Includes: bar charts, spatial maps, radar/spider plots  

📷 *(images inserted here as needed)*  

---

## 🧪 Master Function: Final Analysis + Visualisation

### 🔧 Function: `lines_analysis(...)`  
- Inputs: Transport lines, CBS data  
- Steps: Buffering, spatial join, stat summary  

### 🧪 Function: `lines_visualisation(...)`  
- Inputs: Amsterdam border, joined CBS + vehicle buffers  
- Outputs:  
  - **fig1**: Map of covered area  
  - **fig2**: Bar chart of absolute/relative stats  
  - **fig3**: Percentage-point difference  
  - **fig4**: Pie chart of share vs. city  

#### 📥 INPUT DATA:  
- City Border  
- Selected Vehicle Buffers  
- CBS Full  
- Stats Comparison  

#### 📤 OUTPUT DATA: `fig1` to `fig4` for final visualization  

---

🎯 *Next step: deploy the same pipeline for multiple days or agencies to compare results dynamically.*
