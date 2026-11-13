import QtQuick

// Posicion de un widget: "No" o una casilla de una cuadricula de 3x3 que representa la
// pantalla (las casillas del centro a los lados no se usan).
Row {
    id: posicion

    property string valor: "no"

    signal elegido(string opcion)

    spacing: 8

    readonly property var casillas: [
        "arriba-izquierda", "arriba-centro", "arriba-derecha",
        "", "centro", "",
        "abajo-izquierda", "abajo-centro", "abajo-derecha"
    ]

    Rectangle {
        anchors.verticalCenter: parent.verticalCenter
        width: 40
        height: 24
        radius: 5
        readonly property bool marcado: posicion.valor === "no"
        color: marcado ? Tema.superficie2 : Tema.superficie
        border.width: 1
        border.color: marcado ? Tema.acento : (zonaNo.containsMouse ? Tema.secundario : Tema.borde)

        Text {
            anchors.centerIn: parent
            text: "No"
            color: parent.marcado ? Tema.acento : Tema.secundario
            font.family: Tema.fuente
            font.pixelSize: 12
        }
        MouseArea {
            id: zonaNo
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: if (!parent.marcado) posicion.elegido("no")
        }
    }

    // Marco de la "pantalla" con sus 7 posiciones.
    Rectangle {
        width: 54
        height: 36
        radius: 4
        color: Tema.superficie
        border.width: 1
        border.color: Tema.borde

        Grid {
            anchors.centerIn: parent
            columns: 3
            spacing: 3

            Repeater {
                model: posicion.casillas

                Rectangle {
                    required property string modelData
                    readonly property bool usable: modelData !== ""
                    readonly property bool marcado: usable && modelData === posicion.valor
                    width: 13
                    height: 8
                    radius: 2
                    color: marcado ? Tema.acento
                         : (!usable ? "transparent" : (zona.containsMouse ? Tema.secundario : Tema.borde))

                    MouseArea {
                        id: zona
                        anchors.fill: parent
                        anchors.margins: -1
                        enabled: parent.usable
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (!parent.marcado) posicion.elegido(parent.modelData)
                    }
                }
            }
        }
    }
}
