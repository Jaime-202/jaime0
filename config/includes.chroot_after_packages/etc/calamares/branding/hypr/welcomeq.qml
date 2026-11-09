/* Pantalla de bienvenida propia: comprobaciones visibles e idioma sin capturar el teclado. */
import io.calamares.core 1.0
import io.calamares.ui 1.0

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: bienvenida
    color: "#12141d"

    readonly property string fuente: "JetBrainsMono Nerd Font"
    readonly property string producto: Branding.string(Branding.ProductName)
    readonly property int total: listado.count

    // El modelo se llena desde otro hilo y la vista puede perderse el aviso.
    Timer {
        interval: 400
        running: true
        repeat: true
        onTriggered: {
            if (config.requirementsModel.rowCount() !== listado.count) {
                listado.model = null
                listado.model = config.requirementsModel
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 44
        anchors.rightMargin: 44
        anchors.topMargin: 30
        anchors.bottomMargin: 18
        spacing: 0

        Text {
            Layout.fillWidth: true
            text: "Te damos la bienvenida a " + bienvenida.producto
            color: "#f2f4fb"
            font.family: bienvenida.fuente
            font.pixelSize: 26
            font.bold: true
            wrapMode: Text.WordWrap
        }

        Text {
            Layout.fillWidth: true
            Layout.topMargin: 10
            text: "Este asistente te guiará para instalar " + bienvenida.producto + " en tu equipo. No se modificará nada hasta que confirmes el último paso."
            color: "#b6bcd4"
            font.family: bienvenida.fuente
            font.pixelSize: 14
            lineHeight: 1.25
            wrapMode: Text.WordWrap
        }

        Text {
            Layout.topMargin: 28
            text: "COMPROBACIÓN DEL EQUIPO"
            color: "#7ab0ff"
            font.family: bienvenida.fuente
            font.pixelSize: 12
            font.bold: true
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.topMargin: 10
            Layout.preferredHeight: Math.max(bienvenida.total, 1) * 38 + 12
            radius: 4
            color: "#171a26"
            border.color: "#252939"

            Text {
                anchors.centerIn: parent
                visible: bienvenida.total === 0
                text: "Comprobando tu equipo…"
                color: "#b6bcd4"
                font.family: bienvenida.fuente
                font.pixelSize: 13
            }

            ListView {
                id: listado
                anchors.fill: parent
                anchors.margins: 6
                interactive: false
                clip: true
                model: config.requirementsModel
                delegate: Item {
                    width: listado.width
                    height: 38

                    readonly property color tono: satisfied ? "#a6cbff" : (mandatory ? "#c96a78" : "#a6cbff")

                    Rectangle {
                        id: indicador
                        x: 10
                        anchors.verticalCenter: parent.verticalCenter
                        width: 22; height: 22; radius: 11
                        color: "transparent"
                        border.width: 2
                        border.color: parent.tono
                        Text {
                            anchors.centerIn: parent
                            text: satisfied ? "✓" : (mandatory ? "✕" : "!")
                            color: parent.parent.tono
                            font.family: bienvenida.fuente
                            font.pixelSize: 12
                            font.bold: true
                        }
                    }
                    Text {
                        anchors.left: indicador.right
                        anchors.leftMargin: 14
                        anchors.right: parent.right
                        anchors.rightMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        text: String(satisfied ? details : negatedText).split("<br")[0].split(String.fromCharCode(10))[0]
                        color: satisfied ? "#e0e4f2" : "#f2f4fb"
                        font.family: bienvenida.fuente
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            Layout.topMargin: 12
            visible: bienvenida.total > 0 && !config.requirementsModel.satisfiedRequirements
            text: config.requirementsModel.satisfiedMandatory
                ? "Puedes continuar: lo marcado con ! es solo una recomendación."
                : "Este equipo no cumple lo mínimo para instalar " + bienvenida.producto + ". Corrige lo marcado con ✕ para poder continuar."
            color: config.requirementsModel.satisfiedMandatory ? "#a6cbff" : "#d99aa3"
            font.family: bienvenida.fuente
            font.pixelSize: 13
            wrapMode: Text.WordWrap
        }

        Item { Layout.fillHeight: true }

        Text {
            text: "IDIOMA DE LA INSTALACIÓN"
            color: "#7ab0ff"
            font.family: bienvenida.fuente
            font.pixelSize: 12
            font.bold: true
        }

        ComboBox {
            id: idiomas
            Layout.fillWidth: true
            Layout.topMargin: 10
            Layout.preferredHeight: 38
            // Sin foco de teclado: una tecla pulsada no cambia el idioma por accidente.
            focusPolicy: Qt.NoFocus
            textRole: "label"
            model: config.languagesModel
            currentIndex: config.localeIndex
            onActivated: function(indice) { config.localeIndex = indice }
            font.family: bienvenida.fuente
            font.pixelSize: 13

            background: Rectangle {
                radius: 4
                color: "#0b0d14"
                border.color: idiomas.hovered ? "#7ab0ff" : "#2f3b52"
            }
            contentItem: Text {
                leftPadding: 12
                rightPadding: 32
                verticalAlignment: Text.AlignVCenter
                text: idiomas.displayText
                color: "#e0e4f2"
                font: idiomas.font
                elide: Text.ElideRight
            }
            indicator: Text {
                x: idiomas.width - width - 12
                anchors.verticalCenter: parent.verticalCenter
                text: "▾"
                color: "#7ab0ff"
                font.pixelSize: 14
            }
            delegate: ItemDelegate {
                width: idiomas.width
                height: 32
                highlighted: idiomas.highlightedIndex === index
                background: Rectangle { color: highlighted ? "#2f3b52" : "#0b0d14" }
                contentItem: Text {
                    verticalAlignment: Text.AlignVCenter
                    text: label
                    color: highlighted ? "#f2f4fb" : "#e0e4f2"
                    font: idiomas.font
                    elide: Text.ElideRight
                }
            }
            popup: Popup {
                y: -implicitHeight - 4
                width: idiomas.width
                implicitHeight: Math.min(contentItem.implicitHeight + 2, 260)
                padding: 1
                contentItem: ListView {
                    clip: true
                    implicitHeight: contentHeight
                    model: idiomas.delegateModel
                    currentIndex: idiomas.highlightedIndex
                    ScrollIndicator.vertical: ScrollIndicator {}
                }
                background: Rectangle {
                    radius: 4
                    color: "#0b0d14"
                    border.color: "#2f3b52"
                }
            }
        }
    }
}
