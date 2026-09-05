# Everest north-route data sources

Checked 2026-09-05. Scope: North Base Camp in Tibet, through Advanced Base Camp and North Col, ending at a North Ridge checkpoint near the Camp 2 area. Three segments, three destinations after the start. Camp positions and elevations vary between expeditions; exact route geometry still needs verification.

## Recommended elevation source

- NASA NSIDC High Mountain Asia 8-meter DEM Mosaics Derived from Optical Imagery, Version 1: https://nsidc.org/data/hma_dem8m_mos/versions/1
- Earthdata Search: https://search.earthdata.nasa.gov/search/granules?p=C3249536691-NSIDC_CPRD
- Collection: `C3249536691-NSIDC_CPRD`
- Matching granule: `G3254119188-NSIDC_CPRD`
- Filename: `HMA_DEM8m_MOS_20170716_tile-677.tif`
- Catalog size: approximately 370 MB.
- Catalog footprint encompasses the search rectangle (west, south, east, north): `86.78,27.96,86.99,28.18`.
- Catalog footprint vertices (longitude, latitude): `(86.50654,28.3825)`, `(86.49108,27.48718)`, `(87.50947,27.46912)`, `(87.53548,28.3643)`.
- Direct data URL: https://data.nsidc.earthdatacloud.nasa.gov/nsidc-cumulus-prod-protected/HMA/HMA_DEM8m_MOS/1/2002/01/28/HMA_DEM8m_MOS_20170716_tile-677.tif
- Requires a free NASA Earthdata login. Full DEM not downloaded. The footprint was verified through NASA CMR; valid-pixel coverage and voids along the route remain to be inspected.
- The collection uses source acquisitions from 2002–2016; the filename date is not a claim that the complete landscape was captured on that day.
- Provides elevation, not a photographic surface texture. Eight-meter grid spacing cannot resolve individual footholds.

## Recommended imagery service

- MapTiler Satellite: https://www.maptiler.com/maps/satellite/
- Tiles API: https://docs.maptiler.com/cloud/api/tiles/
- Provider advertises global 2 m/pixel imagery, with finer imagery in selected areas. Exact acquisition date and effective detail for the route have not been sampled.
- Requires a MapTiler account/API key. Use the supported API and applicable plan; offline asset packaging requires the appropriate data rights rather than assuming API access grants redistribution.
- Align photographic tiles and terrain in one metric coordinate system before generating mesh UVs. Do not equate imagery pixel size with terrain elevation resolution.

## Existing visual reference

- RealityMaps Mount Everest 3D: https://mount-everest3d.com/
- Provides an existing interactive photorealistic 3D map. Public pages emphasize Nepal/south-side routes; northern route detail and an export license have not been verified.
- Treat as a visual reference or a licensing lead, not as an openly downloadable Blender asset.

## Higher-resolution partial source inspected

- Etienne Berthier, Pléiades DEM of 23 March 2017 — Khumbu region, Nepal: https://zenodo.org/records/6979691
- File: `Khumbu_2017-03-23_DEM_4m.tif`, 91,262,018 bytes; CC BY 4.0 according to record metadata.
- Raster metadata inspected: EPSG:32645, 4 m pixels, 5093 columns × 4478 rows.
- WGS84 bounding rectangle: west `86.7350076659`, south `27.8747316601`, east `86.9423583589`, north `28.0366713647`.
- Does not cover the full North Base Camp approach. Potential supplemental coverage for upper mountain only, pending valid-pixel inspection and vertical alignment.
- Only a partial temporary download was used to inspect its header; no complete usable raster has been saved in the project.
- The associated high-resolution orthoimages are not included in this download and require separate permission.

## Proposed three segments

1. North Base Camp (~5,200 m) → Advanced Base Camp (~6,400–6,500 m): follow the approach through the Rongbuk/East Rongbuk system, retaining the interim camp as a route detail rather than a fourth destination.
2. Advanced Base Camp → North Col (~7,000 m): glacier approach and steep snow/ice climb.
3. North Col → North Ridge checkpoint near Camp 2 (~7,500–7,800 m): exposed ridge ascent; select one explicit endpoint when digitizing the route.

Route references:
- https://www.alanarnette.com/everest/everestnorthroutes.php
- https://alpenglowexpeditions.com/blog/mt-everest-north-side-2024-update-abc-to-summit
- https://www.furtenbachadventures.com/en/trips/mount-everest-north/

## Build approach after source access

Download and crop elevation data; check missing pixels and vertical datum; retrieve permitted satellite imagery; build all three terrain chunks in a shared metric coordinate frame; add checkpoints and a verified route; refine only the immediate robot corridor. Use measured geometry for the landscape and explicitly reconstructed microdetail for snow and rocks below dataset resolution. Render with the same transforms used for collision geometry.
