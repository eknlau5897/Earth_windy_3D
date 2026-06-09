#!/bin/bash
set -e

INTERVAL=$((6 * 60 * 60)) # 6 hours
DATA_DIR="./data"

echo "=========================================================="
echo " Launching Unified Mass-Layer Weather Ingestion Daemon"
echo "=========================================================="

while true; do
    echo "--- Cycle Started: $(date) ---"
    TARGET_RUN=$(date -u +"%Y-%m-%d 00:00")
    
    # Run the loop while preventing macOS from going to sleep
    caffeinate -i python3 src/process_wind.py --date "$TARGET_RUN" --output-dir "$DATA_DIR"
    
    echo "Data pulling finished. Assessing staging tree..."
    
    # Stage ALL newly compiled png and json variations at once
    git add "$DATA_DIR"/*_wind.png "$DATA_DIR"/*_wind.json
    
    # Check if there are differences to commit
    if ! git diff-index --quiet HEAD --; then
        echo "Modifications discovered. Bundling into a single runtime commit..."
        git commit -m "Update weather matrices: GFS/IFS/AIFS full layers ($TARGET_RUN)"
        
        echo "Pushing changes to GitHub repository..."
        git push origin main
        echo "Commit deployed successfully."
    else
        echo "All output files match existing remote structures. Skipping commit phase."
    fi
    
    echo "Cycle complete. Going to sleep for 6 hours..."
    sleep $INTERVAL
done
