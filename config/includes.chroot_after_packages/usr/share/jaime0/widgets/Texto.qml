import QtQuick

// Texto de los widgets. Sin tarjeta lleva una sombra muy suave para leerse sobre el fondo.
Text {
    property bool tenue: false

    // Sin tarjeta, el gris secundario se pierde sobre zonas claras del fondo: gris medio.
    color: tenue ? (Estado.tarjetas ? Estado.secundario : "#a7b4bc") : Estado.texto
    font.family: Estado.fuente
    font.pixelSize: 12
    style: Estado.tarjetas ? Text.Normal : Text.Raised
    styleColor: "#a0000000"
}
