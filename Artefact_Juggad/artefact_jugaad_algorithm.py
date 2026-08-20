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
    # PARAMETERS
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
    # INSTANCE
    # =========================================================

    def createInstance(self):

        return ArtefactJugaadAlgorithm()

    # =========================================================
    # NAME
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
            "Raster Artefact Correction"
        )

    def groupId(self):

        return "rasterartefactcorrection"

    # =========================================================
    # HELP
    # =========================================================

    def shortHelpString(self):

        return self.tr(
            "ArtefactJugaad corrects localized raster artefacts "
            "using either a reference raster or interpolation. "
            "The Raster to Correct is always treated as the "
            "master grid, preserving its CRS, pixel size, "
            "extent, dimensions and grid alignment."
        )

    # =========================================================
    # INITIALIZE ALGORITHM
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
        # QGIS 3 / QGIS 4 COMPATIBILITY
        # -----------------------------------------------------

        try:

            polygon_source_type = (
                QgsProcessing.SourceType.TypeVectorPolygon
            )

        except AttributeError:

            polygon_source_type = (
                QgsProcessing.TypeVectorPolygon
            )

        # -----------------------------------------------------
        # ARTEFACT POLYGONS
        # -----------------------------------------------------

        self.addParameter(

            QgsProcessingParameterVectorLayer(

                self.ARTEFACT_POLYGONS,

                self.tr(
                    "Artefact Polygons"
                ),

                [polygon_source_type]
            )
        )

        # -----------------------------------------------------
        # QGIS 3 / QGIS 4 INTEGER COMPATIBILITY
        # -----------------------------------------------------

        try:

            integer_type = (
                QgsProcessingParameterNumber.Type.Integer
            )

        except AttributeError:

            integer_type = (
                QgsProcessingParameterNumber.Integer
            )

        # -----------------------------------------------------
        # SEARCH DISTANCE
        # -----------------------------------------------------

        self.addParameter(

            QgsProcessingParameterNumber(

                self.MAX_SEARCH_DISTANCE,

                self.tr(
                    "Interpolation Search Distance (pixels)"
                ),

                type=integer_type,

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
    # PROCESS
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

        if method == 0:

            feedback.pushInfo(
                "Correction method: Reference Raster"
            )

        else:

            feedback.pushInfo(
                "Correction method: Interpolation"
            )

        # =====================================================
        # OUTPUT
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
        # MASTER GRID
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
        # READ MASTER
        # =====================================================

        master_data = (

            master_band
            .ReadAsArray()
            .astype(np.float32)

        )

        feedback.setProgress(10)

        # =====================================================
        # ARTIFACT POLYGONS
        # =====================================================

        polygon_layer = (

            self.parameterAsVectorLayer(

                parameters,

                self.ARTEFACT_POLYGONS,

                context
            )
        )

        if polygon_layer is None:

            master_band = None

            master_ds = None

            raise QgsProcessingException(
                "Artefact Polygon layer is invalid."
            )

        feedback.pushInfo(
            "Preparing Artefact Polygons..."
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

        fill_mask_path = (

            QgsProcessingUtils.generateTempFilename(

                "artefactjugaad_fillmask.tif"

            )
        )

        # =====================================================
        # REPROJECT POLYGONS
        # =====================================================

        if (

            polygon_layer.crs()

            !=

            raster_layer.crs()

        ):

            feedback.pushInfo(
                "Reprojecting Artefact Polygons..."
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
        # OPEN POLYGON DATASET
        # =====================================================

        vector_ds = ogr.Open(

            polygon_path

        )

        if vector_ds is None:

            master_band = None

            master_ds = None

            raise QgsProcessingException(

                "Could not open Artefact Polygon layer."

            )

        vector_layer = (

            vector_ds.GetLayer()

        )

        polygon_count = (

            vector_layer.GetFeatureCount()

        )

        feedback.pushInfo(

            f"Artefact polygons: {polygon_count}"

        )

        # =====================================================
        # CREATE MASK
        # =====================================================

        feedback.pushInfo(

            "Creating artefact mask..."

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

                "Could not create artefact mask."

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
        # CREATE MASK
        # =====================================================

        if method == 1:

            # 1 = valid
            # 0 = artefact

            mask_band.Fill(1)

            gdal.RasterizeLayer(

                mask_ds,

                [1],

                vector_layer,

                burn_values=[0]

            )

        else:

            # 0 = outside
            # 1 = artefact

            mask_band.Fill(0)

            gdal.RasterizeLayer(

                mask_ds,

                [1],

                vector_layer,

                burn_values=[1]

            )

        mask_band.FlushCache()

        # =====================================================
        # READ MASK
        # =====================================================

        mask = (

            mask_band
            .ReadAsArray()

        )

        # =====================================================
        # CLOSE DATASETS
        # =====================================================

        mask_band = None

        mask_ds = None

        vector_layer = None

        vector_ds = None

        feedback.setProgress(25)

        # =====================================================
        # INTERPOLATION
        # =====================================================

        if method == 1:

            feedback.pushInfo(
                "======================================"
            )

            feedback.pushInfo(
                "INTERPOLATION MODE"
            )

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
                    "the artefact polygons."

                )

            # -------------------------------------------------
            # NODATA
            # -------------------------------------------------

            temporary_nodata = -9999.0

            working_data = (

                master_data.copy()

            )

            working_data[

                artifact_pixels

            ] = temporary_nodata

            # -------------------------------------------------
            # WORKING RASTER
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

            max_distance = (

                self.parameterAsInt(

                    parameters,

                    self.MAX_SEARCH_DISTANCE,

                    context

                )

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
            # FILL MASK
            # -------------------------------------------------

            fill_mask_ds = driver.Create(

                fill_mask_path,

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

            fill_mask_band.WriteArray(

                mask

            )

            fill_mask_band.FlushCache()

            # -------------------------------------------------
            # FILL NODATA
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
            # READ RESULT
            # -------------------------------------------------

            interpolated_data = (

                work_band
                .ReadAsArray()
                .astype(np.float32)

            )

            # -------------------------------------------------
            # CLOSE
            # -------------------------------------------------

            work_band = None

            work_ds = None

            fill_mask_band = None

            fill_mask_ds = None

            # -------------------------------------------------
            # FINAL ARRAY
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
            # WRITE OUTPUT
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

                "Interpolation completed."

            )

        # =====================================================
        # REFERENCE RASTER
        # =====================================================

        else:

            feedback.pushInfo(

                "======================================"

            )

            feedback.pushInfo(

                "REFERENCE RASTER MODE"

            )

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
            # ALIGN REFERENCE
            # -------------------------------------------------

            feedback.pushInfo(

                "Aligning Reference Raster..."

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

            else:

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

            aligned_ds = gdal.Warp(

                aligned_reference,

                reference_ds,

                options=warp_options

            )

            reference_band = None

            reference_ds = None

            if aligned_ds is None:

                master_band = None

                master_ds = None

                raise QgsProcessingException(

                    "Failed to align Reference Raster."

                )

            # -------------------------------------------------
            # READ REFERENCE
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
            # VALID REFERENCE
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
            # ARTIFACT PIXELS
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
            # REPLACEMENT MASK
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
            # FINAL ARRAY
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
            # CLOSE REFERENCE
            # -------------------------------------------------

            aligned_band = None

            aligned_ds = None

            # -------------------------------------------------
            # WRITE OUTPUT
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
        # GRID ALIGNMENT
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

        check_ds = None

        feedback.setProgress(95)

        # =====================================================
        # ADD OUTPUT TO QGIS
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
        # FINISH
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