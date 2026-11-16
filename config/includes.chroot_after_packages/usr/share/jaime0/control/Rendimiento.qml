import QtQuick
import QtQuick.Layouts

// PERFORMANCE: lo que ocurre ahora. Carga por nucleo y frecuencias, carga reciente, memoria,
// disco, red, GPU, picos y todos los procesos (ordenar, buscar y ver su detalle). Datos de
// instante.json y de las ordenes "serie", "procesos", "proceso" y "eventos" del servicio. La
// evolucion a largo plazo esta en HEALTH y el perfil de energia en PROFILES y POWER.
Item {
    id: vista

    property var instante: null
    property var estado: null
    property var serie: null

    readonly property var cpu: instante ? instante.cpu : null
    readonly property var ram: instante ? instante.ram : null
    property var procesos: null
    property var detalle: null
    property var picos: []
    property string busqueda: ""
    property string orden: "cpu"
    property int elegido: -1
    readonly property var filtrados: {
        const lista = procesos ? procesos.procesos.slice() : [];
        const b = busqueda.trim().toLowerCase();
        const f = b === "" ? lista : lista.filter(p => String(p.nombre).toLowerCase().includes(b) || String(p.pid) === b);
        const clave = { cpu: p => -(p.cpu || 0), ram: p => -(p.ram || 0), nombre: p => String(p.nombre).toLowerCase(), pid: p => p.pid }[orden];
        f.sort((a, z) => clave(a) < clave(z) ? -1 : clave(a) > clave(z) ? 1 : 0);
        return f.slice(0, 200);
    }
    function hora(t) {
        const f = new Date(t * 1000);
        return [f.getHours(), f.getMinutes(), f.getSeconds()].map(n => String(n).padStart(2, "0")).join(":");
    }
    readonly property var mhz: cpu && cpu.mhz ? cpu.mhz.filter(x => x !== null) : []

    Consulta {
        id: consulta
        onRespuesta: d => { if (d.ok) vista.serie = d; }
    }
    Consulta { id: consultaProc; onRespuesta: d => { if (d.ok) vista.procesos = d; } }
    Consulta { id: consultaDetalle; onRespuesta: d => vista.detalle = d }
    Consulta { id: consultaEventos; onRespuesta: d => { if (d.ok) vista.picos = (d.eventos || []).filter(e => e.tipo === "pico_cpu" || e.tipo === "pico_ram"); } }
    onInstanteChanged: {
        consulta.pedir({ orden: "serie", rango: "5m" });
        consultaProc.pedir({ orden: "procesos" });
    }
    Component.onCompleted: { consultaProc.pedir({ orden: "procesos" }); consultaEventos.pedir({ orden: "eventos" }); }
    Timer { interval: 10000; running: true; repeat: true; onTriggered: consultaEventos.pedir({ orden: "eventos" }) }

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
            Layout.preferredHeight: 170
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
            Layout.preferredHeight: 170
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
                eventos: vista.serie ? (vista.serie.eventos || []).filter(e => e.tipo === "pico_cpu" || e.tipo === "perfil") : []
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

        // ── Memoria, E/S y picos | procesos ──────────────────────────────────
        RowLayout {
            Layout.columnSpan: 2
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10

            ColumnLayout {
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                Layout.fillWidth: true
                spacing: 10
                Marco {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 168
                    ident: "R3"
                    etiqueta: "MEMORY · SWAP · PRESSURE"
                    acento: Tema.cian
                    Column {
                        width: parent.width
                        spacing: 4
                        Medidor {
                            width: parent.width
                            etiqueta: "RAM"
                            valor: vista.ram ? vista.ram.usada / 1024 : null
                            unidad: vista.ram ? "/ " + (vista.ram.total / 1024).toFixed(1) + " GiB" : ""
                            decimales: 1
                            nivel: vista.ram ? vista.ram.usada / vista.ram.total : -1
                            aviso: 0.9
                            critico: 0.95
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
                        Text {
                            width: parent.width
                            wrapMode: Text.WordWrap
                            text: "PRESIÓN (avg10) " + (vista.ram && vista.ram.presion !== null ? vista.ram.presion.toFixed(2) : "N/D") + " · 0 = sin esperas, > 20 ya espera"
                            color: vista.ram && vista.ram.presion > 20 ? Tema.ambar : Tema.secundario
                            font.family: Tema.mono; font.pixelSize: 9
                        }
                    }
                }
                Marco {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    id: marcoES
                    ident: "R5"
                    etiqueta: "DISK · NETWORK · GPU · PEAKS"
                    acento: Tema.cian
                    readonly property var disco: vista.instante && vista.instante.disco && vista.instante.disco.length ? vista.instante.disco[0] : null
                    readonly property var red: vista.instante ? vista.instante.red : null
                    readonly property var gpu: vista.instante ? vista.instante.gpu : null
                    Column {
                        width: parent.width
                        spacing: 3
                        Repeater {
                            model: [
                                ["CARGA 1/5/15", vista.cpu && vista.cpu.carga ? vista.cpu.carga.map(x => x.toFixed(2)).join("  ") : "N/D"],
                                ["DISCO /", marcoES.disco && marcoES.disco.lectura !== null ? "lee " + marcoES.disco.lectura.toFixed(1) + " MB/s · escribe " + marcoES.disco.escritura.toFixed(1) + " MB/s" : "N/D"],
                                ["RED", marcoES.red ? "baja " + marcoES.red.rx.toFixed(1) + " KB/s · sube " + marcoES.red.tx.toFixed(1) + " KB/s" : "N/D"],
                                ["GPU NVIDIA", !marcoES.gpu || marcoES.gpu.nvidia === null ? "no hay" : marcoES.gpu.nvidia === "activa" ? "despierta" + (marcoES.gpu.temp !== null ? " · " + marcoES.gpu.temp.toFixed(0) + " °C" : "") + " (detalle en POWER)" : marcoES.gpu.nvidia === "suspendida" ? "dormida (detalle en POWER)" : "sin controlador"]
                            ]
                            Row {
                                required property var modelData
                                spacing: 8
                                Text { width: 100; text: modelData[0]; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                                Text { text: modelData[1]; color: Tema.texto; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                            }
                        }
                        Item { width: 1; height: 4 }
                        Text { text: "PICOS RECIENTES"; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1 }
                        Text { width: parent.width; wrapMode: Text.WordWrap; visible: vista.picos.length === 0; text: "Ninguno (CPU ≥ 85 % dos muestras seguidas o RAM ≥ 90 %)."; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: 9 }
                        Repeater {
                            model: vista.picos.slice(0, 4)
                            Text {
                                required property var modelData
                                width: parent.width
                                text: vista.hora(modelData.t) + "  " + modelData.texto
                                color: Tema.ambar; font.family: Tema.mono; font.pixelSize: 9; elide: Text.ElideRight
                            }
                        }
                    }
                }
            }

            // Procesos: todos, con orden, busqueda y detalle. Solo lectura: no hay acciones sobre
            // procesos (cerrar uno se hace en la terminal o con btop, sabiendo lo que se hace).
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 2
                ident: "R4"
                etiqueta: "PROCESSES · " + (vista.procesos ? vista.procesos.total + " EN TOTAL" : "N/D")
                acento: Tema.verde
                RowLayout {
                    id: barraProc
                    width: parent.width
                    spacing: 6
                    Entrada {
                        Layout.preferredWidth: 180
                        pista: "buscar nombre o PID"
                        onEditado: t => vista.busqueda = t
                    }
                    Repeater {
                        model: [["cpu", "CPU"], ["ram", "RAM"], ["nombre", "NOMBRE"], ["pid", "PID"]]
                        Rectangle {
                            required property var modelData
                            readonly property bool activo: vista.orden === modelData[0]
                            width: tOrden.implicitWidth + 12; height: 22
                            color: activo ? Tema.verde : "transparent"
                            border.color: activo ? Tema.verde : Tema.borde
                            Text { id: tOrden; anchors.centerIn: parent; text: parent.modelData[1]; color: parent.activo ? Tema.fondo : Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                            TapHandler { onTapped: vista.orden = parent.modelData[0] }
                        }
                    }
                    Item { Layout.fillWidth: true }
                    Text { text: vista.filtrados.length + " mostrados"; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: 9 }
                }
                Text {
                    id: cabeceraProc
                    anchors.top: barraProc.bottom
                    anchors.topMargin: 6
                    text: "    PID  NOMBRE                CPU %    RAM MiB  HILOS  ESTADO"
                    color: Tema.apagado; font.family: Tema.mono; font.pixelSize: 9
                }
                ListView {
                    id: listaProc
                    anchors.top: cabeceraProc.bottom
                    anchors.topMargin: 2
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: detalleProc.top
                    anchors.bottomMargin: 6
                    clip: true
                    model: vista.filtrados
                    delegate: Rectangle {
                        required property var modelData
                        readonly property bool pesado: (modelData.cpu || 0) >= 50 || (vista.ram && modelData.ram !== null && modelData.ram >= vista.ram.total * 0.10)
                        readonly property bool elegido: vista.elegido === modelData.pid
                        width: listaProc.width
                        height: 17
                        color: elegido ? "#0f171b" : "transparent"
                        border.color: elegido ? Tema.cian : "transparent"
                        Rectangle { width: parent.width * Math.min(1, (parent.modelData.cpu || 0) / 100); height: parent.height; color: Tema.verde; opacity: 0.10 }
                        Text {
                            x: 4
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 8
                            text: String(parent.modelData.pid).padStart(7) + "  " + String(parent.modelData.nombre).padEnd(20).slice(0, 20)
                                  + (parent.modelData.cpu === null ? "    —" : parent.modelData.cpu.toFixed(1).padStart(6)) + "  "
                                  + (parent.modelData.ram === null ? "      —" : parent.modelData.ram.toFixed(0).padStart(9)) + "  "
                                  + String(parent.modelData.hilos === null ? "—" : parent.modelData.hilos).padStart(5) + "  " + (parent.modelData.estado || "")
                            color: parent.pesado ? Tema.ambar : Tema.texto
                            font.family: Tema.mono; font.pixelSize: Tema.letraMini
                            elide: Text.ElideRight
                        }
                        TapHandler { onTapped: { vista.elegido = parent.modelData.pid; consultaDetalle.pedir({ orden: "proceso", pid: parent.modelData.pid }); } }
                    }
                }
                Rectangle {
                    id: detalleProc
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 62
                    color: Tema.fondo
                    border.color: Tema.borde
                    Column {
                        x: 8; y: 5
                        width: parent.width - 16
                        spacing: 2
                        Text {
                            width: parent.width
                            text: !vista.detalle ? "Pulsa un proceso para ver su detalle. Ámbar = mucha CPU (≥ 50 %) o RAM (≥ 10 %)."
                                  : vista.detalle.ok === false ? "△ " + vista.detalle.error
                                  : vista.detalle.nombre + " · PID " + vista.detalle.pid + " · padre " + (vista.detalle.padre || "—") + " · usuario " + (vista.detalle.usuario || "—")
                                    + " · " + (vista.detalle.hilos || "—") + " hilos · " + (vista.detalle.ram_mib !== null ? vista.detalle.ram_mib + " MiB" : "RAM N/D")
                                    + (vista.detalle.swap_mib ? " · swap " + vista.detalle.swap_mib + " MiB" : "")
                            color: vista.detalle && vista.detalle.ok === false ? Tema.ambar : Tema.texto
                            font.family: Tema.mono; font.pixelSize: Tema.letraMini; elide: Text.ElideRight
                        }
                        Text {
                            width: parent.width
                            visible: !!(vista.detalle && vista.detalle.ok !== false)
                            text: vista.detalle && vista.detalle.ok !== false ? (vista.detalle.orden || "(sin orden: hilo del núcleo)") : ""
                            color: Tema.verde; font.family: Tema.mono; font.pixelSize: 9; wrapMode: Text.WrapAnywhere; maximumLineCount: 2; elide: Text.ElideRight
                        }
                        Text {
                            visible: !!(vista.detalle && vista.detalle.ok !== false && vista.detalle.inicio)
                            text: vista.detalle && vista.detalle.inicio ? "En marcha desde " + new Date(vista.detalle.inicio * 1000).toLocaleString(Qt.locale(), "dd/MM HH:mm") + " · estado " + (vista.detalle.estado || "—") : ""
                            color: Tema.secundario; font.family: Tema.mono; font.pixelSize: 9
                        }
                    }
                }
            }
        }
    }
}
