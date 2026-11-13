import QtQuick

// Un ajuste: etiqueta, control y boton para volver al valor predeterminado.
Item {
    id: fila

    property var ajuste: ({})
    property var temas: ({})
    property var fondos: []
    property var anclas: []          // jaime0-anclar lista --json
    property var disponibles: []     // jaime0-anclar disponibles --json
    property bool ocupado: false
    property bool abierto: false     // lista de aplicaciones para anclar desplegada

    signal poner(string clave, string valor)
    signal restablecer(string clave)
    signal anclar(var argumentos)
    signal pedirDisponibles()

    readonly property bool esFondo: ajuste.tipo === "fondo"
    readonly property bool esAnclas: ajuste.tipo === "anclas"
    readonly property bool llena: esAnclas && anclas.length >= (ajuste.max || 6)
    readonly property string detalle: {
        if (ajuste.tipo === "acento")
            return ajuste.valor === ajuste.color ? ajuste.color : ajuste.valor + "  " + ajuste.color;
        if (ajuste.tipo === "fondo")
            return ajuste.valor.substring(ajuste.valor.lastIndexOf("/") + 1);
        if (ajuste.tipo === "anclas")
            return anclas.length + " de " + (ajuste.max || 6);
        return "";
    }

    // Tras cada lectura (tambien si un cambio ha fallado) el control vuelve al valor real.
    onAjusteChanged: if (control.item && control.item.reponer) control.item.reponer()

    onLlenaChanged: if (llena) abierto = false

    implicitHeight: esFondo ? cabecera.height + listaFondos.height + 12
                  : esAnclas ? cabecera.height + listaAnclas.height + 12
                  : cabecera.height

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
                    return fila.ajuste.clave.startsWith("widget_") ? conPosicion : conSelector;
                case "texto":
                    return conCampo;
                case "acento":
                    return conMuestras;
                case "anclas":
                    return conAnadir;
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

    Loader {
        id: listaAnclas
        active: fila.esAnclas
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: cabecera.bottom
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        height: item ? item.implicitHeight : 0

        sourceComponent: Anclas {
            lista: fila.anclas
            disponibles: fila.disponibles
            abierto: fila.abierto
            ocupado: fila.ocupado
            onOrden: argumentos => fila.anclar(argumentos)
            onCerrar: fila.abierto = false
        }
    }

    Component {
        id: conAnadir

        Boton {
            glifo: fila.abierto ? "\u{f0143}" : "\u{f0415}"
            texto: fila.abierto ? "Cerrar" : "Añadir"
            activo: fila.abierto || (!fila.ocupado && !fila.llena)
            onPulsado: {
                fila.abierto = !fila.abierto;
                if (fila.abierto)
                    fila.pedirDisponibles();
            }
        }
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
        id: conPosicion

        Posicion {
            valor: fila.ajuste.valor
            onElegido: opcion => fila.poner(fila.ajuste.clave, opcion)
        }
    }

    Component {
        id: conCampo

        Campo {
            valor: fila.ajuste.valor
            pista: "Escribe tu ciudad"
            onAplicado: texto => fila.poner(fila.ajuste.clave, texto)
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
