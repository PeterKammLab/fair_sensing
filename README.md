# Fair Sensing

Fair Sensing is a research-driven Python toolkit for optimizing the spatial deployment of public transport vehicles to maximize environmental sensing, demographic coverage, and spatial fairness. It provides a modular pipeline to prepare, compute, and visualize multiple optimization strategies across urban geographies using GTFS data, CBS (Statistics Netherlands) grids, and spatial analysis techniques.

---

## 💡 Key Features

-   Combine multiple strategies: spatial, demographic, fairness
-   Analyze demographic equity: % youth, elderly, Dutch/non-western migrants
-   Export full sensing coverage and vehicle deployment stats
-   Compatible with GTFS-static, GTFS-realtime and CBS 100x100m grid data

## 📁 Repository Structure

Fair_Sensing_Repo/\n
├── data/                        # Input data: GTFS, CBS, boundary files\n
\n
├── Optimization/               # All vehicle optimization strategy scripts\n
│   ├── analysis_vehicles_stats.py\n
│   ├── calculate_VIZ_frequencies.py\n
│   ├── create_combined_df.py\n
│   ├── create_optimized_vehicles_gdf.py\n
│   ├── optimization_big_merge_stats_VIZ_points.py\n
│   ├── optimization_vehicles_spatial.py\n
│   ├── optimization_vehicles_maximum.py\n
│   ├── optimization_vehicles_fairness.py\n
│   └── vehicle_VIZ_stats_exports.py\n
\n
├── Preparation/                # Preprocessing of CBS grids, GTFS and lines\n
│   ├── analysis_viz_lines_stats_cbs_sensed.py\n
│   ├── cbs_data_cleanup.py\n
│   ├── clean_filter_cbs_city_stats.py\n
│   ├── create_public_lines.py\n
│   ├── fairest_lines_analysis_viz.py\n
│   ├── intersection_points_cbs_frequency.py\n
│   ├── merge_interpolate_gtfs_static_realtime.py\n
│   └── snap_points_to_lines.py\n
\n
├── notebooks/                  # Notebooks for fast analysis\n
│   ├── prep_notebook.ipynb\n
│   ├── opti_notebook.ipynb\n
│   ├── viz_notebook.ipynb\n
│   ├── prep_notebook_3days.ipynb\n
│   ├── prep_notebook_7days.ipynb\n
│   └── opti_notebook_3days.ipynb\n
\n
├── .gitignore\n
└── README.md\n

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
