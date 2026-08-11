# Fuel Route Optimizer API

A high-performance Django API for planning a cost-effective road trip between two USA locations and recommending fuel stops while respecting a vehicle's maximum driving range.

Built for the Spotter coding assessment.

## Assessment Requirements

- USA start and finish locations
- Driving route and GeoJSON map output
- Cost-effective fuel-stop recommendations
- Maximum vehicle range of 500 miles
- 10 MPG fuel-consumption assumption
- Total fuel gallons and total fuel cost
- Supplied fuel-price CSV
- Free geocoding/routing services
- Minimal external routing API calls
- Fast repeated requests through caching
- Django implementation
- Automated tests
- Postman-ready API

## Verified Example

Request:

```json
{
  "start_location": "Chicago, IL",
  "finish_location": "Dallas, TX"
}
```

Verified result:

```text
Route distance:             966.9 miles
Fuel consumption:            96.69 gallons
Total fuel cost:             $292.23
Fuel stops:                  10
Effective vehicle range:     500 miles
Preferred route corridor:      5 miles
Route corridor used:           5 miles
```

Repeated requests can be served from cache:

```text
geocoding_api_calls: 0
routing_api_calls:   0

cache_hits:
  start:  true
  finish: true
  route:  true
```

## Architecture

```text
Postman
   |
   v
Django REST API
   |
   +---- Nominatim (geocoding)
   |
   +---- OSRM (driving route)
   |
   +---- Django Cache
   |
   +---- Fuel Optimization Engine
              |
              v
       Local FuelStation DB
```

## Technology Stack

- Python 3.13.14
- Django 6.x
- Django REST Framework
- SQLite for local development
- Nominatim / OpenStreetMap for geocoding
- OSRM for driving directions
- GeoJSON for map output
- Django cache framework
- Python CSV processing
- Django Test Framework

## Project Structure

```text
fuel_route_optimizer/
├── api/
│   ├── management/
│   │   └── commands/
│   │       ├── build_city_centroids.py
│   │       └── import_fuel_data.py
│   ├── migrations/
│   ├── tests/
│   │   └── test_optimizer.py
│   ├── models.py
│   ├── serializers.py
│   ├── services.py
│   ├── urls.py
│   └── views.py
├── config/
│   ├── settings.py
│   └── urls.py
├── data/
│   ├── fuel-prices-for-be-assessment.csv
│   └── city_centroids.csv
├── manage.py
├── requirements.txt
├── README.md
└── .gitignore
```

## Fuel Optimization

The optimizer solves a constrained cost-minimization problem.

### Effective vehicle range

```text
effective_range =
    min(tank_capacity_gallons × MPG, max_range_miles)
```

With the assessment defaults:

```text
50 gallons × 10 MPG = 500 miles
```

Therefore the hard maximum driving range is 500 miles.

### Station selection

Candidates are evaluated using:

- position along the route
- distance from the route
- fuel price
- reachability within the vehicle range

Stations within the preferred 5-mile route corridor are prioritized. A controlled fallback can be used for sparse city-level fuel data, while the 500-mile driving-range constraint remains hard.

### Cost-aware strategy

At each fuel stop:

1. Find reachable future stations.
2. Look for a cheaper reachable station.
3. If one exists, purchase only enough fuel to reach it.
4. Otherwise purchase enough to reach the furthest feasible planning point, subject to tank capacity.
5. Continue until the destination is reachable.
6. Calculate each purchase and total cost.

This avoids simply choosing the cheapest station in the entire route.

## External APIs

### Nominatim

Used to geocode start and finish locations.

USA validation is performed after geocoding, and results are cached.

### OSRM

Used for driving-route calculation.

The application requests one route with:

```text
overview=full
geometries=geojson
steps=false
alternatives=false
```

The route is cached using the start/finish coordinates.

### API-call optimization

Typical behavior:

```text
First request:
2 geocoding calls + 1 routing call

Repeated request:
0 geocoding calls + 0 routing calls
```

No routing request is made for every fuel station.

## Fuel Data

The supplied fuel-price CSV is imported into the local `FuelStation` table.

The import process:

1. Loads city centroid data.
2. Reads and validates the CSV.
3. Validates USA states.
4. Resolves city/state coordinates.
5. Detects existing/duplicate stations.
6. Bulk-inserts new stations.
7. Displays progress during import.

The current local database contains 6,299 fuel-station records.

## Requirements

- Python 3.13.14
- Django 6.x
- pip

### Tested Python Version

This project is developed and tested with:

```text
Python 3.13.14
```

Verify your Python version:

```powershell
python --version
```

Expected:

```text
Python 3.13.14
```

## Installation

### 1. Clone

```bash
git clone https://github.com/Mohamed-Fasidh/fuel-route-optimizer
cd fuel_route_optimizer
```

### 2. Create virtual environment

Python 3.13.14 is recommended and is the version used for development and testing.

#### Windows PowerShell

```powershell
py -3.13 -m venv .venv
```

Activate:

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.venv\Scripts\Activate.ps1
```

#### Windows troubleshooting

If `py -3.13 -m venv .venv` hangs while Python is running `ensurepip`, create the virtual environment without pip and install pip separately:

```powershell
Remove-Item -Recurse -Force .venv -ErrorAction SilentlyContinue

py -3.13 -m venv .venv --without-pip

.venv\Scripts\Activate.ps1

python -m ensurepip --upgrade
python -m pip install --upgrade pip
```

Then install the project dependencies:

```powershell
python -m pip install -r requirements.txt
```

This fallback is only needed when the standard `venv` command hangs during the `ensurepip` step.

#### Bash / Linux / macOS / Git Bash / WSL

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

If `python3.13` is not available, verify:

```bash
python3 --version
```

Then use the installed Python 3.13 executable.

### 3. Install dependencies

Windows:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Bash / Linux / macOS:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Migrate

```bash
python manage.py migrate
```

## Prepare Fuel Data

Generate city centroids:

```bash
python manage.py build_city_centroids
```

Expected:

```text
Wrote 32,131 city centroids to data\city_centroids.csv.
```

Import fuel prices:

```bash
python manage.py import_fuel_data
```

The importer displays progress and uses bulk insertion for new stations.

For an intentional clean rebuild:

```bash
python manage.py import_fuel_data --clear
```

Do not use `--clear` unless you want to rebuild the local station database.

## Tests

Run:

```bash
python manage.py test
```

Verified result:

```text
Found 4 test(s).
System check identified no issues (0 silenced).
....
----------------------------------------------------------------------
Ran 4 tests

OK
```

## Run the API

```bash
python manage.py runserver
```

Server:

```text
http://127.0.0.1:8000/
```

## Bash / Linux / macOS Commands

The project can also be run from Bash, Linux, macOS, Git Bash, or WSL.

### Clone the repository

```bash
git clone https://github.com/Mohamed-Fasidh/fuel-route-optimizer
cd fuel_route_optimizer
```

### Create and activate the virtual environment

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

If `python3.13` is not available:

```bash
python3 --version
```

### Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Run database migrations

```bash
python manage.py migrate
```

### Build city centroids

```bash
python manage.py build_city_centroids
```

### Import fuel data

```bash
python manage.py import_fuel_data
```

For a clean rebuild:

```bash
python manage.py import_fuel_data --clear
```

### Verify imported fuel stations

```bash
python manage.py shell -c "from api.models import FuelStation; print(FuelStation.objects.count())"
```

Expected current local count:

```text
6299
```

### Run automated tests

```bash
python manage.py test
```

Expected:

```text
Found 4 test(s).
....
----------------------------------------------------------------------
Ran 4 tests

OK
```

### Start the Django development server

```bash
python manage.py runserver
```

The API will be available at:

```text
http://127.0.0.1:8000/
```

### Health check

```bash
curl http://127.0.0.1:8000/api/v1/health/
```

### Route-planning API with curl

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/route-plan/" \
  -H "Content-Type: application/json" \
  -d '{
    "start_location": "Chicago, IL",
    "finish_location": "Dallas, TX"
  }'
```

### Route-planning API with optional vehicle settings

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/route-plan/" \
  -H "Content-Type: application/json" \
  -d '{
    "start_location": "Chicago, IL",
    "finish_location": "Dallas, TX",
    "vehicle_mpg": 10,
    "tank_capacity_gallons": 50,
    "max_range_miles": 500
  }'
```

### Pretty-print JSON with `jq`

If `jq` is installed:

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/route-plan/" \
  -H "Content-Type: application/json" \
  -d '{
    "start_location": "Chicago, IL",
    "finish_location": "Dallas, TX"
  }' | jq
```

### Check API summary and performance

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/route-plan/" \
  -H "Content-Type: application/json" \
  -d '{
    "start_location": "Chicago, IL",
    "finish_location": "Dallas, TX"
  }' | jq '.summary, .performance'
```

### Check fuel stops

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/route-plan/" \
  -H "Content-Type: application/json" \
  -d '{
    "start_location": "Chicago, IL",
    "finish_location": "Dallas, TX"
  }' | jq '.fuel_stops'
```

### Useful development commands

Check Django configuration:

```bash
python manage.py check
```

Open the Django shell:

```bash
python manage.py shell
```

Show migrations:

```bash
python manage.py showmigrations
```

Create migrations after model changes:

```bash
python manage.py makemigrations
```

Apply migrations:

```bash
python manage.py migrate
```

### Git commands

Check repository status:

```bash
git status
```

Add changes:

```bash
git add README.md
```

Commit:

```bash
git commit -m "Update README installation instructions"
```

Push:

```bash
git push
```

## API Endpoints

### Health

```http
GET /api/v1/health/
```

Example:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/
```

Expected:

```json
{
  "status": "ok"
}
```

### Route Planning

```http
POST /api/v1/route-plan/
```

Request:

```json
{
  "start_location": "Chicago, IL",
  "finish_location": "Dallas, TX"
}
```

Optional vehicle settings:

```json
{
  "start_location": "Chicago, IL",
  "finish_location": "Dallas, TX",
  "vehicle_mpg": 10,
  "tank_capacity_gallons": 50,
  "max_range_miles": 500
}
```

### PowerShell Example

```powershell
$body = @{
    start_location = "Chicago, IL"
    finish_location = "Dallas, TX"
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/api/v1/route-plan/" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body

$response | ConvertTo-Json -Depth 10
```

## Response

The API returns:

```text
request
start
finish
summary
fuel_stops
map
performance
```

Example summary:

```json
{
  "route_miles": 966.9,
  "duration_minutes": 1026.2,
  "total_gallons": 96.69,
  "total_fuel_cost": 292.23,
  "fuel_stops": 10,
  "effective_vehicle_range_miles": 500,
  "preferred_route_corridor_miles": 5.0,
  "route_corridor_used_miles": 5.0
}
```

Each fuel stop includes:

```json
{
  "truckstop_id": 12345,
  "station_name": "Example Station",
  "address": "Example Address",
  "city": "Example City",
  "state": "IL",
  "fuel_price_per_gallon": 3.044,
  "purchase_gallons": 7.259,
  "fuel_cost": 22.10,
  "route_position_miles": 380.2,
  "distance_from_route_miles": 0.40,
  "location": {
    "latitude": 0.0,
    "longitude": 0.0,
    "source": "city_centroid"
  }
}
```

The `map` field is a GeoJSON `FeatureCollection` containing:

- the driving route as a `LineString`
- fuel stations as `Point` features

## Performance Design

### Parallel geocoding

Start and finish geocoding are performed concurrently.

### Caching

Geocoding and routing responses are cached.

### Local fuel database

Fuel prices are stored locally, avoiding external fuel-price calls during route requests.

### No station-by-station routing

The optimizer does not call OSRM separately for every fuel candidate.

### Bounded route processing

Route geometry is sampled for local candidate positioning, keeping processing bounded.

These design choices directly address the assessment requirement to minimize free routing API usage.

## Location Accuracy Note

The supplied fuel dataset does not provide precise GPS coordinates for every station.

When exact coordinates are unavailable, the project uses a city-centroid lookup generated from official U.S. Census Places Gazetteer data.

The API makes this explicit:

```json
"location": {
  "source": "city_centroid"
}
```

This prevents city-centroid coordinates from being presented as exact station GPS coordinates.

## Route Distance

OSRM's driving distance is authoritative for the route summary.

Geometry-derived distance is used for local route positioning and candidate evaluation.

## Configuration

Important settings include:

```text
OSRM_BASE_URL
NOMINATIM_BASE_URL
NOMINATIM_USER_AGENT
MAX_STATION_DISTANCE_MILES
GEOCODE_CACHE_SECONDS
ROUTE_CACHE_SECONDS
FUEL_MPG
FUEL_RANGE_MILES
FUEL_TANK_GALLONS
REDIS_URL
```

For the assessment defaults:

```text
FUEL_MPG=10
FUEL_RANGE_MILES=500
FUEL_TANK_GALLONS=50
MAX_STATION_DISTANCE_MILES=5
```

`REDIS_URL` is optional. When Redis is not configured, the project can use Django's local-memory cache for local development.

## Error Handling

The API validates:

- missing locations
- invalid request payloads
- non-USA locations
- invalid MPG
- invalid tank capacity
- invalid maximum range
- missing fuel data
- missing routes
- infeasible fuel plans

## Engineering Principles

- Separation of API and business logic
- Deterministic fuel optimization
- Local fuel-price processing
- External API caching
- Minimal routing API calls
- Explicit validation
- Defensive feasibility checks
- Testable service functions
- Efficient bulk data import
- Transparent location-source metadata
- Clean API response structure

## Future Improvements

For production deployment:

- PostgreSQL/PostGIS
- Exact station GPS coordinates
- Spatial indexes
- Redis distributed caching
- Background fuel-data refresh
- Authentication and rate limiting
- OpenAPI/Swagger documentation
- Additional integration/property-based tests
- Frontend map visualization

These are outside the core assessment scope.

## License

Created as a coding assessment project for Spotter.
