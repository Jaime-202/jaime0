import QtQuick
import QtQuick.Layouts

// SYSTEM OVERVIEW: estado global y resumen de todo, con los datos de jaime0-servicio
// (instante.json y estado.json). Lo que no existe se muestra como N/D.
Item {
    id: vista

    property var instante: null
    property var estado: null
    property var historiaCpu: []
    property var historiaRam: []

    readonly property string global: estado ? estado.estado : "UNKNOWN"
    readonly property var motivos: estado && estado.motivos ? estado.motivos : []
    readonly property var actividad: estado && estado.actividad ? estado.actividad : []
    readonly property var privacidad: estado ? estado.privacidad : null
    readonly property var perfil: estado ? estado.perfil : null
    readonly property var bat: instante ? instante.bateria : null
    readonly property var ram: instante ? instante.ram : null
    readonly property var discoRaiz: instante && instante.disco && instante.disco.length ? instante.disco[0] : null

    function duracion(s) {
        if (s === null || s === undefined) return "N/D";
        const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
        return (d > 0 ? d + "d " : "") + String(h).padStart(2, "0") + "h " + String(m).padStart(2, "0") + "m";
    }
    function hora(t) {
        const f = new Date(t * 1000);
        return String(f.getHours()).padStart(2, "0") + ":" + String(f.getMinutes()).padStart(2, "0") + ":" + String(f.getSeconds()).padStart(2, "0");
    }
    // Servicios importantes (estado.json) y actualizaciones (orden "actualizaciones", sin red).
    readonly property var serviciosMal: estado && estado.servicios ? estado.servicios.filter(x => x.estado === "fallido") : []
    property var actualizaciones: null
    function textoJaime0() {
        const a = actualizaciones;
        if (!a) return "ZYRON: N/D";
        if (!a.jaime0) return "ZYRON: " + (a.error_jaime0 ? "no se puede saber" : "N/D");
        if (a.jaime0.nueva && a.jaime0.disponible) return "ZYRON: " + a.jaime0.disponible.version + " disponible";
        return "ZYRON: " + (a.jaime0.version_instalada || "?") + (a.jaime0.disponible ? " · al día" : " · sin comprobar");
    }
    Consulta { id: consultaAct; onRespuesta: d => { if (d.ok !== false) vista.actualizaciones = d; } }
    Component.onCompleted: consultaAct.pedir({ orden: "actualizaciones" })
    // Sin datos (servicio aun arrancando): reintenta cada 10 s; despues, cada 5 min.
    Timer { interval: vista.actualizaciones ? 300000 : 10000; running: true; repeat: true; onTriggered: consultaAct.pedir({ orden: "actualizaciones" }) }

    function nombrePerfil(p) {
        return { "balanced": "BALANCED", "performance": "PERFORMANCE", "power-saver": "POWER SAVER" }[p] || (p ? p.toUpperCase() : "N/D");
    }

    GridLayout {
        anchors.fill: parent
        columns: 6
        rowSpacing: 10
        columnSpacing: 10

        // ── Estado global ────────────────────────────────────────────────────
        Marco {
            Layout.columnSpan: 4
            Layout.fillWidth: true
            Layout.preferredHeight: 150
            ident: "00"
            etiqueta: "SYSTEM STATUS"
            acento: Tema.colorEstado(vista.global)

            Column {
                anchors.fill: parent
                spacing: 8
                Row {
                    spacing: 12
                    Rectangle {
                        id: luz
                        anchors.verticalCenter: parent.verticalCenter
                        width: 10; height: 10
                        color: Tema.colorEstado(vista.global)
                        // Latido lento solo si hay un problema.
                        SequentialAnimation on opacity {
                            // Solo con animaciones "suave": con "sutil" o "no" la luz no parpadea.
                            running: Tema.nivel === "suave" && (vista.global === "WARNING" || vista.global === "CRITICAL")
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.25; duration: 700 }
                            NumberAnimation { to: 1; duration: 700 }
                            onRunningChanged: if (!running) luz.opacity = 1
                        }
                    }
                    Text {
                        text: vista.estado ? "SYSTEM " + vista.global : "SERVICE OFFLINE"
                        color: Tema.colorEstado(vista.global)
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraGrande
                        font.letterSpacing: 2
                    }
                }
                Text {
                    width: parent.width
                    visible: vista.motivos.length === 0
                    text: vista.estado ? "Todo dentro de los umbrales: temperatura, disco, memoria, batería y servicios."
                                       : "jaime0-servicio no responde: los datos no están al día."
                    color: Tema.secundario
                    font.family: Tema.mono
                    font.pixelSize: Tema.letra
                    wrapMode: Text.WordWrap
                }
                Repeater {
                    model: vista.motivos.slice(0, 4)
                    Text {
                        required property var modelData
                        text: (modelData.gravedad === "CRITICAL" ? "▲ " : "△ ") + modelData.componente.toUpperCase() + "  " + modelData.texto
                        color: Tema.colorEstado(modelData.gravedad)
                        font.family: Tema.mono
                        font.pixelSize: Tema.letra
                    }
                }
                // Problemas del ultimo diagnostico (DIAGNOSTICS los explica; aqui solo se avisa).
                Text {
                    readonly property var d: vista.estado ? vista.estado.diagnostico : null
                    visible: !!(d && d.total > 0)
                    width: parent.width
                    elide: Text.ElideRight
                    text: d && d.total > 0 ? "△ DIAGNOSTICS  " + d.principales.map(p => p.gravedad + " " + p.titulo).join(" · ")
                                             + (d.total > d.principales.length ? " · +" + (d.total - d.principales.length) : "") + "   (tecla 9)" : ""
                    color: d && d.principales.length && (d.principales[0].gravedad === "CRITICAL" || d.principales[0].gravedad === "ERROR") ? Tema.rojo : Tema.ambar
                    font.family: Tema.mono
                    font.pixelSize: Tema.letraMini
                }
            }
        }

        Marco {
            Layout.columnSpan: 2
            Layout.fillWidth: true
            Layout.preferredHeight: 150
            ident: "01"
            etiqueta: "SESSION"
            Column {
                anchors.fill: parent
                spacing: 10
                Repeater {
                    model: [
                        ["UPTIME", vista.duracion(vista.instante ? vista.instante.uptime : null), Tema.texto],
                        ["PROFILE", vista.perfil ? (vista.perfil.nombre || vista.nombrePerfil(vista.perfil.activo)) : "N/D", Tema.cian],
                        ["PRIVACY", vista.privacidad ? vista.privacidad.estado : "N/D", Tema.colorEstado(vista.privacidad ? vista.privacidad.estado : "")]
                    ]
                    Row {
                        required property var modelData
                        width: parent.width
                        Text {
                            width: 90
                            text: modelData[0]
                            color: Tema.secundario
                            font.family: Tema.mono
                            font.pixelSize: Tema.letraMini
                            font.letterSpacing: 1.5
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: modelData[1]
                            color: modelData[2]
                            font.family: Tema.mono
                            font.pixelSize: 16
                        }
                    }
                }
            }
        }

        // ── Recursos ─────────────────────────────────────────────────────────
        Marco {
            Layout.columnSpan: 2
            Layout.fillWidth: true
            Layout.preferredHeight: 170
            ident: "02"
            etiqueta: "CPU"
            Medidor {
                id: medCpu
                width: parent.width
                etiqueta: "LOAD"
                valor: vista.instante && vista.instante.cpu ? vista.instante.cpu.total : null
                unidad: "%"
                decimales: 1
                nivel: disponible ? valor / 100 : -1
                detalle: vista.instante && vista.instante.cpu && vista.instante.cpu.nucleos
                         ? vista.instante.cpu.nucleos.length + " hilos" : ""
            }
            Traza {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.top: medCpu.bottom
                anchors.topMargin: 8
                muestras: vista.historiaCpu
                linea: Tema.verde
            }
        }
        Marco {
            Layout.columnSpan: 2
            Layout.fillWidth: true
            Layout.preferredHeight: 170
            ident: "03"
            etiqueta: "MEMORY"
            Medidor {
                id: medRam
                width: parent.width
                etiqueta: "RAM"
                valor: vista.ram ? vista.ram.usada / 1024 : null
                unidad: vista.ram ? "/ " + (vista.ram.total / 1024).toFixed(1) + " GiB" : ""
                decimales: 1
                nivel: vista.ram ? vista.ram.usada / vista.ram.total : -1
                // Sin datos no se afirma nada; "sin swap" solo si el equipo no tiene.
                detalle: !vista.ram ? "" : vista.ram.swap_total > 0
                         ? "swap " + (vista.ram.swap / 1024).toFixed(1) + " GiB" : "sin swap"
            }
            Traza {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.top: medRam.bottom
                anchors.topMargin: 8
                muestras: vista.historiaRam
                linea: Tema.cian
            }
        }
        Marco {
            Layout.columnSpan: 2
            Layout.fillWidth: true
            Layout.preferredHeight: 170
            ident: "04"
            etiqueta: "THERMAL"
            Column {
                width: parent.width
                spacing: 10
                Medidor {
                    width: parent.width
                    etiqueta: "CPU PACKAGE"
                    valor: vista.instante && vista.instante.cpu ? vista.instante.cpu.temp : null
                    unidad: "°C"
                    decimales: 0
                    nivel: disponible ? valor / 100 : -1
                    aviso: 0.85
                    critico: 0.95
                }
                Text {
                    width: parent.width
                    readonly property var g: vista.instante ? vista.instante.gpu : null
                    text: !g || !g.nvidia ? "GPU NVIDIA  N/D"
                          : "GPU NVIDIA  " + (g.nvidia === "suspendida" ? "SUSPENDIDA · sin consumo" : g.nvidia.toUpperCase())
                    color: Tema.secundario
                    font.family: Tema.mono
                    font.pixelSize: Tema.letraMini
                    elide: Text.ElideRight
                }
                Text {
                    text: vista.instante && vista.instante.temp ? vista.instante.temp.length + " sensores" : "0 sensores"
                    color: Tema.apagado
                    font.family: Tema.mono
                    font.pixelSize: Tema.letraMini
                }
            }
        }

        Marco {
            Layout.columnSpan: 3
            Layout.fillWidth: true
            Layout.preferredHeight: 104
            ident: "05"
            etiqueta: "STORAGE"
            Medidor {
                width: parent.width
                etiqueta: vista.discoRaiz ? "ROOT " + vista.discoRaiz.punto : "ROOT"
                valor: vista.discoRaiz ? vista.discoRaiz.usado : null
                unidad: vista.discoRaiz ? "/ " + vista.discoRaiz.total + " GiB" : ""
                decimales: 1
                nivel: vista.discoRaiz ? vista.discoRaiz.usado / vista.discoRaiz.total : -1
                detalle: vista.discoRaiz && vista.discoRaiz.lectura !== null
                         ? "R " + vista.discoRaiz.lectura.toFixed(1) + " MB/s · W " + vista.discoRaiz.escritura.toFixed(1) + " MB/s" : ""
            }
        }
        Marco {
            Layout.columnSpan: 3
            Layout.fillWidth: true
            Layout.preferredHeight: 104
            ident: "06"
            etiqueta: "BATTERY"
            Medidor {
                width: parent.width
                etiqueta: vista.bat ? vista.bat.estado.toUpperCase() + (vista.instante.cargador ? " · CARGADOR" : "") : vista.instante ? "SIN BATERÍA" : ""
                valor: vista.bat ? vista.bat.nivel : null
                unidad: "%"
                nivel: vista.bat ? vista.bat.nivel / 100 : -1
                // Invertido: lo peligroso es el nivel bajo.
                aviso: 2
                critico: 2
                detalle: !vista.bat ? ""
                         : (vista.bat.minutos_estimados !== null
                            ? "≈ " + Math.floor(vista.bat.minutos_estimados / 60) + "h " + (vista.bat.minutos_estimados % 60) + "m restantes (estimado)"
                            : "autonomía: N/D")
                         + (vista.bat.salud !== null ? " · salud " + vista.bat.salud.toFixed(0) + " %" : "")
            }
        }

        // ── Alertas, actividad y procesos ────────────────────────────────────
        Marco {
            Layout.columnSpan: 2
            Layout.fillWidth: true
            Layout.fillHeight: true
            ident: "07"
            etiqueta: "PRIVACY & SECURITY"
            acento: Tema.colorEstado(vista.privacidad ? vista.privacidad.estado : "")
            Column {
                width: parent.width
                spacing: 6
                Text {
                    text: vista.privacidad ? vista.privacidad.estado : "N/D"
                    color: Tema.colorEstado(vista.privacidad ? vista.privacidad.estado : "")
                    font.family: Tema.mono
                    font.pixelSize: 16
                }
                Repeater {
                    model: vista.privacidad && vista.privacidad.detalles ? vista.privacidad.detalles : []
                    Text {
                        required property var modelData
                        width: parent.width
                        text: "· " + modelData
                        color: Tema.secundario
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                        wrapMode: Text.WordWrap
                    }
                }
                Text {
                    width: parent.width
                    text: "Sin telemetría: los datos se quedan en este equipo."
                    color: Tema.apagado
                    font.family: Tema.mono
                    font.pixelSize: Tema.letraMini
                    wrapMode: Text.WordWrap
                }
            }
        }
        Marco {
            Layout.columnSpan: 2
            Layout.fillWidth: true
            Layout.fillHeight: true
            ident: "08"
            etiqueta: "RECENT ACTIVITY"
            Column {
                width: parent.width
                spacing: 4
                clip: true
                Repeater {
                    model: vista.actividad.slice(-8).reverse()
                    Row {
                        required property var modelData
                        spacing: 8
                        Text {
                            text: vista.hora(modelData.t)
                            color: Tema.cian
                            font.family: Tema.mono
                            font.pixelSize: Tema.letraMini
                        }
                        Text {
                            text: modelData.texto
                            color: Tema.texto
                            font.family: Tema.mono
                            font.pixelSize: Tema.letraMini
                        }
                    }
                }
                Text {
                    visible: vista.actividad.length === 0
                    text: "Sin actividad registrada."
                    color: Tema.apagado
                    font.family: Tema.mono
                    font.pixelSize: Tema.letraMini
                }
            }
        }
        Marco {
            Layout.columnSpan: 2
            Layout.fillWidth: true
            Layout.fillHeight: true
            ident: "09"
            etiqueta: "SERVICES · UPDATES"
            acento: vista.serviciosMal.length ? Tema.rojo : Tema.cian
            Column {
                width: parent.width
                spacing: 3
                Repeater {
                    model: vista.estado && vista.estado.servicios ? vista.estado.servicios : []
                    Row {
                        required property var modelData
                        width: parent.width
                        Text { width: 110; text: modelData.nombre; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                        Text {
                            text: modelData.estado.toUpperCase()
                            // Parado no es un fallo (p. ej. Bluetooth sin adaptador): solo "fallido" es rojo.
                            color: modelData.estado === "activo" ? Tema.verde : modelData.estado === "fallido" ? Tema.rojo
                                 : modelData.estado === "arrancando" ? Tema.cian : Tema.secundario
                            font.family: Tema.mono; font.pixelSize: Tema.letraMini
                        }
                    }
                }
                Text { visible: !(vista.estado && vista.estado.servicios); text: "Consultando servicios…"; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                Item { width: 1; height: 2 }
                Text {
                    width: parent.width
                    text: vista.textoJaime0()
                    color: vista.actualizaciones && vista.actualizaciones.jaime0 && vista.actualizaciones.jaime0.nueva ? Tema.cian : Tema.texto
                    font.family: Tema.mono; font.pixelSize: Tema.letraMini; elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    readonly property var d: vista.actualizaciones ? vista.actualizaciones.debian : null
                    text: !vista.actualizaciones ? "Debian: N/D" : !d ? "Debian: sin comprobar todavía"
                          : "Debian: " + d.paquetes + " paquete(s)" + (d.seguridad.length ? ", " + d.seguridad.length + " de seguridad" : "")
                    color: d && d.seguridad.length ? Tema.ambar : Tema.texto
                    font.family: Tema.mono; font.pixelSize: Tema.letraMini; elide: Text.ElideRight
                }
            }
        }
    }
}
