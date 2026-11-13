import QtQuick

// Boton de un glifo de Nerd Font.
Item {
    id: boton

    property string glifo: ""
    property int tamano: 16
    property bool activo: true
    property bool resaltado: false

    signal pulsado()

    implicitWidth: tamano + 12
    implicitHeight: tamano + 8

    Texto {
        anchors.centerIn: parent
        text: boton.glifo
        font.pixelSize: boton.tamano
        color: !boton.activo ? Estado.borde
             : (zona.containsMouse || boton.resaltado ? Estado.acento : Estado.texto)
    }

    MouseArea {
        id: zona
        anchors.fill: parent
        hoverEnabled: true
        enabled: boton.activo
        cursorShape: Qt.PointingHandCursor
        onClicked: boton.pulsado()
    }
}
