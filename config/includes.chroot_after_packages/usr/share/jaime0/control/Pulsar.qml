import QtQuick

// Lo que hace pulsable a un elemento del Control Center, con raton y con teclado. Se pone
// dentro del boton (o de la fila) en lugar de un TapHandler:
//     Rectangle { ... Pulsar { enabled: ...; onPulsado: ... } }
// Tab y Mayus+Tab lo enfocan en el orden en que aparece; Intro o Espacio lo pulsan; el foco
// se ve con un marco claro alrededor, distinto de los colores de estado. Desactivado
// (enabled: false) no se puede enfocar ni pulsar. "nombre" es lo que lee un lector de
// pantalla (si no se da, el texto del primer Text del elemento).
Item {
    id: pulsar

    property string nombre: ""
    signal pulsado()

    anchors.fill: parent
    activeFocusOnTab: enabled
    Accessible.role: Accessible.Button
    Accessible.name: nombre !== "" ? nombre : textoDe(parent)
    Accessible.onPressAction: pulsado()

    function textoDe(item) {
        if (!item)
            return "";
        if (item.text !== undefined && typeof item.text === "string")
            return item.text;
        for (let i = 0; i < item.children.length; i++) {
            const t = textoDe(item.children[i]);
            if (t !== "")
                return t;
        }
        return "";
    }

    Keys.onReturnPressed: evento => { pulsar.pulsado(); evento.accepted = true; }
    Keys.onEnterPressed: evento => { pulsar.pulsado(); evento.accepted = true; }
    Keys.onSpacePressed: evento => { pulsar.pulsado(); evento.accepted = true; }

    TapHandler { onTapped: pulsar.pulsado() }

    // Marco de foco: blanco, por fuera del elemento, visible sobre cualquier tono.
    Rectangle {
        anchors.fill: parent
        anchors.margins: -3
        color: "transparent"
        border.color: Tema.texto
        border.width: 2
        visible: pulsar.activeFocus
    }
}
