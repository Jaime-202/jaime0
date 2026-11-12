import QtQuick

// Deslizador que solo avisa al soltar: cada cambio recarga Hyprland.
Item {
    id: deslizador

    property real desde: 0
    property real hasta: 1
    property real paso: 1
    property int decimales: 0
    property real valor: 0
    property real mostrado: valor

    signal soltado(real nuevo)

    readonly property real fraccion: hasta > desde ? Math.max(0, Math.min(1, (mostrado - desde) / (hasta - desde))) : 0

    implicitWidth: 190
    implicitHeight: 24

    function reponer() {
        if (!zona.pressed)
            mostrado = valor;
    }

    onValorChanged: reponer()

    Text {
        id: cifra
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: 34
        horizontalAlignment: Text.AlignRight
        text: deslizador.mostrado.toFixed(deslizador.decimales)
        color: zona.pressed ? Tema.acento : Tema.texto
        font.family: Tema.fuente
        font.pixelSize: 12
    }

    Item {
        id: carril
        anchors.left: parent.left
        anchors.right: cifra.left
        anchors.rightMargin: 12
        anchors.top: parent.top
        anchors.bottom: parent.bottom

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            height: 4
            radius: 2
            color: Tema.borde
        }

        Rectangle {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: asa.x + asa.width / 2
            height: 4
            radius: 2
            color: Tema.acento
        }

        Rectangle {
            id: asa
            width: 12
            height: 12
            radius: 3
            anchors.verticalCenter: parent.verticalCenter
            x: deslizador.fraccion * (carril.width - width)
            color: zona.pressed || zona.containsMouse ? Tema.texto : Tema.acento
        }

        MouseArea {
            id: zona
            anchors.fill: parent
            hoverEnabled: true
            preventStealing: true
            cursorShape: Qt.PointingHandCursor

            function fijar(x) {
                const ancho = carril.width - asa.width;
                const f = ancho > 0 ? Math.max(0, Math.min(1, (x - asa.width / 2) / ancho)) : 0;
                const pasos = Math.round(f * (deslizador.hasta - deslizador.desde) / deslizador.paso);
                const v = Math.min(deslizador.hasta, deslizador.desde + pasos * deslizador.paso);
                deslizador.mostrado = Number(v.toFixed(deslizador.decimales));
            }

            onPressed: evento => fijar(evento.x)
            onPositionChanged: evento => {
                if (pressed)
                    fijar(evento.x);
            }
            onReleased: {
                if (Math.abs(deslizador.mostrado - deslizador.valor) > 1e-9)
                    deslizador.soltado(deslizador.mostrado);
            }
            onCanceled: deslizador.mostrado = deslizador.valor
        }
    }
}
