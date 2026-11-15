import QtQuick
import QtQuick.Layouts

// PERFORMANCE: carga por nucleo y frecuencias, carga reciente, memoria, energia y los
// procesos que mas consumen. Datos de instante.json y de la serie de 5 min del servicio.
Item {
    id: vista

    property var instante: null
    property var estado: null
    property var serie: null

    readonly property var cpu: instante ? instante.cpu : null
    readonly property var ram: instante ? instante.ram : null
    readonly property var perfil: estado ? estado.perfil : null
    readonly property var mhz: cpu && cpu.mhz ? cpu.mhz.filter(x => x !== null) : []

    Consulta {
        id: consulta
        onRespuesta: d => { if (d.ok) vista.serie = d; }
    }
    onInstanteChanged: consulta.pedir({ orden: "serie", rango: "5m" })

    function serieDe(nombre, etiqueta, color) {
        const m = serie && serie.metricas ? serie.metricas[nombre] : null;
        return { nombre: etiqueta, color: color, med: m && m.med ? m.med : [] };
    }

    GridLayout {
        anchors.fill: parent
        columns: 2
        rowSpacing: 10
        columnSpacing: 10

        // ── Nucleos ─────────────────────────────────────────────────────────
        Marco {
            Layout.fillWidth: true
            Layout.preferredHeight: 196
            ident: "R1"
            etiqueta: "CPU CORES · " + (vista.cpu && vista.cpu.nucleos ? vista.cpu.nucleos.length + " HILOS" : "N/D")
                      + (vista.mhz.length ? " · " + Math.min.apply(null, vista.mhz) + "–" + Math.max.apply(null, vista.mhz) + " MHz" : " · FRECUENCIA N/D")
            acento: Tema.verde
            Grid {
                id: rejillaNucleos
                anchors.fill: parent
                columns: Math.max(1, Math.floor(width / 120))
                rowSpacing: 8
                columnSpacing: 10
                Repeater {
                    model: vista.cpu && vista.cpu.nucleos ? vista.cpu.nucleos : []
                    Column {
                        required property var modelData
                        required property int index
                        width: (rejillaNucleos.width - (rejillaNucleos.columns - 1) * 10) / rejillaNucleos.columns
                        spacing: 3
                        Row {
                            width: parent.width
                            Text {
                                width: parent.width / 2
                                text: "C" + String(index).padStart(2, "0")
                                color: Tema.apagado
                                font.family: Tema.mono
                                font.pixelSize: Tema.letraMini
                            }
                            Text {
                                width: parent.width / 2
                                horizontalAlignment: Text.AlignRight
                                text: Number(modelData).toFixed(0) + "%"
                                color: modelData >= 85 ? Tema.ambar : Tema.texto
                                font.family: Tema.mono
                                font.pixelSize: Tema.letraMini
                            }
                        }
                        Rectangle {
                            width: parent.width
                            height: 5
                            color: Tema.rejilla
                            Rectangle {
                                width: parent.width * Math.min(1, modelData / 100)
                                height: parent.height
                                color: modelData >= 85 ? Tema.ambar : Tema.verde
                                Behavior on width { NumberAnimation { duration: Tema.medio; easing.type: Easing.OutCubic } }
                            }
                        }
                        Text {
                            readonly property var f: vista.cpu.mhz ? vista.cpu.mhz[index] : null
                            text: f === null || f === undefined ? "— MHz" : f + " MHz"
                            color: Tema.apagado
                            font.family: Tema.mono
                            font.pixelSize: 9
                        }
                    }
                }
            }
        }

        // ── Carga de los ultimos 5 minutos ──────────────────────────────────
        Marco {
            Layout.fillWidth: true
            Layout.preferredHeight: 196
            ident: "R2"
            etiqueta: "CPU LOAD · LAST 5 MIN"
            acento: Tema.verde
            Text {
                id: cargaActual
                text: vista.cpu ? vista.cpu.total.toFixed(1) + "%" : "N/D"
                color: Tema.verde
                font.family: Tema.mono
                font.pixelSize: Tema.letraDato
            }
            Grafica {
                anchors.top: cargaActual.bottom
                anchors.topMargin: 4
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                t: vista.serie ? vista.serie.t : []
                series: [vista.serieDe("cpu", "CPU", Tema.verde)]
                huecos: vista.serie ? vista.serie.huecos : []
                eventos: vista.serie ? (vista.serie.eventos || []).filter(e => e.tipo === "cpu" || e.tipo === "perfil") : []
                umbrales: [{ valor: 85, color: Tema.ambar, etiqueta: "85 %" }]
            }
            Text {
                anchors.centerIn: parent
                visible: !vista.serie || !vista.serie.t || vista.serie.t.length < 2
                text: "RECOGIENDO MUESTRAS… (hace falta 1 minuto de datos)"
                color: Tema.apagado
                font.family: Tema.mono
                font.pixelSize: Tema.letraMini
            }
        }

        // ── Memoria ─────────────────────────────────────────────────────────
        Marco {
            Layout.fillWidth: true
            Layout.fillHeight: true
            ident: "R3"
            etiqueta: "MEMORY · SWAP · PRESSURE"
            acento: Tema.cian
            Column {
                width: parent.width
                spacing: 12
                Medidor {
                    width: parent.width
                    etiqueta: "RAM"
                    valor: vista.ram ? vista.ram.usada / 1024 : null
                    unidad: vista.ram ? "/ " + (vista.ram.total / 1024).toFixed(1) + " GiB" : ""
                    decimales: 1
                    nivel: vista.ram ? vista.ram.usada / vista.ram.total : -1
                    aviso: 0.9
                    critico: 0.95
                    detalle: vista.ram ? "disponible " + ((vista.ram.total - vista.ram.usada) / 1024).toFixed(1) + " GiB" : ""
                }
                Medidor {
                    width: parent.width
                    etiqueta: "SWAP"
                    valor: vista.ram && vista.ram.swap_total > 0 ? vista.ram.swap / 1024 : null
                    unidad: vista.ram && vista.ram.swap_total > 0 ? "/ " + (vista.ram.swap_total / 1024).toFixed(1) + " GiB" : ""
                    decimales: 2
                    nivel: vista.ram && vista.ram.swap_total > 0 ? vista.ram.swap / vista.ram.swap_total : -1
                    aviso: 0.5
                    critico: 0.9
                }
                Medidor {
                    width: parent.width
                    etiqueta: "PRESIÓN DE MEMORIA (avg10)"
                    valor: vista.ram ? vista.ram.presion : null
                    decimales: 2
                    nivel: vista.ram && vista.ram.presion !== null ? Math.min(1, vista.ram.presion / 40) : -1
                    aviso: 0.5
                    critico: 0.9
                    detalle: "0 = sin esperas por memoria; por encima de 20 el sistema ya espera"
                }
            }
        }

        // ── Energia y procesos ──────────────────────────────────────────────
        Marco {
            Layout.fillWidth: true
            Layout.fillHeight: true
            ident: "R4"
            etiqueta: "ENERGY · TOP PROCESSES"
            acento: Tema.cian
            Column {
                width: parent.width
                spacing: 6
                Repeater {
                    model: [
                        ["PERFIL JAIME0", vista.perfil && vista.perfil.nombre ? vista.perfil.nombre : "N/D"],
                        ["ENERGÍA (ppd)", vista.perfil && vista.perfil.energia ? vista.perfil.energia + (vista.perfil.retencion ? " · retenido" : "") : "N/D"],
                        ["RENDIMIENTO", vista.perfil && vista.perfil.degradado ? "degradado: " + vista.perfil.degradado : "sin limitaciones"]
                    ]
                    Row {
                        required property var modelData
                        spacing: 10
                        Text { width: 120; text: modelData[0]; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1 }
                        Text { text: modelData[1]; color: Tema.texto; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                    }
                }
                Rectangle { width: parent.width; height: 1; color: Tema.borde }
                Repeater {
                    model: vista.instante && vista.instante.procesos ? vista.instante.procesos : []
                    Item {
                        required property var modelData
                        width: parent.width
                        height: 18
                        // Barra de fondo proporcional a la CPU del proceso.
                        Rectangle {
                            width: parent.width * Math.min(1, modelData.cpu / 100)
                            height: parent.height
                            color: Tema.verde
                            opacity: 0.12
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            x: 4
                            text: String(modelData.pid).padStart(6) + "  " + modelData.nombre
                            color: Tema.texto
                            font.family: Tema.mono
                            font.pixelSize: Tema.letraMini
                        }
                        Text {
                            anchors.right: parent.right
                            anchors.rightMargin: 4
                            anchors.verticalCenter: parent.verticalCenter
                            text: Number(modelData.cpu).toFixed(1) + "%   " + (modelData.ram !== null ? modelData.ram + " MiB" : "N/D")
                            color: Tema.secundario
                            font.family: Tema.mono
                            font.pixelSize: Tema.letraMini
                        }
                    }
                }
            }
        }
    }
}
