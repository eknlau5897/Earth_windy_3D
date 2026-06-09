import argparse
import json
import os
import sys
import numpy as np
from PIL import Image
from herbie import Herbie

LEVELS = ["10m", "850", "700", "500", "200"]

def parse_args():
    parser = argparse.ArgumentParser(description="Download multi-level global wind fields")
    parser.add_argument("--date", type=str, required=True, help="Date format YYYY-MM-DD HH:MM")
    parser.add_argument("--output-dir", type=str, default="./data", help="Output destination folder")
    return parser.parse_args()

def get_search_string(model, level):
    """Generates the appropriate GRIB search regex depending on the model profile."""
    if model == "gfs":
        if level == "10m":
            return ":[U|V]GRD:10 m"
        return f":[U|V]GRD:{level} mb"
    else: # ecmwf profiles (ifs, aifs)
        if level == "10m":
            return ":(u|v):10m"
        return f":(u|v):{level}"

def extract_layer(model_name, dt_str, level, output_dir):
    print(f" -> Fetching {model_name.upper()} at level: {level}")
    
    herbie_model = "gfs" if model_name == "gfs" else model_name
    product = "0p25" if model_name == "gfs" else "oper"
    search = get_search_string(model_name, level)
    
    try:
        H = Herbie(dt_str, model=herbie_model, product=product, fxx=0, priority=["aws", "azure", "ecmwf"])
        ds = H.xarray(search)
        
        # Identity match on data variables
        u_key = [k for k in ds.data_vars if k.lower() in ['u10', 'u', 'u_grd']][0]
        v_key = [k for k in ds.data_vars if k.lower() in ['v10', 'v', 'v_grd']][0]
        
        u_raw = ds[u_key].values
        v_raw = ds[v_key].values
        
        # Handle coordinate system variations
        lons = ds['longitude'].values
        lats = ds['latitude'].values
        
        if np.max(lons) > 180:
            lons = np.where(lons > 180, lons - 360, lons)
            idx = np.argsort(lons)
            lons = lons[idx]
            u_raw = u_raw[:, idx] if u_raw.ndim == 2 else u_raw[0, :, idx]
            v_raw = v_raw[:, idx] if v_raw.ndim == 2 else v_raw[0, :, idx]

        if lats[0] < lats[-1]:
            lats = lats[::-1]
            u_raw = u_raw[::-1, :]
            v_raw = v_raw[::-1, :]
            
        # Strip dimensional metadata variations if multi-layered structures bleed into xarray
        if u_raw.ndim > 2: u_raw = u_raw.squeeze()
        if v_raw.ndim > 2: v_raw = v_raw.squeeze()

        # Matrix Normalization
        u_min, u_max = float(np.min(u_raw)), float(np.max(u_raw))
        v_min, v_max = float(np.min(v_raw)), float(np.max(v_raw))
        
        u_norm = (u_raw - u_min) / (u_max - u_min) * 255.0 if u_max != u_min else np.zeros_like(u_raw)
        v_norm = (v_raw - v_min) / (v_max - v_min) * 255.0 if v_max != v_min else np.zeros_like(v_raw)
        
        h, w = u_raw.shape
        rgb_buffer = np.zeros((h, w, 3), dtype=np.uint8)
        rgb_buffer[..., 0] = u_norm.astype(np.uint8)
        rgb_buffer[..., 1] = v_norm.astype(np.uint8)
        
        # Format names cleanly: e.g., gfs_850_wind.png
        file_prefix = f"{model_name}_{level}_wind"
        Image.fromarray(rgb_buffer).save(os.path.join(output_dir, f"{file_prefix}.png"))
        
        metadata = {
            "model": model_name, "level": level, "refTime": dt_str, "width": w, "height": h,
            "bounds": [float(np.min(lons)), float(np.min(lats)), float(np.max(lons)), float(np.max(lats))],
            "uMin": u_min, "uMax": u_max, "vMin": v_min, "vMax": v_max
        }
        
        with open(os.path.join(output_dir, f"{file_prefix}.json"), "w") as f:
            json.dump(metadata, f, indent=4)
            
    except Exception as e:
        print(f"   [ERROR] Skipping {model_name} @ {level}: {str(e)}", file=sys.stderr)

if __name__ == "__main__":
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    
    for model in ["gfs", "ifs", "aifs"]:
        print(f"\nProcessing Group: {model.upper()}")
        for lvl in LEVELS:
            extract_layer(model, args.date, lvl, args.output_dir)
