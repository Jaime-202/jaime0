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
    // Contraste (evolucion, fase 9): todo color de texto supera 4.5:1 sobre panel y fondo
    // (pruebas/test_accesibilidad.py lo comprueba). rejilla y borde son solo para lineas.
    readonly property color secundario: "#8796a1"
    readonly property color apagado: "#74848e"
    readonly property color verde: "#54e58a"
    readonly property color cian: "#55cde0"
    readonly property color ambar: "#d9a54a"
    readonly property color rojo: "#d9625b"

    readonly property string mono: "JetBrainsMono Nerd Font"
    readonly property int letraMini: 10          // el tamano minimo: no hay texto mas pequeno
    readonly property int letra: 12
    readonly property int letraDato: 22
    readonly property int letraGrande: 30

    // Nivel de animacion de Jaime0 (ajuste "animaciones": no, sutil, suave). Lo pone
    // shell.qml desde ~/.config/jaime0/generado/control.json. Con "no" no hay transiciones
    // ni movimientos decorativos (barrido de la cabecera, luces que laten).
    property string nivel: "sutil"
    // Escala de la interfaz (ajuste cc_escala, en %) y la que se usa de verdad: si la ventana
    // es demasiado pequena para el diseno, se reduce lo justo para que nada se corte.
    property real escala: 1.0
    readonly property bool animar: nivel !== "no"
    readonly property int rapido: nivel === "no" ? 0 : nivel === "suave" ? 220 : 140
    readonly property int medio: nivel === "no" ? 0 : nivel === "suave" ? 340 : 220

    function colorEstado(e) {
        if (e === "CRITICAL") return rojo;
        if (e === "WARNING") return ambar;
        if (e === "ONLINE" || e === "SECURE") return verde;
        return secundario;
    }
}
