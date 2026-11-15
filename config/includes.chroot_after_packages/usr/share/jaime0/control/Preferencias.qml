import QtQuick
import QtQuick.Layouts
import Quickshell.Io

// SETTINGS: preferencias del Control Center. Se leen y se guardan con jaime0-ajustes
// (mismo esquema, validacion y archivo que el resto de Jaime0), asi que persisten tras
// reiniciar y la aplicacion de ajustes muestra lo mismo.
Item {
    id: vista

    property var ajustes: ({})           // clave -> definicion con valor
    property string mensaje: ""
    property bool mensajeError: false
    property var borradores: ({})        // clave -> texto escrito aun sin guardar

    readonly property var secciones: [
        { id: "C1", titulo: "ANIMATIONS", claves: ["animaciones"],
          nota: "no: sin animaciones · sutil: discretas y rápidas (predeterminado) · suave: más fluidas. Se aplica al escritorio, las notificaciones, los widgets y esta ventana." },
        { id: "C2", titulo: "DATA REFRESH", claves: ["cc_intervalo", "cc_intervalo_rapido"],
          nota: "La medición en segundo plano alimenta el historial y las reglas; con la ventana abierta se mide más a menudo." },
        { id: "C3", titulo: "ALERT THRESHOLDS", claves: ["umbral_temp_aviso", "umbral_temp_critico", "umbral_disco_aviso", "umbral_disco_critico", "umbral_bateria_aviso", "umbral_bateria_critico"],
          nota: "Un aviso debe quedar por debajo de su crítico (en la batería, al revés): si no, no se guarda." },
        { id: "C4", titulo: "HISTORY · NOTIFICATIONS", claves: ["historial_dias", "cc_notificar"],
          nota: "El historial vive en ~/.local/state/jaime0. Los avisos de escritorio son para incidencias nuevas; las recuperaciones no avisan." },
        { id: "C5", titulo: "SHORTCUT", claves: ["control_atajo"],
          nota: "Modificadores SUPER, SHIFT, CTRL o ALT y una tecla, p. ej. SUPER+I o SUPER+SHIFT+C. Se aplica al momento." }
    ]

    function leer() {
        lector.running = false;
        lector.running = true;
    }
    function guardar(clave, valor) {
        vista.mensaje = "Guardando…";
        vista.mensajeError = false;
        escritor.command = ["jaime0-ajustes", "poner", clave, String(valor)];
        escritor.running = true;
    }
    function restablecer(clave) {
        escritor.command = ["jaime0-ajustes", "restablecer", clave];
        escritor.running = true;
    }

    Process {
        id: lector
        command: ["jaime0-ajustes", "ver", "--json"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const d = JSON.parse(text);
                    const m = {};
                    for (const a of d.ajustes) m[a.clave] = a;
                    vista.ajustes = m;
                } catch (e) {
                    vista.mensaje = "No se pudieron leer los ajustes";
                    vista.mensajeError = true;
                }
            }
        }
    }
    Process {
        id: escritor
        stderr: StdioCollector {
            onStreamFinished: if (text.trim() !== "") { vista.mensaje = text.trim().replace(/^jaime0-ajustes: /, ""); vista.mensajeError = true; }
        }
        onExited: (codigo) => {
            if (codigo === 0) { vista.mensaje = "Guardado y aplicado"; vista.mensajeError = false; vista.borradores = ({}); }
            vista.leer();
        }
    }
    Component.onCompleted: leer()

    // Una fila: etiqueta, control segun el tipo, valor de fabrica y restablecer.
    component Fila: Item {
        id: fila
        property string clave: ""
        readonly property var a: vista.ajustes[clave] || null
        width: parent ? parent.width : 0
        height: 28
        visible: a !== null

        Text {
            id: etiqueta
            anchors.verticalCenter: parent.verticalCenter
            width: 300
            text: fila.a ? fila.a.etiqueta : ""
            color: fila.a && fila.a.propio ? Tema.texto : Tema.secundario
            font.family: Tema.mono
            font.pixelSize: Tema.letraMini
            elide: Text.ElideRight
        }
        Loader {
            id: control
            anchors.left: etiqueta.right
            anchors.leftMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            sourceComponent: !fila.a ? null : fila.a.tipo === "opcion" ? cOpcion : fila.a.tipo === "entero" ? cEntero : cTexto
            Component {
                id: cOpcion
                Opciones {
                    ancho: 420
                    opciones: (fila.a.opciones || []).map(o => ({ valor: o, texto: String(o).toUpperCase() }))
                    valor: fila.a.valor
                    onElegido: v => vista.guardar(fila.clave, v)
                }
            }
            Component {
                id: cEntero
                Row {
                    spacing: 4
                    Repeater {
                        model: [["−5", -5], ["−1", -1]]
                        Rectangle {
                            required property var modelData
                            width: 26; height: 20; color: "transparent"; border.color: Tema.borde
                            Text { anchors.centerIn: parent; text: modelData[0]; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: 9 }
                            TapHandler {
                                onTapped: vista.guardar(fila.clave, Math.max(fila.a.min, Math.min(fila.a.max, Number(fila.a.valor) + parent.modelData[1])))
                            }
                        }
                    }
                    Rectangle {
                        width: 54; height: 20; color: Tema.fondo; border.color: Tema.cian
                        Text { anchors.centerIn: parent; text: fila.a.valor; color: Tema.cian; font.family: Tema.mono; font.pixelSize: Tema.letra }
                    }
                    Repeater {
                        model: [["+1", 1], ["+5", 5]]
                        Rectangle {
                            required property var modelData
                            width: 26; height: 20; color: "transparent"; border.color: Tema.borde
                            Text { anchors.centerIn: parent; text: modelData[0]; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: 9 }
                            TapHandler {
                                onTapped: vista.guardar(fila.clave, Math.max(fila.a.min, Math.min(fila.a.max, Number(fila.a.valor) + parent.modelData[1])))
                            }
                        }
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        leftPadding: 6
                        text: fila.a.min + "–" + fila.a.max
                        color: Tema.apagado
                        font.family: Tema.mono
                        font.pixelSize: 9
                    }
                }
            }
            Component {
                id: cTexto
                Row {
                    spacing: 6
                    Entrada {
                        id: campo
                        width: 200
                        texto: fila.a.valor
                        onEditado: t => { const b = Object.assign({}, vista.borradores); b[fila.clave] = t; vista.borradores = b; }
                    }
                    Rectangle {
                        visible: vista.borradores[fila.clave] !== undefined && vista.borradores[fila.clave] !== fila.a.valor
                        width: tAplicar.implicitWidth + 14; height: 22; color: Tema.cian
                        Text { id: tAplicar; anchors.centerIn: parent; text: "APLICAR"; color: Tema.fondo; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                        TapHandler { onTapped: vista.guardar(fila.clave, vista.borradores[fila.clave]) }
                    }
                }
            }
        }
        Text {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            visible: fila.a !== null && fila.a.propio
            text: "↺ " + (fila.a ? String(fila.a.predeterminado).toUpperCase() : "")
            color: Tema.apagado
            font.family: Tema.mono
            font.pixelSize: 9
            TapHandler { onTapped: vista.restablecer(fila.clave) }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        Marco {
            Layout.fillWidth: true
            Layout.preferredHeight: vista.mensaje !== "" ? 78 : 62
            ident: "C0"
            etiqueta: "CONTROL CENTER SETTINGS"
            acento: Tema.cian
            Column {
                width: parent.width
                spacing: 4
                Text {
                    text: "Se guardan en ~/.config/jaime0/ajustes (jaime0-ajustes) y persisten tras reiniciar."
                    color: Tema.secundario
                    font.family: Tema.mono
                    font.pixelSize: Tema.letraMini
                }
                Text {
                    width: parent.width
                    visible: vista.mensaje !== ""
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                    text: (vista.mensajeError ? "△ " : "✓ ") + vista.mensaje
                    color: vista.mensajeError ? Tema.ambar : Tema.verde
                    font.family: Tema.mono
                    font.pixelSize: Tema.letraMini
                }
            }
        }

        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: columna.implicitHeight
            clip: true
            Column {
                id: columna
                width: parent.width
                spacing: 10
                Repeater {
                    model: vista.secciones
                    Marco {
                        id: tarjeta
                        required property var modelData
                        width: columna.width
                        height: 40 + modelData.claves.length * 30 + 22
                        ident: modelData.id
                        etiqueta: modelData.titulo
                        Column {
                            width: parent.width
                            spacing: 2
                            Repeater {
                                model: tarjeta.modelData.claves
                                Fila {
                                    required property string modelData
                                    clave: modelData
                                }
                            }
                            Text {
                                width: parent.width
                                text: tarjeta.modelData.nota
                                color: Tema.apagado
                                font.family: Tema.mono
                                font.pixelSize: 9
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
            }
        }
    }
}
