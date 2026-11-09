/* Presentacion original que acompana a la copia del sistema. */
import QtQuick 2.5
import QtQuick.Layouts 1.3
import calamares.slideshow 1.0
import io.calamares.ui 1.0

Presentation {
    id: presentacion

    readonly property string fuente: "JetBrainsMono Nerd Font"
    readonly property string producto: Branding.string(Branding.ProductName)

    Timer {
        interval: 14000
        running: presentacion.activatedInCalamares
        repeat: true
        onTriggered: presentacion.goToNextSlide()
    }

    Rectangle {
        anchors.fill: parent
        z: -1
        color: "#12141d"
    }

    // Puntos de posicion
    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 14
        spacing: 8
        z: 2
        Repeater {
            model: 5
            Rectangle {
                width: 7; height: 7; radius: 4
                color: index === presentacion.currentSlide ? "#7ab0ff" : "#2f3b52"
            }
        }
    }

    component Titulo: Text {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        color: "#f2f4fb"
        font.family: presentacion.fuente
        font.pixelSize: 24
        font.bold: true
    }
    component Parrafo: Text {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        color: "#b6bcd4"
        font.family: presentacion.fuente
        font.pixelSize: 14
        lineHeight: 1.25
    }
    component Etiqueta: Text {
        color: "#7ab0ff"
        font.family: presentacion.fuente
        font.pixelSize: 13
        font.bold: true
    }
    component Dato: Text {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        color: "#e0e4f2"
        font.family: presentacion.fuente
        font.pixelSize: 14
    }
    component Tecla: Rectangle {
        property alias texto: rotulo.text
        Layout.preferredHeight: 28
        Layout.preferredWidth: rotulo.implicitWidth + 20
        radius: 3
        color: "#171a26"
        border.color: "#2f3b52"
        Text {
            id: rotulo
            anchors.centerIn: parent
            color: "#f2f4fb"
            font.family: presentacion.fuente
            font.pixelSize: 12
            font.bold: true
        }
    }
    component Orden: Rectangle {
        property alias texto: linea.text
        Layout.fillWidth: true
        Layout.preferredHeight: 50
        radius: 3
        color: "#171a26"
        border.color: "#2f3b52"
        Text {
            id: linea
            anchors.verticalCenter: parent.verticalCenter
            x: 16
            color: "#f2f4fb"
            font.family: presentacion.fuente
            font.pixelSize: 14
        }
    }

    Slide {
        anchors.fill: parent
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 40
            anchors.bottomMargin: 44
            spacing: 16
            Titulo { text: presentacion.producto + " se está instalando" }
            Parrafo { text: "Puedes seguir usando el equipo con normalidad. Te avisaremos cuando termine." }
            Item { Layout.preferredHeight: 6 }
            GridLayout {
                columns: 2; columnSpacing: 22; rowSpacing: 12
                Layout.fillWidth: true
                Etiqueta { text: "Escritorio" }  Dato { text: "Hyprland sobre Wayland, con ventanas en mosaico" }
                Etiqueta { text: "Terminal" }    Dato { text: "Kitty, Zsh y Neovim, listos para usar" }
                Etiqueta { text: "Archivos" }    Dato { text: "Thunar, con montaje automático de USB" }
                Etiqueta { text: "Sistema" }     Dato { text: "Solo lo necesario, sin programas de relleno" }
            }
            Item { Layout.fillHeight: true }
        }
    }

    Slide {
        anchors.fill: parent
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 40
            anchors.bottomMargin: 44
            spacing: 16
            Titulo { text: "Todo a mano desde el teclado" }
            Parrafo { text: "La tecla SUPER, la del logotipo, abre y organiza las ventanas." }
            Item { Layout.preferredHeight: 6 }
            GridLayout {
                columns: 2; columnSpacing: 22; rowSpacing: 10
                Layout.fillWidth: true
                Tecla { texto: "SUPER + Intro" }    Dato { text: "Abrir la terminal" }
                Tecla { texto: "SUPER + Espacio" }  Dato { text: "Buscar aplicaciones" }
                Tecla { texto: "SUPER + E" }        Dato { text: "Abrir los archivos" }
                Tecla { texto: "SUPER + Q" }        Dato { text: "Cerrar la ventana" }
                Tecla { texto: "SUPER + 1…9" }      Dato { text: "Cambiar de escritorio" }
            }
            Item { Layout.fillHeight: true }
        }
    }

    Slide {
        anchors.fill: parent
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 40
            anchors.bottomMargin: 44
            spacing: 16
            Titulo { text: "La barra te dice lo importante" }
            Parrafo { text: "Haz clic en cada dato de la barra superior para actuar sobre él." }
            Item { Layout.preferredHeight: 6 }
            GridLayout {
                columns: 2; columnSpacing: 22; rowSpacing: 12
                Layout.fillWidth: true
                Etiqueta { text: "CPU · MEM" }  Dato { text: "Abre el monitor del sistema" }
                Etiqueta { text: "VOL" }        Dato { text: "Abre el control de sonido; la rueda cambia el volumen" }
                Etiqueta { text: "ETH · WIFI" } Dato { text: "Configura la red" }
                Etiqueta { text: "<" }          Dato { text: "Despliega la bandeja del sistema" }
                Etiqueta { text: "PWR" }        Dato { text: "Apagar, reiniciar, suspender o cerrar sesión" }
            }
            Item { Layout.fillHeight: true }
        }
    }

    Slide {
        anchors.fill: parent
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 40
            anchors.bottomMargin: 44
            spacing: 16
            Titulo { text: "Primeros pasos" }
            Parrafo { text: "El sistema no incluye navegador, para que elijas el tuyo. Con una terminal abierta:" }
            Orden { texto: "$ sudo apt install firefox-esr" }
            Parrafo { text: "Para mantener el sistema al día:" }
            Orden { texto: "$ sudo apt update && sudo apt full-upgrade" }
            Item { Layout.fillHeight: true }
        }
    }

    Slide {
        anchors.fill: parent
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 40
            anchors.bottomMargin: 44
            spacing: 16
            Titulo { text: "Casi listo" }
            Parrafo { text: "Al terminar, reinicia y retira el medio de instalación cuando el equipo te lo pida." }
            Item { Layout.preferredHeight: 6 }
            GridLayout {
                columns: 2; columnSpacing: 22; rowSpacing: 12
                Layout.fillWidth: true
                Etiqueta { text: "Inicio" }       Dato { text: "Entra con el usuario y la contraseña que acabas de crear" }
                Etiqueta { text: "Tu carpeta" }   Dato { text: "Ya trae toda la configuración del escritorio" }
                Etiqueta { text: "Personaliza" }  Dato { text: "Todo está en ~/.config, en archivos de texto" }
            }
            Item { Layout.fillHeight: true }
        }
    }

    function onActivate() {
        presentacion.currentSlide = 0
    }
    function onLeave() {
    }
}
