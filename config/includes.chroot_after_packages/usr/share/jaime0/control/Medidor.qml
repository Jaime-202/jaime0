import QtQuick

// Valor tecnico: etiqueta, cifra grande en monoespaciada, detalle y una barra de nivel
// segmentada. "valor" es null cuando el dato no existe: se muestra N/D y no hay barra.
Item {
    id: medidor

    property string etiqueta: ""
    property var valor: null          // numero o null
    property string unidad: ""
    property int decimales: 0
    property string detalle: ""
    property real nivel: -1           // 0..1 para la barra; -1 sin barra
    property real aviso: 0.85
    property real critico: 0.95

    readonly property bool disponible: valor !== null && valor !== undefined
    readonly property color colorNivel: nivel >= critico ? Tema.rojo : nivel >= aviso ? Tema.ambar : Tema.verde

    implicitHeight: columna.implicitHeight

    Column {
        id: columna
        width: parent.width
        spacing: 4

        Text {
            text: medidor.etiqueta
            color: Tema.secundario
            font.family: Tema.mono
            font.pixelSize: Tema.letraMini
            font.letterSpacing: 1.5
        }
        Row {
            spacing: 4
            Text {
                text: medidor.disponible ? Number(medidor.valor).toFixed(medidor.decimales) : "N/D"
                color: medidor.disponible ? Tema.texto : Tema.apagado
                font.family: Tema.mono
                font.pixelSize: Tema.letraDato
            }
            Text {
                visible: medidor.disponible && medidor.unidad !== ""
                anchors.baseline: parent.children[0].baseline
                text: medidor.unidad
                color: Tema.secundario
                font.family: Tema.mono
                font.pixelSize: Tema.letra
            }
        }
        // Barra de 20 segmentos: se ve el nivel sin degradados.
        Row {
            visible: medidor.nivel >= 0
            spacing: 2
            Repeater {
                model: 20
                Rectangle {
                    required property int index
                    width: Math.max(2, (columna.width - 38) / 20)
                    height: 4
                    color: (index + 0.5) / 20 <= medidor.nivel ? medidor.colorNivel : Tema.rejilla
                    Behavior on color { ColorAnimation { duration: Tema.medio } }
                }
            }
        }
        Text {
            visible: medidor.detalle !== ""
            width: parent.width
            text: medidor.detalle
            color: Tema.secundario
            font.family: Tema.mono
            font.pixelSize: Tema.letraMini
            elide: Text.ElideRight
        }
    }
}
