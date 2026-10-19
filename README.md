\[!\[DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23473442.svg)](https://doi.org/10.5281/zenodo.23473442)



\# LEYLA: data-Labelling Engine, energy-Yielding, and active-Learning Automation



\*\*Author:\*\* Alessandro Morittu  

\*\*LinkedIn:\*\* \[Alessandro Morittu](https://www.linkedin.com/in/alessandro-morittu-57758b3a6)  

\*\*GitHub Repository:\*\* \[Armonia-5/LEYLA](https://github.com/Armonia-5/LEYLA.git)



\## 1. WHAT IS LEYLA

\*\*Leyla\*\* is an automated tool designed to build datasets for training machine learning interatomic potentials. Starting from a LAMMPS trajectory, Leyla checks (if an ensemble of models trained on the same dataset with different SEEDs is already available) for which trajectory configurations model predictions exhibit an uncertainty higher than a user-specified threshold using MACE CALCULATOR. Subsequently, from all uncertain configurations, Leyla extracts unique structures using SOAP (Smooth Overlap of Atomic Positions) descriptors. Once unique structures are selected, Leyla computes their energies and forces using CP2K and formats the dataset file to be compatible with the MACE training architecture. Using the generated dataset, it trains 4 models with different SEEDs and selects the model with the lowest energy and force errors.



The primary advantage of Leyla is complete process automation, which eliminates potential human errors during manual file copying and format conversion. Beyond automation, Leyla offers flexible execution by allowing users to define the starting and ending steps of the workflow. If execution crashes before completing training (e.g., due to configuration errors or missing files), or if a dataset already exists and only the TRAINING step is required, or if you simply wish to check query uncertainty without running subsequent steps. In any scenario, Leyla allows you to choose the starting and ending steps, without requiring them to be Step 1 and Step 6, respectively.



Leyla can also be used iteratively to update datasets: by supplying new trajectory files in each iteration, Leyla selects novel structures based on model uncertainty, computes their forces and energies, and expands the existing dataset to train the next generation of models.



\---



\## 2. INSTALLATION



\### AUTOMATIC INSTALLATION (Recommended)

To install Leyla, create a dedicated directory (e.g., LEYLA) and copy all repository files into it.



Once files are copied, check the required environment modules listed in MODULES\_USED.txt (the listed modules correspond to those used during testing; matching or newer versions are recommended).

Similarly, check pip\_list.txt for the Python package environment configuration.



Then, run the installation script from within the LEYLA directory:

./install\_leyla.sh



The script will verify required modules, build the environment, install dependency packages, and install the Leyla package itself.

\--------------------



If you encounter issues with automatic installation, follow the manual steps below:



\--------------------

\### MANUAL INSTALLATION



Copy the files located inside the MANUAL\_INSTALLATION folder.



Load Environment Modules

(Tested with the following modules; use matching or newer versions)



module load python/3.11.7

module load cuda/12.6

module load cmake/3.27.9

module load gcc/12.2.0

module load openmpi/4.1.6--gcc--12.2.0-cuda-12.2

module load intel-oneapi-mkl/2024.0.0





Create and Activate Virtual Environment



python3 -m venv LEYLA

source path/LEYLA/bin/activate



Environment preparation



1\. Install PyTorch

pip install torch==2.7.1+cu126 --extra-index-url https://download.pytorch.org/whl/cu126



2\. Install scientific dependencies:

pip install -r requirements.txt



3\. Install MACE inside the Leyla folder

mkdir MACE

cd MACE

git clone https://github.com/ACEsuit/mace.git

pip install ./mace



4\. Install SYMMETRIX inside the Leyla folder

mkdir SYMMETRYX

cd SYMMETRIX

git clone --recursive https://github.com/wcwitt/symmetrix

cd symmetrix/symmetrix



5\. Set compilers for SYMMETRIX

export CC=$(which mpicc)

export CXX=$(which mpicxx)



6\. Compile and install SYMMETRIX (adjust flags to your cluster architecture):

export CMAKE\_ARGS="-DCMAKE\_C\_COMPILER=gcc \\

&#x20; -DCMAKE\_CXX\_COMPILER=g++ \\

&#x20; -DCMAKE\_CXX\_STANDARD=20 \\

&#x20; -DKokkos\_ENABLE\_CUDA=ON \\

&#x20; -DKokkos\_ARCH\_AMPERE80=ON"



pip install -v -e .



THE ENVIRONMENT IS READY FOR USE.



\---



\## 3. USAGE \& CONFIGURATION



Note on Script Placement:

With automatic installation, Python scripts do not need to be present in your working directory. With manual installation, Python scripts (and other support files) must be present directly in the active working directory.



To run Leyla:

Define all parameters and file names in your YAML configuration file (ensuring specified input files exist in your working directory, if you used MANUAL INSTALLATION you need to have the python scripts in the work directory).



Create execution scripts (job.sh) for each step. (The repository includes example job files for all steps, indicating CPU vs. GPU requirements. Do not rename job.sh files).



Launch the workflow manager using run\_leyla\_master.sh, specifying your desired start and end steps.



Important Execution Notes



Starting from Intermediate Steps:

If you start execution from Step N (where N > 1), your working directory must contain the folder corresponding to Step N - 1, along with all required input files.

Example: If starting from Step 3, your working directory must contain the 02\_MACE\_CALCULATOR folder (earlier step folders are not required) containing traj-above-thresh.xyz.





SOAP conversion: Based on how Leyla is structured, when the following is specified for step 3 in the configuration file:


&#x20; training\_data\_file: "all\_data\_leyla\_test.extxyz"

&#x20; new\_data\_file: "traj-above-thresh.xyz"

&#x20; output\_file: "selected\_with\_soap\_final.extxyz"

&#x20; progress\_file: "soap\_progress.txt"



If training\_data\_file and new\_data\_file have different names, Leyla will automatically select new unique structures to append to an existing dataset.

If training\_data\_file and new\_data\_file have identical names, Leyla assumes no existing dataset exists and creates a brand-new dataset.

Recommendation: Even if starting at Step 4 or later (e.g., if you want to compute forces and energies for an existing dataset to train a model), ensure training\_data\_file and new\_data\_file have same names in the Step 3 section of your YAML file to prevent potential errors.



\## 4. LICENCE

This project is licensed under the MIT License - see the LICENCE file for details.



\## 5. CITATION



If you use LEYLA in your research, please cite it as:



```bibtex

@software{Morittu\_LEYLA\_2026,

&#x20; author       = {Morittu, Alessandro},

&#x20; title        = {{LEYLA: Active Learning Tool}},

&#x20; year         = {2026},

&#x20; publisher    = {Zenodo},

&#x20; version      = {v1.0.1},

&#x20; doi          = {10.5281/zenodo.23473442},

&#x20; url          = {https://doi.org/10.5281/zenodo.23473442}

}

```



Or in text:

Morittu, A. LEYLA: Active Learning Tool (v1.0.1). Zenodo, 2026. DOI: 10.5281/zenodo.23473442.

