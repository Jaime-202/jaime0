import QtQuick
import QtQuick.Layouts
import Quickshell.Io

// UPDATES: actualizaciones de Jaime0 (jaime0-update, publicaciones firmadas) y de Debian (apt,
// via "actualizaciones"). Los datos vienen del servicio (ordenes "actualizaciones" y
// "actualizaciones_comprobar"); el estado es siempre el real: la fase la escribe el propio
// actualizador. Instalar, revertir y recuperar abren una terminal con jaime0-update, que
// muestra los cambios y pide autorizacion: la ventana nunca instala nada por su cuenta.
Item {
    id: vista

    property var datos: null
    property var plan: null                 // de la ultima comprobacion en esta ventana
    property string mensaje: ""
    property bool mensajeError: false
    property bool comprobando: false

    readonly property var j: datos ? datos.jaime0 : null
    readonly property var deb: datos ? datos.debian : null
    readonly property var disp: j ? j.disponible : null

    // Estado visible: solo a partir de datos reales.
    readonly property string estado: {
        if (!datos) return "LOADING";
        if (!j) return "UNAVAILABLE";
        if (j.en_curso) return ({ descargando: "DOWNLOADING", verificando: "VERIFYING", instalando: "INSTALLING" })[j.en_curso.fase] || "INSTALLING";
        if (comprobando || datos.comprobando_desde) return "CHECKING";
        if (j.interrumpida || (j.ultima && j.ultima.resultado === "fallo")) return "UPDATE FAILED";
        if (j.nueva) return "UPDATE AVAILABLE";
        if (!j.comprobado) return "NOT CHECKED";
        return "UP TO DATE";
    }
    readonly property color colorEstado: estado === "UP TO DATE" ? Tema.verde
        : estado === "UPDATE AVAILABLE" || estado === "CHECKING" || estado === "DOWNLOADING"
          || estado === "VERIFYING" || estado === "INSTALLING" ? Tema.cian
        : estado === "UPDATE FAILED" ? Tema.rojo : Tema.ambar
    readonly property string explicacion: {
        if (!datos) return "Leyendo el estado…";
        if (!j) return datos.error_jaime0 || "No se puede saber el estado de las actualizaciones de Jaime0.";
        if (j.en_curso) return "jaime0-update está trabajando en la terminal (" + j.en_curso.fase + (j.en_curso.version ? ", " + j.en_curso.version : "") + "). No cierres la terminal.";
        if (estado === "CHECKING") return "Descargando y verificando el manifiesto firmado y la lista de paquetes de Debian…";
        if (j.interrumpida) return "Una actualización se cortó a medias. RECUPERAR deja los archivos como estaban antes.";
        if (estado === "UPDATE FAILED") return "La última operación falló: " + (j.ultima.detalle || "sin detalle") + ". Nada quedó a medias.";
        if (j.nueva) return "Jaime0 " + disp.version + " (canal " + disp.canal + ") está publicada y firmada. INSTALAR enseña antes qué archivos cambian.";
        if (!j.comprobado) return "Aún no se ha comprobado si hay versiones nuevas.";
        return "No hay ninguna versión más nueva en el canal " + j.canal + ".";
    }

    function fecha(t) {
        if (!t) return "—";
        const f = new Date((typeof t === "number" ? t : Date.parse(t) / 1000) * 1000);
        if (isNaN(f.getTime())) return String(t);
        const p = n => String(n).padStart(2, "0");
        return p(f.getDate()) + "/" + p(f.getMonth() + 1) + "/" + f.getFullYear() + " " + p(f.getHours()) + ":" + p(f.getMinutes());
    }
    function leer() { consulta.pedir({ orden: "actualizaciones" }); }
    function comprobar() {
        vista.comprobando = true;
        vista.mensaje = "";
        comprobacion.pedir({ orden: "actualizaciones_comprobar" });
    }
    function terminal(orden) {
        lanzador.command = ["kitty", "--class", "jaime0-update", "-e", "sh", "-c",
                            orden + "; printf '\\nPulsa Intro para cerrar. '; read -r _"];
        lanzador.running = true;
        vista.mensaje = "Abierta una terminal con: " + orden;
        vista.mensajeError = false;
    }

    Consulta {
        id: consulta
        onRespuesta: d => { if (d.ok !== false) vista.datos = d; }
    }
    Consulta {
        id: comprobacion
        onRespuesta: d => {
            vista.comprobando = false;
            if (d.ok === false) { vista.mensaje = d.error || "no se pudo comprobar"; vista.mensajeError = true; return; }
            vista.datos = d;
            vista.plan = d.plan || null;
            const avisos = d.avisos || [];
            vista.mensaje = avisos.length ? avisos.join(" · ") : "Comprobado";
            vista.mensajeError = avisos.length > 0;
        }
    }
    Process { id: lanzador }
    Component.onCompleted: leer()
    // Mientras la seccion esta abierta: la fase real de una instalacion en la terminal.
    Timer { interval: 4000; running: true; repeat: true; onTriggered: vista.leer() }

    component Dato: Row {
        property string clave: ""
        property string valor: ""
        property color tono: Tema.texto
        spacing: 10
        Text { width: 170; text: parent.clave; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
        Text { width: 250; elide: Text.ElideRight; text: parent.valor; color: parent.tono; font.family: Tema.mono; font.pixelSize: Tema.letra }
    }
    component Boton: Rectangle {
        property string texto: ""
        property color tono: Tema.cian
        property bool activo: true
        signal pulsado()
        width: tBoton.implicitWidth + 18; height: 24
        color: "transparent"
        border.color: activo ? tono : Tema.rejilla
        Text { id: tBoton; anchors.centerIn: parent; text: parent.texto; color: parent.activo ? parent.tono : Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1 }
        TapHandler { enabled: parent.activo; onTapped: parent.pulsado() }
    }
    component Lista: Column {
        property string titulo: ""
        property var elementos: []
        property color tono: Tema.texto
        visible: elementos.length > 0
        spacing: 2
        Text { text: parent.titulo + " (" + parent.elementos.length + ")"; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
        Repeater {
            model: parent.elementos.slice(0, 12)
            Text { required property var modelData; text: "  " + modelData; color: parent.tono; font.family: Tema.mono; font.pixelSize: Tema.letraMini; elide: Text.ElideMiddle; width: 520 }
        }
        Text { visible: parent.elementos.length > 12; text: "  … y " + (parent.elementos.length - 12) + " más"; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        // Estado
        Marco {
            Layout.fillWidth: true
            Layout.preferredHeight: 190
            ident: "U0"
            etiqueta: "UPDATE MANAGER"
            acento: vista.colorEstado
            RowLayout {
                width: parent.width
                spacing: 24
                Column {
                    Layout.fillWidth: true
                    spacing: 6
                    Text { text: vista.estado; color: vista.colorEstado; font.family: Tema.mono; font.pixelSize: Tema.letraGrande; font.letterSpacing: 2 }
                    Text { width: parent.width; text: vista.explicacion; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini; wrapMode: Text.WordWrap }
                    Row {
                        spacing: 8
                        topPadding: 6
                        Boton { texto: vista.estado === "CHECKING" ? "COMPROBANDO…" : "BUSCAR ACTUALIZACIONES"; activo: !!vista.datos && vista.estado !== "CHECKING" && !(vista.j && vista.j.en_curso); onPulsado: vista.comprobar() }
                        Boton { texto: "INSTALAR"; tono: Tema.verde; visible: !!(vista.j && vista.j.nueva); activo: !(vista.j && vista.j.en_curso); onPulsado: vista.terminal("jaime0-update") }
                        Boton { texto: "RECUPERAR"; tono: Tema.ambar; visible: !!(vista.j && vista.j.interrumpida); onPulsado: vista.terminal("sudo /usr/local/bin/jaime0-update recuperar") }
                        Boton { texto: "REVERTIR ÚLTIMA"; tono: Tema.ambar; visible: !!(vista.j && vista.j.puede_revertir) && !(vista.j && vista.j.en_curso); onPulsado: vista.terminal("jaime0-update revertir") }
                    }
                    Text { visible: vista.mensaje !== ""; text: (vista.mensajeError ? "△ " : "✓ ") + vista.mensaje; color: vista.mensajeError ? Tema.ambar : Tema.verde; font.family: Tema.mono; font.pixelSize: Tema.letraMini; width: parent.width; wrapMode: Text.WordWrap }
                }
                Column {
                    Layout.preferredWidth: 420
                    spacing: 5
                    Dato { clave: "VERSIÓN INSTALADA"; valor: vista.j ? (vista.j.version_instalada || "desconocida") : "N/D" }
                    Dato { clave: "DISPONIBLE"; valor: vista.disp ? vista.disp.version + (vista.j.nueva ? "" : " (instalada)") : "—"; tono: vista.j && vista.j.nueva ? Tema.cian : Tema.texto }
                    Dato { clave: "CANAL"; valor: vista.j ? vista.j.canal : "N/D" }
                    Dato { clave: "ÚLTIMA COMPROBACIÓN"; valor: vista.j ? vista.fecha(vista.j.comprobado) : "N/D" }
                    Dato { clave: "ÚLTIMA OPERACIÓN"; valor: vista.j && vista.j.ultima ? vista.j.ultima.operacion + " " + (vista.j.ultima.version || "") + " · " + vista.j.ultima.resultado + " · " + vista.fecha(vista.j.ultima.fecha) : "ninguna"; tono: vista.j && vista.j.ultima && vista.j.ultima.resultado === "fallo" ? Tema.rojo : Tema.texto }
                    Dato { clave: "ACTUALIZADOR · CONFIG."; valor: vista.j ? "v" + vista.j.version_actualizador + " · tu configuración " + ((vista.j.configuracion && vista.j.configuracion.version) || "sin sincronizar") : "N/D" }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10

            // Cambios y archivos
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 3
                ident: "U1"
                etiqueta: vista.disp ? "CHANGES · " + vista.disp.version : "CHANGES"
                Flickable {
                    anchors.fill: parent
                    contentHeight: cambios.implicitHeight
                    clip: true
                    Column {
                        id: cambios
                        width: parent.width
                        spacing: 8
                        Text { visible: !vista.disp; text: "Sin datos de versiones: pulsa BUSCAR ACTUALIZACIONES."; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                        Repeater {
                            model: vista.disp ? (vista.disp.cambios || []) : []
                            Text { required property var modelData; width: cambios.width; text: "· " + modelData; color: Tema.texto; font.family: Tema.mono; font.pixelSize: Tema.letraMini; wrapMode: Text.WordWrap }
                        }
                        Lista { titulo: "PROBLEMAS CONOCIDOS"; elementos: vista.disp ? (vista.disp.problemas_conocidos || []) : []; tono: Tema.ambar }
                        Lista { titulo: "PAQUETES DE DEBIAN QUE PIDE"; elementos: vista.disp ? (vista.disp.paquetes || []) : [] }
                        Lista { titulo: "COMPONENTES"; elementos: vista.disp ? (vista.disp.componentes || []).map(c => typeof c === "string" ? c : (c.nombre || c.id || JSON.stringify(c))) : [] }
                        Text { visible: !!vista.plan; text: "ARCHIVOS QUE CAMBIARÍAN (vista previa; no se ha escrito nada)"; color: Tema.cian; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1 }
                        Repeater {
                            model: vista.plan ? ["sistema", "usuario"] : []
                            Column {
                                required property var modelData
                                readonly property var p: vista.plan[modelData] || {}
                                spacing: 4
                                Text { text: modelData === "sistema" ? "SISTEMA (pide autorización)" : "TU CONFIGURACIÓN (~/.config)"; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                                Lista { titulo: "NUEVOS"; elementos: parent.p.crear || [] }
                                Lista { titulo: "SE REEMPLAZAN (con copia)"; elementos: parent.p.reemplazar || [] }
                                Lista { titulo: "CONFLICTOS: los tuyos no se tocan (se deja .jaime0-nuevo)"; elementos: parent.p.conflictos || []; tono: Tema.ambar }
                                Lista { titulo: "SE RETIRAN (con copia)"; elementos: parent.p.retirar || [] }
                            }
                        }
                    }
                }
            }

            // Debian y conflictos
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 2
                spacing: 10
                Marco {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 170
                    ident: "U2"
                    etiqueta: "DEBIAN PACKAGES · APT"
                    acento: vista.deb && vista.deb.seguridad.length ? Tema.ambar : Tema.verde
                    Column {
                        width: parent.width
                        spacing: 5
                        Dato { clave: "POR ACTUALIZAR"; valor: vista.deb ? vista.deb.paquetes + " paquetes" : "sin comprobar" }
                        Dato { clave: "DE SEGURIDAD"; valor: vista.deb ? String(vista.deb.seguridad.length) : "—"; tono: vista.deb && vista.deb.seguridad.length ? Tema.ambar : Tema.texto }
                        Dato { clave: "COMPROBADO"; valor: vista.deb ? vista.fecha(vista.deb.comprobado) : "—" }
                        Text { width: parent.width; visible: !!vista.deb && vista.deb.seguridad.length > 0; text: vista.deb ? vista.deb.seguridad.slice(0, 8).join(", ") : ""; color: Tema.ambar; font.family: Tema.mono; font.pixelSize: Tema.letraMini; elide: Text.ElideRight }
                        Boton { texto: "INSTALAR CON APT"; activo: !!vista.deb && vista.deb.paquetes > 0; onPulsado: vista.terminal("actualizaciones") }
                    }
                }
                Marco {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    ident: "U3"
                    etiqueta: "LOCAL CHANGES · CONFLICTS"
                    Flickable {
                        anchors.fill: parent
                        contentHeight: listaConf.implicitHeight
                        clip: true
                        Column {
                            id: listaConf
                            width: parent.width
                            spacing: 3
                            Text {
                                width: parent.width
                                visible: !(vista.j && vista.j.conflictos && vista.j.conflictos.length)
                                text: "Ninguno. Si cambias un archivo de Jaime0 y una versión nueva lo trae distinto, el tuyo no se toca: el nuevo se deja al lado como .jaime0-nuevo y aparece aquí."
                                color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini; wrapMode: Text.WordWrap
                            }
                            Repeater {
                                model: vista.j && vista.j.conflictos ? vista.j.conflictos : []
                                Text { required property var modelData; width: listaConf.width; text: (modelData.ambito === "usuario" ? "TUYO    " : "SISTEMA ") + modelData.ruta; color: Tema.ambar; font.family: Tema.mono; font.pixelSize: Tema.letraMini; elide: Text.ElideMiddle }
                            }
                            Text {
                                visible: !!(vista.j && vista.j.conflictos && vista.j.conflictos.length)
                                text: "Resolver: jaime0-update resolver RUTA --diferencias | --usar-nueva | --mantener"
                                color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini
                            }
                        }
                    }
                }
            }
        }
    }
}
