import QtQuick

// Campo de texto de una linea, plano y monoespaciado. "validar" (opcional) devuelve true si
// el texto vale; si no, el borde se pone ambar.
Rectangle {
    id: entrada

    property alias texto: campo.text
    property string pista: ""
    property var validar: null
    property int maximo: 300
    readonly property bool valido: !validar || validar(campo.text)
    signal editado(string texto)

    implicitWidth: 160
    implicitHeight: 22
    color: Tema.fondo
    border.color: campo.activeFocus ? (valido ? Tema.cian : Tema.ambar) : (valido ? Tema.borde : Tema.ambar)
    border.width: 1

    TextInput {
        id: campo
        anchors.fill: parent
        anchors.leftMargin: 6
        anchors.rightMargin: 6
        verticalAlignment: TextInput.AlignVCenter
        color: Tema.texto
        selectionColor: Tema.cian
        selectedTextColor: Tema.fondo
        font.family: Tema.mono
        font.pixelSize: Tema.letraMini
        maximumLength: entrada.maximo
        clip: true
        onTextEdited: entrada.editado(text)
    }
    Text {
        anchors.fill: campo
        anchors.leftMargin: 6
        verticalAlignment: Text.AlignVCenter
        visible: campo.text === "" && !campo.activeFocus
        text: entrada.pista
        color: Tema.apagado
        font.family: Tema.mono
        font.pixelSize: Tema.letraMini
    }
}
