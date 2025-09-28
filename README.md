# ODFL - Compiler Fault Localization Technique

ODFL (**O**ption **D**ifferentiating for **F**ault **L**ocalization) is an innovative technique proposed in the paper "Isolating Compiler Faults through Differentiated Compilation Configurations" for effective compiler fault localization.

This implementation evaluates ODFL's performance using two major C compilers: LLVM and GCC.

## Prerequisites

- Linux workstation

- Python 3.x

- GCC/LLVM build dependencies

## Getting Started

### 1. Setting Up Bug Information

Add compiler bugs to the respective summary files using this format:

```
bugId,trunk_revision,non_triggering_optimization,triggering_optimization,faulty_file
```

Example (from gccbugs_summary.txt):

`56478,r196310,-O1+-c,-O2+-c,gcc/predict.c`

Note: Comprehensive bug information is available in the benchmark directory.

### 2. Installing Target Compilers

Run the appropriate installation script:

```
# For GCC
python gcc-install.py

# For LLVM
python llvm-install.py
```

This will install the specified compiler versions from source.

### 3. Running ODFL Analysis

Execute the appropriate run script:

```
# For GCC
python gcc-run.py

# For LLVM
python llvm-run.py
```

Output:

The analysis generates Ochiai_scoredict.txt, containing suspiciousness scores for compiler source files (sorted in descending order). Higher scores indicate greater likelihood of containing the bug.

The scripts automatically process all bugs listed in the corresponding summary files.

### 4. Evaluating Results

Generate performance metrics with:

```
# For GCC
python gcc-result.py

# For LLVM
python llvm-result.py
```

Metrics Reported:

- Top-N (Top 1, 5, 10, 20)

- MFR (Mean First Rank)

- MAR (Mean Average Rank)

## Documentation

For detailed methodology and technical background, please refer to the original paper:

**"Isolating Compiler Faults through Differentiated Compilation Configurations"**
