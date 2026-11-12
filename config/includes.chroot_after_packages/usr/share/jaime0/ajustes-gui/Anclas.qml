import QtQuick

// Aplicaciones ancladas en la barra (jaime0-anclar): lista ordenada y, si "abierto",
// las disponibles para anclar.
Column {
    id: anclas

    property var lista: []          // jaime0-anclar lista --json
    property var disponibles: []    // jaime0-anclar disponibles --json
    property bool abierto: false
    property bool ocupado: false

    signal orden(var argumentos)    // argumentos de jaime0-anclar
    signal cerrar()

    readonly property string generico: "\u{f0614}"
    readonly property var ids: lista.map(a => a.id)
    readonly property var libres: disponibles.filter(a => ids.indexOf(a.id) < 0)

    spacing: 8

    // Ancladas, en orden
    Rectangle {
        width: parent.width
        height: columna.implicitHeight + 2
        radius: 6
        color: Tema.fondo
        border.width: 1
        border.color: Tema.borde

        Column {
            id: columna
            x: 1
            y: 1
            width: parent.width - 2

            Text {
                visible: anclas.lista.length === 0
                width: parent.width
                height: 32
                leftPadding: 12
                verticalAlignment: Text.AlignVCenter
                text: "Ninguna aplicación anclada"
                color: Tema.secundario
                font.family: Tema.fuente
                font.pixelSize: 12
            }

            Repeater {
                model: anclas.lista

                Rectangle {
                    id: ancla
                    required property var modelData
                    required property int index
                    readonly property bool instalada: modelData.instalada !== false

                    width: columna.width
                    height: 32
                    radius: 5
                    color: zona.hovered ? Tema.superficie2 : Tema.fondo

                    HoverHandler {
                        id: zona
                    }

                    Text {
                        id: icono
                        anchors.left: parent.left
                        anchors.leftMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        width: 20
                        horizontalAlignment: Text.AlignHCenter
                        text: ancla.modelData.icono || anclas.generico
                        color: ancla.instalada ? Tema.acento : Tema.borde
                        font.family: Tema.fuente
                        font.pixelSize: 15
                    }

                    Text {
                        anchors.left: icono.right
                        anchors.leftMargin: 10
                        anchors.right: botones.left
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        text: ancla.modelData.nombre + (ancla.instalada ? "" : "  · no instalada")
                        elide: Text.ElideRight
                        color: ancla.instalada ? Tema.texto : Tema.secundario
                        font.family: Tema.fuente
                        font.pixelSize: 12
                    }

                    Row {
                        id: botones
                        anchors.right: parent.right
                        anchors.rightMargin: 4
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 0

                        Boton {
                            glifo: "\u{f005d}"
                            activo: !anclas.ocupado && ancla.index > 0
                            onPulsado: anclas.orden(["mover", ancla.modelData.id, String(ancla.index)])
                        }
                        Boton {
                            glifo: "\u{f0045}"
                            activo: !anclas.ocupado && ancla.index < anclas.lista.length - 1
                            onPulsado: anclas.orden(["mover", ancla.modelData.id, String(ancla.index + 2)])
                        }
                        Boton {
                            glifo: "\u{f0156}"
                            activo: !anclas.ocupado
                            onPulsado: anclas.orden(["quitar", ancla.modelData.id])
                        }
                    }
                }
            }
        }
    }

    // Disponibles para anclar. Solo se crea mientras esta desplegada.
    Loader {
        active: anclas.abierto
        visible: active
        sourceComponent: panelLibres  // sin tamano propio: toma el del panel
    }

    Component {
        id: panelLibres

        Rectangle {
            width: anclas.width
            height: Math.max(30, Math.min(libresVista.contentHeight, 6 * 30)) + 2
            radius: 6
            color: Tema.fondo
            border.width: 1
            border.color: Tema.borde

            Flickable {
                id: libresVista
                anchors.fill: parent
                anchors.margins: 1
                clip: true
                contentWidth: width
                contentHeight: disponiblesColumna.implicitHeight
                boundsBehavior: Flickable.StopAtBounds

                Column {
                    id: disponiblesColumna
                    width: libresVista.width

                    Text {
                        visible: anclas.libres.length === 0
                        width: parent.width
                        height: 30
                        leftPadding: 12
                        verticalAlignment: Text.AlignVCenter
                        text: anclas.disponibles.length === 0 ? "Buscando aplicaciones…" : "No hay más aplicaciones"
                        color: Tema.secundario
                        font.family: Tema.fuente
                        font.pixelSize: 12
                    }

                    Repeater {
                        model: anclas.libres

                        Rectangle {
                            id: libre
                            required property var modelData

                            width: disponiblesColumna.width
                            height: 30
                            radius: 5
                            color: zonaLibre.containsMouse ? Tema.superficie2 : Tema.fondo

                            Text {
                                id: iconoLibre
                                anchors.left: parent.left
                                anchors.leftMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                width: 20
                                horizontalAlignment: Text.AlignHCenter
                                text: libre.modelData.icono || anclas.generico
                                color: zonaLibre.containsMouse ? Tema.acento : Tema.secundario
                                font.family: Tema.fuente
                                font.pixelSize: 15
                            }

                            Text {
                                anchors.left: iconoLibre.right
                                anchors.leftMargin: 10
                                anchors.right: parent.right
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                text: libre.modelData.nombre
                                elide: Text.ElideRight
                                color: zonaLibre.containsMouse ? Tema.texto : Tema.secundario
                                font.family: Tema.fuente
                                font.pixelSize: 12
                            }

                            MouseArea {
                                id: zonaLibre
                                anchors.fill: parent
                                hoverEnabled: true
                                enabled: !anclas.ocupado
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    anclas.orden([libre.modelData.id]);
                                    anclas.cerrar();
                                }
                            }
                        }
                    }
                }
            }

            // Indicador de desplazamiento
            Rectangle {
                visible: libresVista.height > 0 && libresVista.contentHeight > libresVista.height
                anchors.right: parent.right
                anchors.rightMargin: 3
                y: 1 + libresVista.visibleArea.yPosition * libresVista.height
                width: 3
                height: libresVista.visibleArea.heightRatio * libresVista.height
                radius: 1
                color: Tema.borde
            }
        }
    }
}
