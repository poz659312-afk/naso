"""
Planetary Analog Similarity Model
Finds the top Earth analog locations for any given coordinate on Mars or the Moon.
Supports deployed Neon PostgreSQL database with local CSV fallback.
"""

import math
import os
import json
import pandas as pd
import psycopg2
import psycopg2.extras

# Load .env variables if present
def load_env():
    env_vars = {}
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    os.environ[k] = v
                    env_vars[k] = v
    return env_vars

load_env()

# Precomputed Earth feature statistics (mean and standard deviation across 6.38 million points)
EARTH_STATS = {
    'elevation_m': {'pg_col': 'elevation_m', 'csv_col': '"1_Topography (SRTM)__Elev_m"', 'mean': 635.336, 'std': 827.229, 'default_weight': 0.3},
    'slope_deg': {'pg_col': 'slope_deg', 'csv_col': '"1_Topography (SRTM)__Slope_deg"', 'mean': 0.621, 'std': 1.004, 'default_weight': 1.0},
    'roughness_m': {'pg_col': 'roughness_m', 'csv_col': '"1_Topography (SRTM)__Roughness_m"', 'mean': 39.994, 'std': 64.152, 'default_weight': 1.0},
    'albedo': {'pg_col': 'albedo', 'csv_col': '"2_Spectral_Albedo (MOD09)__Broadband_Albedo"', 'mean': 0.298, 'std': 0.187, 'default_weight': 1.5},
    'temperature_day_K': {'pg_col': '(surf_temp_day_c + 273.15)', 'csv_col': '("3_Thermal_Emissivity (MOD11)__Surf_Temp_Day_C" + 273.15)', 'mean': 271.931, 'std': 24.471, 'default_weight': 1.0},
    'temperature_night_K': {'pg_col': '(surf_temp_night_c + 273.15)', 'csv_col': '("3_Thermal_Emissivity (MOD11)__Surf_Temp_Night_C" + 273.15)', 'mean': 268.055, 'std': 21.737, 'default_weight': 1.0},
    'atm_dust_opacity': {'pg_col': 'atm_dust_opacity', 'csv_col': '"5_Atmosphere (MERRA-2)__atm_dust_opacity"', 'mean': 0.0357, 'std': 0.0625, 'default_weight': 0.5}
}

FAMOUS_SITES = {
    'mars': {
        'Jezero Crater (Perseverance)': (18.38, 77.58),
        'Gale Crater (Curiosity)': (-4.58, 137.44),
        'Olympus Mons': (18.65, -133.80),
        'Valles Marineris': (-13.90, -59.20),
        'Gusev Crater (Spirit)': (-14.57, 175.47),
        'Meridiani Planum (Opportunity)': (-1.94, -5.53),
        'Elysium Planitia (InSight)': (4.50, 135.62),
        'Planum Boreum (North Polar Cap)': (85.00, 0.00),
        'Planum Australe (South Polar Cap)': (-85.00, 0.00)
    },
    'moon': {
        'Apollo 11 (Sea of Tranquility)': (0.67, 23.47),
        'Apollo 12 (Ocean of Storms)': (-3.01, -23.42),
        'Apollo 14 (Fra Mauro)': (-3.64, -17.47),
        'Apollo 15 (Hadley-Apennine)': (26.13, 3.63),
        'Apollo 16 (Descartes Highlands)': (-8.97, 15.50),
        'Apollo 17 (Taurus-Littrow)': (20.19, 30.77),
        'Tycho Crater': (-43.30, -11.20),
        'Copernicus Crater': (9.62, -20.08),
        'Shackleton Crater (South Pole)': (-89.90, 0.00),
        'Mare Serenitatis': (28.00, 17.50)
    }
}

def identify_earth_region(lat, lon):
    """Identifies the approximate geographic region / country for Earth coordinates."""
    if -30 <= lat <= -18 and -72 <= lon <= -66:
        return "Atacama Desert / Andes Altiplano, Chile"
    if -85 <= lat <= -65 and 150 <= lon <= 170:
        return "McMurdo Dry Valleys, Antarctica"
    if lat <= -60:
        return "Antarctic Ice Sheet / Polar Plateau"
    if 33 <= lat <= 38 and -119 <= lon <= -114:
        return "Mojave Desert / Death Valley, USA"
    if 73 <= lat <= 77 and -93 <= lon <= -85:
        return "Devon Island / Haughton Impact Crater, Nunavut, Canada"
    if 63 <= lat <= 67 and -24 <= lon <= -13:
        return "Volcanic Highlands / Askja, Iceland"
    if 76 <= lat <= 81 and 10 <= lon <= 30:
        return "Svalbard / Spitsbergen High Arctic, Norway"
    if 18 <= lat <= 32 and -15 <= lon <= 35:
        return "Sahara Desert, North Africa"
    if -30 <= lat <= -18 and 12 <= lon <= 20:
        return "Namib Desert, Namibia"
    if 28 <= lat <= 35 and 50 <= lon <= 62:
        return "Dasht-e Lut / Kavir Desert, Iran"
    if 11 <= lat <= 15 and 40 <= lon <= 43:
        return "Danakil Depression, Ethiopia / Eritrea"
    if 28 <= lat <= 38 and 78 <= lon <= 103:
        return "Tibetan Plateau / Changtang, China"
    if 36 <= lat <= 40 and 90 <= lon <= 99:
        return "Qaidam Basin Mars Analog, Qinghai, China"
    if 40 <= lat <= 46 and 95 <= lon <= 115:
        return "Gobi Desert, Mongolia / China"
    if -32 <= lat <= -20 and 120 <= lon <= 140:
        return "Great Victoria / Gibson Desert, Australia"
    if 18 <= lat <= 26 and 42 <= lon <= 56:
        return "Rub' al Khali (Empty Quarter), Arabia"
    if 60 <= lat <= 75 and 60 <= lon <= 170:
        return "Siberian Tundra / Verkhoyansk, Russia"
    if 50 <= lat <= 60 and 85 <= lon <= 120:
        return "Sayan / Baikal Mountain Steppe, Siberia"
    if 60 <= lat <= 75 and -165 <= lon <= -110:
        return "Alaskan / Yukon Arctic Tundra, North America"
    if 60 <= lat <= 83 and -60 <= lon <= -20:
        return "Greenland Ice Sheet / Coastal Tundra"
    if lat > 72:
        return f"High Arctic Tundra ({lat:.1f}°N, {lon:.1f}°E)"
    
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"Land area ({abs(lat):.2f}°{ns}, {abs(lon):.2f}°{ew})"


class PlanetaryAnalogModel:
    def __init__(self, database_url=None):
        load_env()
        self.db_url = database_url or os.environ.get("DATABASE_URL")
        self.backend = "neon" if self.db_url else "local"
        self.stats = EARTH_STATS
        self._pg_conn = None

    def _get_pg_conn(self):
        if self._pg_conn is None or self._pg_conn.closed != 0:
            self._pg_conn = psycopg2.connect(self.db_url)
        return self._pg_conn

    def get_target_features(self, body, lat, lon):
        """
        Finds the nearest spatial location directly in the database (Neon PostgreSQL or DuckDB).
        No rounding or coordinate snapping is applied.
        """
        body = body.lower()
        if body not in ('mars', 'moon'):
            raise ValueError(f"Unknown body: {body}. Choose 'mars' or 'moon'.")
            
        table_name = "mars" if body == "mars" else "moon"

        # Validate and clamp coordinates to physical planetary domain
        clean_lat = float(lat)
        clean_lon = float(lon)
        
        # Longitude wrapping if outside [-180, 180]
        if clean_lon > 180.0 or clean_lon < -180.0:
            clean_lon = ((clean_lon + 180.0) % 360.0) - 180.0
        # If clean_lon is 180.0, map to -180.0 (same meridian) since datasets range [-180, 179]
        if clean_lon == 180.0:
            clean_lon = -180.0
            
        clean_lat = max(-90.0, min(90.0, clean_lat))
        if body == 'mars':
            clean_lat = max(-89.0, min(90.0, clean_lat))

        if self.backend == "neon":
            conn = self._get_pg_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(f"""
                    SELECT *,
                           SQRT(POWER(lat - %s, 2) + POWER(lon - %s, 2)) AS coord_dist_deg
                    FROM {table_name}
                    ORDER BY coord_dist_deg ASC
                    LIMIT 1;
                """, (clean_lat, clean_lon))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"No records found in {table_name} table.")
                return dict(row)
        else:
            # Local DuckDB fallback
            import duckdb
            con = duckdb.connect()
            data_file = f"{table_name.capitalize()}Complete_Dataset.csv"
            query = f"""
                SELECT *,
                       SQRT(POWER(lat - ({clean_lat}), 2) + POWER(lon - ({clean_lon}), 2)) AS coord_dist_deg
                FROM '{data_file}'
                ORDER BY coord_dist_deg ASC
                LIMIT 1;
            """
            df = con.execute(query).df()
            if df.empty:
                raise ValueError(f"No records found in local dataset {data_file}.")
            return df.to_dict('records')[0]

    def find_analogs(self, body, lat, lon, top_k=5, weights=None, min_distance_deg=0.2):
        """
        Queries the deployed Neon PostgreSQL database to find top Earth analogs.
        """
        body = body.lower()
        target_row = self.get_target_features(body, lat, lon)
        
        candidate_features = ['elevation_m', 'slope_deg', 'roughness_m', 'albedo', 'temperature_day_K', 'temperature_night_K']
        if body == 'mars':
            candidate_features.append('atm_dust_opacity')
            
        features_used = {}
        diff_terms = []
        
        for feat in candidate_features:
            # In PG columns are lowercase
            pg_feat = feat.lower()
            val = target_row.get(pg_feat) if pg_feat in target_row else target_row.get(feat)
            
            if val is not None and not math.isnan(val):
                stat = self.stats[feat]
                col_expr = stat['pg_col'] if self.backend == "neon" else stat['csv_col']
                std = stat['std']
                
                w = stat['default_weight']
                if weights and feat in weights:
                    w = weights[feat]
                    
                target_val = val
                if feat == 'elevation_m':
                    target_val = max(-415.0, min(7705.0, val))
                    
                features_used[feat] = {
                    'raw_value': val,
                    'used_value': target_val,
                    'weight': w,
                    'earth_std': std
                }
                diff_terms.append(f"{w} * power(({col_expr} - {target_val}) / {std}, 2)")
                
        if not diff_terms:
            raise ValueError(f"No valid features found for target location ({lat}, {lon}) on {body}.")
            
        dist_expr = "sqrt(" + " + ".join(diff_terms) + ")"
        pool_size = top_k * 15 if min_distance_deg > 0 else top_k
        
        if self.backend == "neon":
            conn = self._get_pg_conn()
            query = f"""
            SELECT 
                lat, lon,
                elevation_m,
                slope_deg,
                roughness_m,
                albedo,
                (surf_temp_day_c + 273.15) as temperature_day_k,
                (surf_temp_night_c + 273.15) as temperature_night_k,
                atm_dust_opacity,
                {dist_expr} as distance,
                ROUND((100.0 / (1.0 + {dist_expr}))::numeric, 2) as similarity_score
            FROM earth
            ORDER BY distance ASC
            LIMIT {pool_size};
            """
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(query)
                candidates = pd.DataFrame([dict(r) for r in cur.fetchall()])
        else:
            import duckdb
            con = duckdb.connect()
            query = f"""
            SELECT 
                lat, lon,
                "1_Topography (SRTM)__Elev_m" as elevation_m,
                "1_Topography (SRTM)__Slope_deg" as slope_deg,
                "1_Topography (SRTM)__Roughness_m" as roughness_m,
                "2_Spectral_Albedo (MOD09)__Broadband_Albedo" as albedo,
                ("3_Thermal_Emissivity (MOD11)__Surf_Temp_Day_C" + 273.15) as temperature_day_K,
                ("3_Thermal_Emissivity (MOD11)__Surf_Temp_Night_C" + 273.15) as temperature_night_K,
                "5_Atmosphere (MERRA-2)__atm_dust_opacity" as atm_dust_opacity,
                {dist_expr} as distance,
                round(100.0 / (1.0 + {dist_expr}), 2) as similarity_score
            FROM 'earth.csv'
            ORDER BY distance ASC
            LIMIT {pool_size}
            """
            candidates = con.execute(query).df()
            
        # Spatial deduplication
        selected_rows = []
        for _, row in candidates.iterrows():
            too_close = False
            for s in selected_rows:
                deg_dist = math.sqrt((row['lat'] - s['lat'])**2 + (row['lon'] - s['lon'])**2)
                if deg_dist < min_distance_deg:
                    too_close = True
                    break
            if not too_close:
                selected_rows.append(row)
            if len(selected_rows) == top_k:
                break
                
        results_df = pd.DataFrame(selected_rows)
        results_df['region'] = [identify_earth_region(r['lat'], r['lon']) for _, r in results_df.iterrows()]
        
        coord_dist = round(float(target_row.get('coord_dist_deg', 0.0)), 4)
        
        return {
            'body': body.capitalize(),
            'database': "Neon PostgreSQL (Deployed)",
            'target_input': {'lat': lat, 'lon': lon},
            'target_matched_point': {
                'lat': target_row['lat'],
                'lon': target_row['lon'],
                'distance_to_input_deg': coord_dist
            },
            'features_used': features_used,
            'analogs': results_df
        }

    def find_analogs_by_name(self, body, site_name, top_k=5):
        """Finds analogs by a predefined landmark site name."""
        body = body.lower()
        sites = FAMOUS_SITES.get(body, {})
        matched_coords = None
        for name, coords in sites.items():
            if site_name.lower() in name.lower():
                matched_coords = coords
                matched_name = name
                break
        if not matched_coords:
            available = ", ".join(sites.keys())
            raise ValueError(f"Site '{site_name}' not recognized for {body}. Known sites: {available}")
        
        res = self.find_analogs(body, matched_coords[0], matched_coords[1], top_k=top_k)
        res['site_name'] = matched_name
        return res
