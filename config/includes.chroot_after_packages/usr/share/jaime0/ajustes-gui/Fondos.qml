import QtQuick

// Lista de fondos disponibles por nombre de archivo (sin miniaturas: ahorran ~10 MB).
Rectangle {
    id: fondos

    property var rutas: []
    property string valor: ""

    signal elegido(string ruta)

    function nombre(ruta) {
        return ruta.substring(ruta.lastIndexOf("/") + 1);
    }

    implicitHeight: lista.implicitHeight + 2
    radius: 6
    color: Tema.fondo
    border.width: 1
    border.color: Tema.borde

    Column {
        id: lista
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 1

        Text {
            visible: fondos.rutas.length === 0
            width: parent.width
            height: 30
            leftPadding: 12
            verticalAlignment: Text.AlignVCenter
            text: "No hay imágenes en /usr/share/backgrounds/jaime0 ni en ~/.local/share/backgrounds"
            elide: Text.ElideRight
            color: Tema.secundario
            font.family: Tema.fuente
            font.pixelSize: 11
        }

        Repeater {
            model: fondos.rutas

            Rectangle {
                required property string modelData
                readonly property bool marcado: modelData === fondos.valor

                width: lista.width
                height: 30
                radius: 5
                color: marcado || zona.containsMouse ? Tema.superficie2 : Tema.fondo

                Rectangle {
                    visible: parent.marcado
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    width: 2
                    height: 18
                    radius: 1
                    color: Tema.acento
                }

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.right: parent.right
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: fondos.nombre(parent.modelData)
                    elide: Text.ElideMiddle
                    color: parent.marcado ? Tema.texto : Tema.secundario
                    font.family: Tema.fuente
                    font.pixelSize: 12
                }

                MouseArea {
                    id: zona
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (!parent.marcado) fondos.elegido(parent.modelData)
                }
            }
        }
    }
}
