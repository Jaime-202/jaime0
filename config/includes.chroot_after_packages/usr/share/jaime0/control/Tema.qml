pragma Singleton

import QtQuick
import Quickshell

// Paleta y medidas del Control Center. Es la misma identidad de Jaime0, pero con mas
// presencia del cian y de las lineas tecnicas que el escritorio normal.
Singleton {
    readonly property color fondo: "#080b0d"
    readonly property color panel: "#101519"
    readonly property color panel2: "#0c1114"
    readonly property color borde: "#26343a"
    readonly property color rejilla: "#14202a"
    readonly property color texto: "#d8e2e8"
    readonly property color secundario: "#71818c"
    readonly property color apagado: "#45545c"
    readonly property color verde: "#54e58a"
    readonly property color cian: "#55cde0"
    readonly property color ambar: "#d9a54a"
    readonly property color rojo: "#d9625b"

    readonly property string mono: "JetBrainsMono Nerd Font"
    readonly property int letraMini: 10
    readonly property int letra: 12
    readonly property int letraDato: 22
    readonly property int letraGrande: 30

    // Duracion de las transiciones (ms). Se ajustara con el nivel de animacion (fase 7).
    readonly property int rapido: 140
    readonly property int medio: 220

    function colorEstado(e) {
        if (e === "CRITICAL") return rojo;
        if (e === "WARNING") return ambar;
        if (e === "ONLINE" || e === "SECURE") return verde;
        return secundario;
    }
}
