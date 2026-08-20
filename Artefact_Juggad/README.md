# 🛠️ ArtefactJugaad

[![Version](https://img.shields.io/badge/version-1.6.0-blue.svg)](https://github.com/your-username/ArtefactJugaad)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![QGIS](https://img.shields.io/badge/QGIS-3.40+-brightgreen.svg)](https://qgis.org)

---

ArtefactJugaad is a QGIS plugin designed to correct spatial artefacts in raster datasets. It provides a robust and efficient solution for cleaning up raster data by employing two primary correction approaches:

1. **Reference Raster Replacement:** Replaces identified artefact pixels using a corresponding, valid reference raster.
2. **Interpolation Correction:** Reconstructs pseudo-values within defined artefact polygons using surrounding valid pixels via GDAL interpolation.

The plugin ensures that the "Raster to Correct" (the master grid) maintains its original Coordinate Reference System (CRS), pixel size, extent, dimensions, and grid alignment throughout the process.

## 📖 Table of Contents
- [Features](#-features)
- [Requirements](#-requirements)
- [Usage](#-usage)
- [Author](#-author)
- [License](#-license)

## ✨ Features
- **Dual Correction Methods:** Choose between Reference Raster or Interpolation-based correction.
- **Master Grid Preservation:** Ensures the output raster exactly matches the properties of the input raster.
- **GDAL Powered:** Leverages powerful GDAL capabilities for raster processing and interpolation.
- **QGIS Integration:** Seamlessly integrated into the QGIS Processing framework.

## 📋 Requirements
- QGIS 3.40 or higher
- GDAL
- NumPy

## 🚀 Usage

1. Install the plugin in QGIS.
2. Open the **ArtefactJugaad** tool from the *Processing Toolbox* (under "Raster Artifact Correction").
3. Select the **Correction Method**.
4. Specify the **Raster to Correct**.
5. Provide the **Artifact Polygons** layer.
6. If using the Reference Raster method, provide the **Reference Raster**.
7. If using the Interpolation method, set the **Interpolation Search Distance**.
8. Run the algorithm to generate the corrected raster.

## 👤 Author
Raghavendra SP

## ⚖️ License
This project is licensed under the [MIT License](LICENSE).
