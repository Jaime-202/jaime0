import QtQuick

// Muestras de color de los temas de acento.
Row {
    id: muestras

    property var temas: ({})
    property string valor: ""

    signal elegido(string tema)

    spacing: 6

    Repeater {
        model: Object.keys(muestras.temas)

        Rectangle {
            required property string modelData
            readonly property bool marcado: modelData === muestras.valor

            width: 24
            height: 24
            radius: 6
            color: Tema.superficie
            border.width: 1
            border.color: marcado ? Tema.texto : (zona.containsMouse ? Tema.secundario : Tema.superficie)

            Rectangle {
                anchors.fill: parent
                anchors.margins: 3
                radius: 4
                color: muestras.temas[parent.modelData]
            }

            MouseArea {
                id: zona
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: if (!parent.marcado) muestras.elegido(parent.modelData)
            }
        }
    }
}
