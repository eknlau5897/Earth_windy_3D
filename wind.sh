#!/bin/bash
set -e

INTERVAL=$((6 * 60 * 60)) 
DATA_DIR="./data"

echo "=========================================================="
echo " Starting Streaming, Caffeinated Weather Daemon (wind.sh)"
echo "=========================================================="

while true; do
    echo "--- Cycle Started: $(date) ---"
    
    # 1. TIME CALCULATIONS WITH YESTERDAY'S CALENDAR LOOKBACK
    CURRENT_UTC_HOUR=$(date -u +"%H")
    
    # Round down to the nearest standard operational model cycle run (00, 06, 12, 18)
    if [ "$CURRENT_UTC_HOUR" -ge 23 ]; then
        NEAREST_CYCLE="18:00"
        CURRENT_UTC_DATE=$(date -u +"%Y-%m-%d")
    elif [ "$CURRENT_UTC_HOUR" -ge 17 ]; then
        NEAREST_CYCLE="12:00"
        CURRENT_UTC_DATE=$(date -u +"%Y-%m-%d")
    elif [ "$CURRENT_UTC_HOUR" -ge 11 ]; then
        NEAREST_CYCLE="06:00"
        CURRENT_UTC_DATE=$(date -u +"%Y-%m-%d")
    elif [ "$CURRENT_UTC_HOUR" -ge 5 ]; then
        NEAREST_CYCLE="00:00"
        CURRENT_UTC_DATE=$(date -u +"%Y-%m-%d")
    else
        # FIXED: For the 00Z run, we strictly pull yesterday's date (Day -1)
        NEAREST_CYCLE="18:00"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS specific date math subtraction
            CURRENT_UTC_DATE=$(date -u -v-1d +"%Y-%m-%d")
        else
            # Linux specific date math subtraction fallback
            CURRENT_UTC_DATE=$(date -u -d "yesterday" +"%Y-%m-%d")
        fi
    fi
    
    TARGET_RUN="$CURRENT_UTC_DATE $NEAREST_CYCLE"
    echo "Current UTC hour is $CURRENT_UTC_HOUR. Configured timeline target: $TARGET_RUN"
    
    # 2. RUN PIPELINE WITH AUTOMATIC RUN FALLBACK
    echo "Streaming slices directly to memory..."
    
    if ! caffeinate -i python3 wind.py --date "$TARGET_RUN" --output-dir "$DATA_DIR"; then
        echo "[WARNING] $TARGET_RUN data stream failed. Stepping back an additional operational cycle..."
        
        if [[ "$OSTYPE" == "darwin"* ]]; then
            TARGET_RUN=$(date -j -v-6H -f "%Y-%m-%d %H:%M" "$TARGET_RUN" +"%Y-%m-%d %H:%M")
        else
            TARGET_RUN=$(date -d "$TARGET_RUN - 6 hours" +"%Y-%m-%d %H:%M")
        fi
        
        echo "[FALLBACK] Rerouting pipeline engine to: $TARGET_RUN"
        caffeinate -i python3.11 wind.py --date "$TARGET_RUN" --output-dir "$DATA_DIR"
    fi
    
    echo "Matrix translation loop finished successfully."
    
    # 3. COMPREHENSIVE WORKSPACE CLEANUP
    echo "Cleaning residual index maps..."
    find . -type f \( -name "*.idx" -o -name "*.tmp" -o -name "*.log" \) -delete 2>/dev/null || true
    echo "Local workspace clean."
    
    # 4. SINGLE UNIFIED GIT COMMIT & TRANSACTION
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