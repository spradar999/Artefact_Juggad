import os

from qgis.PyQt.QtGui import QIcon

from qgis.core import QgsProcessingProvider

from .artefact_jugaad_algorithm import ArtefactJugaadAlgorithm


class ArtefactJugaadProvider(QgsProcessingProvider):

    def id(self):

        return "artefactjugaad"

    def name(self):

        return "ArtefactJugaad"

    def longName(self):

        return "ArtefactJugaad - Raster Artefact Correction"

    def icon(self):

        icon_path = os.path.join(
            os.path.dirname(__file__),
            "icon.png"
        )

        if os.path.exists(icon_path):

            return QIcon(icon_path)

        return QIcon()

    def loadAlgorithms(self):

        self.addAlgorithm(
            ArtefactJugaadAlgorithm()
        )