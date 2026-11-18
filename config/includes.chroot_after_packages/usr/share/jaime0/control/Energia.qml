import QtQuick
import QtQuick.Layouts
import Quickshell.Io

// POWER: estado energetico (orden "energia" de jaime0-servicio) y lo que se puede ajustar sin
// root. Cada dato dice de donde sale: MEDIDO (lo da el hardware), CALCULADO, ESTIMADO (supone
// que el consumo sigue igual) o N/D. Cada ajuste tiene un unico dueno: el perfil de energia lo
// pone el perfil de ZYRON (PROFILES; aqui solo se elige), la inactividad son ajustes de
// jaime0-ajustes y las reacciones al cargador o a la bateria son reglas de AUTOMATION. Lo que
// necesita root (logind, limite de carga, gobernador) solo se muestra.
Item {
    id: vista

    property var datos: null
    property var instante: null
    property var serie: null
    property int rango: 0
    property string mensaje: ""
    property bool mensajeError: false

    readonly property var rangos: [{ id: "1h", nombre: "1 H" }, { id: "24h", nombre: "24 H" }, { id: "historia", nombre: "HISTORY" }]
    readonly property var bat: datos ? datos.bateria : null
    readonly property var gpus: datos && datos.graficas ? datos.graficas.graficas || [] : []
    readonly property var inact: datos ? datos.inactividad : null
    readonly property var energeticos: ["balanced", "performance", "power-saver", "custom"]

    function tonoOrigen(o) { return ({ medido: Tema.texto, calculado: Tema.cian, estimado: Tema.ambar })[o] || Tema.apagado; }
    function etiquetaOrigen(o) { return ({ medido: "MEDIDO", calculado: "CALCULADO", estimado: "ESTIMADO" })[o] || "N/D"; }
    function valor(d, unidad, dec) {
        if (!d || d.valor === null || d.valor === undefined) return "N/D";
        return (dec === undefined ? d.valor : Number(d.valor).toFixed(dec)) + (unidad ? " " + unidad : "");
    }
    function duracion(d) {
        if (!d || d.valor === null) return "N/D";
        return Math.floor(d.valor / 60) + "h " + String(d.valor % 60).padStart(2, "0") + "m";
    }
    function textoEnergia(e) {
        const n = ({ balanced: "equilibrado", performance: "alto rendimiento", "power-saver": "ahorro" })[e];
        return n ? "perfil de energía " + n : "no cambia el perfil de energía";
    }
    function textoAccion(a) {
        return ({ suspend: "suspender", ignore: "nada", lock: "bloquear", poweroff: "apagar", hibernate: "hibernar",
                  "hybrid-sleep": "suspensión híbrida", "suspend-then-hibernate": "suspender y luego hibernar" })[a] || a || "N/D";
    }
    function textoMin(m) { return m === null || m === undefined ? "N/D" : m === 0 ? "nunca" : m + " min"; }

    function leer() { consulta.pedir({ orden: "energia" }); }
    function pedirSerie() { consultaSerie.pedir({ orden: "serie", rango: rangos[rango].id }); }
    function ponerPerfil(id) { cambioPerfil.pedir({ orden: "perfil", valor: id }); }
    function ponerAjuste(clave, v) {
        escritor.command = ["jaime0-ajustes", "poner", clave, String(v)];
        escritor.running = true;
    }

    Consulta { id: consulta; onRespuesta: d => { if (d.ok !== false) vista.datos = d; else { vista.mensaje = d.error || "sin respuesta del servicio"; vista.mensajeError = true; } } }
    Consulta { id: consultaSerie; onRespuesta: d => vista.serie = d.ok ? d : null }
    Consulta {
        id: cambioPerfil
        onRespuesta: d => {
            vista.mensajeError = d.ok === false || (d.fallos || []).length > 0;
            vista.mensaje = d.ok === false ? (d.error || "no se pudo cambiar el perfil")
                          : (d.fallos || []).length ? "Perfil " + d.nombre + " con fallos: " + d.fallos.join("; ") : "Perfil " + d.nombre + " aplicado";
            vista.leer();
        }
    }
    Process {
        id: escritor
        stderr: StdioCollector { onStreamFinished: if (text.trim() !== "") { vista.mensaje = text.trim().replace(/^jaime0-ajustes: /, ""); vista.mensajeError = true; } }
        onExited: code => { if (code === 0) { vista.mensaje = "Guardado: se aplica al momento"; vista.mensajeError = false; } vista.leer(); }
    }
    Component.onCompleted: { leer(); pedirSerie(); }
    onRangoChanged: { serie = null; pedirSerie(); }
    Timer { interval: 10000; running: true; repeat: true; onTriggered: { vista.leer(); vista.pedirSerie(); } }

    component Linea: RowLayout {
        property string nombre: ""
        property string texto: ""
        property string origen: ""
        property color tono: Tema.texto
        width: parent ? parent.width : 0
        spacing: 6
        Text { text: parent.nombre; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini; Layout.preferredWidth: 100; elide: Text.ElideRight; Layout.alignment: Qt.AlignTop }
        Text { text: parent.texto; color: parent.origen === "no_disponible" ? Tema.apagado : parent.tono; font.family: Tema.mono; font.pixelSize: Tema.letraMini; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Text { visible: parent.origen !== ""; text: vista.etiquetaOrigen(parent.origen); color: vista.tonoOrigen(parent.origen); font.family: Tema.mono; font.pixelSize: Tema.letraMini; Layout.alignment: Qt.AlignTop }
    }
    component Titulo: Text { color: Tema.cian; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1.5 }
    component Nota: Text { width: parent ? parent.width : 0; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini; wrapMode: Text.WordWrap }
    component Boton: Rectangle {
        property string texto: ""
        property color tono: Tema.cian
        property bool activo: true
        property bool marcado: false
        signal pulsado()
        width: tB.implicitWidth + 14; height: 20
        color: marcado ? Qt.rgba(tono.r, tono.g, tono.b, 0.15) : "transparent"
        border.color: activo ? tono : Tema.rejilla
        Text { id: tB; anchors.centerIn: parent; text: parent.texto; color: parent.activo ? parent.tono : Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1 }
        Pulsar { enabled: parent.activo; onPulsado: parent.pulsado() }
    }
    component Minutos: RowLayout {
        property string nombre: ""
        property string clave: ""
        property var actual: null
        property int paso: 5
        property int maximo: 120
        property bool editable: true
        width: parent ? parent.width : 0
        spacing: 6
        Text { text: parent.nombre; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini; Layout.fillWidth: true }
        Boton { texto: "−"; activo: parent.editable && parent.actual > 0; onPulsado: vista.ponerAjuste(parent.clave, Math.max(0, parent.actual - parent.paso)) }
        Text { text: vista.textoMin(parent.actual); color: Tema.texto; font.family: Tema.mono; font.pixelSize: Tema.letraMini; Layout.preferredWidth: 52; horizontalAlignment: Text.AlignHCenter }
        Boton { texto: "+"; activo: parent.editable && parent.actual !== null && parent.actual < parent.maximo; onPulsado: vista.ponerAjuste(parent.clave, Math.min(parent.maximo, parent.actual + parent.paso)) }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        // ── P0 · Resumen ────────────────────────────────────────────────────────
        Marco {
            Layout.fillWidth: true
            Layout.preferredHeight: 84
            ident: "P0"
            etiqueta: "POWER MANAGER"
            acento: vista.bat && vista.bat.estado === "descargando" ? Tema.ambar : Tema.verde
            RowLayout {
                width: parent.width
                spacing: 24
                Column {
                    spacing: 4
                    Text {
                        text: !vista.datos ? "LEYENDO…" : vista.bat ? vista.valor(vista.bat.nivel, "%") + "  " + vista.bat.estado.toUpperCase() : "SIN BATERÍA"
                        color: Tema.texto; font.family: Tema.mono; font.pixelSize: Tema.letraDato
                    }
                    Text {
                        text: !vista.datos ? "" : (vista.datos.cargador === true ? "Cargador conectado" : vista.datos.cargador === false ? "Sin cargador" : "Cargador: N/D")
                              + (vista.bat && vista.bat.autonomia_min.valor !== null ? "  ·  autonomía ≈ " + vista.duracion(vista.bat.autonomia_min) + " (estimada)" : "")
                              + (vista.bat && vista.bat.hasta_llena_min.valor !== null ? "  ·  llena en ≈ " + vista.duracion(vista.bat.hasta_llena_min) + " (estimado)" : "")
                        color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini
                    }
                }
                Column {
                    Layout.fillWidth: true
                    spacing: 4
                    Text {
                        text: vista.datos ? "PERFIL " + (vista.datos.perfil.nombre || "N/D") + "  ·  ENERGÍA " + (vista.datos.perfil.energia || "N/D").toUpperCase() : ""
                        color: Tema.cian; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1
                    }
                    Text {
                        text: vista.datos && vista.datos.perfil.retencion ? "Retenido por el perfil de " + Tema.producto + " (power-profiles-daemon)" : vista.datos && vista.datos.perfil.degradado ? "△ power-profiles-daemon limita el rendimiento: " + vista.datos.perfil.degradado : ""
                        color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini
                    }
                }
                Column {
                    spacing: 4
                    Row {
                        spacing: 8
                        Repeater {
                            model: ["medido", "calculado", "estimado", "no_disponible"]
                            Text { required property var modelData; text: "■ " + vista.etiquetaOrigen(modelData); color: vista.tonoOrigen(modelData); font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                        }
                    }
                    Text { visible: vista.mensaje !== ""; text: (vista.mensajeError ? "△ " : "✓ ") + vista.mensaje; color: vista.mensajeError ? Tema.ambar : Tema.verde; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 240
            spacing: 10

            // ── P1 · Bateria ────────────────────────────────────────────────────
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 3
                ident: "P1"
                etiqueta: "BATTERY"
                Flickable {
                    anchors.fill: parent
                    contentHeight: colBat.implicitHeight
                    clip: true
                    Column {
                        id: colBat
                        width: parent.width
                        spacing: 3
                        Nota { visible: !!vista.datos && !vista.bat; text: "Este equipo no tiene batería (o el firmware no la expone en /sys/class/power_supply)." }
                        Linea { visible: !!vista.bat; nombre: "Nivel"; texto: vista.valor(vista.bat && vista.bat.nivel, "%"); origen: vista.bat ? vista.bat.nivel.origen : "" }
                        Linea { visible: !!vista.bat; nombre: "Capacidad diseño"; texto: vista.bat ? vista.valor(vista.bat.capacidad_diseno, vista.bat.unidad) : ""; origen: vista.bat ? vista.bat.capacidad_diseno.origen : "" }
                        Linea { visible: !!vista.bat; nombre: "Capacidad actual"; texto: vista.bat ? vista.valor(vista.bat.capacidad_actual, vista.bat.unidad) : ""; origen: vista.bat ? vista.bat.capacidad_actual.origen : "" }
                        Linea { visible: !!vista.bat; nombre: "Salud"; texto: vista.valor(vista.bat && vista.bat.salud, "%", 0); origen: vista.bat ? vista.bat.salud.origen : "" }
                        Linea {
                            visible: !!vista.bat; nombre: "Ciclos"
                            texto: vista.bat ? vista.valor(vista.bat.ciclos) + (vista.bat.ciclos_sin_contar ? " · puede no contarlos" : "") : ""
                            origen: vista.bat ? vista.bat.ciclos.origen : ""
                        }
                        Linea { visible: !!vista.bat; nombre: "Consumo"; texto: vista.valor(vista.bat && vista.bat.potencia, "W", 1); origen: vista.bat ? vista.bat.potencia.origen : "" }
                        Linea { visible: !!vista.bat; nombre: "Descarga"; texto: vista.bat && vista.bat.descarga_pct_h.valor !== null ? vista.bat.descarga_pct_h.valor + " %/h" : "N/D · faltan 10 min en batería"; origen: vista.bat ? vista.bat.descarga_pct_h.origen : "" }
                        Linea { visible: !!vista.bat; nombre: "Autonomía"; texto: vista.duracion(vista.bat && vista.bat.autonomia_min); origen: vista.bat ? vista.bat.autonomia_min.origen : "" }
                        Linea { visible: !!vista.bat; nombre: "Tensión"; texto: vista.valor(vista.bat && vista.bat.voltaje, "V", 2); origen: vista.bat ? vista.bat.voltaje.origen : "" }
                        Linea { visible: !!vista.bat; nombre: "Límite de carga"; texto: vista.bat && vista.bat.limite_carga.valor !== null ? vista.bat.limite_carga.valor + " % · cambiarlo pide root" : "N/D · no lo expone"; origen: vista.bat ? vista.bat.limite_carga.origen : "" }
                        Linea { visible: !!vista.bat; nombre: "Batería"; texto: vista.bat ? [vista.bat.fabricante, vista.bat.modelo, vista.bat.tecnologia].filter(x => x).join(" · ") || "N/D" : "" }
                        Item { width: 1; height: 6 }
                        Titulo { text: "TEMPERATURAS" }
                        Linea { readonly property var c: vista.instante && vista.instante.cpu ? vista.instante.cpu.temp : null; nombre: "CPU"; texto: c !== null ? c.toFixed(0) + " °C" : "N/D · sin sensor"; origen: c !== null ? "medido" : "no_disponible" }
                        Linea { readonly property var g: vista.instante && vista.instante.gpu ? vista.instante.gpu.temp : null; nombre: "GPU NVIDIA"; texto: g !== null ? g.toFixed(0) + " °C" : "N/D · dormida o sin ella"; origen: g !== null ? "medido" : "no_disponible" }
                    }
                }
            }

            // ── P2 · Graficas ───────────────────────────────────────────────────
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 3
                ident: "P2"
                etiqueta: "GRAPHICS"
                Flickable {
                    anchors.fill: parent
                    contentHeight: colGpu.implicitHeight
                    clip: true
                    Column {
                        id: colGpu
                        width: parent.width
                        spacing: 3
                        Nota {
                            visible: !!vista.datos
                            color: Tema.texto
                            text: !vista.datos ? "" : ({ offload: "PRIME render offload: el escritorio usa la integrada y la NVIDIA solo se enciende para lo que abras con «prime-run PROGRAMA».",
                                                         nvidia_principal: "La NVIDIA dibuja el escritorio: no puede dormirse mientras haya sesión gráfica.",
                                                         sin_driver: "Hay una NVIDIA pero su controlador no está cargado: el escritorio usa la integrada (detalle: jaime0-nvidia)." })[vista.datos.graficas.prime]
                                  || "Sin gráfica NVIDIA: nada que repartir."
                        }
                        Repeater {
                            model: vista.gpus
                            Column {
                                id: gpu
                                required property var modelData
                                width: colGpu.width
                                spacing: 2
                                topPadding: 6
                                Titulo { text: gpu.modelData.fabricante.toUpperCase() + " · " + gpu.modelData.rol.toUpperCase() + (gpu.modelData.principal ? " · PANTALLA" : "") }
                                Linea { nombre: "Controlador"; texto: gpu.modelData.driver || "sin controlador"; tono: gpu.modelData.driver ? Tema.texto : Tema.ambar }
                                Linea {
                                    nombre: "Energía"
                                    texto: (gpu.modelData.energia === "suspended" ? "dormida (casi no gasta)" : gpu.modelData.energia === "active" ? "despierta" : (gpu.modelData.energia || "N/D"))
                                           + (gpu.modelData.control === "on" ? " · siempre (control = on)" : "")
                                    origen: gpu.modelData.energia ? "medido" : "no_disponible"
                                    tono: gpu.modelData.energia === "active" && gpu.modelData.rol === "dedicada" ? Tema.ambar : Tema.texto
                                }
                                Linea { visible: gpu.modelData.modulo !== undefined; nombre: "Módulo"; texto: gpu.modelData.modulo ? gpu.modelData.modulo + (gpu.modelData.modeset === "Y" ? " · modeset" : "") : "no cargado" }
                                Linea { visible: !!gpu.modelData.medidas; nombre: "Consumo"; texto: gpu.modelData.medidas ? vista.valor(gpu.modelData.medidas.vatios, "W", 1) + " · uso " + vista.valor(gpu.modelData.medidas.uso, "%", 0) : ""; origen: gpu.modelData.medidas ? gpu.modelData.medidas.vatios.origen : "" }
                                Linea { visible: gpu.modelData.rol === "dedicada" && gpu.modelData.energia !== "active" && gpu.modelData.modulo !== undefined; nombre: "Consumo"; texto: "sin medir: medirlo la despertaría"; origen: "no_disponible" }
                                Nota {
                                    visible: !!gpu.modelData.uso
                                    color: gpu.modelData.uso && gpu.modelData.uso.procesos.length ? Tema.ambar : Tema.secundario
                                    text: !gpu.modelData.uso ? "" : gpu.modelData.uso.procesos.length
                                          ? "La usan: " + gpu.modelData.uso.procesos.map(p => p.nombre + " (" + p.pid + ")").join(", ") + ". Mientras sigan abiertos no se duerme."
                                          : "Ningún programa tuyo la usa" + (gpu.modelData.uso.parcial ? " (los de otros usuarios no se ven sin root)." : ".")
                                }
                            }
                        }
                        Item { width: 1; height: 6 }
                        Titulo { text: "CPU" }
                        Linea { nombre: "Controlador"; texto: vista.datos && vista.datos.cpu.driver ? vista.datos.cpu.driver + (vista.datos.cpu.gobernador ? " · " + vista.datos.cpu.gobernador : "") : "N/D"; origen: vista.datos && vista.datos.cpu.driver ? "medido" : "no_disponible" }
                        Linea { nombre: "Preferencia (EPP)"; texto: vista.datos && vista.datos.cpu.epp ? vista.datos.cpu.epp : "N/D"; origen: vista.datos && vista.datos.cpu.epp ? "medido" : "no_disponible" }
                        Linea { nombre: "Turbo"; texto: !vista.datos || vista.datos.cpu.turbo === null ? "N/D" : vista.datos.cpu.turbo ? "activado" : "desactivado"; origen: vista.datos && vista.datos.cpu.turbo !== null ? "medido" : "no_disponible" }
                        Linea { nombre: "Perfil plataforma"; texto: vista.datos && vista.datos.cpu.perfil_plataforma ? vista.datos.cpu.perfil_plataforma : "N/D"; origen: vista.datos && vista.datos.cpu.perfil_plataforma ? "medido" : "no_disponible" }
                        Nota { text: "Los ajusta el perfil de energía (power-profiles-daemon): no se tocan a mano." }
                    }
                }
            }

            // ── P3 · Ajustes de energia ─────────────────────────────────────────
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 4
                ident: "P3"
                etiqueta: "ENERGY SETTINGS"
                acento: Tema.verde
                Flickable {
                    anchors.fill: parent
                    contentHeight: colAj.implicitHeight
                    clip: true
                    Column {
                        id: colAj
                        width: parent.width
                        spacing: 4
                        Titulo { text: "PERFIL DE ENERGÍA" }
                        Flow {
                            width: parent.width
                            spacing: 6
                            Repeater {
                                model: vista.datos ? vista.datos.perfiles.filter(p => vista.energeticos.includes(p.id)) : []
                                Boton {
                                    required property var modelData
                                    texto: modelData.nombre
                                    marcado: vista.datos.perfil.activo === modelData.id
                                    tono: marcado ? Tema.verde : Tema.cian
                                    onPulsado: vista.ponerPerfil(modelData.id)
                                }
                            }
                        }
                        Repeater {
                            model: vista.datos ? vista.datos.perfiles.filter(p => vista.energeticos.includes(p.id)) : []
                            Nota {
                                required property var modelData
                                color: vista.datos.perfil.activo === modelData.id ? Tema.texto : Tema.secundario
                                text: modelData.nombre + ": " + vista.textoEnergia(modelData.energia) + (modelData.cambios.length > (modelData.energia ? 1 : 0) ? "; además " + modelData.cambios.filter(c => !c.startsWith("Energía")).join(", ").toLowerCase() : "") + "."
                            }
                        }
                        Nota { text: "Son los perfiles de PROFILES (tecla 3): aquí solo se elige. FOCUS y MULTIMEDIA dejan la energía como esté." }
                        Item { width: 1; height: 4 }
                        Titulo { text: "INACTIVIDAD" }
                        Nota {
                            visible: !!(vista.inact && vista.inact.personalizado)
                            color: Tema.ambar
                            text: "Tu ~/.config/hypr/hypridle.conf está personalizado: manda el tuyo y estos tiempos no se aplican."
                        }
                        Nota { visible: !!(vista.inact && vista.inact.inhibida_por); color: Tema.ambar; text: vista.inact && vista.inact.inhibida_por ? "El perfil " + vista.inact.inhibida_por + " evita ahora el bloqueo y el apagado de pantalla." : "" }
                        Minutos { nombre: "Bloquear"; clave: "inactividad_bloqueo"; actual: vista.inact ? vista.inact.bloqueo : null; editable: !!vista.inact && !vista.inact.personalizado }
                        Minutos { nombre: "Apagar pantalla"; clave: "inactividad_pantalla"; actual: vista.inact ? vista.inact.pantalla : null; editable: !!vista.inact && !vista.inact.personalizado }
                        Minutos { nombre: "Suspender"; clave: "inactividad_suspender"; actual: vista.inact ? vista.inact.suspender : null; maximo: 240; paso: 10; editable: !!vista.inact && !vista.inact.personalizado }
                        RowLayout {
                            width: parent.width
                            Text { text: "Suspender con cargador"; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini; Layout.fillWidth: true }
                            Boton {
                                texto: !vista.inact || vista.inact.con_cargador === null ? "N/D" : vista.inact.con_cargador ? "SÍ" : "NO"
                                activo: !!vista.inact && vista.inact.con_cargador !== null && !vista.inact.personalizado
                                onPulsado: vista.ponerAjuste("suspender_con_cargador", vista.inact.con_cargador ? "no" : "si")
                            }
                        }
                        Item { width: 1; height: 4 }
                        Titulo { text: "SUSPENSIÓN" }
                        Linea {
                            nombre: "Modo"
                            texto: !vista.datos ? "" : !vista.datos.suspension.puede_suspender ? "este equipo no puede suspender" : (vista.datos.suspension.modo === "deep" ? "deep (en RAM, gasta muy poco)" : vista.datos.suspension.modo === "s2idle" ? "s2idle (gasta algo más)" : vista.datos.suspension.modo || "N/D")
                            origen: vista.datos && vista.datos.suspension.modo ? "medido" : "no_disponible"
                        }
                        Linea { nombre: "Al cerrar la tapa"; texto: vista.datos ? vista.textoAccion(vista.datos.suspension.tapa) + " · con cargador: " + vista.textoAccion(vista.datos.suspension.tapa_cargador) : "" }
                        Nota { text: "La tapa y el botón los decide logind (/etc/systemd/logind.conf, requiere root)." }
                        Item { width: 1; height: 4 }
                        Titulo { text: "AL CONECTAR O DESCONECTAR" }
                        Nota { visible: !!vista.datos && vista.datos.reglas.length === 0; text: "Ninguna regla reacciona a la batería, al cargador ni a la suspensión. Se crean en AUTOMATION (tecla 4), p. ej. «al desconectar el cargador → POWER SAVER»." }
                        Repeater {
                            model: vista.datos ? vista.datos.reglas : []
                            Linea { required property var modelData; nombre: modelData.activa ? "ACTIVA" : "PAUSADA"; texto: modelData.nombre + " · " + (modelData.acciones || []).join(", "); tono: modelData.activa ? Tema.texto : Tema.apagado }
                        }
                    }
                }
            }
        }

        // ── P4 · Historial ──────────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 190
            Layout.maximumHeight: 190
            spacing: 10
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 7
                ident: "P4"
                etiqueta: "POWER HISTORY"
                Row {
                    id: chipsRango
                    spacing: 6
                    Repeater {
                        model: vista.rangos
                        Boton {
                            required property var modelData
                            required property int index
                            texto: modelData.nombre
                            marcado: vista.rango === index
                            onPulsado: vista.rango = index
                        }
                    }
                }
                Text {
                    anchors.centerIn: parent
                    visible: !vista.serie
                    text: "SIN DATOS SUFICIENTES PARA ESTE RANGO"
                    color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini
                }
                RowLayout {
                    visible: !!vista.serie
                    anchors.top: chipsRango.bottom
                    anchors.topMargin: 6
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    spacing: 8
                    Grafica {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        decimales: 0
                        t: vista.serie ? vista.serie.t : []
                        series: [vista.serieDe("bateria", "BATERÍA", Tema.verde), vista.serieDe("cargador", "CARGADOR", Tema.cian, 100)]
                        huecos: vista.serie ? vista.serie.huecos : []
                        eventos: vista.serie ? (vista.serie.eventos || []).filter(e => e.tipo === "perfil" && e.valor) : []
                    }
                    Grafica {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        unidad: "W"
                        autoescala: true
                        t: vista.serie ? vista.serie.t : []
                        series: [vista.serieDe("vatios", "CONSUMO", Tema.ambar)]
                        huecos: vista.serie ? vista.serie.huecos : []
                        Text { anchors.centerIn: parent; visible: !vista.conDatos(["vatios"]); text: "SIN MEDIDA DE CONSUMO"; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                    }
                    Grafica {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        unidad: "°C"
                        minimo: 20
                        maximo: 105
                        decimales: 0
                        t: vista.serie ? vista.serie.t : []
                        series: [vista.serieDe("temp", "CPU", Tema.ambar), vista.serieDe("gpu_temp", "GPU", Tema.cian)]
                        huecos: vista.serie ? vista.serie.huecos : []
                        Text { anchors.centerIn: parent; visible: !vista.conDatos(["temp", "gpu_temp"]); text: "SIN SENSORES DE TEMPERATURA"; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                    }
                }
            }
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 3
                id: marcoPerfiles
                ident: "P5"
                etiqueta: "BY ENERGY PROFILE"
                readonly property var hist: vista.datos ? vista.datos.historial : null
                Column {
                    width: parent.width
                    spacing: 3
                    Linea {
                        nombre: "Con cargador 24 h"
                        texto: !marcoPerfiles.hist || !marcoPerfiles.hist.cargador_24h.minutos ? "sin datos aún"
                               : (marcoPerfiles.hist.cargador_24h.conectado / 60).toFixed(1) + " h de " + (marcoPerfiles.hist.cargador_24h.minutos / 60).toFixed(1) + " h medidas"
                        origen: marcoPerfiles.hist && marcoPerfiles.hist.cargador_24h.minutos ? "medido" : "no_disponible"
                    }
                    Text { text: "EN BATERÍA         MIN    W MEDIO   %/h"; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                    Repeater {
                        model: marcoPerfiles.hist ? marcoPerfiles.hist.perfiles : []
                        Text {
                            required property var modelData
                            text: modelData.perfil.padEnd(16) + String(modelData.minutos).padStart(5) + "   "
                                  + (modelData.vatios.valor !== null ? modelData.vatios.valor.toFixed(1).padStart(7) : "    N/D") + "   "
                                  + (modelData.descarga_pct_h.valor !== null ? modelData.descarga_pct_h.valor.toFixed(1) : "N/D")
                            color: modelData.vatios.valor !== null ? Tema.texto : Tema.apagado
                            font.family: Tema.mono; font.pixelSize: Tema.letraMini
                        }
                    }
                    Nota {
                        text: marcoPerfiles.hist && marcoPerfiles.hist.perfiles.length
                              ? "Calculado con los minutos enteros en batería de las últimas 48 h (10 min como mínimo por perfil)."
                              : "Aún no hay minutos en batería con un perfil conocido: se calcula solo con datos medidos, nada se rellena."
                    }
                }
            }
        }
    }

    function conDatos(nombres) {
        return !!serie && nombres.some(n => serie.metricas[n] && (serie.metricas[n].med || []).some(v => v !== null));
    }
    function serieDe(nombre, etiqueta, color, escala) {
        const m = serie && serie.metricas && serie.metricas[nombre] ? serie.metricas[nombre] : { med: [] };
        const f = v => v === null || v === undefined ? null : (escala ? v * escala : v);
        return { nombre: etiqueta, color: color, med: (m.med || []).map(f), min: m.min ? m.min.map(f) : null, max: m.max ? m.max.map(f) : null };
    }
}
