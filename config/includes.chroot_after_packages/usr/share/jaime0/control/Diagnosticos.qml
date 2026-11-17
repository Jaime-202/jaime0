import QtQuick
import QtQuick.Layouts
import Quickshell.Io

// DIAGNOSTICS: problemas interpretados por jaime0-diagnostico (que se detecto, causa probable,
// consecuencias y que hacer). HEALTH sigue las metricas y sus tendencias; aqui se explica que
// pasa. Las reparaciones nunca se hacen desde la ventana: REPARAR abre una terminal con
// "jaime0-diagnostico reparar ID", que ensena las ordenes y pide confirmacion.
Item {
    id: vista

    property var datos: null                // {ultimo, error, ejecutando_desde}
    property var historial: null
    property string elegido: ""
    property string mensaje: ""
    property bool mensajeError: false
    property bool ejecutando: false

    readonly property var ultimo: datos ? datos.ultimo : null
    readonly property var problemas: ultimo ? (ultimo.problemas || []) : []
    readonly property var problema: problemas.find(p => p.id === elegido) || (problemas.length ? problemas[0] : null)
    readonly property bool enMarcha: ejecutando || !!(datos && datos.ejecutando_desde)

    function color(g) {
        return g === "CRITICAL" || g === "ERROR" ? Tema.rojo : g === "WARNING" ? Tema.ambar
             : g === "OK" ? Tema.verde : g === "INFO" ? Tema.cian : Tema.apagado;
    }
    function textoEstado(e) { return ({ NO_DISPONIBLE: "NO DISPONIBLE", NO_APLICA: "NO APLICA" })[e] || e; }
    function fecha(t) {
        if (!t) return "—";
        const f = new Date(t * 1000);
        const p = n => String(n).padStart(2, "0");
        return p(f.getDate()) + "/" + p(f.getMonth() + 1) + " " + p(f.getHours()) + ":" + p(f.getMinutes());
    }
    function leer() {
        consulta.pedir({ orden: "diagnostico" });
        consultaHistorial.pedir({ orden: "diagnostico_historial" });
    }
    function ejecutar() {
        vista.ejecutando = true;
        vista.mensaje = "";
        ejecucion.pedir({ orden: "diagnostico_ejecutar" });
    }
    function reparar(id) {
        lanzador.command = ["kitty", "--class", "jaime0-diagnostico", "-e", "sh", "-c",
                            "jaime0-diagnostico reparar " + id + "; printf '\\nPulsa Intro para cerrar. '; read -r _"];
        lanzador.running = true;
        vista.mensaje = "Abierta una terminal: revisa las órdenes antes de confirmar.";
        vista.mensajeError = false;
    }

    Consulta { id: consulta; onRespuesta: d => { if (d.ok !== false) vista.datos = d; } }
    Consulta { id: consultaHistorial; onRespuesta: d => { if (d.ok !== false) vista.historial = d; } }
    Consulta {
        id: ejecucion
        onRespuesta: d => {
            vista.ejecutando = false;
            if (d.ok === false) { vista.mensaje = d.error || "no se pudo diagnosticar"; vista.mensajeError = true; }
            else { vista.mensaje = "Diagnóstico terminado en " + Number(d.duracion || 0).toFixed(1) + " s"; vista.mensajeError = false; }
            vista.leer();
        }
    }
    Process { id: lanzador }
    Component.onCompleted: leer()
    Timer { interval: 5000; running: vista.enMarcha; repeat: true; onTriggered: vista.leer() }

    component Etiqueta: Rectangle {
        property string texto: ""
        property color tono: Tema.secundario
        width: tEt.implicitWidth + 10; height: 16
        color: "transparent"; border.color: tono
        Text { id: tEt; anchors.centerIn: parent; text: parent.texto; color: parent.tono; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
    }
    component Bloque: Column {
        property string titulo: ""
        property var lineas: []
        property color tono: Tema.texto
        visible: lineas.length > 0
        width: parent ? parent.width : 0
        spacing: 2
        Text { text: parent.titulo; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1 }
        Repeater {
            model: parent.lineas
            Text { required property var modelData; width: parent.width; text: "· " + modelData; color: parent.tono; font.family: Tema.mono; font.pixelSize: Tema.letraMini; wrapMode: Text.WrapAnywhere }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        Marco {
            Layout.fillWidth: true
            Layout.preferredHeight: 92
            ident: "X0"
            etiqueta: "ZYRON DIAGNOSTICS"
            acento: vista.ultimo && (vista.ultimo.resumen.CRITICAL || vista.ultimo.resumen.ERROR) ? Tema.rojo
                   : vista.ultimo && vista.ultimo.resumen.WARNING ? Tema.ambar : Tema.verde
            RowLayout {
                width: parent.width
                spacing: 20
                Column {
                    spacing: 4
                    Text {
                        text: vista.enMarcha ? "RUNNING" : !vista.ultimo ? "NOT RUN"
                              : vista.problemas.filter(p => p.gravedad !== "INFO").length + " PROBLEMAS"
                        color: vista.enMarcha ? Tema.cian : !vista.ultimo ? Tema.ambar
                               : vista.problemas.filter(p => p.gravedad !== "INFO").length ? Tema.ambar : Tema.verde
                        font.family: Tema.mono; font.pixelSize: Tema.letraDato
                    }
                    Text {
                        text: vista.ultimo ? "Comprobado " + vista.fecha(vista.ultimo.t) + " · " + Number(vista.ultimo.duracion || 0).toFixed(1) + " s"
                              : vista.datos && vista.datos.error ? "△ " + vista.datos.error : "Aún no se ha ejecutado: se hace solo a los 2 min de entrar y cada 6 h."
                        color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini
                    }
                }
                Row {
                    Layout.fillWidth: true
                    spacing: 6
                    Repeater {
                        model: ["CRITICAL", "ERROR", "WARNING", "INFO", "NO_DISPONIBLE", "NO_APLICA"]
                        Etiqueta {
                            required property var modelData
                            texto: vista.textoEstado(modelData) + " " + (vista.ultimo && vista.ultimo.resumen ? (vista.ultimo.resumen[modelData] || 0) : "—")
                            tono: vista.ultimo && vista.ultimo.resumen && vista.ultimo.resumen[modelData] ? vista.color(modelData) : Tema.apagado
                        }
                    }
                }
                Column {
                    spacing: 4
                    Rectangle {
                        width: tEj.implicitWidth + 18; height: 24
                        color: "transparent"; border.color: vista.enMarcha ? Tema.rejilla : Tema.cian
                        Text { id: tEj; anchors.centerIn: parent; text: vista.enMarcha ? "DIAGNOSTICANDO…" : "EJECUTAR DIAGNÓSTICO"; color: vista.enMarcha ? Tema.apagado : Tema.cian; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1 }
                        Pulsar { enabled: !vista.enMarcha; onPulsado: vista.ejecutar() }
                    }
                    Text { visible: vista.mensaje !== ""; text: (vista.mensajeError ? "△ " : "✓ ") + vista.mensaje; color: vista.mensajeError ? Tema.ambar : Tema.verde; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 220
            spacing: 10

            // Problemas
            Marco {
                Layout.fillHeight: true
                Layout.preferredWidth: 330
                ident: "X1"
                etiqueta: "PROBLEMS"
                Flickable {
                    anchors.fill: parent
                    contentHeight: listaProblemas.implicitHeight
                    clip: true
                    Column {
                        id: listaProblemas
                        width: parent.width
                        spacing: 4
                        Text {
                            width: parent.width
                            visible: vista.ultimo && vista.problemas.length === 0
                            text: "Ningún problema. Lo que el equipo no tiene (por ejemplo, sin NVIDIA o sin batería) no cuenta como problema."
                            color: Tema.verde; font.family: Tema.mono; font.pixelSize: Tema.letraMini; wrapMode: Text.WordWrap
                        }
                        Repeater {
                            model: vista.problemas
                            Rectangle {
                                id: filaP
                                required property var modelData
                                readonly property bool sel: vista.problema && vista.problema.id === modelData.id
                                width: listaProblemas.width
                                height: 48
                                color: sel ? "#0f171b" : Tema.panel2
                                border.color: sel ? vista.color(modelData.gravedad) : Tema.borde
                                Column {
                                    x: 8; y: 6
                                    width: parent.width - 16
                                    spacing: 3
                                    Row {
                                        spacing: 6
                                        Etiqueta { texto: filaP.modelData.gravedad; tono: vista.color(filaP.modelData.gravedad) }
                                        Text { text: filaP.modelData.titulo; color: Tema.texto; font.family: Tema.mono; font.pixelSize: Tema.letraMini; width: listaProblemas.width - 110; elide: Text.ElideRight }
                                    }
                                    Text {
                                        text: filaP.modelData.componente + (filaP.modelData.veces > 1 ? " · visto " + filaP.modelData.veces + " veces desde " + vista.fecha(filaP.modelData.primera_vez) : "")
                                        color: filaP.modelData.veces > 1 ? Tema.ambar : Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini
                                    }
                                }
                                Pulsar { onPulsado: vista.elegido = filaP.modelData.id }
                            }
                        }
                    }
                }
            }

            // Detalle
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ident: "X2"
                etiqueta: vista.problema ? vista.problema.titulo : "DETAIL"
                acento: vista.problema ? vista.color(vista.problema.gravedad) : Tema.borde
                Flickable {
                    anchors.fill: parent
                    contentHeight: detalle.implicitHeight
                    clip: true
                    Column {
                        id: detalle
                        width: parent.width
                        spacing: 9
                        visible: !!vista.problema
                        Text { text: vista.problema ? vista.problema.gravedad + " · " + vista.problema.componente + " · " + String(vista.problema.area).toUpperCase() : ""; color: vista.problema ? vista.color(vista.problema.gravedad) : Tema.texto; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1 }
                        Bloque { titulo: "DETECTADO"; lineas: vista.problema ? vista.problema.detectado || [] : [] }
                        Bloque { titulo: "CAUSAS POSIBLES (no confirmadas)"; lineas: vista.problema ? vista.problema.causas_probables || [] : []; tono: Tema.secundario }
                        Bloque { titulo: "CONSECUENCIAS"; lineas: vista.problema && vista.problema.consecuencias ? [vista.problema.consecuencias] : [] }
                        Bloque { titulo: "QUÉ HACER"; lineas: vista.problema ? vista.problema.recomendacion || [] : []; tono: Tema.cian }
                        Column {
                            id: bloqueRep
                            width: parent.width
                            spacing: 4
                            visible: !!(vista.problema && vista.problema.reparacion)
                            readonly property var rep: vista.problema ? vista.problema.reparacion : null
                            Text { text: "REPARACIÓN" + (parent.rep && parent.rep.root ? " · PIDE CONTRASEÑA DE ADMINISTRADOR" : ""); color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1 }
                            Text { width: parent.width; text: parent.rep ? parent.rep.descripcion : ""; color: Tema.texto; font.family: Tema.mono; font.pixelSize: Tema.letraMini; wrapMode: Text.WordWrap }
                            Rectangle {
                                width: parent.width
                                height: ordenes.implicitHeight + 12
                                color: Tema.fondo; border.color: Tema.borde
                                Column {
                                    id: ordenes
                                    x: 8; y: 6
                                    width: parent.width - 16
                                    Repeater {
                                        model: bloqueRep.rep ? bloqueRep.rep.ordenes || [] : []
                                        Text { required property var modelData; width: ordenes.width; text: "$ " + modelData; color: Tema.verde; font.family: Tema.mono; font.pixelSize: Tema.letraMini; wrapMode: Text.WrapAnywhere }
                                    }
                                }
                            }
                            Text { visible: !!(parent.rep && parent.rep.copia); text: parent.rep && parent.rep.copia ? "Antes se copia: " + parent.rep.copia : ""; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                            Rectangle {
                                width: tRep.implicitWidth + 18; height: 24
                                color: "transparent"; border.color: Tema.ambar
                                Text { id: tRep; anchors.centerIn: parent; text: "REPARAR (en una terminal, con confirmación)"; color: Tema.ambar; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                                Pulsar { onPulsado: vista.reparar(vista.problema.id) }
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 170
            Layout.maximumHeight: 170
            spacing: 10

            // Comprobaciones por area
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 3
                ident: "X3"
                etiqueta: "CHECKS"
                Flickable {
                    anchors.fill: parent
                    contentHeight: areas.implicitHeight
                    clip: true
                    Flow {
                        id: areas
                        width: parent.width
                        spacing: 14
                        Repeater {
                            model: vista.ultimo ? vista.ultimo.areas || [] : []
                            Column {
                                id: area
                                required property var modelData
                                width: (areas.width - 28) / 3
                                spacing: 2
                                Text { text: area.modelData.nombre; color: Tema.cian; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1.5 }
                                Repeater {
                                    model: area.modelData.comprobaciones || []
                                    Text {
                                        required property var modelData
                                        width: area.width
                                        text: vista.textoEstado(modelData.estado).padEnd(13) + " " + modelData.nombre
                                        color: vista.color(modelData.estado)
                                        font.family: Tema.mono; font.pixelSize: Tema.letraMini
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Historial
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 2
                ident: "X4"
                etiqueta: "HISTORY"
                Flickable {
                    anchors.fill: parent
                    contentHeight: hist.implicitHeight
                    clip: true
                    Column {
                        id: hist
                        width: parent.width
                        spacing: 2
                        Text { visible: !(vista.historial && (vista.historial.problemas || []).length); text: "Sin problemas registrados."; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                        Repeater {
                            model: vista.historial ? (vista.historial.problemas || []).slice(0, 30) : []
                            Text {
                                required property var modelData
                                width: hist.width
                                elide: Text.ElideRight
                                text: (modelData.estado === "resuelto" ? "RESUELTO " : "ACTIVO   ") + modelData.titulo + " · " + modelData.veces + "× · " + vista.fecha(modelData.ultima_vez)
                                      + ((modelData.reparaciones || []).length ? " · reparado " + modelData.reparaciones.length + "×" : "")
                                color: modelData.estado === "resuelto" ? Tema.verde : vista.color(modelData.gravedad)
                                font.family: Tema.mono; font.pixelSize: Tema.letraMini
                            }
                        }
                    }
                }
            }
        }
    }
}
