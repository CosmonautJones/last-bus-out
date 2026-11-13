# Data sources

The hackathon requires a list of every public source. Raw files are downloaded by
`scripts/fetch_data.py` into `data/raw/` (gitignored) and processed by `scripts/build_index.py`.

| Dataset | Publisher | URL | Terms |
|---|---|---|---|
| DDOT GTFS schedule | City of Detroit, Detroit Department of Transportation | https://www.detroitmi.gov/Portals/0/docs/deptoftransportation/pdfs/ddot_gtfs.zip | Listed on data.gov as CC0 / public domain |
| SMART GTFS schedule | Suburban Mobility Authority for Regional Transportation | https://apps1.smartbus.org/gtfs/smart_gtfs.zip | Public developer feed; confirm terms on smartbus.org before any commercial use |
| ACS 5-year, table B25044 (tenure by vehicles available) | U.S. Census Bureau | https://api.census.gov/data/2023/acs/acs5 | U.S. government work, public domain |
| Cartographic boundary file, census tracts (MI) | U.S. Census Bureau | https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_26_tract_500k.zip | Public domain |
| Geocoder | U.S. Census Bureau | https://geocoding.geo.census.gov/geocoder/ | Public service |
| Basemap tiles | Esri, HERE, Garmin, OpenStreetMap contributors | https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer | Esri Master License Agreement; free for non-commercial use with attribution |

Context figures cited in the pitch:
- DDOT performance dashboard (on-time %): https://detroitmi.gov/taxonomy/term/5641
- Transportation Riders United, State of Transit 2025: https://www.detroittransit.org/wp-content/uploads/2025/01/State-of-Transit-Report-2025-WEB.pdf
- DDOT/Lyft late-night jobs pilot: https://michiganchronicle.com/ddot-partners-with-lyft-on-pilot-program-for-improved-late-night-jobs-access/

"Car-free households" = B25044_003E (owner-occupied, no vehicle) + B25044_010E (renter-occupied, no vehicle).
