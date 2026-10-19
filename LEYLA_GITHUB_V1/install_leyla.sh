#!/usr/bin/env bash
# ==============================================================================
# LEYLA Automated Environment Installer
# Compatible with CINECA Leonardo, Generic HPC Lmod Clusters, and Local Workstations
# ==============================================================================

set -e

echo "=================================================================="
echo "          LEYLA: AUTOMATED ENVIRONMENT SETUP                      "
echo "=================================================================="

# ------------------------------------------------------------------------------
# 1. HELPER: DYNAMIC MODULE LOADER FOR HPC SYSTEMS
# ------------------------------------------------------------------------------
load_module_pattern() {
    local category_name="$1"
    shift
    local patterns=("$@")

    if command -v module >/dev/null 2>&1 || [ -n "$MODULESHOME" ]; then
        echo "[INFO] Searching HPC module for ${category_name}..."
        for pat in "${patterns[@]}"; do
            if module load "$pat" 2>/dev/null; then
                echo "[SUCCESS] Loaded module pattern: $pat"
                return 0
            fi
        done
        echo "[WARNING] No module matched for ${category_name}. Using system default binaries."
    else
        echo "[INFO] 'module' command not available. Relying on system PATH for ${category_name}."
    fi
    return 0
}

# Load toolchain dynamically by priority patterns
load_module_pattern "Python" "python/3.11" "python/3" "Python/3.11" "python"
load_module_pattern "GCC" "gcc/12" "gcc/13" "gcc" "GCC"
load_module_pattern "CUDA" "cuda/12" "cuda/12.6" "cuda" "CUDA"
load_module_pattern "CMake" "cmake/3.27" "cmake" "CMake"
load_module_pattern "MPI" "openmpi" "mpich" "intel-oneapi-mpi"
load_module_pattern "MKL" "intel-oneapi-mkl" "mkl"

# ------------------------------------------------------------------------------
# 2. PREREQUISITE VERIFICATION
# ------------------------------------------------------------------------------
echo "------------------------------------------------------------------"
echo "[INFO] Verifying core system binaries..."

for cmd in python3 gcc g++ cmake; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "[ERROR] Missing required binary: $cmd. Please ensure it is installed or loaded via modules."
        exit 1
    fi
done

PY_MAJOR_MINOR=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[INFO] Detected Python version: $PY_MAJOR_MINOR"

# ------------------------------------------------------------------------------
# 3. VIRTUAL ENVIRONMENT CREATION
# ------------------------------------------------------------------------------
ENV_NAME="${1:-LEYLA}"

if [ ! -d "$ENV_NAME" ]; then
    echo "[INFO] Creating Virtual Environment in '$ENV_NAME'..."
    python3 -m venv --prompt LEYLA "$ENV_NAME"
else
    echo "[INFO] Re-using existing environment directory '$ENV_NAME'..."
fi

# Activate Virtual Environment
source "$ENV_NAME/bin/activate"

echo "[INFO] Upgrading core pip packages..."
pip install --upgrade pip setuptools wheel

# ------------------------------------------------------------------------------
# 4. INSTALL PYTORCH WITH CUDA SUPPORT
# ------------------------------------------------------------------------------
echo "------------------------------------------------------------------"
echo "[INFO] Installing PyTorch..."

if command -v nvcc >/dev/null 2>&1 || [ -d "/usr/local/cuda" ]; then
    echo "[INFO] CUDA environment detected. Installing PyTorch with CUDA 12.x support..."
    pip install torch==2.7.1+cu126 --extra-index-url https://download.pytorch.org/whl/cu126 || \
    pip install torch --extra-index-url https://download.pytorch.org/whl/cu121 || \
    pip install torch
else
    echo "[WARNING] CUDA not detected directly. Installing default PyTorch package..."
    pip install torch
fi

# ------------------------------------------------------------------------------
# 5. INSTALL LEYLA DEPENDENCIES & PACKAGE
# ------------------------------------------------------------------------------
echo "------------------------------------------------------------------"
echo "[INFO] Installing LEYLA and its dependencies from pyproject.toml..."
pip install -e .

# ------------------------------------------------------------------------------
# 6. BUILD & INSTALL MACE (DIRECTLY INSIDE VENV)
# ------------------------------------------------------------------------------
echo "------------------------------------------------------------------"
echo "[INFO] Setting up MACE repository inside environment..."

mkdir -p "$ENV_NAME/MACE"
if [ ! -d "$ENV_NAME/MACE/mace/.git" ]; then
    git clone https://github.com/ACEsuit/mace.git "$ENV_NAME/MACE/mace"
else
    echo "[INFO] MACE repository already cloned. Updating..."
    (cd "$ENV_NAME/MACE/mace" && git pull)
fi

echo "[INFO] Installing MACE..."
pip install "$ENV_NAME/MACE/mace"

# ------------------------------------------------------------------------------
# 7. BUILD & INSTALL SYMMETRIX (DIRECTLY INSIDE VENV)
# ------------------------------------------------------------------------------
echo "------------------------------------------------------------------"
echo "[INFO] Setting up SYMMETRIX repository inside environment..."

mkdir -p "$ENV_NAME/SYMMETRIX"
if [ ! -d "$ENV_NAME/SYMMETRIX/symmetrix/.git" ]; then
    git clone --recursive https://github.com/wcwitt/symmetrix "$ENV_NAME/SYMMETRIX/symmetrix"
else
    echo "[INFO] Symmetrix repository already cloned."
fi

# Automated patch for pyproject.toml CMake constraint issue
PYPROJ="$ENV_NAME/SYMMETRIX/symmetrix/symmetrix/pyproject.toml"
if [ -f "$PYPROJ" ]; then
    echo "[INFO] Patching $PYPROJ for compatibility..."
    sed -i 's/cmake.minimum-version = ">=3.27"/cmake.version = ">=3.27"/g' "$PYPROJ"
fi

# Configure MPI Compilers
if command -v mpicc >/dev/null 2>&1; then
    export CC=$(which mpicc)
    export CXX=$(which mpicxx)
else
    export CC=$(which gcc)
    export CXX=$(which g++)
fi

# Set Kokkos Build Arguments based on system GPU availability
if command -v nvcc >/dev/null 2>&1; then
    export CMAKE_ARGS="-DCMAKE_C_COMPILER=gcc \
      -DCMAKE_CXX_COMPILER=g++ \
      -DCMAKE_CXX_STANDARD=20 \
      -DKokkos_ENABLE_CUDA=ON \
      -DKokkos_ARCH_AMPERE80=ON"
else
    export CMAKE_ARGS="-DCMAKE_C_COMPILER=gcc \
      -DCMAKE_CXX_COMPILER=g++ \
      -DCMAKE_CXX_STANDARD=20"
fi

echo "[INFO] Compiling and installing SYMMETRIX..."
pip install -v -e "$ENV_NAME/SYMMETRIX/symmetrix/symmetrix"

# ------------------------------------------------------------------------------
# 8. VERIFICATION & FINAL SUMMARY
# ------------------------------------------------------------------------------
echo "=================================================================="
echo "          LEYLA ENVIRONMENT SETUP COMPLETED SUCCESSFULLY!        "
echo "=================================================================="
echo "Activated Python: $(which python3)"
echo "PyTorch Version:  $(python3 -c 'import torch; print(torch.__version__)')"
echo "MACE status:      $(python3 -c 'import mace; print("OK")' 2>/dev/null || echo "FAILED")"
echo "Symmetrix status: $(python3 -c 'import symmetrix; print("OK")' 2>/dev/null || echo "CHECK")"
echo "LEYLA Command:    $(which leyla 2>/dev/null || echo "FAILED")"
echo "------------------------------------------------------------------"