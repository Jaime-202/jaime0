/* Barra lateral del instalador: marca y pasos con su estado.
   Original de este proyecto, sobre la interfaz QML publica del instalador. */
import io.calamares.ui 1.0
import io.calamares.core 1.0

import QtQuick 2.3
import QtQuick.Layouts 1.3

Rectangle {
    id: barra
    color: "#0b0d14"
    anchors.fill: parent

    readonly property string fuente: "JetBrainsMono Nerd Font"

    Rectangle {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 1
        color: "#252939"
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 28
        anchors.bottomMargin: 20
        spacing: 0

        Image {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 72
            Layout.preferredHeight: 72
            source: "file:/" + Branding.imagePath(Branding.ProductLogo)
            sourceSize.width: 144
            sourceSize.height: 144
            fillMode: Image.PreserveAspectFit
            smooth: true
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 12
            Layout.leftMargin: 14
            Layout.rightMargin: 14
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: Branding.string(Branding.ProductName)
            color: "#f2f4fb"
            font.family: barra.fuente
            font.pixelSize: 15
            font.bold: true
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 2
            text: "Instalación"
            color: "#7a819e"
            font.family: barra.fuente
            font.pixelSize: 12
        }

        Item { Layout.preferredHeight: 28 }

        Repeater {
            model: ViewManager

            Item {
                id: paso
                Layout.fillWidth: true
                Layout.preferredHeight: 46

                readonly property bool actual: index === ViewManager.currentStepIndex
                readonly property bool hecho: index < ViewManager.currentStepIndex

                Rectangle {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    anchors.topMargin: 3
                    anchors.bottomMargin: 3
                    radius: 4
                    color: paso.actual ? "#171a26" : "transparent"
                    border.width: paso.actual ? 1 : 0
                    border.color: "#2f3b52"
                }

                // Linea que une cada paso con el siguiente
                Rectangle {
                    visible: index < ViewManager.rowCount() - 1
                    x: 30
                    y: parent.height / 2 + 11
                    width: 2
                    height: parent.height - 22
                    color: paso.hecho ? "#7ab0ff" : "#252939"
                }

                Rectangle {
                    id: marca
                    x: 20
                    anchors.verticalCenter: parent.verticalCenter
                    width: 22
                    height: 22
                    radius: 11
                    color: paso.hecho ? "#7ab0ff" : (paso.actual ? "#252939" : "transparent")
                    border.width: 2
                    border.color: paso.hecho || paso.actual ? "#7ab0ff" : "#2f3b52"

                    Text {
                        anchors.centerIn: parent
                        text: paso.hecho ? "✓" : (index + 1)
                        color: paso.hecho || paso.actual ? "#f2f4fb" : "#565c78"
                        font.family: barra.fuente
                        font.pixelSize: 11
                        font.bold: true
                    }
                }

                Text {
                    anchors.left: marca.right
                    anchors.leftMargin: 12
                    anchors.right: parent.right
                    anchors.rightMargin: 16
                    anchors.verticalCenter: parent.verticalCenter
                    elide: Text.ElideRight
                    text: display
                    color: paso.actual ? "#f2f4fb" : (paso.hecho ? "#b6bcd4" : "#7a819e")
                    font.family: barra.fuente
                    font.pixelSize: 13
                    font.bold: paso.actual
                }
            }
        }

        Item { Layout.fillHeight: true }

        Text {
            Layout.alignment: Qt.AlignHCenter
            text: "Paso " + Math.min(ViewManager.currentStepIndex + 1, ViewManager.rowCount()) + " de " + ViewManager.rowCount()
            color: "#565c78"
            font.family: barra.fuente
            font.pixelSize: 12
        }
    }
}
