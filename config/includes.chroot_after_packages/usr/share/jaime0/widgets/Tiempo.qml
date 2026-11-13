import QtQuick
import Quickshell.Io

// El tiempo de la ciudad de los ajustes (jaime0-tiempo, Open-Meteo). Se consulta al
// arrancar, cada 30 minutos y cuando cambia la ciudad; jaime0-tiempo guarda cache.
Tarjeta {
    id: tiempo

    property var datos: null
    ancho: 220

    function consultar() {
        if (!proceso.running)
            proceso.running = true;
    }

    Process {
        id: proceso
        command: ["jaime0-tiempo"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    tiempo.datos = JSON.parse(text);
                } catch (e) {
                    tiempo.datos = { ok: false, error: "No se pudo leer el tiempo" };
                }
            }
        }
    }

    Timer {
        interval: 30 * 60 * 1000
        repeat: true
        running: true
        onTriggered: tiempo.consultar()
    }

    Connections {
        target: Estado
        function onCiudadChanged() { tiempo.consultar(); }
    }

    Component.onCompleted: consultar()

    Row {
        spacing: 12
        visible: tiempo.datos !== null && tiempo.datos.ok === true

        Texto {
            text: tiempo.datos && tiempo.datos.ok ? tiempo.datos.icono : ""
            font.pixelSize: 40
            color: Estado.acento
            anchors.verticalCenter: parent.verticalCenter
        }

        Column {
            spacing: 2
            Texto {
                text: tiempo.datos && tiempo.datos.ok ? Math.round(tiempo.datos.temperatura) + "°" : ""
                font.pixelSize: 32
                font.weight: Font.Light
            }
            Texto {
                tenue: true
                text: tiempo.datos && tiempo.datos.ok ? tiempo.datos.descripcion : ""
            }
        }
    }

    Texto {
        visible: tiempo.datos !== null && tiempo.datos.ok === true
        tenue: true
        width: parent.width
        elide: Text.ElideRight
        text: tiempo.datos && tiempo.datos.ok
              ? "\u{f005d} " + tiempo.datos.maxima + "°  \u{f0045} " + tiempo.datos.minima + "°  ·  "
                + tiempo.datos.ciudad + (tiempo.datos.antiguo ? "  (sin conexión)" : "")
              : ""
        font.pixelSize: 11
    }

    Texto {
        visible: tiempo.datos !== null && tiempo.datos.ok !== true
        tenue: true
        width: parent.width
        wrapMode: Text.WordWrap
        text: tiempo.datos && tiempo.datos.ok !== true ? "\u{f0590}  " + tiempo.datos.error : ""
        font.pixelSize: 11
    }
}
