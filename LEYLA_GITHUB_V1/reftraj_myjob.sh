#!/bin/bash
#SBATCH INFOS (USE CPUs)

source path/LEYLA/bin/activate

# Dynamic module extraction from YAML
MODULE_1=$(python -c "import yaml; print(yaml.safe_load(open('leyla_config.yaml'))['step_04_reftraj']['modules'][0])")
MODULE_2=$(python -c "import yaml; print(yaml.safe_load(open('leyla_config.yaml'))['step_04_reftraj']['modules'][1])")

module load $MODULE_1
module load $MODULE_2

export OMP_NUM_THREADS=${THREADS_PER_RANK:-1}

# =========================================================================
# CONFIGURATION VARIABLES FROM LEYLA CONFIG
# =========================================================================
INP_FILE=$(python -c "import yaml; print(yaml.safe_load(open('leyla_config.yaml'))['step_04_reftraj']['inp_file'])")
TRAJ_FILE=$(python -c "import yaml; print(yaml.safe_load(open('leyla_config.yaml'))['step_04_reftraj']['traj_file'])")
COORD_DAT=$(python -c "import yaml; print(yaml.safe_load(open('leyla_config.yaml'))['step_04_reftraj']['coord_dat'])")
COORD_XYZ=$(python -c "import yaml; print(yaml.safe_load(open('leyla_config.yaml'))['step_04_reftraj']['coord_xyz'])")
CP2K_BIN=$(python -c "import yaml; print(yaml.safe_load(open('leyla_config.yaml'))['step_04_reftraj']['cp2k_bin'])")

BASE_DIR=$PWD

# =========================================================================
# PREVENTIVE SYSTEM CHECK
# =========================================================================
if [ ! -f "$BASE_DIR/$INP_FILE" ]; then
    echo "FATAL ERROR: Input file '$INP_FILE' not found in $BASE_DIR!"
    exit 1
fi

if [ ! -f "$BASE_DIR/$TRAJ_FILE" ]; then
    echo "FATAL ERROR: Trajectory file '$TRAJ_FILE' not found in $BASE_DIR!"
    echo "Check the name of the TRAJ_FILE variable in the script!"
    exit 1
fi

# Extract LAST_SNAPSHOT from original input file
LAST_SNAPSHOT=$(grep "LAST_SNAPSHOT" $INP_FILE | awk '{print $2}' | tr -d ',\r')

CURRENT_DIR=$BASE_DIR
RUN_COUNT=1
SYSTEM_CRASHES=0  # Counter for true system/setup errors only

# =========================================================================
# START OF AUTOMATION LOOP
# =========================================================================
while true; do
    echo "=========================================================="
    echo "Starting RUN $RUN_COUNT in folder: $CURRENT_DIR"
    echo "=========================================================="
    
    cd "$CURRENT_DIR"

    # 1. CP2K Execution
    mpirun -np $SLURM_NTASKS $CP2K_BIN -i $INP_FILE -o output
    CP2K_STATUS=$?

    # If CP2K finished without errors
    if [ $CP2K_STATUS -eq 0 ]; then
        echo "Job completed successfully or reached LAST_SNAPSHOT!"
        break
    fi

    echo "Detected CP2K crash."

    # 2. Crash point identification
    CURRENT_FIRST=$(grep "FIRST_SNAPSHOT" $INP_FILE | awk '{print $2}' | tr -d ',\r')
    PROJECT_NAME=$(grep -i "PROJECT" "$INP_FILE" | head -n 1 | awk '{print $2}' | tr -d '\r')
    ENER_FILE="${PROJECT_NAME}-1.ener"
    COMPLETED_STEPS=0
    
    if [ -f "$ENER_FILE" ]; then
        LINES=$(wc -l < "$ENER_FILE")
        if [ "$LINES" -gt 1 ]; then
            COMPLETED_STEPS=$((LINES - 1))
        fi
    fi

    # Check if CP2K output contains an explicit SCF failure message
    IS_SCF_FAILURE=0
    if grep -iE "SCF run NOT converged|failed to converge|Maximum number of SCF" output > /dev/null 2>&1; then
        IS_SCF_FAILURE=1
    fi

    # CRITICALITY CHECK:
    if [ $COMPLETED_STEPS -eq 0 ] && [ $IS_SCF_FAILURE -eq 0 ]; then
        SYSTEM_CRASHES=$((SYSTEM_CRASHES + 1))
        echo "WARNING: SYSTEM / SETUP crash on startup! (Attempt $SYSTEM_CRASHES of 2)"
        
        if [ $SYSTEM_CRASHES -ge 2 ]; then
            echo "FATAL ERROR: CP2K keeps crashing on startup due to non-SCF convergence errors."
            echo "Check output file or cp2k.err to verify permissions, memory, or modules."
            exit 1
        fi
    else
        SYSTEM_CRASHES=0
    fi

    # Calculation of crash and restart points
    FAILED_SNAP=$((CURRENT_FIRST + COMPLETED_STEPS))
    NEXT_SNAP=$((FAILED_SNAP + 1))

    if [ $COMPLETED_STEPS -eq 0 ] && [ $IS_SCF_FAILURE -eq 1 ]; then
        echo "The initial snapshot ($FAILED_SNAP) did not reach SCF convergence at the very first step."
    else
        echo "Last snapshot calculated successfully: $((FAILED_SNAP - 1))"
        echo "Crash at snapshot: $FAILED_SNAP"
    fi
    
    if [ $NEXT_SNAP -gt $LAST_SNAPSHOT ]; then
        echo "All valid snapshots up to $LAST_SNAPSHOT have been processed. Finished."
        break
    fi

    # 3. Creation of new run_n folder
    RUN_COUNT=$((RUN_COUNT + 1))
    NEW_DIR="${BASE_DIR}/run_${RUN_COUNT}"
    mkdir -p "$NEW_DIR"
    
    echo "Preparing restart from snapshot $NEXT_SNAP in $NEW_DIR..."

    # 4. Copying necessary files
    cp "${BASE_DIR}/$INP_FILE" "$NEW_DIR/" || { echo "Error copying $INP_FILE"; exit 1; }
    cp "${BASE_DIR}/$TRAJ_FILE" "$NEW_DIR/" || { echo "Error copying $TRAJ_FILE"; exit 1; }
    
    [ -f "${BASE_DIR}/$COORD_DAT" ] && cp "${BASE_DIR}/$COORD_DAT" "$NEW_DIR/"
    [ -f "${BASE_DIR}/$COORD_XYZ" ] && cp "${BASE_DIR}/$COORD_XYZ" "$NEW_DIR/"

    # 5. Updating the input file
    sed -i "s/.*FIRST_SNAPSHOT.*/      FIRST_SNAPSHOT $NEXT_SNAP/" "$NEW_DIR/$INP_FILE"

    # 6. Generating the README file
    CURRENT_DATE=$(date "+%d/%m/%Y %H:%M:%S")
    cat <<EOF > "$NEW_DIR/README"
Date: $CURRENT_DATE
Automatic restart after crash at snapshot $FAILED_SNAP.
New start from snapshot $NEXT_SNAP.
EOF

    # 7. Moving to the new folder
    CURRENT_DIR=$NEW_DIR
    
done

echo "Automation script completed successfully."
