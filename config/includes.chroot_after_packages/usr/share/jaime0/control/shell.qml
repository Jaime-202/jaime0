//@ pragma Env QT_QUICK_BACKEND=software
// Jaime0 Control Center. Lo abre y lo cierra "jaime0-control":
//   quickshell -p /usr/share/jaime0/control/shell.qml
// No mide nada: lee lo que publica jaime0-servicio en $XDG_RUNTIME_DIR/jaime0
// (instante.json y estado.json) y, mientras esta abierto, le pide muestras cada 2 s.
// Al cerrar la ventana el proceso termina y el servicio vuelve a su ritmo normal.

import QtQuick
import Quickshell
import Quickshell.Io

ShellRoot {
    id: raiz

    readonly property string dir: (Quickshell.env("XDG_RUNTIME_DIR") || "/tmp") + "/jaime0"
    property var instante: null
    property var estado: null
    property var historiaCpu: []
    property var historiaRam: []
    property real ultimaMuestra: 0
    property int seccion: 0
    property string ahora: ""
    property string equipo: ""

    readonly property var secciones: [
        { id: "SYSTEM", titulo: "OVERVIEW" },
        { id: "PERFORMANCE", titulo: "CPU · MEMORY · PROCESSES", fase: "Fase 4",
          contenido: ["Uso por núcleo y frecuencias", "Procesos que más consumen, con su historial", "Presión de memoria y swap"] },
        { id: "PROFILES", titulo: "SMART PROFILES", fase: "Fase 4",
          contenido: ["BALANCED, PERFORMANCE, POWER SAVER, FOCUS, MULTIMEDIA y CUSTOM", "Qué cambia cada perfil y solo lo que admite este equipo", "Volver al perfil anterior"] },
        { id: "AUTOMATION", titulo: "JAIME0 RULES", fase: "Fase 6",
          contenido: ["Reglas CUANDO → SI → HACER por eventos reales", "Activar, editar y borrar reglas", "Historial de ejecuciones: correctas y fallidas"] },
        { id: "PRIVACY & SECURITY", titulo: "PRIVACY CENTER", fase: "Fase 5",
          contenido: ["Cortafuegos UFW: estado, reglas y puertos", "Conexiones activas y sus procesos", "Micrófono, cámara y pantalla en uso"] },
        { id: "HEALTH", titulo: "SYSTEM HEALTH" },
        { id: "SETTINGS", titulo: "CONTROL CENTER SETTINGS", fase: "Fase 7",
          contenido: ["Animaciones OFF, SUBTLE y SMOOTH", "Frecuencia de actualización y umbrales de alerta", "Historial, atajo y notificaciones"] }
    ]

    function leerJson(vista) {
        try {
            return JSON.parse(vista.text());
        } catch (e) {
            return null;
        }
    }

    // ── Datos del servicio ───────────────────────────────────────────────────────
    FileView {
        id: archivoInstante
        path: raiz.dir + "/instante.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            const d = raiz.leerJson(archivoInstante);
            if (!d || d.v !== 1 || d.t === raiz.ultimaMuestra)
                return;
            raiz.ultimaMuestra = d.t;
            raiz.instante = d;
            // Solo muestras reales: se acumulan mientras la ventana esta abierta.
            raiz.historiaCpu = raiz.historiaCpu.concat([d.cpu ? d.cpu.total : null]).slice(-90);
            raiz.historiaRam = raiz.historiaRam.concat([d.ram ? d.ram.usada / d.ram.total * 100 : null]).slice(-90);
        }
    }
    FileView {
        id: archivoEstado
        path: raiz.dir + "/estado.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            const d = raiz.leerJson(archivoEstado);
            if (d && d.v === 1)
                raiz.estado = d;
        }
    }
    FileView {
        id: archivoEquipo
        path: "/proc/sys/kernel/hostname"
        blockLoading: true
        printErrors: false
    }

    // Mientras la ventana este abierta, el servicio muestrea cada 2 s (la peticion caduca
    // a los 15 s; se renueva cada 10 s).
    Socket {
        id: canal
        path: raiz.dir + "/control.sock"
        onConnectedChanged: {
            if (connected) {
                write('{"orden":"rapido"}\n');
                flush();
            }
        }
    }
    Timer {
        interval: 10000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            canal.connected = false;
            canal.connected = true;
        }
    }
    Timer {
        interval: 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            const f = new Date();
            raiz.ahora = [f.getHours(), f.getMinutes(), f.getSeconds()].map(n => String(n).padStart(2, "0")).join(":");
        }
    }
    Component.onCompleted: equipo = archivoEquipo.text().trim()

    // ── Ventana ──────────────────────────────────────────────────────────────────
    FloatingWindow {
        id: ventana
        visible: true
        title: "Jaime0 Control Center"
        implicitWidth: 1180
        implicitHeight: 760
        color: Tema.fondo
        onVisibleChanged: if (!visible) Qt.quit()

        Item {
            id: lienzo
            anchors.fill: parent
            focus: true
            Keys.onEscapePressed: Qt.quit()
            Keys.onPressed: evento => {
                const n = evento.key - Qt.Key_1;
                if (n >= 0 && n < raiz.secciones.length) {
                    raiz.seccion = n;
                    evento.accepted = true;
                }
            }

            // Entrada al abrir: aparece y baja unos pixeles.
            opacity: 0
            Component.onCompleted: entrada.start()
            ParallelAnimation {
                id: entrada
                NumberAnimation { target: lienzo; property: "opacity"; from: 0; to: 1; duration: Tema.medio; easing.type: Easing.OutCubic }
                NumberAnimation { target: contenido; property: "anchors.topMargin"; from: 0; to: 8; duration: Tema.medio; easing.type: Easing.OutCubic }
            }

            // ── Cabecera ─────────────────────────────────────────────────────────
            Rectangle {
                id: cabecera
                anchors.left: parent.left
                anchors.right: parent.right
                height: 46
                color: Tema.panel2

                Row {
                    id: titulo
                    anchors.left: parent.left
                    anchors.leftMargin: 16
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 10
                    Rectangle { width: 8; height: 8; color: Tema.verde; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: "JAIME0 // CONTROL CENTER"
                        color: Tema.texto
                        font.family: Tema.mono
                        font.pixelSize: 14
                        font.letterSpacing: 3
                    }
                }
                // Ruta de la seccion: entre el titulo y el bloque derecho, recortada si no cabe.
                Text {
                    anchors.left: titulo.right
                    anchors.leftMargin: 28
                    anchors.right: derecha.left
                    anchors.rightMargin: 28
                    anchors.verticalCenter: parent.verticalCenter
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    text: raiz.secciones[raiz.seccion].id + "  /  " + raiz.secciones[raiz.seccion].titulo
                    color: Tema.cian
                    font.family: Tema.mono
                    font.pixelSize: Tema.letraMini
                    font.letterSpacing: 2
                }
                Row {
                    id: derecha
                    anchors.right: parent.right
                    anchors.rightMargin: 16
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 14
                    Text {
                        text: raiz.equipo.toUpperCase()
                        color: Tema.secundario
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                        font.letterSpacing: 1.5
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: raiz.ahora
                        color: Tema.texto
                        font.family: Tema.mono
                        font.pixelSize: Tema.letra
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Rectangle {
                        readonly property string e: raiz.estado ? raiz.estado.estado : "OFFLINE"
                        width: textoEstado.implicitWidth + 16
                        height: 20
                        color: "transparent"
                        border.color: Tema.colorEstado(e)
                        border.width: 1
                        Text {
                            id: textoEstado
                            anchors.centerIn: parent
                            text: parent.e
                            color: Tema.colorEstado(parent.e)
                            font.family: Tema.mono
                            font.pixelSize: Tema.letraMini
                            font.letterSpacing: 1.5
                        }
                    }
                }
                // Linea inferior con un segmento que la recorre despacio (barrido HUD).
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: Tema.borde
                    // Una pasada corta cada 10 s, no en bucle: una animacion continua obliga a
                    // redibujar sin parar y, por software, cuesta CPU de verdad.
                    Rectangle {
                        id: barrido
                        x: -80
                        width: 80
                        height: 1
                        color: Tema.cian
                        opacity: 0.7
                        NumberAnimation on x {
                            id: pasada
                            running: false
                            from: -80
                            to: cabecera.width
                            duration: 1400
                            easing.type: Easing.InOutQuad
                        }
                    }
                    Timer {
                        interval: 10000
                        running: true
                        repeat: true
                        onTriggered: pasada.restart()
                    }
                }
            }

            // ── Navegacion ───────────────────────────────────────────────────────
            Rectangle {
                id: navegacion
                anchors.top: cabecera.bottom
                anchors.bottom: pie.top
                anchors.left: parent.left
                width: 200
                color: Tema.panel2
                Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Tema.borde }

                Column {
                    anchors.top: parent.top
                    anchors.topMargin: 14
                    width: parent.width
                    spacing: 2
                    Repeater {
                        model: raiz.secciones
                        Item {
                            id: elemento
                            required property var modelData
                            required property int index
                            readonly property bool activo: raiz.seccion === index
                            width: navegacion.width
                            height: 36

                            Rectangle {
                                anchors.fill: parent
                                color: elemento.activo ? Tema.panel : raiz_hover.hovered ? "#0f171b" : "transparent"
                                Behavior on color { ColorAnimation { duration: Tema.rapido } }
                            }
                            Rectangle {
                                width: 2
                                height: elemento.activo ? parent.height : 0
                                anchors.verticalCenter: parent.verticalCenter
                                color: Tema.verde
                                Behavior on height { NumberAnimation { duration: Tema.rapido; easing.type: Easing.OutCubic } }
                            }
                            Row {
                                anchors.verticalCenter: parent.verticalCenter
                                x: 16
                                spacing: 10
                                Text {
                                    text: String(elemento.index + 1).padStart(2, "0")
                                    color: elemento.activo ? Tema.verde : Tema.apagado
                                    font.family: Tema.mono
                                    font.pixelSize: Tema.letraMini
                                }
                                Text {
                                    text: elemento.modelData.id
                                    color: elemento.activo ? Tema.texto : raiz_hover.hovered ? Tema.cian : Tema.secundario
                                    font.family: Tema.mono
                                    font.pixelSize: Tema.letraMini
                                    font.letterSpacing: 1.5
                                }
                                Text {
                                    visible: !!elemento.modelData.fase
                                    text: "·"
                                    color: Tema.apagado
                                    font.family: Tema.mono
                                    font.pixelSize: Tema.letraMini
                                }
                            }
                            HoverHandler { id: raiz_hover }
                            TapHandler { onTapped: raiz.seccion = elemento.index }
                        }
                    }
                }
                Text {
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 12
                    x: 16
                    width: parent.width - 32
                    text: "1–7  sección\nESC  cerrar"
                    color: Tema.apagado
                    font.family: Tema.mono
                    font.pixelSize: Tema.letraMini
                    lineHeight: 1.3
                }
            }

            // ── Contenido ────────────────────────────────────────────────────────
            Item {
                id: contenido
                anchors.top: cabecera.bottom
                anchors.topMargin: 8
                anchors.bottom: pie.top
                anchors.bottomMargin: 8
                anchors.left: navegacion.right
                anchors.leftMargin: 12
                anchors.right: parent.right
                anchors.rightMargin: 12

                // Solo existe la seccion visible: las demas no gastan nada.
                Loader {
                    id: cargador
                    anchors.fill: parent
                    sourceComponent: raiz.seccion === 0 ? vistaSistema : raiz.seccion === 5 ? vistaSalud : vistaPendiente
                    onLoaded: cambio.restart()
                }
                ParallelAnimation {
                    id: cambio
                    NumberAnimation { target: cargador; property: "opacity"; from: 0; to: 1; duration: Tema.rapido; easing.type: Easing.OutCubic }
                    NumberAnimation { target: cargador; property: "anchors.leftMargin"; from: 10; to: 0; duration: Tema.rapido; easing.type: Easing.OutCubic }
                }
                Connections {
                    target: raiz
                    function onSeccionChanged() { cambio.restart(); }
                }

                Component {
                    id: vistaSistema
                    Sistema {
                        instante: raiz.instante
                        estado: raiz.estado
                        historiaCpu: raiz.historiaCpu
                        historiaRam: raiz.historiaRam
                    }
                }
                Component {
                    id: vistaSalud
                    Salud {
                        instante: raiz.instante
                        estado: raiz.estado
                    }
                }
                Component {
                    id: vistaPendiente
                    Pendiente {
                        seccion: raiz.secciones[raiz.seccion].id
                        fase: raiz.secciones[raiz.seccion].fase || ""
                        lista: raiz.secciones[raiz.seccion].contenido || []
                    }
                }
            }

            // ── Pie ──────────────────────────────────────────────────────────────
            Rectangle {
                id: pie
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 26
                color: Tema.panel2
                Rectangle { width: parent.width; height: 1; color: Tema.borde }

                readonly property var svc: raiz.estado ? raiz.estado.servicio : null
                readonly property bool fresco: raiz.instante && (Date.now() / 1000 - raiz.instante.t) < 30

                Row {
                    anchors.left: parent.left
                    anchors.leftMargin: 16
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 18
                    Text {
                        text: (pie.fresco ? "● " : "○ ") + "jaime0-servicio" + (pie.svc ? "  PID " + pie.svc.pid : "")
                        color: pie.fresco ? Tema.verde : Tema.ambar
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                    }
                    Text {
                        text: raiz.instante ? "MUESTRA CADA " + raiz.instante.intervalo + " s" : "SIN DATOS"
                        color: Tema.secundario
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                    }
                    Text {
                        visible: raiz.instante !== null
                        text: raiz.instante ? "ÚLTIMA " + new Date(raiz.instante.t * 1000).toTimeString().slice(0, 8) : ""
                        color: Tema.secundario
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                    }
                }
                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: 16
                    anchors.verticalCenter: parent.verticalCenter
                    text: "LOCAL · SIN TELEMETRÍA"
                    color: Tema.apagado
                    font.family: Tema.mono
                    font.pixelSize: Tema.letraMini
                    font.letterSpacing: 1.5
                }
            }
        }
    }
}
