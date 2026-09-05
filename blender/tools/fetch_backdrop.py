"""Crop public Copernicus elevation tiles for the Everest skyline."""
from pathlib import Path
import json
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform

root = Path(__file__).resolve().parents[1]
dest = root / "assets" / "terrain"
dest.mkdir(parents=True, exist_ok=True)
points = []
for lat, south, north in [(27, 27.94, 28.0), (28, 28.0, 28.13)]:
    tile = f"Copernicus_DSM_COG_10_N{lat}_00_E086_00_DEM"
    url = f"https://copernicus-dem-30m.s3.amazonaws.com/{tile}/{tile}.tif"
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
        with rasterio.open(url) as ds:
            win = from_bounds(86.79, south, 86.999, north, ds.transform).round_offsets().round_lengths()
            data = ds.read(1, window=win)
            aff = ds.window_transform(win)
            rows, cols = np.indices(data.shape)
            lon = aff.c + (cols + .5) * aff.a
            la = aff.f + (rows + .5) * aff.e
            points.append((data,lon,la))
    print('Read', tile, data.shape, flush=True)

data = np.concatenate([p[0] for p in points[::-1]],axis=0)
lon = np.concatenate([p[1] for p in points[::-1]],axis=0)
lat = np.concatenate([p[2] for p in points[::-1]],axis=0)
ex, ny = transform('EPSG:4326','EPSG:32645',lon.ravel(),lat.ravel())
np.savez_compressed(dest / 'everest_backdrop.npz', elevation=data, easting=np.array(ex).reshape(data.shape), northing=np.array(ny).reshape(data.shape), longitude=lon, latitude=lat)
for la,lo in [(28.045,86.945),(28.055,86.94),(28.06,86.945),(28.04,86.93),(27.9881,86.925)]:
    idx=np.unravel_index(np.argmin((lat-la)**2+(lon-lo)**2),lat.shape)
    print('Location',la,lo,'elevation',float(data[idx]),'UTM',float(np.array(ex).reshape(data.shape)[idx]),float(np.array(ny).reshape(data.shape)[idx]))
(dest/'source.json').write_text(json.dumps({'source':'https://registry.opendata.aws/copernicus-dem/','product':'Copernicus GLO-30 public, 2021 release','role':'measured distant mountain backdrop','grid_spacing_m':30,'extent':[86.79,27.94,86.999,28.13]},indent=2))
