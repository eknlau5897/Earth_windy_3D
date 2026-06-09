import argparse
import json
import os
import sys
import numpy as np
from PIL import Image

# Force Herbie to use an isolated system tmp directory before loading the module
os.environ["HERBIE_SAVE_DIR"] = "/tmp/herbie"
from herbie import Herbie

LEVELS = ["10m", "850", "700", "500", "200"]

def parse_args():
    parser = argparse.ArgumentParser(description="Stream global wind fields via xarray")
    parser.add_argument("--date", type=str, required=True, help="Date format YYYY-MM-DD HH:MM")
    parser.add_argument("--output-dir", type=str, default="./data", help="Output destination folder")
    return parser.parse_args()

def generate_forecast_hours():
    return list(range(0, 121, 6)) + list(range(132, 241, 12))

def get_search_string(model, level):
    if model == "gfs":
        return ":[U|V]GRD:10 m" if level == "10m" else f":[U|V]GRD:{level} mb"
    else:  
        return ":(u|v):10m" if level == "10m" else f":(u|v):{level}"

def extract_forecast_step(model_name, dt_str, level, fxx, output_dir):
    print(f" -> Streaming {model_name.upper()} | Level: {level} | Forecast: +{fxx}h")
    
    herbie_model = "gfs" if model_name == "gfs" else model_name
    product = "0p25" if model_name == "gfs" else "oper"
    search = get_search_string(model_name, level)
    
    file_prefix = f"{model_name}_{level}_{fxx}h_wind"
    png_path = os.path.join(output_dir, f"{file_prefix}.png")
    json_path = os.path.join(output_dir, f"{file_prefix}.json")

    if os.path.exists(png_path) and os.path.exists(json_path):
        return

    try:
        H = Herbie(dt_str, model=herbie_model, product=product, fxx=fxx, priority=["aws", "azure", "ecmwf"])
        ds = H.xarray(search)
        
        u_key = [k for k in ds.data_vars if k.lower() in ['u10', 'u', 'u_grd']][0]
        v_key = [k for k in ds.data_vars if k.lower() in ['v10', 'v', 'v_grd']][0]
        
        u_raw = ds[u_key].values
        v_raw = ds[v_key].values
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
            
        if u_raw.ndim > 2: u_raw = u_raw.squeeze()
        if v_raw.ndim > 2: v_raw = v_raw.squeeze()

        u_min, u_max = float(np.min(u_raw)), float(np.max(u_raw))
        v_min, v_max = float(np.min(v_raw)), float(np.max(v_raw))
        
        u_norm = (u_raw - u_min) / (u_max - u_min) * 255.0 if u_max != u_min else np.zeros_like(u_raw)
        v_norm = (v_raw - v_min) / (v_max - v_min) * 255.0 if v_max != v_min else np.zeros_like(v_raw)
        
        h, w = u_raw.shape
        rgb_buffer = np.zeros((h, w, 3), dtype=np.uint8)
        rgb_buffer[..., 0] = u_norm.astype(np.uint8)
        rgb_buffer[..., 1] = v_norm.astype(np.uint8)
        
        Image.fromarray(rgb_buffer).save(png_path)
        
        metadata = {
            "model": model_name, "level": level, "forecastHour": fxx, "refTime": dt_str, "width": w, "height": h,
            "bounds": [float(np.min(lons)), float(np.min(lats)), float(np.max(lons)), float(np.max(lats))],
            "uMin": u_min, "uMax": u_max, "vMin": v_min, "vMax": v_max
        }
        
        with open(json_path, "w") as f:
            json.dump(metadata, f, indent=4)
            
        ds.close()
            
    except Exception as e:
        print(f"   [ERROR] Skipping {model_name} @ {level} fxx={fxx}: {str(e)}", file=sys.stderr)

if __name__ == "__main__":
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    
    forecast_hours = generate_forecast_hours()
    
    for model in ["gfs", "ifs", "aifs"]:
        for lvl in LEVELS:
            for fxx in forecast_hours:
                extract_forecast_step(model, args.date, lvl, fxx, args.output_dir)