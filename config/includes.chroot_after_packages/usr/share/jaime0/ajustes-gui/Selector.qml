import QtQuick

// Una opcion entre varias (p. ej. arriba / abajo).
Row {
    id: selector

    property var opciones: []
    property string valor: ""

    signal elegido(string opcion)

    spacing: 4

    Repeater {
        model: selector.opciones

        Rectangle {
            required property string modelData
            readonly property bool marcado: modelData === selector.valor

            width: Math.max(64, nombre.implicitWidth + 20)
            height: 24
            radius: 5
            color: marcado ? Tema.superficie2 : Tema.superficie
            border.width: 1
            border.color: marcado ? Tema.acento : (zona.containsMouse ? Tema.secundario : Tema.borde)

            Text {
                id: nombre
                anchors.centerIn: parent
                text: parent.modelData
                color: parent.marcado ? Tema.acento : Tema.secundario
                font.family: Tema.fuente
                font.pixelSize: 12
            }

            MouseArea {
                id: zona
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: if (!parent.marcado) selector.elegido(parent.modelData)
            }
        }
    }
}
