# Fair Sensing

Fair Sensing is a research-driven Python toolkit for optimizing the spatial deployment of public transport vehicles to maximize environmental sensing, demographic coverage, and spatial fairness. It provides a modular pipeline to prepare, compute, and visualize multiple optimization strategies across urban geographies using GTFS data, CBS (Statistics Netherlands) grids, and spatial analysis techniques.

---

## 💡 Key Features

-   Combine multiple strategies: spatial, demographic, fairness
-   Analyze demographic equity: % youth, elderly, Dutch/non-western migrants
-   Export full sensing coverage and vehicle deployment stats
-   Compatible with GTFS-static, GTFS-realtime and CBS 100x100m grid data

## 📁 Repository Structure

Fair_Sensing_Repo/
├── data/                             # Input data: GTFS, CBS, boundary files
├── Optimization/                     # All vehicle optimization strategy scripts
│   ├── analysis_vehicles_stats.py
│   ├── calculate_VIZ_frequencies.py
│   ├── create_combined_df.py
│   ├── create_optimized_vehicles_gdf.py
│   ├── optimization_big_merge_stats_VIZ_points.py
│   ├── optimization_vehicles_spatial.py
│   ├── optimization_vehicles_maximum.py
│   ├── optimization_vehicles_fairness.py
│   └── vehicle_VIZ_stats_exports.py
├── Preparation/                      # Preprocessing of CBS grids, GTFS and lines
│   ├── analysis_viz_lines_stats_cbs_sensed.py
│   ├── cbs_data_cleanup.py
│   ├── clean_filter_cbs_city_stats.py
│   ├── create_public_lines.py
│   ├── fairest_lines_analysis_viz.py
│   ├── intersection_points_cbs_frequency.py
│   ├── merge_interpolate_gtfs_static_realtime.py
│   └── snap_points_to_lines.py
├── notebooks/                        # Notebooks for fast analysis
│   ├── prep_notebook.ipynb
│   ├── opti_notebook.ipynb
│   ├── viz_notebook.ipynb
│   ├── prep_notebook_3days.ipynb
│   ├── prep_notebook_7days.ipynb
│   └── opti_notebook_3days.ipynb
├── .gitignore
└── README.md

## ⚙️ Installation

Clone the repository and install required dependencies:

```bash
git clone [https://github.com/your-org/Fair_Sensing.git](https://github.com/your-org/Fair_Sensing.git)
cd Fair_Sensing
pip install -r requirements.txt

## 🚀 How to Use

### 1. 📊 Data Preparation  
Prepare GTFS and CBS data for analysis:

```bash
python Preparation/cbs_data_cleanup.py
python Preparation/merge_interpolate_gtfs_static_realtime.py

### 2. 🧠 Run Optimization Strategies

Each script implements a specific logic:

-   **Spatial coverage:** `optimization_vehicles_spatial.py`
-   **Maximize population sensing:** `optimization_vehicles_maximum.py`
-   **Fairness-based matching:** `optimization_vehicles_fairness.py`
-   **Combine outputs:** `create_combined_df.py`

Example:

```bash
python Optimization/optimization_vehicles_spatial.py

### 3. 📈 Analysis & Export

Analyze statistics and export visual-ready outputs:

```bash
python Optimization/analysis_vehicles_stats.py
python Optimization/calculate_VIZ_frequencies.py
python Optimization/vehicle_VIZ_stats_exports.py

### 4. 🧪 Notebooks

Use notebooks for interactive workflows:

-   `prep_notebook.ipynb`: Clean and prepare CBS and GTFS
-   `opti_notebook.ipynb`: Run optimization strategies
-   `viz_notebook.ipynb`: Visualize outputs and maps
-   `*_3days.ipynb`, `*_7days.ipynb`: Sensitivity tests on time windows

## 📄 License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).
