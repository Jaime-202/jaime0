import QtQuick

// Fila de opciones exclusivas (chips cuadrados). "opciones": [{valor, texto, disponible}].
Row {
    id: fila

    property var opciones: []
    property string valor: ""
    signal elegido(string valor)

    spacing: 4

    Repeater {
        model: fila.opciones
        Rectangle {
            id: chip
            required property var modelData
            readonly property bool activo: fila.valor === modelData.valor
            readonly property bool usable: modelData.disponible !== false
            width: texto.implicitWidth + 14
            height: 20
            color: activo ? Tema.cian : "transparent"
            border.color: activo ? Tema.cian : usable ? Tema.borde : Tema.rejilla
            border.width: 1
            Behavior on color { ColorAnimation { duration: Tema.rapido } }
            Text {
                id: texto
                anchors.centerIn: parent
                text: chip.modelData.texto
                color: chip.activo ? Tema.fondo : chip.usable ? Tema.secundario : Tema.rejilla
                font.family: Tema.mono
                font.pixelSize: Tema.letraMini
            }
            TapHandler { enabled: chip.usable; onTapped: fila.elegido(chip.modelData.valor) }
        }
    }
}
