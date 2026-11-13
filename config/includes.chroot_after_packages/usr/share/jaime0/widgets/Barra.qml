import QtQuick

// Barra fina de progreso o de uso.
Item {
    id: barra

    property real valor: 0          // 0..1
    property color color: Estado.acento

    implicitHeight: 4

    Rectangle {
        anchors.fill: parent
        radius: 2
        color: Estado.borde
    }

    Rectangle {
        width: Math.round(parent.width * Math.max(0, Math.min(1, barra.valor)))
        height: parent.height
        radius: 2
        color: barra.color
    }
}
