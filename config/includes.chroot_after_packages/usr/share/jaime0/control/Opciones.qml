import QtQuick

// Opciones exclusivas (chips cuadrados). "opciones": [{valor, texto, disponible}].
// Con "ancho" > 0 pasan a la linea siguiente si no caben (editor de reglas, columnas
// estrechas); sin el, van en una sola fila.
Flow {
    id: fila

    property var opciones: []
    property string valor: ""
    property real ancho: 0
    signal elegido(string valor)

    spacing: 4
    width: ancho > 0 ? ancho : 2000

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
                color: chip.activo ? Tema.fondo : chip.usable ? Tema.secundario : Tema.apagado
                font.family: Tema.mono
                font.pixelSize: Tema.letraMini
            }
            Pulsar { enabled: chip.usable; onPulsado: fila.elegido(chip.modelData.valor) }
        }
    }
}
