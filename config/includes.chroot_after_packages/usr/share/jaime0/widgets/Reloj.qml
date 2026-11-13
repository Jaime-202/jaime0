import QtQuick

// Hora grande y fecha. Se redibuja una vez por minuto, alineado al cambio de minuto.
Tarjeta {
    id: reloj

    property date ahora: new Date()

    Timer {
        id: minuto
        repeat: false
        running: true
        onTriggered: {
            reloj.ahora = new Date();
            interval = 60000 - (reloj.ahora.getSeconds() * 1000 + reloj.ahora.getMilliseconds()) + 50;
            start();
        }
        Component.onCompleted: {
            interval = 60000 - (reloj.ahora.getSeconds() * 1000 + reloj.ahora.getMilliseconds()) + 50;
        }
    }

    Texto {
        text: Qt.formatTime(reloj.ahora, Estado.doceHoras ? "h:mm AP" : "HH:mm")
        font.pixelSize: 56
        font.weight: Font.Light
    }

    Texto {
        tenue: true
        text: Qt.locale("es_ES").toString(reloj.ahora, "dddd, d 'de' MMMM")
        font.pixelSize: 13
    }
}
