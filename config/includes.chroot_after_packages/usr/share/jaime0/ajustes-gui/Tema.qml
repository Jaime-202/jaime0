pragma Singleton

import QtQuick
import Quickshell

// Colores y fuente de la identidad de ZYRON. "acento" lo pone shell.qml con el valor
// actual de jaime0-ajustes.
Singleton {
    readonly property color fondo: "#080b0d"
    readonly property color superficie: "#101519"
    readonly property color superficie2: "#151c21"
    readonly property color borde: "#26343a"
    readonly property color texto: "#d8e2e8"
    readonly property color secundario: "#71818c"
    readonly property color cian: "#55cde0"
    readonly property color error: "#e0705f"
    property color acento: "#54e58a"
    readonly property string fuente: "JetBrainsMono Nerd Font"
}
