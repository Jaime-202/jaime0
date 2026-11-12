import QtQuick

Rectangle {
    id: interruptor

    property bool activo: false

    signal cambiado(bool nuevo)

    implicitWidth: 36
    implicitHeight: 20
    radius: 5
    color: activo ? Tema.acento : Tema.superficie2
    border.width: 1
    border.color: activo ? Tema.acento : (zona.containsMouse ? Tema.secundario : Tema.borde)

    Rectangle {
        width: 12
        height: 12
        radius: 3
        anchors.verticalCenter: parent.verticalCenter
        x: interruptor.activo ? parent.width - width - 4 : 4
        color: interruptor.activo ? Tema.fondo : Tema.secundario
    }

    MouseArea {
        id: zona
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: interruptor.cambiado(!interruptor.activo)
    }
}
