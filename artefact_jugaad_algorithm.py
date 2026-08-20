import os
import numpy as np

from qgis.PyQt.QtCore import QCoreApplication

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingException,
    QgsRasterLayer,
    QgsProject,
    QgsProcessingUtils
)

from osgeo import gdal, ogr


class ArtefactJugaadAlgorithm(QgsProcessingAlgorithm):

    # =========================================================
    # PARAMETER NAMES
    # =========================================================

    METHOD = "METHOD"

    RASTER_TO_CORRECT = "RASTER_TO_CORRECT"

    REFERENCE_RASTER = "REFERENCE_RASTER"

    ARTEFACT_POLYGONS = "ARTEFACT_POLYGONS"

    MAX_SEARCH_DISTANCE = "MAX_SEARCH_DISTANCE"

    OUTPUT = "OUTPUT"

    # =========================================================
    # TRANSLATION
    # =========================================================

    def tr(self, text):

        return QCoreApplication.translate(
            "ArtefactJugaad",
            text
        )

    # =========================================================
    # CREATE INSTANCE
    # =========================================================

    def createInstance(self):

        return ArtefactJugaadAlgorithm()

    # =========================================================
    # ID
    # =========================================================

    def name(self):

        return "artefactjugaad"

    # =========================================================
    # DISPLAY NAME
    # =========================================================

    def displayName(self):

        return self.tr(
            "ArtefactJugaad"
        )

    # =========================================================
    # GROUP
    # =========================================================

    def group(self):

        return self.tr(
            "Raster Artifact Correction"
        )

    def groupId(self):

        return "rasterartifactcorrection"

    # =========================================================
    # HELP
    # =========================================================

    def shortHelpString(self):

        return self.tr(
            "ArtefactJugaad corrects raster artifacts using "
            "either a Reference Raster or interpolation. "
            "The Raster to Correct is always the master grid. "
            "The output preserves its CRS, pixel size, extent, "
            "dimensions and grid alignment."
        )

    # =========================================================
    # PARAMETERS
    # =========================================================

    def initAlgorithm(self, config=None):

        # -----------------------------------------------------
        # CORRECTION METHOD
        # -----------------------------------------------------

        self.addParameter(

            QgsProcessingParameterEnum(

                self.METHOD,

                self.tr(
                    "Correction Method"
                ),

                options=[
                    self.tr(
                        "Reference Raster"
                    ),
                    self.tr(
                        "Interpolation"
                    )
                ],

                defaultValue=0
            )
        )

        # -----------------------------------------------------
        # RASTER TO CORRECT
        # -----------------------------------------------------

        self.addParameter(

            QgsProcessingParameterRasterLayer(

                self.RASTER_TO_CORRECT,

                self.tr(
                    "Raster to Correct"
                )
            )
        )

        # -----------------------------------------------------
        # REFERENCE RASTER
        # -----------------------------------------------------

        self.addParameter(

            QgsProcessingParameterRasterLayer(

                self.REFERENCE_RASTER,

                self.tr(
                    "Reference Raster"
                ),

                optional=True
            )
        )

        # -----------------------------------------------------
        # ARTIFACT POLYGONS
        # -----------------------------------------------------

        self.addParameter(

            QgsProcessingParameterVectorLayer(

                self.ARTEFACT_POLYGONS,

                self.tr(
                    "Artifact Polygons"
                ),

                [
                    QgsProcessing.TypeVectorPolygon
                ]
            )
        )

        # -----------------------------------------------------
        # INTERPOLATION DISTANCE
        # -----------------------------------------------------

        self.addParameter(

            QgsProcessingParameterNumber(

                self.MAX_SEARCH_DISTANCE,

                self.tr(
                    "Interpolation Search Distance (pixels)"
                ),

                type=
                QgsProcessingParameterNumber.Integer,

                defaultValue=100,

                minValue=1,

                maxValue=100000
            )
        )

        # -----------------------------------------------------
        # OUTPUT
        # -----------------------------------------------------

        self.addParameter(

            QgsProcessingParameterRasterDestination(

                self.OUTPUT,

                self.tr(
                    "Output Corrected Raster"
                )
            )
        )

    # =========================================================
    # MAIN PROCESS
    # =========================================================

    def processAlgorithm(
        self,
        parameters,
        context,
        feedback
    ):

        # =====================================================
        # METHOD
        # =====================================================

        method = self.parameterAsInt(
            parameters,
            self.METHOD,
            context
        )

        # 0 = Reference Raster
        # 1 = Interpolation

        if method == 0:

            feedback.pushInfo(
                "Correction method: Reference Raster"
            )

        else:

            feedback.pushInfo(
                "Correction method: Interpolation"
            )
        # =====================================================
        # OUTPUT PATH
        # =====================================================

        output = self.parameterAsOutputLayer(
            parameters,
            self.OUTPUT,
            context
        )

        if not output:
            raise QgsProcessingException(
                "Output raster path is invalid."
            )
        # =====================================================
        # RASTER TO CORRECT
        # =====================================================

        raster_layer = self.parameterAsRasterLayer(
            parameters,
            self.RASTER_TO_CORRECT,
            context
        )

        if raster_layer is None:

            raise QgsProcessingException(
                "Raster to Correct is invalid."
            )

        raster_path = raster_layer.source()

        feedback.pushInfo(
            "Opening Raster to Correct..."
        )

        master_ds = gdal.Open(
            raster_path,
            gdal.GA_ReadOnly
        )

        if master_ds is None:

            raise QgsProcessingException(
                "Could not open Raster to Correct."
            )

        # =====================================================
        # MASTER RASTER INFORMATION
        # =====================================================

        width = master_ds.RasterXSize

        height = master_ds.RasterYSize

        master_gt = master_ds.GetGeoTransform()

        master_projection = master_ds.GetProjection()

        master_band = master_ds.GetRasterBand(1)

        master_nodata = (
            master_band.GetNoDataValue()
        )

        pixel_x = master_gt[1]

        pixel_y = abs(
            master_gt[5]
        )

        xmin = master_gt[0]

        ymax = master_gt[3]

        xmax = (
            xmin
            +
            master_gt[1] * width
        )

        ymin = (
            ymax
            +
            master_gt[5] * height
        )

        feedback.pushInfo(
            "======================================"
        )

        feedback.pushInfo(
            "MASTER GRID"
        )

        feedback.pushInfo(
            f"Size: {width} x {height}"
        )

        feedback.pushInfo(
            f"Pixel size: {pixel_x} x {pixel_y}"
        )

        feedback.pushInfo(
            f"CRS: {raster_layer.crs().authid()}"
        )

        feedback.pushInfo(
            f"NoData: {master_nodata}"
        )

        feedback.pushInfo(
            "======================================"
        )

        # =====================================================
        # READ MASTER DATA
        # =====================================================

        master_data = (
            master_band
            .ReadAsArray()
            .astype(np.float32)
        )

        feedback.setProgress(10)

        # =====================================================
        # ARTIFACT POLYGON
        # =====================================================

        polygon_layer = self.parameterAsVectorLayer(
            parameters,
            self.ARTEFACT_POLYGONS,
            context
        )

        if polygon_layer is None:

            raise QgsProcessingException(
                "Artifact Polygon layer is invalid."
            )

        feedback.pushInfo(
            "Preparing Artifact Polygons..."
        )

        polygon_path = polygon_layer.source()

        # =====================================================
        # UNIQUE TEMPORARY FILES
        # =====================================================

        mask_path = (
            QgsProcessingUtils.generateTempFilename(
                "artefactjugaad_mask.tif"
            )
        )

        polygon_output = (
            QgsProcessingUtils.generateTempFilename(
                "artefactjugaad_polygons.gpkg"
            )
        )

        aligned_reference = (
            QgsProcessingUtils.generateTempFilename(
                "artefactjugaad_reference.tif"
            )
        )

        working_raster = (
            QgsProcessingUtils.generateTempFilename(
                "artefactjugaad_working.tif"
            )
        )

        # =====================================================
        # REPROJECT POLYGONS IF NECESSARY
        # =====================================================

        if (
            polygon_layer.crs()
            !=
            raster_layer.crs()
        ):

            feedback.pushInfo(
                "Reprojecting Artifact Polygons..."
            )

            import processing

            reprojection_result = processing.run(

                "native:reprojectlayer",

                {
                    "INPUT":
                        polygon_layer,

                    "TARGET_CRS":
                        raster_layer.crs(),

                    "OUTPUT":
                        polygon_output
                },

                context=context,

                feedback=feedback
            )

            polygon_path = (
                reprojection_result["OUTPUT"]
            )

        # =====================================================
        # OPEN POLYGON WITH OGR
        # =====================================================

        vector_ds = ogr.Open(
            polygon_path
        )

        if vector_ds is None:

            raise QgsProcessingException(
                "Could not open Artifact Polygon layer."
            )

        vector_layer = vector_ds.GetLayer()

        polygon_count = (
            vector_layer.GetFeatureCount()
        )

        feedback.pushInfo(
            f"Artifact polygons: {polygon_count}"
        )

        # =====================================================
        # CREATE MASK
        # =====================================================

        feedback.pushInfo(
            "Creating artifact mask..."
        )

        driver = gdal.GetDriverByName(
            "GTiff"
        )

        mask_ds = driver.Create(

            mask_path,

            width,

            height,

            1,

            gdal.GDT_Byte,

            options=[
                "COMPRESS=DEFLATE",
                "TILED=YES"
            ]
        )

        if mask_ds is None:

            vector_layer = None
            vector_ds = None
            master_band = None
            master_ds = None

            raise QgsProcessingException(
                "Could not create artifact mask."
            )

        mask_ds.SetGeoTransform(
            master_gt
        )

        mask_ds.SetProjection(
            master_projection
        )

        mask_band = (
            mask_ds.GetRasterBand(1)
        )

        # =====================================================
        # MASK CREATION
        # =====================================================

        if method == 1:

            # -------------------------------------------------
            # INTERPOLATION
            #
            # 1 = valid pixel
            # 0 = artifact
            # -------------------------------------------------

            mask_band.Fill(1)

            gdal.RasterizeLayer(

                mask_ds,

                [1],

                vector_layer,

                burn_values=[0]
            )

        else:

            # -------------------------------------------------
            # REFERENCE RASTER
            #
            # 0 = outside artifact
            # 1 = artifact
            # -------------------------------------------------

            mask_band.Fill(0)

            gdal.RasterizeLayer(

                mask_ds,

                [1],

                vector_layer,

                burn_values=[1]
            )

        mask_band.FlushCache()

        # =====================================================
        # READ MASK INTO MEMORY
        # =====================================================

        mask = (
            mask_band
            .ReadAsArray()
        )

        # =====================================================
        # CLOSE OGR/GDAL MASK DATASETS
        #
        # IMPORTANT FOR WINDOWS
        # =====================================================

        mask_band = None

        mask_ds = None

        vector_layer = None

        vector_ds = None

        feedback.setProgress(25)

        # =====================================================
        # INTERPOLATION MODE
        # =====================================================

        if method == 1:

            feedback.pushInfo(
                "======================================"
            )

            feedback.pushInfo(
                "INTERPOLATION MODE"
            )

            # -------------------------------------------------
            # ARTIFACT PIXELS
            # -------------------------------------------------

            artifact_pixels = (
                mask == 0
            )

            artifact_count = int(
                np.count_nonzero(
                    artifact_pixels
                )
            )

            feedback.pushInfo(
                f"Artifact pixels: {artifact_count}"
            )

            if artifact_count == 0:

                master_band = None
                master_ds = None

                raise QgsProcessingException(
                    "No raster pixels were found inside "
                    "the artifact polygons."
                )

            # -------------------------------------------------
            # TEMPORARY NODATA
            # -------------------------------------------------

            temporary_nodata = -9999.0

            working_data = (
                master_data.copy()
            )

            working_data[
                artifact_pixels
            ] = temporary_nodata

            # -------------------------------------------------
            # CREATE WORKING RASTER
            # -------------------------------------------------

            feedback.pushInfo(
                "Creating working raster..."
            )

            work_ds = driver.Create(

                working_raster,

                width,

                height,

                1,

                gdal.GDT_Float32,

                options=[
                    "COMPRESS=DEFLATE",
                    "TILED=YES"
                ]
            )

            if work_ds is None:

                master_band = None
                master_ds = None

                raise QgsProcessingException(
                    "Could not create working raster."
                )

            work_ds.SetGeoTransform(
                master_gt
            )

            work_ds.SetProjection(
                master_projection
            )

            work_band = (
                work_ds.GetRasterBand(1)
            )

            work_band.SetNoDataValue(
                temporary_nodata
            )

            work_band.WriteArray(
                working_data
            )

            work_band.FlushCache()

            # -------------------------------------------------
            # SEARCH DISTANCE
            # -------------------------------------------------

            max_distance = self.parameterAsInt(

                parameters,

                self.MAX_SEARCH_DISTANCE,

                context
            )

            feedback.pushInfo(
                f"Interpolation search distance: "
                f"{max_distance} pixels"
            )

            feedback.pushInfo(
                f"Approximate map distance: "
                f"{max_distance * pixel_x:.2f}"
            )

            # -------------------------------------------------
            # RECREATE MASK
            #
            # We need a fresh GDAL dataset because
            # the previous one has been closed.
            # -------------------------------------------------

            interpolation_mask_path = (
                QgsProcessingUtils.generateTempFilename(
                    "artefactjugaad_fillmask.tif"
                )
            )

            fill_mask_ds = driver.Create(

                interpolation_mask_path,

                width,

                height,

                1,

                gdal.GDT_Byte,

                options=[
                    "COMPRESS=DEFLATE",
                    "TILED=YES"
                ]
            )

            fill_mask_ds.SetGeoTransform(
                master_gt
            )

            fill_mask_ds.SetProjection(
                master_projection
            )

            fill_mask_band = (
                fill_mask_ds.GetRasterBand(1)
            )

            # mask already contains:
            #
            # 1 = valid
            # 0 = artifact

            fill_mask_band.WriteArray(
                mask
            )

            fill_mask_band.FlushCache()

            # -------------------------------------------------
            # INTERPOLATION
            # -------------------------------------------------

            feedback.pushInfo(
                "Running GDAL FillNodata..."
            )

            result = gdal.FillNodata(

                targetBand=work_band,

                maskBand=fill_mask_band,

                maxSearchDist=max_distance,

                smoothingIterations=0
            )

            if result != 0:

                work_band = None

                work_ds = None

                fill_mask_band = None

                fill_mask_ds = None

                master_band = None

                master_ds = None

                raise QgsProcessingException(
                    "GDAL FillNodata failed."
                )

            work_band.FlushCache()

            # -------------------------------------------------
            # READ INTERPOLATED RESULT
            # -------------------------------------------------

            interpolated_data = (
                work_band
                .ReadAsArray()
                .astype(np.float32)
            )

            # -------------------------------------------------
            # CLOSE WORKING DATASET
            # -------------------------------------------------

            work_band = None

            work_ds = None

            fill_mask_band = None

            fill_mask_ds = None

            # -------------------------------------------------
            # IMPORTANT
            #
            # Only replace artifact pixels.
            #
            # Everything else remains exactly as
            # the original raster.
            # -------------------------------------------------

            final_data = (
                master_data.copy()
            )

            final_data[
                artifact_pixels
            ] = (
                interpolated_data[
                    artifact_pixels
                ]
            )

            # -------------------------------------------------
            # WRITE FINAL OUTPUT
            # -------------------------------------------------

            feedback.pushInfo(
                "Writing corrected raster..."
            )

            output_ds = driver.Create(

                output,

                width,

                height,

                1,

                gdal.GDT_Float32,

                options=[
                    "COMPRESS=DEFLATE",
                    "TILED=YES"
                ]
            )

            if output_ds is None:

                master_band = None
                master_ds = None

                raise QgsProcessingException(
                    "Could not create output raster."
                )

            output_ds.SetGeoTransform(
                master_gt
            )

            output_ds.SetProjection(
                master_projection
            )

            output_band = (
                output_ds.GetRasterBand(1)
            )

            # -------------------------------------------------
            # PRESERVE NODATA
            # -------------------------------------------------

            if master_nodata is not None:

                output_band.SetNoDataValue(
                    master_nodata
                )

            else:

                # Keep output valid without assigning
                # NoData to the original raster.
                output_band.DeleteNoDataValue()

            output_band.WriteArray(
                final_data
            )

            output_band.FlushCache()

            output_ds.FlushCache()

            output_band = None

            output_ds = None

            feedback.pushInfo(
                "Interpolation completed."
            )

        # =====================================================
        # REFERENCE RASTER MODE
        # =====================================================

        else:

            feedback.pushInfo(
                "======================================"
            )

            feedback.pushInfo(
                "REFERENCE RASTER MODE"
            )

            # -------------------------------------------------
            # GET REFERENCE RASTER
            # -------------------------------------------------

            reference_layer = (
                self.parameterAsRasterLayer(

                    parameters,

                    self.REFERENCE_RASTER,

                    context
                )
            )

            if reference_layer is None:

                master_band = None
                master_ds = None

                raise QgsProcessingException(

                    "Reference Raster is required "
                    "when Reference Raster mode is selected."
                )

            reference_path = (
                reference_layer.source()
            )

            feedback.pushInfo(
                "Opening Reference Raster..."
            )

            reference_ds = gdal.Open(

                reference_path,

                gdal.GA_ReadOnly
            )

            if reference_ds is None:

                master_band = None
                master_ds = None

                raise QgsProcessingException(

                    "Could not open Reference Raster."
                )

            reference_band = (
                reference_ds.GetRasterBand(1)
            )

            reference_nodata = (
                reference_band.GetNoDataValue()
            )

            # -------------------------------------------------
            # ALIGN REFERENCE RASTER
            # -------------------------------------------------

            feedback.pushInfo(
                "Aligning Reference Raster..."
            )

            warp_options = gdal.WarpOptions(

                format="GTiff",

                outputBounds=(

                    xmin,

                    ymin,

                    xmax,

                    ymax
                ),

                width=width,

                height=height,

                dstSRS=master_projection,

                resampleAlg="bilinear",

                dstNodata=-9999,

                creationOptions=[

                    "COMPRESS=DEFLATE",

                    "TILED=YES"
                ]
            )

            if reference_nodata is not None:

                warp_options = gdal.WarpOptions(

                    format="GTiff",

                    outputBounds=(

                        xmin,

                        ymin,

                        xmax,

                        ymax
                    ),

                    width=width,

                    height=height,

                    dstSRS=master_projection,

                    resampleAlg="bilinear",

                    srcNodata=reference_nodata,

                    dstNodata=-9999,

                    creationOptions=[

                        "COMPRESS=DEFLATE",

                        "TILED=YES"
                    ]
                )

            aligned_ds = gdal.Warp(

                aligned_reference,

                reference_ds,

                options=warp_options
            )

            # Close original reference dataset
            reference_band = None
            reference_ds = None

            if aligned_ds is None:

                master_band = None
                master_ds = None

                raise QgsProcessingException(

                    "Failed to align Reference Raster."
                )

            # -------------------------------------------------
            # READ ALIGNED REFERENCE
            # -------------------------------------------------

            aligned_band = (
                aligned_ds.GetRasterBand(1)
            )

            reference_data = (
                aligned_band
                .ReadAsArray()
                .astype(np.float32)
            )

            # -------------------------------------------------
            # REFERENCE VALIDITY
            # -------------------------------------------------

            valid_reference = (
                np.isfinite(
                    reference_data
                )
            )

            valid_reference &= (
                reference_data != -9999
            )

            # -------------------------------------------------
            # ARTIFACT MASK
            # -------------------------------------------------

            artifact_pixels = (
                mask == 1
            )

            artifact_count = int(
                np.count_nonzero(
                    artifact_pixels
                )
            )

            feedback.pushInfo(
                f"Artifact pixels: {artifact_count}"
            )

            # -------------------------------------------------
            # ONLY REPLACE WHERE:
            #
            # 1. Pixel is inside artifact polygon
            # 2. Reference raster has a valid value
            # -------------------------------------------------

            replace_mask = (
                artifact_pixels
                &
                valid_reference
            )

            replacement_count = int(
                np.count_nonzero(
                    replace_mask
                )
            )

            feedback.pushInfo(
                f"Pixels replaced: {replacement_count}"
            )

            # -------------------------------------------------
            # CREATE FINAL ARRAY
            # -------------------------------------------------

            final_data = (
                master_data.copy()
            )

            final_data[
                replace_mask
            ] = (
                reference_data[
                    replace_mask
                ]
            )

            # -------------------------------------------------
            # CLOSE ALIGNED REFERENCE
            # -------------------------------------------------

            aligned_band = None

            aligned_ds = None

            # -------------------------------------------------
            # WRITE FINAL OUTPUT
            # -------------------------------------------------

            feedback.pushInfo(
                "Writing corrected raster..."
            )

            output_ds = driver.Create(

                output,

                width,

                height,

                1,

                gdal.GDT_Float32,

                options=[
                    "COMPRESS=DEFLATE",
                    "TILED=YES"
                ]
            )

            if output_ds is None:

                master_band = None
                master_ds = None

                raise QgsProcessingException(

                    "Could not create output raster."
                )

            output_ds.SetGeoTransform(
                master_gt
            )

            output_ds.SetProjection(
                master_projection
            )

            output_band = (
                output_ds.GetRasterBand(1)
            )

            # -------------------------------------------------
            # PRESERVE MASTER NODATA
            # -------------------------------------------------

            if master_nodata is not None:

                output_band.SetNoDataValue(
                    master_nodata
                )

            else:

                output_band.DeleteNoDataValue()

            output_band.WriteArray(
                final_data
            )

            output_band.FlushCache()

            output_ds.FlushCache()

            output_band = None

            output_ds = None

            feedback.pushInfo(
                "Reference Raster correction completed."
            )

        # =====================================================
        # CLOSE MASTER
        # =====================================================

        master_band = None

        master_ds = None

        feedback.setProgress(90)

        # =====================================================
        # VERIFY OUTPUT
        # =====================================================

        feedback.pushInfo(
            "Verifying output..."
        )

        check_ds = gdal.Open(
            output,
            gdal.GA_ReadOnly
        )

        if check_ds is None:

            raise QgsProcessingException(
                "Output verification failed."
            )

        check_width = (
            check_ds.RasterXSize
        )

        check_height = (
            check_ds.RasterYSize
        )

        check_gt = (
            check_ds.GetGeoTransform()
        )

        check_projection = (
            check_ds.GetProjection()
        )

        # -----------------------------------------------------
        # SIZE
        # -----------------------------------------------------

        if (

            check_width != width

            or

            check_height != height

        ):

            check_ds = None

            raise QgsProcessingException(

                "Output dimensions do not match "
                "Raster to Correct."
            )

        # -----------------------------------------------------
        # PIXEL SIZE
        # -----------------------------------------------------

        if (

            not np.isclose(

                check_gt[1],

                master_gt[1],

                rtol=0,

                atol=1e-10
            )

            or

            not np.isclose(

                abs(check_gt[5]),

                abs(master_gt[5]),

                rtol=0,

                atol=1e-10
            )

        ):

            check_ds = None

            raise QgsProcessingException(

                "Output pixel size does not match "
                "Raster to Correct."
            )

        # -----------------------------------------------------
        # GRID ORIGIN / ALIGNMENT
        # -----------------------------------------------------

        for i in range(6):

            if not np.isclose(

                check_gt[i],

                master_gt[i],

                rtol=0,

                atol=1e-10

            ):

                check_ds = None

                raise QgsProcessingException(

                    "Output grid alignment does not "
                    "match Raster to Correct."
                )

        # -----------------------------------------------------
        # PROJECTION
        # -----------------------------------------------------

        if check_projection != master_projection:

            check_ds = None

            raise QgsProcessingException(

                "Output projection does not match "
                "Raster to Correct."
            )

        # -----------------------------------------------------
        # CLOSE CHECK DATASET
        # -----------------------------------------------------

        check_ds = None

        feedback.setProgress(95)

        # =====================================================
        # LOAD OUTPUT INTO QGIS
        # =====================================================

        result_layer = QgsRasterLayer(

            output,

            os.path.basename(output)
        )

        if result_layer.isValid():

            QgsProject.instance().addMapLayer(
                result_layer
            )

        # =====================================================
        # FINAL MESSAGE
        # =====================================================

        feedback.setProgress(100)

        feedback.pushInfo(
            "======================================"
        )

        feedback.pushInfo(
            "ArtefactJugaad completed successfully!"
        )

        if method == 0:

            feedback.pushInfo(
                "Method: Reference Raster"
            )

        else:

            feedback.pushInfo(
                "Method: Interpolation"
            )

        feedback.pushInfo(
            f"Output size: "
            f"{width} x {height}"
        )

        feedback.pushInfo(
            f"Output pixel size: "
            f"{pixel_x} x {pixel_y}"
        )

        feedback.pushInfo(
            f"Output CRS: "
            f"{raster_layer.crs().authid()}"
        )

        feedback.pushInfo(
            f"Output: {output}"
        )

        feedback.pushInfo(
            "======================================"
        )

        return {
            self.OUTPUT: output
        }