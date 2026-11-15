import QtQuick
import QtQuick.Layouts

// PROFILES: los perfiles de jaime0-servicio (orden "perfiles"), con lo que cambia cada
// uno y si este equipo lo admite. Aplicar un perfil es pedirselo al servicio: la ventana
// no toca nada por su cuenta.
Item {
    id: vista

    property var estado: null
    property var datos: null          // respuesta de "perfiles"
    property string mensaje: ""
    property bool ocupado: false
    property var borrador: ({})       // edicion de CUSTOM
    property bool editando: false

    readonly property var perfiles: datos ? datos.perfiles : []
    readonly property string activo: datos ? datos.activo : (estado && estado.perfil ? estado.perfil.activo : "")
    readonly property var actual: perfiles.find(p => p.id === activo) || null
    readonly property var anterior: datos ? perfiles.find(p => p.id === datos.anterior) || null : null
    readonly property var cap: datos ? datos.capacidades : null
    readonly property var infoPerfil: estado ? estado.perfil : null

    function leer() { consulta.pedir({ orden: "perfiles" }); }
    function aplicar(id) {
        ocupado = true;
        mensaje = "";
        cambio.pedir({ orden: "perfil", valor: id, origen: "usuario" });
    }

    Consulta {
        id: consulta
        onRespuesta: d => {
            if (d.ok === false) { vista.mensaje = d.error || "sin respuesta del servicio"; return; }
            vista.datos = d;
            if (!vista.editando) vista.borrador = Object.assign({}, d.personalizado && d.personalizado.ajustes ? d.personalizado.ajustes : {});
        }
    }
    Consulta {
        id: cambio
        onRespuesta: d => {
            vista.ocupado = false;
            if (d.ok === false)
                vista.mensaje = d.error || "no se pudo aplicar";
            else if (d.fallos && d.fallos.length)
                vista.mensaje = "Aplicado con avisos: " + d.fallos.join(" · ");
            else
                vista.mensaje = "";
            destello.restart();
            vista.leer();
        }
    }
    Component.onCompleted: leer()
    // Un cambio hecho desde fuera (jaime0-perfil, una regla) llega por estado.json.
    onInfoPerfilChanged: if (infoPerfil && datos && infoPerfil.activo !== datos.activo) leer()

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        // ── Perfil activo ────────────────────────────────────────────────────
        Marco {
            id: cabecera
            Layout.fillWidth: true
            Layout.preferredHeight: 92
            ident: "P0"
            etiqueta: "ACTIVE PROFILE"
            acento: Tema.verde

            // Destello al cambiar de perfil: el borde se ilumina un instante.
            Rectangle {
                id: luz
                parent: cabecera
                anchors.fill: parent
                color: "transparent"
                border.color: Tema.verde
                border.width: 1
                opacity: 0
                SequentialAnimation on opacity {
                    id: destello
                    running: false
                    NumberAnimation { to: 1; duration: Tema.rapido }
                    NumberAnimation { to: 0; duration: 600; easing.type: Easing.OutCubic }
                }
            }

            RowLayout {
                anchors.fill: parent
                spacing: 24
                Column {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 160
                    spacing: 4
                    Text {
                        width: parent.width
                        elide: Text.ElideRight
                        text: vista.actual ? vista.actual.nombre : (vista.activo ? vista.activo.toUpperCase() : "N/D")
                        color: Tema.verde
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraGrande
                        font.letterSpacing: 2
                    }
                    Text {
                        width: parent.width
                        elide: Text.ElideRight
                        text: vista.ocupado ? "APLICANDO…" : vista.actual ? vista.actual.descripcion : ""
                        color: Tema.secundario
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                    }
                }
                Column {
                    spacing: 4
                    Layout.alignment: Qt.AlignVCenter
                    Repeater {
                        model: [
                            ["ENERGY", vista.infoPerfil && vista.infoPerfil.energia ? vista.infoPerfil.energia + (vista.infoPerfil.retencion ? " · retenido" : "") : "N/D"],
                            ["DEGRADED", vista.infoPerfil && vista.infoPerfil.degradado ? vista.infoPerfil.degradado : "no"],
                            ["ORIGIN", vista.infoPerfil && vista.infoPerfil.origen ? vista.infoPerfil.origen : "N/D"]
                        ]
                        Row {
                            required property var modelData
                            spacing: 10
                            Text { width: 72; text: modelData[0]; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1.5 }
                            Text { text: modelData[1]; color: Tema.texto; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                        }
                    }
                }
                // Volver al anterior y editar CUSTOM (fuera de las tarjetas: un clic aqui no
                // aplica ningun perfil).
                Column {
                    Layout.alignment: Qt.AlignVCenter
                    spacing: 6
                Rectangle {
                    visible: vista.anterior !== null
                    width: textoAnterior.implicitWidth + 18
                    height: 26
                    color: "transparent"
                    border.color: Tema.cian
                    border.width: 1
                    Text {
                        id: textoAnterior
                        anchors.centerIn: parent
                        text: "↶ VOLVER A " + (vista.anterior ? vista.anterior.nombre : "")
                        color: Tema.cian
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                        font.letterSpacing: 1
                    }
                    TapHandler {
                        onTapped: {
                            vista.ocupado = true;
                            cambio.pedir({ orden: "perfil_anterior" });
                        }
                    }
                }
                Rectangle {
                    width: textoEditar.implicitWidth + 18
                    height: 26
                    color: vista.editando ? Tema.cian : "transparent"
                    border.color: Tema.cian
                    border.width: 1
                    Text {
                        id: textoEditar
                        anchors.centerIn: parent
                        text: vista.editando ? "CERRAR EDITOR" : "✎ EDITAR CUSTOM"
                        color: vista.editando ? Tema.fondo : Tema.cian
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                        font.letterSpacing: 1
                    }
                    TapHandler { onTapped: vista.editando = !vista.editando }
                }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            visible: vista.mensaje !== "" || (vista.infoPerfil && vista.infoPerfil.fallos && vista.infoPerfil.fallos.length > 0)
            text: vista.mensaje !== "" ? "△ " + vista.mensaje
                  : "△ " + (vista.infoPerfil && vista.infoPerfil.fallos ? vista.infoPerfil.fallos.join(" · ") : "")
            color: Tema.ambar
            font.family: Tema.mono
            font.pixelSize: Tema.letraMini
            wrapMode: Text.WordWrap
        }

        // ── Los seis perfiles ────────────────────────────────────────────────
        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 3
            rowSpacing: 10
            columnSpacing: 10

            Repeater {
                model: vista.perfiles
                Marco {
                    id: tarjeta
                    required property var modelData
                    required property int index
                    readonly property bool esActivo: modelData.id === vista.activo
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    ident: "P" + (index + 1)
                    etiqueta: esActivo ? "ACTIVE" : modelData.disponible ? "READY" : "UNAVAILABLE"
                    acento: esActivo ? Tema.verde : modelData.disponible ? Tema.cian : Tema.apagado
                    color: esActivo ? "#0f1a15" : selector.hovered && modelData.disponible ? "#0f171b" : Tema.panel
                    Behavior on color { ColorAnimation { duration: Tema.rapido } }

                    Column {
                        width: parent.width
                        spacing: 6
                        Text {
                            text: tarjeta.modelData.nombre
                            color: tarjeta.esActivo ? Tema.verde : tarjeta.modelData.disponible ? Tema.texto : Tema.apagado
                            font.family: Tema.mono
                            font.pixelSize: 17
                            font.letterSpacing: 2
                        }
                        Text {
                            width: parent.width
                            text: tarjeta.modelData.descripcion
                            color: Tema.secundario
                            font.family: Tema.mono
                            font.pixelSize: Tema.letraMini
                            wrapMode: Text.WordWrap
                            maximumLineCount: 3
                            elide: Text.ElideRight
                        }
                        Repeater {
                            model: tarjeta.modelData.cambios.length ? tarjeta.modelData.cambios : ["Sin cambios: tu configuración tal cual"]
                            Text {
                                required property var modelData
                                width: parent.width
                                text: "→ " + modelData
                                color: tarjeta.modelData.disponible ? Tema.texto : Tema.apagado
                                font.family: Tema.mono
                                font.pixelSize: Tema.letraMini
                                elide: Text.ElideRight
                            }
                        }
                        Text {
                            visible: !tarjeta.modelData.disponible && !!tarjeta.modelData.motivo
                            width: parent.width
                            text: "✕ " + (tarjeta.modelData.motivo || "")
                            color: Tema.ambar
                            font.family: Tema.mono
                            font.pixelSize: Tema.letraMini
                            wrapMode: Text.WordWrap
                        }
                    }
                    HoverHandler { id: selector }
                    TapHandler {
                        enabled: tarjeta.modelData.disponible && !tarjeta.esActivo && !vista.ocupado
                        onTapped: vista.aplicar(tarjeta.modelData.id)
                    }
                }
            }
        }

        // ── Editor de CUSTOM ─────────────────────────────────────────────────
        Marco {
            id: editor
            Layout.fillWidth: true
            Layout.preferredHeight: vista.editando ? 150 : 0
            visible: vista.editando
            ident: "P6"
            etiqueta: "CUSTOM · ELIGE QUÉ SE APLICA"
            acento: Tema.cian

            readonly property var filas: {
                const c = vista.cap || {};
                const energias = c.energia || [];
                return [
                    { clave: "energia", etiqueta: "ENERGÍA", opciones: [
                        { valor: "balanced", texto: "EQUILIBRADA" },
                        { valor: "performance", texto: "RENDIMIENTO", disponible: energias.indexOf("performance") >= 0 },
                        { valor: "power-saver", texto: "AHORRO", disponible: energias.indexOf("power-saver") >= 0 }] },
                    { clave: "animaciones", etiqueta: "ANIMACIONES", opciones: [
                        { valor: "base", texto: "COMO ESTÉN" }, { valor: "si", texto: "SÍ", disponible: c.animaciones }, { valor: "no", texto: "NO", disponible: c.animaciones }] },
                    { clave: "desenfoque", etiqueta: "DESENFOQUE", opciones: [
                        { valor: "base", texto: "COMO ESTÉ" }, { valor: "si", texto: "SÍ", disponible: c.animaciones }, { valor: "no", texto: "NO", disponible: c.animaciones }] },
                    { clave: "no_molestar", etiqueta: "NO MOLESTAR", opciones: [
                        { valor: "base", texto: "COMO ESTÉ" }, { valor: "si", texto: "SÍ", disponible: c.no_molestar }, { valor: "no", texto: "NO", disponible: c.no_molestar }] },
                    { clave: "inhibir_inactividad", etiqueta: "SIN BLOQUEO", opciones: [
                        { valor: "no", texto: "NO" }, { valor: "si", texto: "SÍ", disponible: c.inhibir_inactividad }] },
                    { clave: "modo_noche", etiqueta: "MODO NOCHE", opciones: [
                        { valor: "base", texto: "COMO ESTÉ" }, { valor: "si", texto: "SÍ", disponible: c.modo_noche }, { valor: "no", texto: "NO", disponible: c.modo_noche }] }
                ];
            }

            RowLayout {
                anchors.fill: parent
                spacing: 16
                GridLayout {
                    columns: 2
                    rowSpacing: 4
                    columnSpacing: 12
                    Repeater {
                        model: editor.filas
                        delegate: Item {
                            required property var modelData
                            implicitWidth: filaEditor.implicitWidth
                            implicitHeight: 22
                            Row {
                                id: filaEditor
                                spacing: 10
                                Text {
                                    width: 96
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.etiqueta
                                    color: Tema.secundario
                                    font.family: Tema.mono
                                    font.pixelSize: Tema.letraMini
                                    font.letterSpacing: 1
                                }
                                Opciones {
                                    ancho: 360
                                    opciones: modelData.opciones
                                    valor: vista.borrador[modelData.clave] || (modelData.clave === "energia" ? "balanced" : modelData.clave === "inhibir_inactividad" ? "no" : "base")
                                    onElegido: v => {
                                        const b = Object.assign({}, vista.borrador);
                                        b[modelData.clave] = v;
                                        vista.borrador = b;
                                    }
                                }
                            }
                        }
                    }
                }
                Item { Layout.fillWidth: true }
                Rectangle {
                    Layout.alignment: Qt.AlignBottom
                    width: textoGuardar.implicitWidth + 18
                    height: 26
                    color: Tema.cian
                    Text {
                        id: textoGuardar
                        anchors.centerIn: parent
                        text: "GUARDAR CUSTOM"
                        color: Tema.fondo
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                        font.letterSpacing: 1
                    }
                    TapHandler {
                        onTapped: {
                            vista.editando = false;
                            cambio.pedir({ orden: "personalizado", ajustes: vista.borrador });
                        }
                    }
                }
            }
        }
    }
}
