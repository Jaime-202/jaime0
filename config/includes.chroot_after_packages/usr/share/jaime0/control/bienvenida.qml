//@ pragma Env QT_QUICK_BACKEND=software
// Bienvenida: primeros pasos tras instalar. La abre "jaime0-bienvenida" (la primera vez que
// se entra en el escritorio, o a mano desde el lanzador):
//   quickshell -p /usr/share/jaime0/control/bienvenida.qml
// Cada paso muestra el estado real del equipo (nmcli, jaime0-nvidia, atajos) y abre las
// herramientas que ya existen; aqui no se cambia nada por si solo.

import QtQuick
import Quickshell
import Quickshell.Io

ShellRoot {
    id: raiz

    property int paso: 0
    readonly property var pasos: ["BIENVENIDA", "RED", "GRÁFICA", "CUENTA", "ATAJOS", "LISTO"]
    property string red: ""
    property string nvidia: ""
    property var atajos: []
    readonly property string usuario: Quickshell.env("USER") || ""

    // Los atajos que conviene saber el primer dia (por su descripcion en hyprland.lua).
    readonly property var esenciales: ["Lanzador de aplicaciones", "Abrir la terminal", "Ver todos los atajos",
        "Cerrar la ventana", "Control Center", "Red y Wi-Fi", "Gestor de archivos", "Menú de energía"]

    function abrir(orden) {
        lanzador.command = orden;
        lanzador.running = true;
    }
    function terminal(orden) {
        abrir(["kitty", "--class", "nmtui-flotante", "-e", "sh", "-c",
               orden + "; printf '\\nPulsa Intro para cerrar. '; read -r _"]);
    }
    function comprobar() {
        consultaRed.running = true;
        consultaNvidia.running = true;
        consultaAtajos.running = true;
    }

    Process { id: lanzador }
    Process {
        id: consultaRed
        command: ["nmcli", "-t", "-f", "STATE", "general"]
        stdout: StdioCollector { onStreamFinished: raiz.red = this.text.trim() }
        onExited: (codigo) => { if (codigo !== 0) raiz.red = "sin NetworkManager"; }
    }
    Process {
        id: consultaNvidia
        command: ["jaime0-nvidia"]
        stdout: StdioCollector { onStreamFinished: raiz.nvidia = this.text.trim() }
    }
    Process {
        id: consultaAtajos
        command: ["atajos"]
        stdout: StdioCollector {
            onStreamFinished: {
                const filas = [];
                for (const linea of this.text.split("\n")) {
                    const partes = linea.trim().split(/\s{2,}/);
                    if (partes.length < 2) continue;
                    const desc = partes.slice(1).join(" ");
                    if (raiz.esenciales.some(e => desc.indexOf(e) === 0))
                        filas.push({ teclas: partes[0], desc: desc });
                }
                raiz.atajos = filas;
            }
        }
    }
    // Nombre del sistema (marca.conf, PRODUCTO="..."), el unico sitio donde se escribe.
    FileView {
        id: archivoMarca
        path: "/usr/local/share/marca/marca.conf"
        blockLoading: true
        printErrors: false
        onLoaded: {
            const m = archivoMarca.text().match(/^PRODUCTO="?([^"\n]+)"?$/m);
            if (m) Tema.producto = m[1];
        }
    }
    Component.onCompleted: comprobar()

    FloatingWindow {
        id: ventana
        visible: true
        title: "Bienvenida"
        implicitWidth: 720
        implicitHeight: 520
        color: Tema.fondo
        onVisibleChanged: if (!visible) Qt.quit()

        Item {
            id: lienzo
            anchors.fill: parent
            focus: true
            Keys.onEscapePressed: Qt.quit()
            Keys.onRightPressed: if (raiz.paso < raiz.pasos.length - 1) raiz.paso++
            Keys.onLeftPressed: if (raiz.paso > 0) raiz.paso--

            // Pasos arriba: el actual en verde.
            Row {
                id: indice
                x: 28
                y: 22
                spacing: 18
                Repeater {
                    model: raiz.pasos
                    Text {
                        required property int index
                        required property string modelData
                        text: String(index + 1).padStart(2, "0") + " " + modelData
                        color: index === raiz.paso ? Tema.verde : Tema.apagado
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                        font.letterSpacing: 1.5
                    }
                }
            }

            Marco {
                id: panel
                anchors.top: indice.bottom
                anchors.topMargin: 16
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: pie.top
                anchors.margins: 28
                anchors.bottomMargin: 16
                etiqueta: raiz.pasos[raiz.paso]
                ident: String(raiz.paso + 1).padStart(2, "0")
                acento: Tema.verde
                relleno: 22

                Column {
                    anchors.fill: parent
                    spacing: 14

                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        color: Tema.texto
                        font.family: Tema.mono
                        font.pixelSize: 18
                        text: ["Te damos la bienvenida a " + Tema.producto,
                               "Conexión a internet",
                               "Gráfica NVIDIA",
                               "Tu cuenta",
                               "Atajos para empezar",
                               "Todo listo"][raiz.paso]
                    }
                    Texto {
                        visible: raiz.paso === 0
                        text: "El sistema ya está instalado. Estos pasos revisan lo que conviene tener a punto el primer día: la red, la gráfica, tu cuenta y los atajos de teclado.\n\nNo cambian nada por sí solos: cada botón abre la herramienta que hace falta. Puedes cerrar esta ventana cuando quieras; se vuelve a abrir buscando \"Bienvenida\" en el lanzador (SUPER + Espacio)."
                    }

                    // ── Red ──
                    Texto {
                        visible: raiz.paso === 1
                        color: raiz.red === "connected" ? Tema.verde : Tema.ambar
                        text: raiz.red === "" ? "Comprobando..." :
                              raiz.red === "connected" ? "Conectado a internet." :
                              raiz.red.indexOf("connected") === 0 ? "Conectado, pero sin salida completa a internet (" + raiz.red + ")." :
                              "Sin conexión (" + raiz.red + ")."
                    }
                    Texto {
                        visible: raiz.paso === 1
                        text: "Las actualizaciones y la instalación de programas necesitan red. La red y el Wi-Fi se configuran desde el icono de la barra o con SUPER + W."
                    }
                    Row {
                        visible: raiz.paso === 1
                        spacing: 10
                        Boton { texto: "Configurar la red"; onPulsado: raiz.abrir(["kitty", "--class", "nmtui-flotante", "-e", "nmtui"]) }
                        Boton { texto: "Comprobar de nuevo"; onPulsado: consultaRed.running = true }
                    }

                    // ── Grafica ──
                    Texto {
                        visible: raiz.paso === 2
                        text: raiz.nvidia === "" ? "Comprobando..." : raiz.nvidia
                        font.pixelSize: Tema.letraMini + 1
                    }
                    Texto {
                        visible: raiz.paso === 2 && raiz.nvidia.indexOf("jaime0-nvidia registrar") >= 0
                        text: "Con Secure Boot hay que registrar una vez la clave del controlador: este botón abre una terminal que explica cada paso."
                    }
                    Row {
                        visible: raiz.paso === 2
                        spacing: 10
                        Boton {
                            visible: raiz.nvidia.indexOf("jaime0-nvidia registrar") >= 0
                            texto: "Registrar la clave"
                            onPulsado: raiz.terminal("jaime0-nvidia registrar")
                        }
                        Boton { texto: "Comprobar de nuevo"; onPulsado: consultaNvidia.running = true }
                    }

                    // ── Cuenta ──
                    Texto {
                        visible: raiz.paso === 3
                        text: "Usuario: " + raiz.usuario + "\n\nLa clave que elegiste al instalar sirve para entrar, desbloquear la pantalla y para sudo. Si el disco va cifrado, su clave es aparte y se pide al arrancar.\n\nLa privacidad (cortafuegos, ubicación, cámara) se revisa en el Control Center, sección PRIVACY & SECURITY."
                    }
                    Row {
                        visible: raiz.paso === 3
                        spacing: 10
                        Boton { texto: "Cambiar mi clave"; onPulsado: raiz.terminal("passwd") }
                        Boton { texto: "Abrir el Control Center"; onPulsado: raiz.abrir(["jaime0-control"]) }
                    }

                    // ── Atajos ──
                    Column {
                        visible: raiz.paso === 4
                        spacing: 6
                        Repeater {
                            model: raiz.atajos
                            Row {
                                required property var modelData
                                spacing: 14
                                Text { width: 210; text: modelData.teclas; color: Tema.cian; font.family: Tema.mono; font.pixelSize: Tema.letra }
                                Text { text: modelData.desc; color: Tema.texto; font.family: Tema.mono; font.pixelSize: Tema.letra }
                            }
                        }
                        Texto {
                            visible: raiz.atajos.length === 0
                            text: "No se pudo leer la lista de atajos de Hyprland. En una terminal: atajos"
                        }
                    }
                    Boton { visible: raiz.paso === 4; texto: "Ver todos los atajos"; onPulsado: raiz.abrir(["atajos", "--rofi"]) }

                    // ── Listo ──
                    Texto {
                        visible: raiz.paso === 5
                        text: "Conviene buscar actualizaciones ahora: la instalación trae los paquetes del día en que se compiló el sistema.\n\nEl Control Center (SUPER + I) reúne el estado del equipo, los perfiles, la energía y las actualizaciones."
                    }
                    Row {
                        visible: raiz.paso === 5
                        spacing: 10
                        Boton {
                            texto: "Buscar actualizaciones"
                            onPulsado: raiz.abrir(["kitty", "--class", "actualizaciones", "-e", "sh", "-c",
                                                   "actualizaciones; echo; echo Pulsa Intro para cerrar.; read -r _"])
                        }
                        Boton { texto: "Abrir el Control Center"; onPulsado: raiz.abrir(["jaime0-control"]) }
                    }
                }
            }

            // Navegacion.
            Row {
                id: pie
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 28
                spacing: 10
                Boton { visible: raiz.paso > 0; texto: "Atrás"; onPulsado: raiz.paso-- }
                Boton {
                    texto: raiz.paso < raiz.pasos.length - 1 ? "Siguiente" : "Terminar"
                    principal: true
                    onPulsado: raiz.paso < raiz.pasos.length - 1 ? raiz.paso++ : Qt.quit()
                }
            }
            Text {
                anchors.left: parent.left
                anchors.verticalCenter: pie.verticalCenter
                anchors.leftMargin: 28
                text: "← → pasos    Tab botones    Esc cerrar"
                color: Tema.apagado
                font.family: Tema.mono
                font.pixelSize: Tema.letraMini
            }
        }
    }

    component Texto: Text {
        width: parent ? parent.width : 0
        wrapMode: Text.WordWrap
        color: Tema.secundario
        font.family: Tema.mono
        font.pixelSize: Tema.letra
        lineHeight: 1.2
    }
    component Boton: Rectangle {
        id: boton
        property string texto: ""
        property bool principal: false
        signal pulsado()
        width: etiqueta.implicitWidth + 28
        height: 32
        color: principal ? Tema.verde : Tema.panel2
        border.color: principal ? Tema.verde : Tema.borde
        border.width: 1
        Text {
            id: etiqueta
            anchors.centerIn: parent
            text: boton.texto
            color: boton.principal ? Tema.fondo : Tema.texto
            font.family: Tema.mono
            font.pixelSize: Tema.letra
        }
        Pulsar { onPulsado: boton.pulsado() }
    }
}
