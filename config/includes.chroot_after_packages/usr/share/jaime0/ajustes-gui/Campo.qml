import QtQuick

// Campo de texto de una linea (p. ej. la ciudad del tiempo). Se aplica al pulsar Intro o
// al salir del campo; Escape deshace lo escrito.
Rectangle {
    id: campo

    property string valor: ""
    property string pista: ""

    signal aplicado(string texto)

    width: 200
    height: 26
    radius: 5
    color: Tema.superficie
    border.width: 1
    border.color: entrada.activeFocus ? Tema.acento : Tema.borde

    onValorChanged: if (!entrada.activeFocus) entrada.text = valor

    TextInput {
        id: entrada
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        verticalAlignment: TextInput.AlignVCenter
        clip: true
        text: campo.valor
        color: Tema.texto
        selectionColor: Tema.acento
        selectedTextColor: Tema.fondo
        font.family: Tema.fuente
        font.pixelSize: 12
        maximumLength: 60

        function aplicar() {
            if (text.trim() !== campo.valor)
                campo.aplicado(text.trim());
        }

        onAccepted: { aplicar(); focus = false; }
        onActiveFocusChanged: if (!activeFocus) aplicar()
        Keys.onEscapePressed: event => { text = campo.valor; focus = false; event.accepted = true; }
    }

    Text {
        anchors.left: parent.left
        anchors.leftMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        visible: entrada.text === "" && !entrada.activeFocus
        text: campo.pista
        color: Tema.secundario
        font.family: Tema.fuente
        font.pixelSize: 12
    }
}
