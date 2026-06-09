#!/bin/bash
set -e

INTERVAL=$((6 * 60 * 60)) 
DATA_DIR="./data"
HERBIE_CACHE_DIR="$HOME/src/herbie_data" # Default Herbie cache path

echo "=========================================================="
echo " Launching Unified Mass-Layer Self-Cleaning Ingestion Loop"
echo "=========================================================="

while true; do
    echo "--- Cycle Started: $(date) ---"
    TARGET_RUN=$(date -u +"%Y-%m-%d 00:00")
    
    # 1. Run the extraction pipeline
    caffeinate -i python3 src/process_wind.py --date "$TARGET_RUN" --output-dir "$DATA_DIR"
    
    # 2. Storage Cleanup Phase
    echo "Initiating history and raw file cache purge..."
    
    # Delete Herbie's raw downloaded GRIB2 files to save disk space
    if [ -d "$HERBIE_CACHE_DIR" ]; then
        rm -rf "$HERBIE_CACHE_DIR"/*
        echo "Successfully cleared raw Herbie data cache directory."
    else
        echo "Herbie default cache directory not found or empty. Skipping."
    fi

    # Clean up any temporary lockfiles or partial download remnants (.idx, .grib2)
    find . -type f \( -name "*.grib2" -o -name "*.idx" -o -name "*.tmp" \) -delete
    echo "Local temp files and GRIB indexes evacuated."
    
    # 3. Git Staging & Deployment
    echo "Staging clean matrix output arrays..."
    git add "$DATA_DIR"/*_*_*h_wind.png "$DATA_DIR"/*_*_*h_wind.json
    
    if ! git diff-index --quiet HEAD --; then
        echo "Changes detected. Pushing compressed timeline payload..."
        git commit -m "Update timeline maps: 3 Models, 5 Layers, 0-240h Forecast ($TARGET_RUN)"
        git push origin main
        echo "Synchronization push completed successfully."
    else
        echo "No matrix updates required."
    fi
    
    echo "Next run scheduled in 6 hours..."
    sleep $INTERVAL
done