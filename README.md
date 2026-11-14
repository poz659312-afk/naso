# Planetary Analog Matching API

A high-performance FastAPI service that matches any coordinate on **Mars** or the **Moon** to its **Top 5 most similar Earth environmental, topographic, and thermal analog areas** using a deployed **Neon Serverless PostgreSQL database**.

---

## Architecture Overview

```
Frontend / Client Request
       │
       ▼
 FastAPI Service (app.py)
       │
       ├─► 1. Snaps decimal input to nearest valid planetary coordinate
       │
       ├─► 2. Queries deployed Neon PostgreSQL ('mars' / 'moon' table)
       │      to extract topography, albedo, thermal & dust opacity features
       │
       └─► 3. Evaluates standardized Euclidean distance across 6.38M points
              in the deployed Neon PostgreSQL ('earth' table)
       │
       ▼
 Top 5 Earth Analog Areas (Coordinates, Similarity %, Region & Google Maps Link)
```

- **Database**: Neon Serverless PostgreSQL 17 (`aws-us-east-1`)
- **Tables**:
  - `mars` (64,800 rows)
  - `moon` (65,160 rows)
  - `earth` (268,252 rows - 0.25° grid, ~0.25s matching speed)
  - `earth_backup` (6,381,087 rows - original 0.05° archive preserved)

---

## Getting Started

### 1. Installation

```bash
git clone <your-repo-url>
cd naso
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the example environment file and configure your Neon connection string:

```bash
cp .env.example .env
```

Edit `.env`:
```env
DATABASE_URL=postgresql://neondb_owner:<password>@<host>/neondb?sslmode=require
```

### 3. Run Locally

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

- Interactive Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | API status & deployed database metadata |
| `POST` | `/api/analogs` | **Primary Endpoint**: Pass location & planet to get top Earth analogs |
| `GET` | `/api/analogs` | Query parameter variant (browser & curl friendly) |
| `GET` | `/api/landmarks` | List predefined famous craters on Mars & Moon with coordinates |
| `GET` | `/api/landmarks/{planet}/{landmark_name}` | Look up analogs directly by landmark name |

See [ENDPOINTS.md](ENDPOINTS.md) for full request/response schemas and examples.

---

## Deployment (Render, Railway, Fly.io, etc.)

1. Connect this GitHub repository to your cloud deployment platform (Render, Railway, Heroku, etc.).
2. Set the environment variable `DATABASE_URL` in your platform's dashboard with your Neon connection string.
3. Deploy using Docker or Python runtime (`Procfile` / `Dockerfile` provided).
