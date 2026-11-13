import QtQuick

// Contenedor de cada widget: tarjeta (#101519 al 92 %, borde 1 px, esquinas 8) o, con
// "tarjetas": false, sin fondo.
Item {
    id: tarjeta

    default property alias contenido: caja.data
    property int relleno: 14
    property int alineacion: Qt.AlignLeft     // la pone Panel.qml segun la posicion
    property int ancho: 0                      // 0 = el del contenido
    property bool mostrar: true                // false: el widget no ocupa sitio (Panel.qml)

    implicitWidth: (ancho > 0 ? ancho : caja.implicitWidth) + 2 * relleno
    implicitHeight: caja.implicitHeight + 2 * relleno

    Rectangle {
        anchors.fill: parent
        visible: Estado.tarjetas
        color: Estado.tarjeta
        radius: 8
        border.width: 1
        border.color: Estado.borde
    }

    Column {
        id: caja
        x: tarjeta.relleno
        y: tarjeta.relleno
        width: tarjeta.width - 2 * tarjeta.relleno
        spacing: 8
    }
}
