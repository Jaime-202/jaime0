import QtQuick
import QtQuick.Layouts

// PRIVACY & SECURITY: lo que el servicio comprueba de verdad (orden "privacidad"), en tres
// categorias que calcula el servicio (privacidad.categorias_privacidad):
//   ACTIVE SECURITY          protecciones y lo que se expone a la red
//   APPLICATION PERMISSIONS  lo que pueden usar las aplicaciones
//   SYSTEM VISIBILITY        lo que no se puede comprobar o no aplica a este equipo
// Estados: ACTIVE, WARNING, DISABLED, UNAVAILABLE y NOT APPLICABLE. Lo no comprobable nunca
// cuenta como problema ni como proteccion. Nada se cambia desde aqui; las reglas del
// cortafuegos se leen solo si las pides (contrasena, solo lectura).
Item {
    id: vista

    property var datos: null
    property var reglas: null
    property string avisoReglas: ""
    property bool pidiendoReglas: false

    readonly property var resumen: datos ? datos.estado : null
    readonly property var cat: datos ? datos.categorias : null
    readonly property var cf: datos ? datos.cortafuegos : null
    readonly property var puertos: datos && datos.puertos ? datos.puertos : []

    function hora(t) {
        const f = new Date(t * 1000);
        const p = n => String(n).padStart(2, "0");
        return p(f.getDate()) + "/" + p(f.getMonth() + 1) + " " + p(f.getHours()) + ":" + p(f.getMinutes());
    }
    function color(e) {
        return ({ ACTIVE: Tema.verde, WARNING: Tema.ambar, DISABLED: Tema.secundario, UNAVAILABLE: Tema.cian })[e] || Tema.apagado;
    }
    function texto(e) { return e === "NOT_APPLICABLE" ? "NOT APPLICABLE" : e; }

    Consulta {
        id: consulta
        onRespuesta: d => { if (d.ok !== false) vista.datos = d; }
    }
    Consulta {
        id: consultaReglas
        onRespuesta: d => {
            vista.pidiendoReglas = false;
            if (d.ok === false) { vista.avisoReglas = d.error || "no se pudieron leer las reglas"; vista.reglas = null; }
            else { vista.avisoReglas = ""; vista.reglas = d; }
        }
    }
    Component.onCompleted: consulta.pedir({ orden: "privacidad" })
    Timer {
        interval: 10000; running: true; repeat: true
        onTriggered: consulta.pedir({ orden: "privacidad" })
    }

    component Linea: Text {
        width: parent ? parent.width : 0
        color: Tema.texto
        font.family: Tema.mono
        font.pixelSize: Tema.letraMini
        elide: Text.ElideRight
    }
    component Etiqueta: Text {
        color: Tema.apagado
        font.family: Tema.mono
        font.pixelSize: Tema.letraMini
        font.letterSpacing: 1.5
    }
    // Una categoria: lista de elementos con su estado, texto y detalle.
    component Categoria: Marco {
        id: marcoCat
        property var elementos: []
        property string explicacion: ""
        Layout.fillWidth: true
        Layout.fillHeight: true
        acento: elementos.some(e => e.estado === "WARNING") ? Tema.ambar : Tema.cian
        Flickable {
            anchors.fill: parent
            contentHeight: columnaCat.implicitHeight
            clip: true
            Column {
                id: columnaCat
                width: parent.width
                spacing: 7
                Text { width: parent.width; text: marcoCat.explicacion; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: 9; wrapMode: Text.WordWrap }
                Repeater {
                    model: marcoCat.elementos
                    Column {
                        id: elemento
                        required property var modelData
                        width: columnaCat.width
                        spacing: 2
                        Row {
                            spacing: 8
                            Rectangle {
                                width: tEstado.implicitWidth + 10; height: 16
                                color: "transparent"; border.color: vista.color(elemento.modelData.estado)
                                Text { id: tEstado; anchors.centerIn: parent; text: vista.texto(elemento.modelData.estado); color: vista.color(elemento.modelData.estado); font.family: Tema.mono; font.pixelSize: 9 }
                            }
                            Text { text: elemento.modelData.nombre; color: Tema.texto; font.family: Tema.mono; font.pixelSize: Tema.letraMini; anchors.verticalCenter: parent.verticalCenter }
                        }
                        Text { width: parent.width; text: elemento.modelData.texto; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: 9; wrapMode: Text.WordWrap }
                        Repeater {
                            model: (elemento.modelData.detalle || []).slice(0, 6)
                            Text { required property var modelData; width: elemento.width; text: "  · " + modelData; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: 9; elide: Text.ElideRight }
                        }
                    }
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        // ── Estado ───────────────────────────────────────────────────────────
        Marco {
            Layout.fillWidth: true
            Layout.preferredHeight: 100
            ident: "S0"
            etiqueta: "PRIVACY STATUS"
            acento: Tema.colorEstado(vista.resumen ? vista.resumen.estado : "")
            RowLayout {
                anchors.fill: parent
                spacing: 24
                Text {
                    text: vista.resumen ? vista.resumen.estado : "N/D"
                    color: Tema.colorEstado(vista.resumen ? vista.resumen.estado : "")
                    font.family: Tema.mono
                    font.pixelSize: Tema.letraGrande
                    font.letterSpacing: 2
                }
                Column {
                    Layout.fillWidth: true
                    spacing: 3
                    Repeater {
                        model: vista.resumen ? (vista.resumen.motivos || []).slice(0, 2).map(m => ["△ ", m, Tema.ambar])
                                                .concat((vista.resumen.detalles || []).slice(0, 2).map(d => ["· ", d, Tema.texto])) : []
                        Linea {
                            required property var modelData
                            text: modelData[0] + modelData[1]
                            color: modelData[2]
                        }
                    }
                    Linea {
                        text: "Son comprobaciones concretas, no una garantía de que el equipo sea invulnerable."
                        color: Tema.apagado
                    }
                }
                Column {
                    spacing: 1
                    Repeater {
                        model: ["ACTIVE", "WARNING", "DISABLED", "UNAVAILABLE", "NOT_APPLICABLE"]
                        Text {
                            required property var modelData
                            text: vista.texto(modelData).padEnd(15) + (vista.cat ? vista.cat.cuenta[modelData] : "—")
                            color: vista.cat && vista.cat.cuenta[modelData] ? vista.color(modelData) : Tema.rejilla
                            font.family: Tema.mono; font.pixelSize: 9
                        }
                    }
                }
            }
        }

        // ── Las tres categorias ──────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 220
            spacing: 10
            Categoria {
                ident: "S1"
                etiqueta: "ACTIVE SECURITY"
                elementos: vista.cat ? vista.cat.activa : []
                explicacion: "Protecciones comprobadas y lo que el equipo expone a la red."
            }
            Categoria {
                ident: "S2"
                etiqueta: "APPLICATION PERMISSIONS"
                elementos: vista.cat ? vista.cat.permisos : []
                explicacion: "Lo que pueden usar las aplicaciones: dispositivos, privilegios y permisos."
            }
            Categoria {
                ident: "S3"
                etiqueta: "SYSTEM VISIBILITY"
                elementos: vista.cat ? vista.cat.visibilidad : []
                explicacion: "Lo que no se puede comprobar o este equipo no tiene. No es un problema de seguridad ni cuenta como protección."
            }
        }

        // ── Reglas del cortafuegos, puertos y conexiones, historial ─────────
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 170
            Layout.maximumHeight: 170
            spacing: 10

            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ident: "S4"
                etiqueta: "FIREWALL RULES"
                Flickable {
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: botonReglas.top
                    anchors.bottomMargin: 6
                    contentHeight: listaReglas.implicitHeight
                    clip: true
                    Column {
                        id: listaReglas
                        width: parent.width
                        spacing: 2
                        Linea {
                            text: !vista.cf || !vista.cf.instalado ? "UFW no está instalado."
                                  : "Registro: " + (vista.cf.registro || "N/D") + " · enrutado: " + ((vista.cf.politicas || {}).enrutado || "N/D")
                            color: Tema.secundario
                        }
                        Linea { visible: vista.avisoReglas !== ""; text: "△ " + vista.avisoReglas; color: Tema.ambar }
                        Linea {
                            visible: vista.reglas !== null && (!vista.reglas.reglas || vista.reglas.reglas.length === 0)
                            text: "Sin reglas: no se permite ninguna entrada (solo lo que tú inicias)."
                            color: Tema.secundario
                        }
                        Repeater {
                            model: vista.reglas && vista.reglas.reglas ? vista.reglas.reglas : []
                            Linea {
                                required property var modelData
                                text: modelData.destino + "  " + modelData.accion + "  " + modelData.origen + (modelData.ipv6 ? " (v6)" : "")
                                      + (modelData.comentario ? "  # " + modelData.comentario : "")
                                color: /DENY|REJECT/.test(modelData.accion) ? Tema.ambar : Tema.texto
                            }
                        }
                    }
                }
                Rectangle {
                    id: botonReglas
                    anchors.bottom: parent.bottom
                    visible: !!(vista.cf && vista.cf.instalado)
                    width: textoReglas.implicitWidth + 16
                    height: 22
                    color: "transparent"
                    border.color: Tema.cian
                    Text {
                        id: textoReglas
                        anchors.centerIn: parent
                        text: vista.pidiendoReglas ? "ESPERANDO AUTORIZACIÓN…" : "VER REGLAS · PIDE CONTRASEÑA · SOLO LECTURA"
                        color: Tema.cian
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                    }
                    TapHandler {
                        enabled: !vista.pidiendoReglas
                        onTapped: {
                            vista.pidiendoReglas = true;
                            vista.avisoReglas = "";
                            consultaReglas.pedir({ orden: "ufw_reglas" });
                        }
                    }
                }
            }

            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ident: "S5"
                etiqueta: "PORTS · CONNECTIONS"
                Flickable {
                    anchors.fill: parent
                    contentHeight: listaRed.implicitHeight
                    clip: true
                    Column {
                        id: listaRed
                        width: parent.width
                        spacing: 2
                        Linea { visible: vista.puertos.length === 0; text: "Ningún programa escucha conexiones."; color: Tema.secundario }
                        Repeater {
                            model: vista.puertos
                            Linea {
                                required property var modelData
                                text: (modelData.expuesto ? "◆ " : "· ") + modelData.protocolo + " " + modelData.direccion + ":" + modelData.puerto
                                      + "  " + (modelData.proceso || "(proceso de otro usuario)")
                                color: modelData.expuesto ? Tema.ambar : Tema.secundario
                            }
                        }
                        Item { width: 1; height: 4 }
                        Linea { visible: !vista.datos || !vista.datos.conexiones || vista.datos.conexiones.length === 0; text: "Sin conexiones establecidas."; color: Tema.secundario }
                        Repeater {
                            model: vista.datos && vista.datos.conexiones ? vista.datos.conexiones : []
                            Linea {
                                required property var modelData
                                text: "→ " + (modelData.proceso || "(otro usuario)") + " · " + modelData.conexiones + " conexión" + (modelData.conexiones === 1 ? "" : "es")
                                      + " · " + (modelData.destinos || []).slice(0, 2).join("  ") + ((modelData.destinos || []).length > 2 ? "  …" : "")
                                color: Tema.texto
                            }
                        }
                        Linea { text: "◆ = abierto a la red"; color: Tema.apagado; visible: vista.puertos.some(p => p.expuesto) }
                    }
                }
            }

            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ident: "S6"
                etiqueta: "HISTORY"
                Flickable {
                    anchors.fill: parent
                    contentHeight: listaHist.implicitHeight
                    clip: true
                    Column {
                        id: listaHist
                        width: parent.width
                        spacing: 2
                        Linea {
                            visible: !vista.datos || !vista.datos.historial || vista.datos.historial.length === 0
                            text: "Sin cambios registrados."
                            color: Tema.apagado
                        }
                        Repeater {
                            model: vista.datos && vista.datos.historial ? vista.datos.historial : []
                            Linea {
                                required property var modelData
                                text: vista.hora(modelData.t) + "  " + modelData.texto
                                color: Tema.secundario
                            }
                        }
                    }
                }
            }
        }
    }
}
