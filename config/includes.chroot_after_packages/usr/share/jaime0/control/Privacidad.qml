import QtQuick
import QtQuick.Layouts

// PRIVACY & SECURITY: lo que el servicio comprueba de verdad (orden "privacidad"). Nada se
// cambia desde aqui; las reglas del cortafuegos se leen solo si las pides (contrasena).
Item {
    id: vista

    property var datos: null
    property var reglas: null
    property string avisoReglas: ""
    property bool pidiendoReglas: false

    readonly property var resumen: datos ? datos.estado : null
    readonly property var cf: datos ? datos.cortafuegos : null
    readonly property var disp: datos ? datos.dispositivos : null
    readonly property var puertos: datos && datos.puertos ? datos.puertos : []
    readonly property var expuestos: puertos.filter(p => p.expuesto)

    function hora(t) {
        const f = new Date(t * 1000);
        const p = n => String(n).padStart(2, "0");
        return p(f.getDate()) + "/" + p(f.getMonth() + 1) + " " + p(f.getHours()) + ":" + p(f.getMinutes());
    }
    function colorUso(lista) { return lista && lista.length ? Tema.ambar : Tema.verde; }

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

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        // ── Estado ───────────────────────────────────────────────────────────
        Marco {
            Layout.fillWidth: true
            Layout.preferredHeight: 92
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
                        model: vista.resumen ? (vista.resumen.motivos || []).map(m => ["△ ", m, Tema.ambar])
                                                .concat((vista.resumen.detalles || []).map(d => ["· ", d, Tema.texto])) : []
                        Linea {
                            required property var modelData
                            text: modelData[0] + modelData[1]
                            color: modelData[2]
                        }
                    }
                    Linea {
                        text: "Lo que se ve aquí son comprobaciones concretas, no una garantía de que el equipo sea invulnerable."
                        color: Tema.apagado
                    }
                }
                Column {
                    Layout.alignment: Qt.AlignVCenter
                    spacing: 2
                    Etiqueta { text: "LOCAL · SIN TELEMETRÍA" }
                    Etiqueta { text: "NADA SALE DEL EQUIPO" }
                }
            }
        }

        // ── Cortafuegos, puertos y dispositivos ─────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            // Altura fija: si no, el contenido desplazable de los paneles la estira y la fila
            // de abajo (conexiones, privilegios, telemetria) se queda sin sitio.
            Layout.preferredHeight: 230
            Layout.maximumHeight: 230
            Layout.fillHeight: false
            spacing: 10

            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ident: "S1"
                etiqueta: "FIREWALL · UFW"
                acento: vista.cf && vista.cf.activo ? Tema.verde : Tema.ambar
                Column {
                    id: columnaCf
                    width: parent.width
                    spacing: 4
                    Text {
                        text: !vista.cf ? "N/D" : !vista.cf.instalado ? "NO INSTALADO" : vista.cf.activo ? "ACTIVO" : "INACTIVO"
                        color: vista.cf && vista.cf.activo ? Tema.verde : Tema.ambar
                        font.family: Tema.mono
                        font.pixelSize: 16
                    }
                    Repeater {
                        model: vista.cf && vista.cf.politicas ? [
                            ["ENTRANTE", vista.cf.politicas.entrante], ["SALIENTE", vista.cf.politicas.saliente],
                            ["ENRUTADO", vista.cf.politicas.enrutado], ["REGISTRO", vista.cf.registro || "N/D"]] : []
                        Row {
                            required property var modelData
                            spacing: 8
                            Etiqueta { width: 76; text: modelData[0] }
                            Text { text: modelData[1] || "N/D"; color: Tema.texto; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                        }
                    }
                }
                // Reglas: solo con autorizacion, cuando se pide.
                Flickable {
                    anchors.top: columnaCf.bottom
                    anchors.topMargin: 8
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
                            visible: vista.avisoReglas !== ""
                            text: "△ " + vista.avisoReglas
                            color: Tema.ambar
                        }
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
                    visible: vista.cf && vista.cf.instalado
                    width: textoReglas.implicitWidth + 16
                    height: 22
                    color: "transparent"
                    border.color: Tema.cian
                    border.width: 1
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
                ident: "S2"
                etiqueta: "OPEN PORTS · " + vista.expuestos.length + " A LA RED"
                acento: vista.expuestos.length ? Tema.ambar : Tema.verde
                Flickable {
                    anchors.fill: parent
                    contentHeight: listaPuertos.implicitHeight
                    clip: true
                    Column {
                        id: listaPuertos
                        width: parent.width
                        spacing: 3
                        Linea {
                            visible: vista.puertos.length === 0
                            text: "Ningún programa escucha conexiones."
                            color: Tema.secundario
                        }
                        Repeater {
                            model: vista.puertos
                            Linea {
                                required property var modelData
                                text: (modelData.expuesto ? "◆ " : "· ") + modelData.protocolo + " " + modelData.direccion + ":" + modelData.puerto
                                      + "  " + (modelData.proceso || "(proceso de otro usuario)")
                                color: modelData.expuesto ? Tema.ambar : Tema.secundario
                            }
                        }
                        Linea {
                            visible: vista.expuestos.length > 0
                            text: "◆ = abierto a la red; UFW lo bloquea salvo que una regla lo permita."
                            color: Tema.apagado
                            wrapMode: Text.WordWrap
                            elide: Text.ElideNone
                        }
                    }
                }
            }

            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ident: "S3"
                etiqueta: "DEVICES IN USE"
                Column {
                    width: parent.width
                    spacing: 10
                    Repeater {
                        model: [
                            ["MICRÓFONO", vista.disp ? vista.disp.microfono : null],
                            ["CÁMARA", vista.disp ? vista.disp.camara : null],
                            ["PANTALLA COMPARTIDA", vista.disp ? vista.disp.pantalla : null]
                        ]
                        Column {
                            required property var modelData
                            width: parent.width
                            spacing: 2
                            Row {
                                spacing: 8
                                Rectangle {
                                    id: punto
                                    width: 8; height: 8
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: modelData[1] === null ? Tema.apagado : vista.colorUso(modelData[1])
                                    // Parpadeo lento mientras algo usa el dispositivo.
                                    SequentialAnimation on opacity {
                                        running: modelData[1] !== null && modelData[1].length > 0
                                        loops: Animation.Infinite
                                        NumberAnimation { to: 0.3; duration: 800 }
                                        NumberAnimation { to: 1; duration: 800 }
                                        onRunningChanged: if (!running) punto.opacity = 1
                                    }
                                }
                                Etiqueta { text: modelData[0] }
                            }
                            Linea {
                                text: modelData[1] === null ? "N/D (no se puede comprobar)"
                                      : modelData[1].length === 0 ? "sin uso"
                                      : modelData[1].map(x => x.aplicacion + (x.pid ? " (" + x.pid + ")" : "")).join(", ")
                                color: modelData[1] && modelData[1].length ? Tema.ambar : Tema.secundario
                            }
                        }
                    }
                }
            }
        }

        // ── Conexiones, aplicaciones y privilegios, telemetria e historial ───
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10

            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ident: "S4"
                etiqueta: "ACTIVE CONNECTIONS · POR PROCESO"
                Flickable {
                    anchors.fill: parent
                    contentHeight: listaCon.implicitHeight
                    clip: true
                    Column {
                        id: listaCon
                        width: parent.width
                        spacing: 4
                        Linea {
                            visible: !vista.datos || !vista.datos.conexiones || vista.datos.conexiones.length === 0
                            text: "Sin conexiones establecidas."
                            color: Tema.secundario
                        }
                        Repeater {
                            model: vista.datos && vista.datos.conexiones ? vista.datos.conexiones : []
                            Column {
                                required property var modelData
                                width: listaCon.width
                                Linea {
                                    text: (modelData.proceso || "(otro usuario)") + "  ·  " + modelData.conexiones + " conexión" + (modelData.conexiones === 1 ? "" : "es")
                                    color: Tema.texto
                                }
                                Linea {
                                    text: "   → " + (modelData.destinos || []).slice(0, 3).join("  ") + ((modelData.destinos || []).length > 3 ? "  …" : "")
                                    color: Tema.apagado
                                }
                            }
                        }
                    }
                }
            }

            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ident: "S5"
                etiqueta: "APPS · PRIVILEGES · SERVICES"
                Flickable {
                    anchors.fill: parent
                    contentHeight: listaApps.implicitHeight
                    clip: true
                    Column {
                        id: listaApps
                        width: parent.width
                        spacing: 3
                        Etiqueta { text: "FLATPAK · " + (vista.datos && vista.datos.flatpak ? vista.datos.flatpak.estado : "N/D") }
                        Linea {
                            text: vista.datos && vista.datos.flatpak ? vista.datos.flatpak.texto || "" : ""
                            color: Tema.secundario
                            wrapMode: Text.WordWrap
                            elide: Text.ElideNone
                        }
                        Item { width: 1; height: 4 }
                        Etiqueta { text: "TUS GRUPOS CON PRIVILEGIOS" }
                        Repeater {
                            model: vista.datos && vista.datos.privilegios ? vista.datos.privilegios.grupos : []
                            Linea {
                                required property var modelData
                                text: modelData.texto
                                color: modelData.grupo === "sudo" ? Tema.ambar : Tema.texto
                            }
                        }
                        Item { width: 1; height: 4 }
                        Etiqueta { text: "SERVICIOS" }
                        Repeater {
                            model: vista.datos && vista.datos.servicios ? vista.datos.servicios : []
                            Linea {
                                required property var modelData
                                text: modelData.nombre + " · " + modelData.estado + " — " + modelData.texto
                                color: modelData.estado === "activo" ? Tema.texto : Tema.apagado
                            }
                        }
                    }
                }
            }

            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ident: "S6"
                etiqueta: "TELEMETRY · HISTORY"
                Flickable {
                    anchors.fill: parent
                    contentHeight: listaTel.implicitHeight
                    clip: true
                    Column {
                        id: listaTel
                        width: parent.width
                        spacing: 3
                        Repeater {
                            model: vista.datos && vista.datos.telemetria ? vista.datos.telemetria : []
                            Linea {
                                required property var modelData
                                text: modelData.elemento + ": " + modelData.texto
                                color: modelData.estado === "ACTIVO" ? Tema.ambar : Tema.texto
                                wrapMode: Text.WordWrap
                                elide: Text.ElideNone
                            }
                        }
                        Item { width: 1; height: 6 }
                        Etiqueta { text: "HISTORIAL" }
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
