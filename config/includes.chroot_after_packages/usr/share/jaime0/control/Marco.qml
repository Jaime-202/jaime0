import QtQuick

// Panel tecnico: fondo plano, borde fino, marcas en las esquinas y una etiqueta con su
// identificador (p. ej. "02 · CPU"). Sin esquinas redondeadas ni sombras.
Rectangle {
    id: marco

    property string etiqueta: ""
    property string ident: ""
    property color acento: Tema.cian
    default property alias contenido: interior.data
    property int relleno: 12

    color: Tema.panel
    border.color: Tema.borde
    border.width: 1

    // Marcas de esquina (HUD): dos trazos cortos en cada esquina, en el color de acento.
    Repeater {
        model: 4
        Item {
            required property int index
            readonly property bool derecha: index % 2 === 1
            readonly property bool abajo: index >= 2
            x: derecha ? marco.width - 8 : 0
            y: abajo ? marco.height - 8 : 0
            width: 8
            height: 8
            Rectangle { x: parent.derecha ? 7 : 0; width: 1; height: 8; color: marco.acento; opacity: 0.8 }
            Rectangle { y: parent.abajo ? 7 : 0; width: 8; height: 1; color: marco.acento; opacity: 0.8 }
        }
    }

    Row {
        id: cabecera
        visible: marco.etiqueta !== ""
        x: marco.relleno
        y: 8
        spacing: 8
        Text {
            text: marco.ident
            visible: marco.ident !== ""
            color: marco.acento
            font.family: Tema.mono
            font.pixelSize: Tema.letraMini
        }
        Text {
            text: marco.etiqueta
            color: Tema.secundario
            font.family: Tema.mono
            font.pixelSize: Tema.letraMini
            font.letterSpacing: 1.5
        }
    }

    Item {
        id: interior
        anchors.fill: parent
        anchors.margins: marco.relleno
        anchors.topMargin: cabecera.visible ? 28 : marco.relleno
    }
}
