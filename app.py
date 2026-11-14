"""
FastAPI Application for Planetary Analog Similarity Matching
Endpoints to find Earth analogs for Mars and Moon locations.
Supports coordinate inputs from frontend (including any decimals) and retrieves
the nearest spatial location directly from the planetary database.
"""

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, root_validator
from typing import List, Optional, Dict, Any, Union
import math

from planetary_analog_model import PlanetaryAnalogModel, FAMOUS_SITES

app = FastAPI(
    title="Planetary Analog API",
    description="Find the most similar Earth environmental, topographic, and thermal analog locations for any coordinate on Mars or the Moon.",
    version="1.1.0"
)

# Enable CORS for frontend applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the model instance using the deployed Neon PostgreSQL database
model = PlanetaryAnalogModel()


# --- Pydantic Request & Response Schemas ---

class AnalogRequest(BaseModel):
    # Support both 'planet' and common typos like 'plants'
    planet: Optional[str] = Field(None, description="Target body: 'mars' or 'moon'", examples=["mars"])
    plants: Optional[str] = Field(None, description="Alternative alias for planet", examples=["mars"])
    
    # Support top-level latitude/longitude or lat/lon
    latitude: Optional[float] = Field(None, description="Latitude on target body (-90 to 90)", examples=[18.38])
    longitude: Optional[float] = Field(None, description="Longitude on target body (-180 to 180)", examples=[77.58])
    lat: Optional[float] = Field(None, description="Short alias for latitude", examples=[18.38])
    lon: Optional[float] = Field(None, description="Short alias for longitude", examples=[77.58])
    
    # Support nested location object e.g. {"latitude": 18.38, "longitude": 77.58} or [18.38, 77.58]
    location: Optional[Union[Dict[str, Any], List[float]]] = Field(
        None, 
        description="Location object or [lat, lon] list from frontend",
        examples=[{"lat": 18.38, "lon": 77.58}]
    )
    
    top_k: Optional[int] = Field(5, ge=1, le=50, description="Number of top Earth analogs to return (default: 5)", examples=[5])

    @root_validator(pre=True)
    def parse_and_validate_frontend_input(cls, values):
        # 1. Resolve planet / plants
        planet_val = values.get("planet") or values.get("plants")
        if not planet_val:
            raise ValueError("Target planet is required ('mars' or 'moon').")
        body = str(planet_val).strip().lower()
        if body not in ("mars", "moon"):
            raise ValueError(f"Invalid planet '{planet_val}'. Supported values are 'mars' and 'moon'.")
        values["planet"] = body
        
        # 2. Resolve latitude and longitude from various frontend patterns
        lat_val = values.get("latitude") if values.get("latitude") is not None else values.get("lat")
        lon_val = values.get("longitude") if values.get("longitude") is not None else values.get("lon")
        
        loc = values.get("location")
        if loc is not None:
            if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                lat_val = loc[0]
                lon_val = loc[1]
            elif isinstance(loc, dict):
                lat_val = loc.get("latitude") if loc.get("latitude") is not None else loc.get("lat", lat_val)
                lon_val = loc.get("longitude") if loc.get("longitude") is not None else loc.get("lon", lon_val)

        if lat_val is None or lon_val is None:
            raise ValueError("Both latitude and longitude must be provided.")
            
        try:
            raw_lat = float(lat_val)
            raw_lon = float(lon_val)
        except (ValueError, TypeError):
            raise ValueError(f"Latitude ({lat_val}) and Longitude ({lon_val}) must be valid numeric values.")

        values["latitude"] = raw_lat
        values["longitude"] = raw_lon
        return values


class EarthAnalogItem(BaseModel):
    rank: int
    similarity_score_pct: float
    distance_metric: float
    region: str
    latitude: float
    longitude: float
    google_maps_url: str
    elevation_m: float
    slope_deg: float
    roughness_m: float
    albedo: float
    temperature_day_K: float
    temperature_night_K: float
    temperature_day_C: float
    temperature_night_C: float
    atm_dust_opacity: Optional[float] = None

class TargetLocationInfo(BaseModel):
    planet: str
    database_backend: str
    input_coordinates: Dict[str, float]
    matched_database_coordinates: Dict[str, float]
    distance_to_matched_point_deg: float
    nearest_valid_coordinates: Dict[str, float]  # Kept for frontend backwards compatibility
    search_method: str = "database_nearest_spatial_neighbor"
    note: str
    features: Dict[str, Any]

class AnalogResponse(BaseModel):
    success: bool
    target: TargetLocationInfo
    analogs_count: int
    top_analogs: List[EarthAnalogItem]


# --- Helper to format output ---

def format_analogs_response(raw_result: Dict[str, Any], top_k: int) -> AnalogResponse:
    target_in = raw_result['target_input']
    target_pt = raw_result['target_matched_point']
    features_info = raw_result['features_used']
    analogs_df = raw_result['analogs']
    
    in_lat = float(target_in['lat'])
    in_lon = float(target_in['lon'])
    matched_lat = float(target_pt['lat'])
    matched_lon = float(target_pt['lon'])
    dist_deg = round(float(target_pt.get('distance_to_input_deg', 0.0)), 4)
    
    if dist_deg > 0:
        note = f"Queried database for nearest spatial location to ({in_lat}, {in_lon}); matched ({matched_lat}, {matched_lon}) at distance {dist_deg}°."
    else:
        note = f"Input coordinates match exact database point ({matched_lat}, {matched_lon})."
    
    # Clean features summary for JSON response
    features_dict = {}
    for feat_name, feat_meta in features_info.items():
        val = feat_meta['raw_value']
        features_dict[feat_name] = None if math.isnan(val) else round(val, 4)
        
    analog_items = []
    for rank, (_, row) in enumerate(analogs_df.head(top_k).iterrows(), 1):
        dust_val = None
        if 'atm_dust_opacity' in row and not math.isnan(row['atm_dust_opacity']):
            dust_val = round(float(row['atm_dust_opacity']), 4)
            
        t_day_raw = row['temperature_day_k'] if 'temperature_day_k' in row else row.get('temperature_day_K', 273.15)
        t_night_raw = row['temperature_night_k'] if 'temperature_night_k' in row else row.get('temperature_night_K', 273.15)
        t_day_k = round(float(t_day_raw), 2)
        t_night_k = round(float(t_night_raw), 2)
        
        analog_items.append(EarthAnalogItem(
            rank=rank,
            similarity_score_pct=round(float(row['similarity_score']), 2),
            distance_metric=round(float(row['distance']), 4),
            region=str(row['region']),
            latitude=round(float(row['lat']), 4),
            longitude=round(float(row['lon']), 4),
            google_maps_url=f"https://www.google.com/maps?q={row['lat']},{row['lon']}",
            elevation_m=round(float(row['elevation_m']), 1),
            slope_deg=round(float(row['slope_deg']), 2),
            roughness_m=round(float(row['roughness_m']), 2),
            albedo=round(float(row['albedo']), 4),
            temperature_day_K=t_day_k,
            temperature_night_K=t_night_k,
            temperature_day_C=round(t_day_k - 273.15, 2),
            temperature_night_C=round(t_night_k - 273.15, 2),
            atm_dust_opacity=dust_val
        ))
        
    return AnalogResponse(
        success=True,
        target=TargetLocationInfo(
            planet=raw_result['body'],
            database_backend=raw_result.get('database', 'Neon PostgreSQL (Deployed)'),
            input_coordinates={'latitude': in_lat, 'longitude': in_lon},
            matched_database_coordinates={'latitude': matched_lat, 'longitude': matched_lon},
            distance_to_matched_point_deg=dist_deg,
            nearest_valid_coordinates={'latitude': matched_lat, 'longitude': matched_lon},
            search_method="database_nearest_spatial_neighbor",
            note=note,
            features=features_dict
        ),
        analogs_count=len(analog_items),
        top_analogs=analog_items
    )


# --- Endpoints ---

@app.get("/", tags=["Info"])
def root():
    return {
        "service": "Planetary Analog Matching API",
        "version": "2.0.0",
        "database": "Neon PostgreSQL (Deployed)",
        "neon_organization": "org-billowing-lab-59129646",
        "neon_project": "naso (snowy-feather-09084620)",
        "deployed_tables": {
            "moon": "65,160 rows",
            "mars": "64,800 rows",
            "earth": "268,252 rows (0.25° grid, high-speed matching)",
            "earth_backup": "6,381,087 rows (original 0.05° grid preserved)"
        },
        "documentation": "/docs",
        "description": "Send coordinates on Mars or Moon to get the top 5 most similar analog areas on Earth.",
        "location_matching": "Coordinates from frontend are matched to the nearest spatial neighbor directly in the database (no Python round applied).",
        "endpoints": {
            "POST /api/analogs": "Find top Earth analogs using JSON body (supports {latitude, longitude}, {lat, lon}, {location: ...}, and any decimal inputs)",
            "GET /api/analogs": "Find top Earth analogs using query parameters",
            "GET /api/landmarks": "List famous Mars & Moon landmark sites",
            "GET /api/landmarks/{planet}/{landmark_name}": "Find Earth analogs for a landmark site"
        }
    }


@app.post("/api/analogs", response_model=AnalogResponse, tags=["Analogs"])
def find_analogs_post(request: AnalogRequest):
    """
    Find top Earth analog locations for a given coordinate on Mars or the Moon.
    
    - **planet** (or **plants**): 'mars' or 'moon'
    - **latitude** (or **lat**): Latitude (-90 to +90, supports decimal numbers)
    - **longitude** (or **lon**): Longitude (-180 to +180, supports decimal numbers)
    - **location**: Alternative nested object `{"lat": 18.38, "lon": 77.58}` or `[18.38, 77.58]`
    - **top_k**: Number of analogs (default: 5)
    
    *Nearest Spatial Matching*: Coordinates from frontend are matched directly against the nearest database records via spatial minimum distance.
    """
    body = request.planet
    try:
        raw_res = model.find_analogs(
            body=body,
            lat=request.latitude,
            lon=request.longitude,
            top_k=request.top_k
        )
        return format_analogs_response(raw_res, top_k=request.top_k)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/api/analogs", response_model=AnalogResponse, tags=["Analogs"])
def find_analogs_get(
    planet: str = Query(..., description="Target planet: 'mars' or 'moon'"),
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude on target body (-90 to 90, supports decimals)"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude on target body (-180 to 180, supports decimals)"),
    top_k: int = Query(5, ge=1, le=50, description="Number of top Earth analogs to return (default: 5)")
):
    """
    GET variant to test analog searches in a web browser or curl.
    Coordinates are matched directly against the nearest database spatial record.
    """
    return find_analogs_post(AnalogRequest(planet=planet, latitude=latitude, longitude=longitude, top_k=top_k))


@app.get("/api/landmarks", tags=["Landmarks"])
def list_landmarks():
    """
    List known landmark sites on Mars and the Moon with their coordinates.
    """
    formatted = {}
    for body, sites in FAMOUS_SITES.items():
        formatted[body] = [
            {"name": name, "latitude": coords[0], "longitude": coords[1]}
            for name, coords in sites.items()
        ]
    return formatted


@app.get("/api/landmarks/{planet}/{landmark_name}", response_model=AnalogResponse, tags=["Landmarks"])
def find_analogs_by_landmark(
    planet: str,
    landmark_name: str,
    top_k: int = Query(5, ge=1, le=50, description="Number of top Earth analogs to return")
):
    """
    Find Earth analogs for a landmark site by name (e.g. 'jezero', 'olympus', 'apollo 11').
    """
    body = planet.strip().lower()
    if body not in ("mars", "moon"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid planet '{planet}'. Supported planets are 'mars' and 'moon'."
        )
        
    try:
        raw_res = model.find_analogs_by_name(body=body, site_name=landmark_name, top_k=top_k)
        return format_analogs_response(raw_res, top_k=top_k)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


if __name__ == "__main__":
    import os
    import uvicorn
    
    port_env = os.environ.get("PORT", "8000")
    try:
        port = int(port_env)
    except ValueError:
        port = 8000
        
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting Planetary Analog API on {host}:{port}...")
    uvicorn.run("app:app", host=host, port=port)
