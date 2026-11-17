import QtQuick
import QtQuick.Layouts
import Quickshell.Io

// HEALTH: consola de diagnostico. Las series vienen de jaime0-servicio (orden "serie");
// los valores actuales, de instante.json. Un rango sin datos suficientes no se ofrece.
Item {
    id: salud

    property var instante: null
    property var estado: null

    // Rangos: REAL TIME son los ultimos 2 minutos del anillo, refrescados con cada muestra.
    readonly property var rangos: [
        { id: "rt",       nombre: "REAL TIME",     peticion: "5m",       segundos: 120 },
        { id: "5m",       nombre: "LAST 5 MIN",    peticion: "5m",       segundos: 300 },
        { id: "1h",       nombre: "LAST HOUR",     peticion: "1h",       segundos: 3600 },
        { id: "24h",      nombre: "LAST 24 HOURS", peticion: "24h",      segundos: 86400 },
        { id: "historia", nombre: "HISTORY",       peticion: "historia", segundos: 0 }
    ]
    property int rango: 0
    property var serie: null
    property string aviso: ""
    property var disponible: ({})
    property var incidencias: []
    property var umbrales: ({ temp_aviso: 85, temp_critico: 95, disco_aviso: 85, disco_critico: 95 })
    property bool diagnostico: false

    readonly property var r: rangos[rango]

    // Deteccion de hardware (orden "hardware"): que tiene este equipo y si ZYRON puede leerlo.
    property var hardware: null
    function textoHw(e) { return ({ compatible: "COMPATIBLE", detectado: "DETECTADO", no_disponible: "NO DISPONIBLE", error_lectura: "ERROR DE LECTURA" })[e] || e; }
    function colorHw(e) { return ({ compatible: Tema.verde, detectado: Tema.ambar, error_lectura: Tema.rojo })[e] || Tema.apagado; }
    Consulta { id: consultaHw; onRespuesta: d => { if (d.ok) salud.hardware = d; } }
    Timer { interval: 30000; running: salud.diagnostico; repeat: true; triggeredOnStart: true; onTriggered: consultaHw.pedir({ orden: "hardware" }) }

    // Serie recortada a los ultimos N segundos (REAL TIME).
    function recortar(s, segundos) {
        if (!s || !s.t || !segundos || s.peticion === "historia") return s;
        const limite = s.t[s.t.length - 1] - segundos;
        let i = 0;
        while (i < s.t.length && s.t[i] < limite) i++;
        const out = { t: s.t.slice(i), metricas: {}, huecos: s.huecos || [], eventos: (s.eventos || []).filter(e => e.t >= limite) };
        for (const k in s.metricas) {
            const m = s.metricas[k];
            out.metricas[k] = { med: m.med ? m.med.slice(i) : null, min: m.min ? m.min.slice(i) : null, max: m.max ? m.max.slice(i) : null };
        }
        return out;
    }
    readonly property var vista: recortar(serie, r.id === "rt" || r.id === "5m" ? r.segundos : 0)

    function metrica(nombre) {
        return vista && vista.metricas && vista.metricas[nombre] ? vista.metricas[nombre] : { med: [] };
    }
    function serieDe(nombre, etiqueta, color) {
        const m = metrica(nombre);
        return { nombre: etiqueta, color: color, med: m.med || [], min: m.min || null, max: m.max || null };
    }
    function estadistica(nombre) {
        const v = (metrica(nombre).med || []).filter(x => x !== null);
        if (!v.length) return null;
        return { media: v.reduce((a, b) => a + b, 0) / v.length, pico: Math.max.apply(null, v), minimo: Math.min.apply(null, v) };
    }

    function pedirSerie() { consulta.pedir({ orden: "serie", rango: r.peticion }); }

    Consulta {
        id: consulta
        onRespuesta: datos => {
            if (datos.disponible) salud.disponible = datos.disponible;
            if (datos.ok) {
                datos.peticion = salud.r.peticion;
                salud.serie = datos;
                salud.aviso = "";
            } else {
                salud.serie = null;
                salud.aviso = datos.error || "sin respuesta del servicio";
            }
        }
    }
    Consulta {
        id: consultaIncidencias
        onRespuesta: datos => { if (datos.ok !== false && datos.incidencias) salud.incidencias = datos.incidencias; }
    }
    // Umbrales actuales (los mismos que usa el servicio), para las lineas de referencia.
    Process {
        id: leerAjustes
        command: ["jaime0-ajustes", "ver", "--json"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const d = JSON.parse(text);
                    const u = {};
                    for (const a of d.ajustes)
                        if (a.clave.startsWith("umbral_")) u[a.clave.slice(7)] = Number(a.valor);
                    salud.umbrales = Object.assign({}, salud.umbrales, u);
                } catch (e) {}
            }
        }
    }

    onRangoChanged: { serie = null; pedirSerie(); }
    Component.onCompleted: { pedirSerie(); consultaIncidencias.pedir({ orden: "incidencias", limite: 30 }); }
    // REAL TIME y 5 min se rehacen con cada muestra; los demas, cada 30 s.
    property real ultimaPeticion: 0
    onInstanteChanged: {
        const ahora = Date.now() / 1000;
        if (r.id === "rt" || r.id === "5m" || ahora - ultimaPeticion > 30) {
            ultimaPeticion = ahora;
            pedirSerie();
        }
    }
    Timer {
        interval: 30000; running: true; repeat: true
        onTriggered: consultaIncidencias.pedir({ orden: "incidencias", limite: 30 })
    }

    // ── Distribucion ─────────────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        // CABECERA — SYSTEM HEALTH
        Marco {
            Layout.fillWidth: true
            Layout.preferredHeight: 76
            ident: "H0"
            etiqueta: "SYSTEM HEALTH"
            acento: Tema.colorEstado(salud.estado ? salud.estado.estado : "")
            RowLayout {
                anchors.fill: parent
                spacing: 18
                Text {
                    text: salud.estado ? salud.estado.estado : "OFFLINE"
                    color: Tema.colorEstado(salud.estado ? salud.estado.estado : "")
                    font.family: Tema.mono
                    font.pixelSize: 20
                    font.letterSpacing: 2
                }
                Repeater {
                    model: [
                        ["CPU", salud.instante && salud.instante.cpu ? salud.instante.cpu.total.toFixed(1) + "%" : "N/D"],
                        ["RAM", salud.instante && salud.instante.ram ? (salud.instante.ram.usada / salud.instante.ram.total * 100).toFixed(0) + "%" : "N/D"],
                        ["TEMP", salud.instante && salud.instante.cpu && salud.instante.cpu.temp !== null ? salud.instante.cpu.temp.toFixed(0) + "°C" : "N/D"],
                        ["ALERTS", salud.estado ? String(salud.estado.motivos.length) : "N/D"]
                    ]
                    Column {
                        required property var modelData
                        Text { text: modelData[0]; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1.5 }
                        Text { text: modelData[1]; color: Tema.texto; font.family: Tema.mono; font.pixelSize: 14 }
                    }
                }
                Item { Layout.fillWidth: true }
                // Selector de intervalo: los rangos sin datos suficientes quedan apagados.
                Row {
                    spacing: 4
                    Repeater {
                        model: salud.rangos
                        Rectangle {
                            id: boton
                            required property var modelData
                            required property int index
                            readonly property bool activo: salud.rango === index
                            readonly property bool usable: index === 0 || salud.disponible[modelData.peticion] === true
                            width: textoBoton.implicitWidth + 14
                            height: 22
                            color: activo ? Tema.verde : "transparent"
                            border.color: activo ? Tema.verde : usable ? Tema.borde : Tema.rejilla
                            border.width: 1
                            Text {
                                id: textoBoton
                                anchors.centerIn: parent
                                text: boton.modelData.nombre
                                color: boton.activo ? Tema.fondo : boton.usable ? Tema.secundario : Tema.apagado
                                font.family: Tema.mono
                                font.pixelSize: Tema.letraMini
                            }
                            Pulsar { enabled: boton.usable; onPulsado: salud.rango = boton.index }
                        }
                    }
                }
                Rectangle {
                    width: textoDiag.implicitWidth + 14
                    height: 22
                    color: salud.diagnostico ? Tema.cian : "transparent"
                    border.color: Tema.cian
                    border.width: 1
                    Text {
                        id: textoDiag
                        anchors.centerIn: parent
                        text: "SENSORS & TRENDS"
                        color: salud.diagnostico ? Tema.fondo : Tema.cian
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                    }
                    Pulsar { onPulsado: salud.diagnostico = !salud.diagnostico }
                }
            }
        }

        // ZONA PRINCIPAL — LIVE MONITORING (CPU y RAM, las graficas mas grandes)
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: salud.diagnostico ? 180 : 230
            spacing: 10
            Repeater {
                model: [
                    { clave: "cpu", ident: "H1", titulo: "CPU LOAD", color: Tema.verde, actual: salud.instante && salud.instante.cpu ? salud.instante.cpu.total : null },
                    { clave: "ram", ident: "H2", titulo: "MEMORY", color: Tema.cian, actual: salud.instante && salud.instante.ram ? salud.instante.ram.usada / salud.instante.ram.total * 100 : null }
                ]
                Marco {
                    id: marcoVivo
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    ident: modelData.ident
                    etiqueta: modelData.titulo + " · " + salud.r.nombre
                    acento: modelData.color
                    readonly property var est: salud.estadistica(modelData.clave)

                    Row {
                        id: lecturas
                        spacing: 22
                        Text {
                            text: marcoVivo.modelData.actual === null ? "N/D" : marcoVivo.modelData.actual.toFixed(1) + "%"
                            color: marcoVivo.modelData.color
                            font.family: Tema.mono
                            font.pixelSize: Tema.letraDato
                        }
                        Repeater {
                            model: marcoVivo.est ? [
                                ["MEDIA", marcoVivo.est.media.toFixed(1) + "%"],
                                ["PICO", marcoVivo.est.pico.toFixed(1) + "%"],
                                // Comparacion del valor actual con la media del intervalo.
                                ["VS MEDIA", marcoVivo.modelData.actual === null ? "N/D"
                                    : (marcoVivo.modelData.actual - marcoVivo.est.media >= 0 ? "+" : "") + (marcoVivo.modelData.actual - marcoVivo.est.media).toFixed(1)]
                            ] : []
                            Column {
                                required property var modelData
                                anchors.bottom: parent.bottom
                                Text { text: modelData[0]; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1 }
                                Text { text: modelData[1]; color: Tema.texto; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                            }
                        }
                    }
                    Grafica {
                        anchors.top: lecturas.bottom
                        anchors.topMargin: 6
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        t: salud.vista ? salud.vista.t : []
                        series: [salud.serieDe(marcoVivo.modelData.clave, marcoVivo.modelData.titulo, marcoVivo.modelData.color)]
                        huecos: salud.vista ? salud.vista.huecos : []
                        eventos: salud.vista ? (salud.vista.eventos || []).filter(e => marcoVivo.modelData.clave === "cpu" ? e.tipo !== "ram" : e.tipo === "ram" || e.tipo === "estado") : []
                        umbrales: marcoVivo.modelData.clave === "ram" ? [{ valor: 90, color: Tema.ambar, etiqueta: "90 %" }] : [{ valor: 85, color: Tema.ambar, etiqueta: "85 %" }]
                    }
                    Text {
                        anchors.centerIn: parent
                        visible: !salud.vista || !salud.vista.t || salud.vista.t.length < 2
                        text: salud.aviso !== "" ? "SIN DATOS · " + salud.aviso : "RECOGIENDO MUESTRAS…"
                        color: Tema.apagado
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                    }
                }
            }
        }

        // ZONA SECUNDARIA — HARDWARE (o SENSORS & TRENDS: estadisticas del rango, sensores y eventos; los
        // problemas interpretados estan en DIAGNOSTICS)
        Loader {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 150
            sourceComponent: salud.diagnostico ? vistaDiagnostico : vistaHardware
        }

        // ZONA INFERIOR — SYSTEM EVENTS
        Marco {
            Layout.fillWidth: true
            Layout.preferredHeight: 118
            ident: "H6"
            etiqueta: "SYSTEM EVENTS · INCIDENCIAS Y EVENTOS"
            Flickable {
                anchors.fill: parent
                contentHeight: listaEventos.implicitHeight
                clip: true
                Column {
                    id: listaEventos
                    width: parent.width
                    spacing: 3
                    Text {
                        visible: salud.incidencias.length === 0
                        text: "Sin incidencias registradas: todos los componentes dentro de sus umbrales."
                        color: Tema.apagado
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                    }
                    Repeater {
                        model: salud.incidencias.slice(0, 20)
                        Text {
                            required property var modelData
                            width: listaEventos.width
                            elide: Text.ElideRight
                            text: {
                                const f = new Date(modelData.t * 1000);
                                const p = n => String(n).padStart(2, "0");
                                return p(f.getDate()) + "/" + p(f.getMonth() + 1) + " " + p(f.getHours()) + ":" + p(f.getMinutes())
                                    + "  " + modelData.gravedad.padEnd(8) + " " + modelData.componente.toUpperCase().padEnd(9) + " "
                                    + modelData.descripcion + (modelData.recomendacion ? "  →  " + modelData.recomendacion : "");
                            }
                            color: Tema.colorEstado(modelData.gravedad === "NORMAL" ? "ONLINE" : modelData.gravedad)
                            font.family: Tema.mono
                            font.pixelSize: Tema.letraMini
                        }
                    }
                }
            }
        }
    }

    // ── HARDWARE DIAGNOSTICS: termico, almacenamiento y bateria ──────────────────
    Component {
        id: vistaHardware
        RowLayout {
            spacing: 10
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                id: marcoTermico
                ident: "H3"
                etiqueta: "THERMAL"
                acento: Tema.ambar
                readonly property var temp: salud.instante && salud.instante.cpu ? salud.instante.cpu.temp : null
                Text {
                    id: tempActual
                    text: marcoTermico.temp === null ? "N/D" : marcoTermico.temp.toFixed(0) + " °C"
                    color: marcoTermico.temp === null ? Tema.apagado
                         : marcoTermico.temp >= salud.umbrales.temp_critico ? Tema.rojo
                         : marcoTermico.temp >= salud.umbrales.temp_aviso ? Tema.ambar : Tema.texto
                    font.family: Tema.mono
                    font.pixelSize: Tema.letraDato
                }
                Text {
                    anchors.left: tempActual.right
                    anchors.leftMargin: 12
                    anchors.baseline: tempActual.baseline
                    text: {
                        const g = salud.instante ? salud.instante.gpu : null;
                        return !g || !g.nvidia ? "" : "GPU " + (g.temp !== null && g.temp !== undefined ? g.temp + " °C" : g.nvidia.toUpperCase());
                    }
                    color: Tema.secundario
                    font.family: Tema.mono
                    font.pixelSize: Tema.letraMini
                }
                Grafica {
                    visible: !!(salud.instante && salud.instante.temp && salud.instante.temp.length > 0)
                    anchors.top: tempActual.bottom
                    anchors.topMargin: 4
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    unidad: "°C"
                    minimo: 20
                    maximo: 105
                    decimales: 0
                    t: salud.vista ? salud.vista.t : []
                    series: [salud.serieDe("temp", "CPU", Tema.ambar), salud.serieDe("gpu_temp", "GPU", Tema.cian)]
                    huecos: salud.vista ? salud.vista.huecos : []
                    eventos: salud.vista ? (salud.vista.eventos || []).filter(e => e.tipo === "temperatura") : []
                    umbrales: [{ valor: salud.umbrales.temp_aviso, color: Tema.ambar, etiqueta: "AVISO" },
                               { valor: salud.umbrales.temp_critico, color: Tema.rojo, etiqueta: "CRÍTICO" }]
                }
                Text {
                    anchors.centerIn: parent
                    visible: !salud.instante || !salud.instante.temp || salud.instante.temp.length === 0
                    text: "SIN SENSORES DE TEMPERATURA"
                    color: Tema.apagado
                    font.family: Tema.mono
                    font.pixelSize: Tema.letraMini
                }
            }
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ident: "H4"
                etiqueta: "STORAGE"
                Column {
                    id: discos
                    width: parent.width
                    spacing: 6
                    Repeater {
                        model: salud.instante && salud.instante.disco ? salud.instante.disco : []
                        Medidor {
                            required property var modelData
                            width: discos.width
                            etiqueta: modelData.punto
                            valor: modelData.usado
                            unidad: "/ " + modelData.total + " GiB"
                            decimales: 1
                            nivel: modelData.total ? modelData.usado / modelData.total : -1
                            aviso: salud.umbrales.disco_aviso / 100
                            critico: salud.umbrales.disco_critico / 100
                        }
                    }
                    Repeater {
                        model: salud.instante && salud.instante.smart ? salud.instante.smart : []
                        Text {
                            required property var modelData
                            width: discos.width
                            elide: Text.ElideRight
                            text: "SMART " + modelData.estado + "  " + modelData.disco
                                  + (modelData.temperatura !== null ? "  " + modelData.temperatura + "°C" : "")
                                  + (modelData.horas !== null ? "  " + modelData.horas + " h" : "")
                            color: Tema.colorEstado(modelData.estado === "OK" ? "ONLINE" : modelData.estado === "FALLO" ? "CRITICAL" : "")
                            font.family: Tema.mono
                            font.pixelSize: Tema.letraMini
                        }
                    }
                    Text {
                        visible: !salud.instante || !salud.instante.smart || salud.instante.smart.length === 0
                        text: "SMART: N/D en este equipo"
                        color: Tema.apagado
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                    }
                }
                Grafica {
                    anchors.top: discos.bottom
                    anchors.topMargin: 6
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    unidad: "MB/s"
                    autoescala: true
                    t: salud.vista ? salud.vista.t : []
                    series: [salud.serieDe("lectura", "LECTURA", Tema.verde), salud.serieDe("escritura", "ESCRITURA", Tema.cian)]
                    huecos: salud.vista ? salud.vista.huecos : []
                }
            }
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                id: marcoBateria
                ident: "H5"
                etiqueta: "BATTERY"
                acento: Tema.verde
                readonly property var bat: salud.instante ? salud.instante.bateria : null
                Column {
                    id: datosBat
                    width: parent.width
                    spacing: 2
                    Text {
                        text: marcoBateria.bat ? marcoBateria.bat.nivel + " %  " + marcoBateria.bat.estado.toUpperCase() : salud.instante ? "SIN BATERÍA" : "N/D"
                        color: Tema.texto
                        font.family: Tema.mono
                        font.pixelSize: 16
                    }
                    Text {
                        readonly property var b: marcoBateria.bat
                        text: !b ? "" : (b.vatios !== null ? b.vatios.toFixed(1) + " W" : "consumo N/D")
                              + "  ·  " + (b.minutos_estimados !== null ? "≈ " + Math.floor(b.minutos_estimados / 60) + "h " + (b.minutos_estimados % 60) + "m ESTIMADO" : "autonomía N/D")
                              + (b.salud !== null ? "  ·  salud " + b.salud.toFixed(0) + " %" : "")
                        color: Tema.secundario
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                    }
                }
                Grafica {
                    anchors.top: datosBat.bottom
                    anchors.topMargin: 6
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    decimales: 0
                    t: salud.vista ? salud.vista.t : []
                    series: [salud.serieDe("bateria", "NIVEL", Tema.verde)]
                    huecos: salud.vista ? salud.vista.huecos : []
                    eventos: salud.vista ? (salud.vista.eventos || []).filter(e => e.tipo === "cargador") : []
                    umbrales: [{ valor: salud.umbrales.bateria_aviso || 15, color: Tema.ambar, etiqueta: "AVISO" }]
                }
            }
        }
    }

    // ── SENSORS & TRENDS: estadisticas del rango, todos los sensores y eventos. Los nucleos y
    // los procesos estan en PERFORMANCE (lo que pasa ahora): aqui no se repiten. ──────────
    Component {
        id: vistaDiagnostico
        RowLayout {
            spacing: 10
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 3
                ident: "D1"
                etiqueta: "TRENDS · " + salud.r.nombre
                acento: Tema.cian
                Flickable {
                    anchors.fill: parent
                    contentHeight: tablaTendencias.implicitHeight
                    clip: true
                Column {
                    id: tablaTendencias
                    width: parent.width
                    spacing: 3
                    Text { text: "MÉTRICA          MÍNIMO    MEDIA    PICO"; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                    Repeater {
                        model: [["cpu", "CPU %"], ["ram", "RAM %"], ["swap", "SWAP %"], ["presion", "PRESIÓN"], ["temp", "TEMP CPU °C"],
                                ["gpu_temp", "TEMP GPU °C"], ["bateria", "BATERÍA %"], ["disco", "DISCO %"], ["lectura", "LECTURA MB/s"], ["escritura", "ESCRITURA MB/s"]]
                        Text {
                            required property var modelData
                            readonly property var e: salud.estadistica(modelData[0])
                            text: modelData[1].padEnd(15) + (e ? e.minimo.toFixed(1).padStart(8) + e.media.toFixed(1).padStart(9) + e.pico.toFixed(1).padStart(8) : "   sin datos en este rango")
                            color: e ? Tema.texto : Tema.apagado
                            font.family: Tema.mono; font.pixelSize: Tema.letraMini
                        }
                    }
                    Text {
                        width: parent.width
                        text: "Solo datos medidos del rango elegido arriba; los huecos no cuentan. Lo que pasa ahora mismo está en PERFORMANCE."
                        color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini; wrapMode: Text.WordWrap
                    }
                }
                }
            }
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 4
                ident: "D2"
                etiqueta: "HARDWARE · SENSORS"
                acento: Tema.cian
                Flickable {
                    anchors.fill: parent
                    contentHeight: tabla.implicitHeight
                    clip: true
                    Column {
                        id: tabla
                        width: parent.width
                        spacing: 3
                        Text {
                            text: salud.hardware ? ["compatible", "detectado", "no_disponible", "error_lectura"].map(e => salud.textoHw(e) + " " + salud.hardware.cuenta[e]).join("   ") : "Detectando…"
                            color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini
                        }
                        Repeater {
                            model: salud.hardware ? salud.hardware.componentes : []
                            Column {
                                id: comp
                                required property var modelData
                                width: tabla.width
                                spacing: 1
                                Row {
                                    spacing: 6
                                    Text { width: 112; text: salud.textoHw(comp.modelData.estado); color: salud.colorHw(comp.modelData.estado); font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                                    Text { text: comp.modelData.nombre; color: Tema.texto; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                                }
                                Text { x: 118; width: comp.width - 118; text: comp.modelData.detalle; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini; wrapMode: Text.WordWrap }
                                Repeater {
                                    model: (comp.modelData.valores || []).slice(0, 8)
                                    Text {
                                        required property var modelData
                                        x: 118
                                        text: modelData.id.padEnd(28).slice(0, 28) + " " + modelData.valor + " " + modelData.unidad
                                        color: modelData.unidad === "°C" && modelData.valor >= salud.umbrales.temp_aviso ? Tema.ambar : Tema.texto
                                        font.family: Tema.mono; font.pixelSize: Tema.letraMini
                                    }
                                }
                            }
                        }
                    }
                }
            }
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 2
                ident: "D3"
                etiqueta: "EVENTS · DEL RANGO"
                acento: Tema.cian
                Flickable {
                    anchors.fill: parent
                    contentHeight: listaProc.implicitHeight
                    clip: true
                    Column {
                        id: listaProc
                        width: parent.width
                        spacing: 2
                        Text {
                            visible: !(salud.vista && salud.vista.eventos && salud.vista.eventos.length)
                            text: "Sin eventos en este rango."
                            color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini
                        }
                        Repeater {
                            model: salud.vista && salud.vista.eventos ? salud.vista.eventos.slice(-40).reverse() : []
                            Text {
                                required property var modelData
                                width: listaProc.width
                                elide: Text.ElideRight
                                text: "▼ " + new Date(modelData.t * 1000).toTimeString().slice(0, 8) + "  " + modelData.texto
                                color: Tema.colorEstado(modelData.gravedad === "INFO" ? "" : modelData.gravedad)
                                font.family: Tema.mono
                                font.pixelSize: Tema.letraMini
                            }
                        }
                    }
                }
            }
        }
    }
}
