#!/bin/bash
set -e

INTERVAL=$((6 * 60 * 60)) 
DATA_DIR="./data"

echo "=========================================================="
echo " Starting Streaming, Caffeinated Weather Daemon (wind.sh)"
echo "=========================================================="

while true; do
    echo "--- Cycle Started: $(date) ---"
    TARGET_RUN=$(date -u +"%Y-%m-%d 00:00")
    
    # Execute Python streaming data pipeline via Caffeinate assertion lock
    echo "Streaming slices directly to memory (Preventing system sleep)..."
    caffeinate -i python3.11 wind.py --date "$TARGET_RUN" --output-dir "$DATA_DIR"
    echo "Matrix translation loop finished successfully."
    
    # Safe environmental workspace cleanup
    echo "Cleaning residual index maps..."
    find . -type f \( -name "*.idx" -o -name "*.tmp" -o -name "*.log" \) -delete 2>/dev/null || true
    echo "Local workspace clean."
    
    # Single Unified Git Transaction
    echo "Staging compressed outputs..."
    git add "$DATA_DIR"/*_*_*h_wind.png "$DATA_DIR"/*_*_*h_wind.json
    
    if ! git diff-index --quiet HEAD --; then
        echo "Bundling timeline into a single commit transaction..."
        git commit -m "Update weather matrices: GFS/IFS/AIFS 0-240h Stream ($TARGET_RUN)"
        git push origin main
        echo "Deployment push complete."
    else
        echo "No data changes found. Skipping Git push."
    fi
    
    echo "Sleeping for 6 hours..."
    sleep $INTERVAL
done