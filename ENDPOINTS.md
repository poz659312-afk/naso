# Planetary Analog Similarity Matching API - Endpoints Documentation

A FastAPI service that matches any location on **Mars** or the **Moon** to its **Top 5 most similar Earth environmental, topographic, and thermal analog areas** using a deployed **Neon PostgreSQL cloud database**.

---

## Deployed Database Architecture

- **Database**: Neon Serverless PostgreSQL 17
- **Project**: `naso` (`snowy-feather-09084620`)
- **Organization**: `org-billowing-lab-59129646`
- **Region**: AWS US East (N. Virginia) (`aws-us-east-1`)
- **Tables**:
  1. `mars` (64,800 rows) — Complete physical, topographic, thermal, and atmospheric dataset.
  2. `moon` (65,160 rows) — Topographic, thermal, and optical albedo dataset.
  3. `earth` (268,252 rows) — 0.25° spatial resolution Earth observations (~25 km grid, ~0.25s query speed).
  4. `earth_backup` (6,381,087 rows) — Original 0.05° high-density Earth observation archive preserved.

> [!NOTE]
> Connection credentials are automatically read from the [.env](file:///c:/Users/Mohamed%20Alaa/Downloads/naso/.env) file (`DATABASE_URL`). Connection strings and passwords are never printed or committed.

---

## Starting the Server

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

- **Base URL**: `http://127.0.0.1:8000`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **OpenAPI Redoc**: `http://127.0.0.1:8000/redoc`

---

## Endpoints Summary

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | API status, deployed database info, and route directory |
| `POST` | `/api/analogs` | **Main Endpoint**: Pass coordinates & planet to get top Earth analogs from Neon DB |
| `GET` | `/api/analogs` | Query parameter variant (browser & curl friendly) |
| `GET` | `/api/landmarks` | List predefined famous sites on Mars and Moon with coordinates |
| `GET` | `/api/landmarks/{planet}/{landmark_name}` | Look up Earth analogs directly by landmark name |
| `GET` | `/docs` | Interactive Swagger UI |

---

## 1. POST `/api/analogs` (Primary Endpoint)

Queries the deployed Neon database to retrieve the target planet's features, then compares against the 6.38M-row Earth table.

### Decimal & Frontend Flexibility
- **Decimal Coordinates**: Automatically rounded/snapped to the nearest valid integer grid numbers on the target body.
- **Flexible Keys**: Accepts `planet` or `plants`.
- **Flexible Location Formats**: Accepts `latitude`/`longitude`, `lat`/`lon`, or nested `location` objects/arrays.

### Example Request Body
```json
{
  "planet": "mars",
  "latitude": 18.3847,
  "longitude": 77.5819,
  "top_k": 5
}
```

### Response Example (`200 OK`)
```json
{
  "success": true,
  "target": {
    "planet": "Mars",
    "database_backend": "Neon PostgreSQL (Deployed)",
    "input_coordinates": {
      "latitude": 18.3847,
      "longitude": 77.5819
    },
    "nearest_valid_coordinates": {
      "latitude": 18,
      "longitude": 78
    },
    "was_decimal": true,
    "adjustment_note": "Input decimal coordinates (18.3847, 77.5819) were converted to nearest valid planetary grid coordinate (18, 78).",
    "features": {
      "elevation_m": -2341.0,
      "slope_deg": 2.135,
      "roughness_m": 50.857,
      "albedo": 0.183,
      "temperature_day_K": 265.526,
      "temperature_night_K": 192.527,
      "atm_dust_opacity": 0.102
    }
  },
  "analogs_count": 5,
  "top_analogs": [
    {
      "rank": 1,
      "similarity_score_pct": 28.4,
      "distance_metric": 2.521,
      "region": "Siberian Tundra / Verkhoyansk, Russia",
      "latitude": 64.675,
      "longitude": 126.275,
      "google_maps_url": "https://www.google.com/maps?q=64.675,126.275",
      "elevation_m": 183.4,
      "slope_deg": 1.93,
      "roughness_m": 59.31,
      "albedo": 0.172,
      "temperature_day_K": 231.9,
      "temperature_night_K": 231.4,
      "temperature_day_C": -41.25,
      "temperature_night_C": -41.75,
      "atm_dust_opacity": 0.0115
    }
  ]
}
```

---

## 2. GET `/api/analogs` (Query Parameter Variant)

```bash
curl "http://127.0.0.1:8000/api/analogs?planet=moon&latitude=0.67&longitude=23.47&top_k=5"
```

---

## 3. GET `/api/landmarks`

```bash
curl "http://127.0.0.1:8000/api/landmarks"
```

---

## 4. GET `/api/landmarks/{planet}/{landmark_name}`

```bash
curl "http://127.0.0.1:8000/api/landmarks/mars/olympus?top_k=3"
```

---

## 5. GET `/` (Health & Architecture Info)

```json
{
  "service": "Planetary Analog Matching API",
  "version": "2.0.0",
  "database": "Neon PostgreSQL (Deployed)",
  "neon_organization": "org-billowing-lab-59129646",
  "neon_project": "naso (snowy-feather-09084620)",
  "deployed_tables": {
    "moon": "65,160 rows",
    "mars": "64,800 rows",
    "earth": "6,381,087 rows"
  }
}
```
