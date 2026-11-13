import QtQuick
import Quickshell.Io
import Quickshell.Services.Pipewire

// Volumen (PipeWire) y, si el equipo tiene pantalla con brillo regulable, brillo.
Tarjeta {
    id: sonido

    readonly property var salida: Pipewire.defaultAudioSink
    readonly property bool hayAudio: salida !== null && salida.audio !== null
    property string pantalla: ""        // /sys/class/backlight/<pantalla>, si existe
    property real brillo: 0

    ancho: 240

    PwObjectTracker {
        objects: sonido.salida ? [sonido.salida] : []
    }

    // Brillo: se busca una vez la pantalla y se lee cada pocos segundos (las teclas de
    // brillo lo cambian por fuera).
    Process {
        command: ["sh", "-c", "ls /sys/class/backlight 2>/dev/null | head -n 1"]
        running: true
        stdout: StdioCollector { onStreamFinished: sonido.pantalla = text.trim() }
    }
    Process {
        id: leerBrillo
        command: ["sh", "-c", "cd /sys/class/backlight/" + sonido.pantalla + " && echo $(cat brightness) $(cat max_brightness)"]
        stdout: StdioCollector {
            onStreamFinished: {
                const p = text.trim().split(" ");
                if (p.length === 2 && Number(p[1]) > 0)
                    sonido.brillo = Number(p[0]) / Number(p[1]);
            }
        }
    }
    Timer {
        interval: 5000
        repeat: true
        triggeredOnStart: true
        running: sonido.pantalla !== "" && !deslizadorBrillo.arrastrando
        onTriggered: leerBrillo.running = true
    }
    Process {
        id: fijarBrillo
        property int porcentaje: 0
        command: ["brightnessctl", "-q", "set", porcentaje + "%"]
    }

    Row {
        width: parent.width
        spacing: 8
        visible: sonido.hayAudio

        Boton {
            glifo: sonido.hayAudio && sonido.salida.audio.muted ? "\u{f075f}" : "\u{f057e}"
            anchors.verticalCenter: parent.verticalCenter
            onPulsado: sonido.salida.audio.muted = !sonido.salida.audio.muted
        }
        Deslizador {
            width: parent.width - 80
            anchors.verticalCenter: parent.verticalCenter
            valor: sonido.hayAudio ? Math.min(1, sonido.salida.audio.volume) : 0
            onMovido: nuevo => sonido.salida.audio.volume = nuevo
        }
        Texto {
            width: 36
            horizontalAlignment: Text.AlignRight
            anchors.verticalCenter: parent.verticalCenter
            tenue: true
            text: sonido.hayAudio ? Math.round(sonido.salida.audio.volume * 100) + "%" : ""
        }
    }

    Row {
        width: parent.width
        spacing: 8
        visible: sonido.pantalla !== ""

        Boton {
            glifo: "\u{f00e0}"
            activo: false
            anchors.verticalCenter: parent.verticalCenter
        }
        Deslizador {
            id: deslizadorBrillo
            width: parent.width - 80
            anchors.verticalCenter: parent.verticalCenter
            valor: sonido.brillo
            onSoltado: nuevo => {
                fijarBrillo.porcentaje = Math.max(1, Math.round(nuevo * 100));
                fijarBrillo.running = true;
                sonido.brillo = nuevo;
            }
        }
        Texto {
            width: 36
            horizontalAlignment: Text.AlignRight
            anchors.verticalCenter: parent.verticalCenter
            tenue: true
            text: Math.round((deslizadorBrillo.arrastrando ? deslizadorBrillo.mostrado : sonido.brillo) * 100) + "%"
        }
    }

    Texto {
        visible: !sonido.hayAudio && sonido.pantalla === ""
        tenue: true
        text: "Sin salida de sonido"
    }
}
