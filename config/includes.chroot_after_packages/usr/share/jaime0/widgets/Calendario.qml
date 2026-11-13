import QtQuick

// Calendario del mes actual, lunes primero, con hoy marcado en el color de acento.
Tarjeta {
    id: calendario

    property date hoy: new Date()
    readonly property int anio: hoy.getFullYear()
    readonly property int mes: hoy.getMonth()
    readonly property int diasMes: new Date(anio, mes + 1, 0).getDate()
    // Huecos antes del dia 1 con la semana empezando en lunes.
    readonly property int hueco: (new Date(anio, mes, 1).getDay() + 6) % 7
    readonly property int celda: 30

    // Comprueba cada 10 minutos si ha cambiado el dia.
    Timer {
        interval: 600000
        repeat: true
        running: true
        onTriggered: {
            const ahora = new Date();
            if (ahora.getDate() !== calendario.hoy.getDate() || ahora.getMonth() !== calendario.mes)
                calendario.hoy = ahora;
        }
    }

    Texto {
        text: {
            const nombre = Qt.locale("es_ES").standaloneMonthName(calendario.mes, Locale.LongFormat);
            return nombre.charAt(0).toUpperCase() + nombre.slice(1) + " " + calendario.anio;
        }
        font.pixelSize: 13
        font.weight: Font.DemiBold
    }

    Grid {
        columns: 7
        spacing: 0

        Repeater {
            model: ["lu", "ma", "mi", "ju", "vi", "sá", "do"]
            Texto {
                required property string modelData
                width: calendario.celda
                height: 20
                horizontalAlignment: Text.AlignHCenter
                tenue: true
                text: modelData
                font.pixelSize: 11
            }
        }

        Repeater {
            model: calendario.hueco + calendario.diasMes
            Item {
                required property int index
                readonly property int dia: index - calendario.hueco + 1
                readonly property bool esHoy: dia === calendario.hoy.getDate()
                width: calendario.celda
                height: 24

                Rectangle {
                    anchors.centerIn: parent
                    width: 24
                    height: 22
                    radius: 5
                    visible: parent.esHoy
                    color: Estado.acento
                }
                Texto {
                    anchors.centerIn: parent
                    visible: parent.dia > 0
                    text: parent.dia
                    font.pixelSize: 12
                    font.weight: parent.esHoy ? Font.Bold : Font.Normal
                    color: parent.esHoy ? Estado.fondo : Estado.texto
                    style: Text.Normal
                }
            }
        }
    }
}
