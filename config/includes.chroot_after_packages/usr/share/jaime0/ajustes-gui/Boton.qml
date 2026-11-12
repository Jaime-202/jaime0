import QtQuick

// Boton pequeno: un glifo de Nerd Font y, si hace falta, un texto.
Rectangle {
    id: boton

    property string glifo: ""
    property string texto: ""
    property bool activo: true

    signal pulsado()

    implicitWidth: texto !== "" ? fila.implicitWidth + 16 : 24
    implicitHeight: 24
    radius: 5
    color: activo && zona.containsMouse ? Tema.superficie2 : "transparent"
    border.width: 1
    border.color: texto !== "" ? (activo && zona.containsMouse ? Tema.secundario : Tema.borde)
                               : (activo && zona.containsMouse ? Tema.borde : "transparent")

    Row {
        id: fila
        anchors.centerIn: parent
        spacing: 6

        Text {
            visible: boton.glifo !== ""
            anchors.verticalCenter: parent.verticalCenter
            text: boton.glifo
            color: !boton.activo ? Tema.borde : (zona.containsMouse ? Tema.acento : Tema.secundario)
            font.family: Tema.fuente
            font.pixelSize: 14
        }
        Text {
            visible: boton.texto !== ""
            anchors.verticalCenter: parent.verticalCenter
            text: boton.texto
            color: !boton.activo ? Tema.borde : (zona.containsMouse ? Tema.texto : Tema.secundario)
            font.family: Tema.fuente
            font.pixelSize: 12
        }
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
