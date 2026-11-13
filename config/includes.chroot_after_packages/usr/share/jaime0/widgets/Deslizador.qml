import QtQuick

// Deslizador fino. "movido" mientras se arrastra; "soltado" al soltar.
Item {
    id: deslizador

    property real valor: 0          // 0..1, valor real
    property real mostrado: valor
    readonly property bool arrastrando: zona.pressed

    signal movido(real nuevo)
    signal soltado(real nuevo)

    implicitHeight: 18

    onValorChanged: if (!zona.pressed) mostrado = valor

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        height: 4
        radius: 2
        color: Estado.borde
    }

    Rectangle {
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: asa.x + asa.width / 2
        height: 4
        radius: 2
        color: Estado.acento
    }

    Rectangle {
        id: asa
        width: 12
        height: 12
        radius: 3
        anchors.verticalCenter: parent.verticalCenter
        x: Math.max(0, Math.min(1, deslizador.mostrado)) * (deslizador.width - width)
        color: zona.pressed || zona.containsMouse ? Estado.texto : Estado.acento
    }

    MouseArea {
        id: zona
        anchors.fill: parent
        hoverEnabled: true
        preventStealing: true
        cursorShape: Qt.PointingHandCursor

        function fijar(x) {
            const ancho = deslizador.width - asa.width;
            deslizador.mostrado = ancho > 0 ? Math.max(0, Math.min(1, (x - asa.width / 2) / ancho)) : 0;
            deslizador.movido(deslizador.mostrado);
        }

        onPressed: evento => fijar(evento.x)
        onPositionChanged: evento => {
            if (pressed)
                fijar(evento.x);
        }
        onReleased: deslizador.soltado(deslizador.mostrado)
        onCanceled: deslizador.mostrado = deslizador.valor
    }
}
