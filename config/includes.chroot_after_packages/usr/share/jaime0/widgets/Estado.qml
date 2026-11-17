pragma Singleton

import QtQuick
import Quickshell

// Paleta de ZYRON y configuracion de los widgets (~/.config/jaime0/generado/widgets.json,
// que escribe jaime0-ajustes). shell.qml llama a cargar() cada vez que cambia el archivo.
Singleton {
    readonly property color fondo: "#080b0d"
    readonly property color tarjeta: "#eb101519"     // #101519 al 92 %
    readonly property color superficie2: "#151c21"
    readonly property color borde: "#26343a"
    readonly property color texto: "#d8e2e8"
    readonly property color secundario: "#71818c"
    readonly property color rojo: "#d9625b"
    readonly property string fuente: "JetBrainsMono Nerd Font"

    // Orden de apilado dentro de una misma posicion.
    readonly property var claves: ["reloj", "musica", "tiempo", "sonido", "sistema", "calendario"]
    readonly property var posiciones: ["arriba-izquierda", "arriba-centro", "arriba-derecha", "centro",
                                       "abajo-izquierda", "abajo-centro", "abajo-derecha"]

    property color acento: "#54e58a"
    property bool tarjetas: true
    property bool doceHoras: false
    property string ciudad: ""
    property var widgets: ({})          // clave -> posicion, solo los activados
    // Nivel de animacion de ZYRON (no, sutil, suave) y la duracion que le corresponde.
    property string animaciones: "sutil"
    readonly property int duracion: animaciones === "no" ? 0 : animaciones === "suave" ? 420 : 220

    function cargar(texto) {
        let d = {};
        if (texto && texto.trim() !== "") {
            try {
                d = JSON.parse(texto);
            } catch (e) {
                return;  // archivo a medio escribir: se queda la configuracion anterior
            }
        }
        acento = /^#[0-9a-fA-F]{6}$/.test(d.acento || "") ? d.acento : "#54e58a";
        tarjetas = d.tarjetas !== false;
        doceHoras = d.reloj_formato === "12h";
        ciudad = typeof d.ciudad === "string" ? d.ciudad : "";
        animaciones = ["no", "sutil", "suave"].indexOf(d.animaciones) >= 0 ? d.animaciones : "sutil";
        const w = {};
        for (const c of claves)
            if (d.widgets && posiciones.indexOf(d.widgets[c]) >= 0)
                w[c] = d.widgets[c];
        if (JSON.stringify(w) !== JSON.stringify(widgets))
            widgets = w;
    }
}
