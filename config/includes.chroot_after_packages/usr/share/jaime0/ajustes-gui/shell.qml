//@ pragma Env QT_QUICK_BACKEND=software
// Aplicacion de ajustes de Jaime0. La abre "jaime0-ajustes" sin argumentos:
//   quickshell -p /usr/share/jaime0/ajustes-gui/shell.qml
// Lee los ajustes con "jaime0-ajustes ver --json" y los cambia con "poner" y
// "restablecer", que validan, guardan y aplican. Tras cada cambio se vuelven a leer.
// Se dibuja por software: es una ventana pequena y asi no carga OpenGL (menos memoria y
// funciona tambien en maquinas virtuales con aceleracion 3D rota).

import QtQuick
import Quickshell
import Quickshell.Io

ShellRoot {
    id: raiz

    property var datos: null
    property string error: ""
    property string leido: ""
    property var pendientes: []     // [{orden, clave}]
    property bool releer: false

    // Aplicaciones ancladas (jaime0-anclar). Se releen cuando cambia el ajuste "anclas".
    property var anclas: []
    property var disponibles: []
    property var ultimasAnclas: null
    property bool releerAnclas: false

    // Estructura (grupos y claves) y valores van por separado: al releer solo cambian los
    // valores y los controles se actualizan sin rehacerse (no se pierde el desplazamiento).
    property var estructura: []
    property string firma: ""
    property var mapa: ({})

    function cargar(d) {
        const nuevoMapa = {};
        const grupos = [];
        for (const a of d.ajustes) {
            nuevoMapa[a.clave] = a;
            let g = grupos.find(x => x.grupo === a.grupo);
            if (!g) {
                g = { grupo: a.grupo, claves: [] };
                grupos.push(g);
            }
            g.claves.push(a.clave);
            if (a.tipo === "acento" && a.color)
                Tema.acento = a.color;
        }
        mapa = nuevoMapa;
        datos = d;
        const valorAnclas = nuevoMapa.anclas ? nuevoMapa.anclas.valor : null;
        if (valorAnclas !== null && valorAnclas !== ultimasAnclas) {
            ultimasAnclas = valorAnclas;
            leerAnclas();
        }
        const nuevaFirma = JSON.stringify(grupos);
        if (nuevaFirma !== firma) {
            firma = nuevaFirma;
            estructura = grupos;
        }
    }
    readonly property bool ocupado: escritor.running || pendientes.length > 0

    function leer() {
        if (lector.running)
            releer = true;
        else
            lector.lanzar(["jaime0-ajustes", "ver", "--json"]);
    }

    function leerAnclas() {
        if (lectorAnclas.running)
            releerAnclas = true;
        else
            lectorAnclas.lanzar(["jaime0-anclar", "lista", "--json"]);
    }

    function leerDisponibles() {
        if (!lectorDisponibles.running)
            lectorDisponibles.lanzar(["jaime0-anclar", "disponibles", "--json"]);
    }

    // Una orden cada vez. Si llegan varias mientras se aplica otra, de cada ajuste solo
    // se guarda la ultima (las de jaime0-anclar van todas, en orden).
    function encolar(orden, clave) {
        error = "";
        if (escritor.running) {
            pendientes = pendientes.filter(p => clave === "" || p.clave !== clave).concat([{ orden: orden, clave: clave }]);
            return;
        }
        escritor.lanzar(orden);
    }

    function ejecutar(argumentos) {
        encolar(["jaime0-ajustes"].concat(argumentos), argumentos[1]);
    }

    function anclar(argumentos) {
        encolar(["jaime0-anclar"].concat(argumentos), "");
    }

    function mensaje(errores, codigo) {
        const texto = errores.trim().replace(/^jaime0-[a-z]+:\s*/, "");
        return texto !== "" ? texto : "La orden terminó con el código " + codigo;
    }

    settings.watchFiles: false

    Component.onCompleted: leer()

    // Si el archivo del usuario cambia por fuera (terminal, editor), se vuelve a leer.
    FileView {
        path: raiz.datos ? raiz.datos.archivo : ""
        watchChanges: true
        printErrors: false
        onFileChanged: raiz.leer()
    }

    Orden {
        id: lector
        onTerminado: (codigo, salida, errores) => {
            if (codigo !== 0) {
                raiz.error = raiz.mensaje(errores, codigo);
            } else if (salida !== raiz.leido) {
                try {
                    raiz.cargar(JSON.parse(salida));
                    raiz.leido = salida;
                } catch (e) {
                    raiz.error = "No se entiende la respuesta de jaime0-ajustes ver --json";
                }
            }
            if (raiz.releer) {
                raiz.releer = false;
                raiz.leer();
            }
        }
    }

    Orden {
        id: escritor
        onTerminado: (codigo, salida, errores) => {
            if (codigo !== 0)
                raiz.error = raiz.mensaje(errores, codigo);
            raiz.leido = "";  // rehace los controles aunque nada cambie (p. ej. tras un error)
            if (escritor.command[0] === "jaime0-anclar")
                raiz.ultimasAnclas = null;  // y relee tambien la lista de ancladas
            raiz.leer();
            if (raiz.pendientes.length > 0) {
                const siguiente = raiz.pendientes[0];
                raiz.pendientes = raiz.pendientes.slice(1);
                escritor.lanzar(siguiente.orden);
            }
        }
    }

    Orden {
        id: lectorAnclas
        onTerminado: (codigo, salida, errores) => {
            if (codigo !== 0) {
                raiz.error = raiz.mensaje(errores, codigo);
            } else {
                try {
                    raiz.anclas = JSON.parse(salida);
                } catch (e) {
                    raiz.error = "No se entiende la respuesta de jaime0-anclar lista --json";
                }
            }
            if (raiz.releerAnclas) {
                raiz.releerAnclas = false;
                raiz.leerAnclas();
            }
        }
    }

    Orden {
        id: lectorDisponibles
        onTerminado: (codigo, salida, errores) => {
            if (codigo !== 0) {
                raiz.error = raiz.mensaje(errores, codigo);
                return;
            }
            try {
                raiz.disponibles = JSON.parse(salida);
            } catch (e) {
                raiz.error = "No se entiende la respuesta de jaime0-anclar disponibles --json";
            }
        }
    }

    FloatingWindow {
        id: ventana

        title: "Ajustes de Jaime0"
        implicitWidth: 560
        implicitHeight: 640
        minimumSize: Qt.size(460, 360)
        color: Tema.fondo
        visible: true

        onVisibleChanged: if (!visible) Qt.quit()

        FocusScope {
            anchors.fill: parent
            focus: true
            Keys.onEscapePressed: Qt.quit()

            // Cabecera
            Rectangle {
                id: cabecera
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 52
                color: Tema.fondo

                Rectangle {
                    id: marca
                    anchors.left: parent.left
                    anchors.leftMargin: 20
                    anchors.verticalCenter: parent.verticalCenter
                    width: 8
                    height: 8
                    radius: 2
                    color: Tema.acento
                }

                Text {
                    id: titulo
                    anchors.left: marca.right
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Ajustes"
                    color: Tema.texto
                    font.family: Tema.fuente
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                }

                Text {
                    anchors.left: titulo.right
                    anchors.leftMargin: 16
                    anchors.right: parent.right
                    anchors.rightMargin: 20
                    anchors.verticalCenter: parent.verticalCenter
                    horizontalAlignment: Text.AlignRight
                    elide: Text.ElideLeft
                    text: {
                        if (raiz.ocupado)
                            return "aplicando…";
                        if (!raiz.datos)
                            return "";
                        const casa = Quickshell.env("HOME");
                        const ruta = raiz.datos.archivo;
                        return casa && ruta.startsWith(casa + "/") ? "~" + ruta.substring(casa.length) : ruta;
                    }
                    color: raiz.ocupado ? Tema.acento : Tema.secundario
                    font.family: Tema.fuente
                    font.pixelSize: 11
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 1
                    color: Tema.borde
                }
            }

            // Errores y avisos
            Rectangle {
                id: mensajes
                readonly property var avisos: raiz.datos ? raiz.datos.avisos : []
                visible: raiz.error !== "" || avisos.length > 0
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: visible ? columnaMensajes.implicitHeight + 24 : 0
                color: Tema.superficie

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    height: 1
                    color: Tema.borde
                }

                Column {
                    id: columnaMensajes
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 20
                    anchors.rightMargin: 20
                    spacing: 6

                    Item {
                        visible: raiz.error !== ""
                        width: parent.width
                        height: textoError.implicitHeight

                        Rectangle {
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: 2
                            radius: 1
                            color: Tema.error
                        }

                        Text {
                            id: textoError
                            anchors.left: parent.left
                            anchors.leftMargin: 12
                            anchors.right: cerrarError.left
                            anchors.rightMargin: 8
                            text: raiz.error
                            wrapMode: Text.Wrap
                            color: Tema.error
                            font.family: Tema.fuente
                            font.pixelSize: 12
                        }

                        Text {
                            id: cerrarError
                            anchors.right: parent.right
                            anchors.top: parent.top
                            text: "\u{f0156}"
                            color: zonaCerrar.containsMouse ? Tema.texto : Tema.secundario
                            font.family: Tema.fuente
                            font.pixelSize: 13

                            MouseArea {
                                id: zonaCerrar
                                anchors.fill: parent
                                anchors.margins: -4
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: raiz.error = ""
                            }
                        }
                    }

                    Repeater {
                        model: mensajes.avisos

                        Text {
                            required property string modelData
                            width: columnaMensajes.width
                            text: modelData
                            wrapMode: Text.Wrap
                            color: Tema.secundario
                            font.family: Tema.fuente
                            font.pixelSize: 11
                        }
                    }
                }
            }

            // Ajustes por grupos
            Flickable {
                id: desplazable
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: cabecera.bottom
                anchors.bottom: mensajes.top
                clip: true
                contentWidth: width
                contentHeight: contenido.implicitHeight + 40
                boundsBehavior: Flickable.StopAtBounds

                Column {
                    id: contenido
                    x: 16
                    y: 16
                    width: desplazable.width - 32
                    spacing: 18

                    Repeater {
                        model: raiz.estructura

                        Column {
                            id: grupo
                            required property var modelData
                            width: contenido.width
                            spacing: 8

                            Text {
                                leftPadding: 4
                                text: grupo.modelData.grupo.toUpperCase()
                                color: Tema.secundario
                                font.family: Tema.fuente
                                font.pixelSize: 10
                                font.letterSpacing: 1.2
                            }

                            Rectangle {
                                width: parent.width
                                height: filas.implicitHeight + 2
                                radius: 8
                                color: Tema.superficie
                                border.width: 1
                                border.color: Tema.borde

                                Column {
                                    id: filas
                                    x: 1
                                    y: 1
                                    width: parent.width - 2

                                    Repeater {
                                        model: grupo.modelData.claves

                                        Column {
                                            id: celda
                                            required property string modelData
                                            required property int index
                                            width: filas.width

                                            Rectangle {
                                                visible: celda.index > 0
                                                width: parent.width
                                                height: 1
                                                color: Tema.borde
                                            }

                                            Fila {
                                                width: parent.width
                                                height: implicitHeight
                                                ajuste: raiz.mapa[celda.modelData]
                                                temas: raiz.datos.temas
                                                fondos: raiz.datos.fondos
                                                anclas: raiz.anclas
                                                disponibles: raiz.disponibles
                                                ocupado: raiz.ocupado
                                                onAnclar: argumentos => raiz.anclar(argumentos)
                                                onPedirDisponibles: raiz.leerDisponibles()
                                                onPoner: (clave, valor) => raiz.ejecutar(["poner", clave, valor])
                                                onRestablecer: clave => raiz.ejecutar(["restablecer", clave])
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Indicador de desplazamiento
            Rectangle {
                visible: desplazable.contentHeight > desplazable.height
                anchors.right: parent.right
                anchors.rightMargin: 4
                y: desplazable.y + desplazable.visibleArea.yPosition * desplazable.height
                width: 3
                height: desplazable.visibleArea.heightRatio * desplazable.height
                radius: 1
                color: desplazable.moving ? Tema.secundario : Tema.borde
            }
        }
    }
}
