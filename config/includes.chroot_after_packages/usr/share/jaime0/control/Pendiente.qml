import QtQuick

// Seccion aun no construida. Lo dice tal cual y explica que traera: no muestra datos
// inventados ni controles que no hacen nada.
Marco {
    id: pendiente

    property string seccion: ""
    property string fase: ""
    property var lista: []

    etiqueta: seccion
    ident: "··"
    acento: Tema.apagado

    Column {
        anchors.centerIn: parent
        width: Math.min(parent.width, 560)
        spacing: 14

        Text {
            text: "MODULE OFFLINE · " + pendiente.fase
            color: Tema.secundario
            font.family: Tema.mono
            font.pixelSize: 16
            font.letterSpacing: 2
        }
        Text {
            width: parent.width
            text: "Esta sección todavía no está construida. Llegará en la " + pendiente.fase.toLowerCase() + " con:"
            color: Tema.secundario
            font.family: Tema.mono
            font.pixelSize: Tema.letra
            wrapMode: Text.WordWrap
        }
        Repeater {
            model: pendiente.lista
            Text {
                required property var modelData
                width: parent.width
                text: "—  " + modelData
                color: Tema.apagado
                font.family: Tema.mono
                font.pixelSize: Tema.letra
                wrapMode: Text.WordWrap
            }
        }
    }
}
