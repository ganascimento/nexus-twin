<div align="center">

# 🌍 Nexus Twin — Geo Data

### Real São Paulo road network for map rendering and truck-aware routing.

<br />

[![OpenStreetMap](https://img.shields.io/badge/OpenStreetMap-7EBC6F?style=flat-square&logo=openstreetmap&logoColor=white)](https://www.openstreetmap.org/)
[![Planetiler](https://img.shields.io/badge/Planetiler-FF6B35?style=flat-square&logoColor=white)](https://github.com/onthegomap/planetiler)
[![Valhalla](https://img.shields.io/badge/Valhalla-F05032?style=flat-square&logoColor=white)](https://valhalla.github.io/valhalla/)
[![Martin](https://img.shields.io/badge/Martin-000000?style=flat-square&logoColor=white)](https://github.com/maplibre/martin)
[![PMTiles](https://img.shields.io/badge/PMTiles-1976D2?style=flat-square&logoColor=white)](https://protomaps.com/docs/pmtiles)

</div>

---

## 🧭 What this folder is

This is the **one-time geo data pipeline** for Nexus Twin. All data files are heavy (~4 GB combined) and **not versioned in git** — you generate them once locally.

Three artifacts are needed for the map + routing to work:

| Artifact               | What it is                                                  | Used by    | Size       |
| ---------------------- | ----------------------------------------------------------- | ---------- | ---------- |
| `sudeste-latest.osm.pbf` | OSM extract of southeast Brazil (includes SP)               | Both       | ~800 MB    |
| `sudeste.pmtiles`        | Vector tiles built from the PBF (ruas, rodovias, labels)   | Martin     | ~2–4 GB    |
| `valhalla_tiles/`        | Routing graph optimized for truck costing                  | Valhalla   | ~1–2 GB    |

Everything goes into `geo/data/` — the rest of the stack (Martin, Valhalla) consumes them via volume mounts defined in `../docker-compose.yml`.

> ⚠️ Without this data, the simulation still runs but the map is blank and truck routes fall back to straight lines between origin and destination.

---

## 🛠️ Prerequisites

- **Docker 24+** with ~6 GB of free disk space
- **wget** (or equivalent — curl works too)
- Run every command below from the **project root** (`nexus-twin/`), not from inside `geo/`.

---

## 🚀 Pipeline — 3 steps

### Step 1 — Download the OSM extract

Geofabrik provides ready-made OSM PBF files per region. We use the **Sudeste** extract (covers SP, RJ, MG, ES — ~800 MB).

```bash
wget https://download.geofabrik.de/south-america/brazil/sudeste-latest.osm.pbf \
  -O geo/data/sudeste-latest.osm.pbf
```

> Want a lighter region? Substitute with any Geofabrik extract. Just keep the output filename the same or update the path in `docker-compose.yml`.

---

### Step 2 — Build vector tiles with Planetiler (~30 min)

These are the tiles Martin serves to MapLibre for the base map.

**2a)** Pre-download Planetiler's auxiliary datasets (done first so the build does not pause on slow CDNs):

```bash
mkdir -p geo/data/sources

wget -O geo/data/sources/natural_earth_vector.sqlite.zip \
  https://naciscdn.org/naturalearth/packages/natural_earth_vector.sqlite.zip

wget -O geo/data/sources/water-polygons-split-3857.zip \
  https://osmdata.openstreetmap.de/download/water-polygons-split-3857.zip

wget -O geo/data/sources/lake_centerline.shp.zip \
  https://osmdata.openstreetmap.de/download/lake-centerline.shp.zip
```

**2b)** Run Planetiler — it auto-detects the pre-downloaded files and skips to processing:

```bash
docker run --rm -v $(pwd)/geo/data:/data ghcr.io/onthegomap/planetiler:latest \
  --osm-path=/data/sudeste-latest.osm.pbf \
  --output=/data/sudeste.pmtiles
```

Expect ~30 minutes on a modern laptop. Output: `geo/data/sudeste.pmtiles` (~2–4 GB).

---

### Step 3 — Build the Valhalla routing graph (~20–30 min)

Valhalla builds a **truck-optimized routing graph** from the same PBF. We run the container in build mode, then remove the copied PBF (only the tiles are needed at runtime).

```bash
mkdir -p geo/data/valhalla_tiles

cp geo/data/sudeste-latest.osm.pbf geo/data/valhalla_tiles/

docker run --rm -v $(pwd)/geo/data/valhalla_tiles:/custom_files \
  -e use_tiles_ignore_pbf=False \
  -e build_elevation=False \
  -e build_admins=False \
  ghcr.io/gis-ops/docker-valhalla/valhalla:latest

# Once the build finishes, the PBF is no longer needed — only the generated tiles
rm geo/data/valhalla_tiles/sudeste-latest.osm.pbf
```

Output: `geo/data/valhalla_tiles/` (~1–2 GB of routing tiles).

---

## 📂 What the folder should look like after

```
geo/data/
├── sudeste-latest.osm.pbf    # ~800 MB — from Geofabrik
├── sudeste.pmtiles            # ~2–4 GB — from Planetiler
├── sources/                   # Planetiler auxiliary datasets
│   ├── natural_earth_vector.sqlite.zip
│   ├── water-polygons-split-3857.zip
│   └── lake_centerline.shp.zip
└── valhalla_tiles/            # ~1–2 GB — from Valhalla
    ├── admins.sqlite
    ├── timezones.sqlite
    └── *.gph                  # the routing graph
```

---

## 🔄 Picking up the new data

After the three steps, restart the services that mount `geo/data/`:

```bash
docker compose restart martin valhalla
```

From here, the **Martin** tile server responds at `http://localhost:3001/sudeste/{z}/{x}/{y}` and **Valhalla** accepts routing requests at `http://localhost:8002/route`.

You should see the São Paulo map with real highways on the dashboard at **<http://localhost:5173>** and trucks will move along actual roads (Anhanguera, Bandeirantes, Dutra, Castelo Branco, Ayrton Senna, etc) between factories, warehouses, and stores.

---

## 🧪 Verifying the routing engine

Quick sanity check for Valhalla — route from Campinas to São Paulo:

```bash
curl -s -X POST http://localhost:8002/route \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      {"lat": -22.9099, "lon": -47.0626},
      {"lat": -23.5505, "lon": -46.6333}
    ],
    "costing": "truck"
  }' | jq '.trip.summary'
```

Should return a summary with `length` (km) and `time` (seconds). If you get an empty or error response, check `docker compose logs valhalla`.

---

## 📚 Related docs

- **[`../README.md`](../README.md)** — project overview + quick start
- **[`../backend/README.md`](../backend/README.md)** — simulation engine + agents
- **[`../frontend/README.md`](../frontend/README.md)** — dashboard + map layers
