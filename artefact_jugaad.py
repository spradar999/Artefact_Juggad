from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon

from qgis.core import QgsApplication

from .artefact_jugaad_provider import ArtefactJugaadProvider

import os
import processing


class ArtefactJugaadPlugin:

    def __init__(self, iface):

        self.iface = iface
        self.provider = None
        self.action = None

    # =====================================================
    # INITIALIZE
    # =====================================================

    def initGui(self):

        # Register Processing provider
        self.provider = ArtefactJugaadProvider()

        QgsApplication.processingRegistry().addProvider(
            self.provider
        )

        # Plugin icon
        icon_path = os.path.join(
            os.path.dirname(__file__),
            "icon.png"
        )

        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            icon = QIcon()

        # Plugin action
        self.action = QAction(
            icon,
            "ArtefactJugaad",
            self.iface.mainWindow()
        )

        self.action.setToolTip(
            "Raster Artefact Correction"
        )

        self.action.triggered.connect(
            self.run_artefact_jugaad
        )

        # Add to Plugins menu
        self.iface.addPluginToMenu(
            "&ArtefactJugaad",
            self.action
        )

        # Add toolbar icon
        self.iface.addToolBarIcon(
            self.action
        )

    # =====================================================
    # RUN
    # =====================================================

    def run_artefact_jugaad(self):

        processing.execAlgorithmDialog(
            "artefactjugaad:artefactjugaad",
            {}
        )

    # =====================================================
    # UNLOAD
    # =====================================================

    def unload(self):

        if self.provider:

            QgsApplication.processingRegistry().removeProvider(
                self.provider
            )

        if self.action:

            self.iface.removePluginMenu(
                "&ArtefactJugaad",
                self.action
            )

            self.iface.removeToolBarIcon(
                self.action
            )