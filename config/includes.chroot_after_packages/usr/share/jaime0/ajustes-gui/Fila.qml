import QtQuick

// Un ajuste: etiqueta, control y boton para volver al valor predeterminado.
Item {
    id: fila

    property var ajuste: ({})
    property var temas: ({})
    property var fondos: []

    signal poner(string clave, string valor)
    signal restablecer(string clave)

    readonly property bool esFondo: ajuste.tipo === "fondo"
    readonly property string detalle: {
        if (ajuste.tipo === "acento")
            return ajuste.valor === ajuste.color ? ajuste.color : ajuste.valor + "  " + ajuste.color;
        if (ajuste.tipo === "fondo")
            return ajuste.valor.substring(ajuste.valor.lastIndexOf("/") + 1);
        return "";
    }

    // Tras cada lectura (tambien si un cambio ha fallado) el control vuelve al valor real.
    onAjusteChanged: if (control.item && control.item.reponer) control.item.reponer()

    implicitHeight: esFondo ? cabecera.height + listaFondos.height + 12 : cabecera.height

    Item {
        id: cabecera
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: fila.detalle !== "" ? 52 : 46

        Column {
            anchors.left: parent.left
            anchors.leftMargin: 14
            anchors.right: control.left
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            spacing: 3

            Text {
                width: parent.width
                text: fila.ajuste.etiqueta
                elide: Text.ElideRight
                color: Tema.texto
                font.family: Tema.fuente
                font.pixelSize: 12
            }
            Text {
                visible: fila.detalle !== ""
                width: parent.width
                text: fila.detalle
                elide: Text.ElideMiddle
                color: Tema.secundario
                font.family: Tema.fuente
                font.pixelSize: 11
            }
        }

        Loader {
            id: control
            anchors.right: botonRestablecer.left
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            sourceComponent: {
                switch (fila.ajuste.tipo) {
                case "entero":
                case "decimal":
                    return conDeslizador;
                case "sino":
                    return conInterruptor;
                case "opcion":
                    return conSelector;
                case "acento":
                    return conMuestras;
                default:
                    return null;
                }
            }
        }

        Rectangle {
            id: botonRestablecer
            anchors.right: parent.right
            anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            width: 24
            height: 24
            radius: 5
            visible: fila.ajuste.propio === true
            color: zonaRestablecer.containsMouse ? Tema.superficie2 : Tema.superficie
            border.width: 1
            border.color: zonaRestablecer.containsMouse ? Tema.borde : Tema.superficie

            Text {
                anchors.centerIn: parent
                text: "\u{f099b}"
                color: zonaRestablecer.containsMouse ? Tema.acento : Tema.secundario
                font.family: Tema.fuente
                font.pixelSize: 14
            }

            MouseArea {
                id: zonaRestablecer
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: fila.restablecer(fila.ajuste.clave)
            }
        }
    }

    Fondos {
        id: listaFondos
        visible: fila.esFondo
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: cabecera.bottom
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        height: fila.esFondo ? implicitHeight : 0
        rutas: fila.esFondo ? fila.fondos : []
        valor: fila.esFondo ? fila.ajuste.valor : ""
        onElegido: ruta => fila.poner(fila.ajuste.clave, ruta)
    }

    Component {
        id: conDeslizador

        Deslizador {
            readonly property bool decimal: fila.ajuste.tipo === "decimal"
            width: 190
            desde: fila.ajuste.min
            hasta: fila.ajuste.max
            paso: decimal ? 0.05 : 1
            decimales: decimal ? 2 : 0
            valor: Number(fila.ajuste.valor)
            onSoltado: nuevo => fila.poner(fila.ajuste.clave, nuevo.toFixed(decimales))
        }
    }

    Component {
        id: conInterruptor

        Interruptor {
            activo: fila.ajuste.valor === "si"
            onCambiado: nuevo => fila.poner(fila.ajuste.clave, nuevo ? "si" : "no")
        }
    }

    Component {
        id: conSelector

        Selector {
            opciones: fila.ajuste.opciones
            valor: fila.ajuste.valor
            onElegido: opcion => fila.poner(fila.ajuste.clave, opcion)
        }
    }

    Component {
        id: conMuestras

        Muestras {
            temas: fila.temas
            valor: fila.ajuste.valor
            onElegido: tema => fila.poner(fila.ajuste.clave, tema)
        }
    }
}
