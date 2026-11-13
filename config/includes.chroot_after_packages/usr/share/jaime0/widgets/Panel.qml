import QtQuick
import Quickshell
import Quickshell.Wayland

// Un panel por posicion: apila, en orden, los widgets que el usuario ha puesto ahi.
// Capa Bottom: encima del fondo y debajo de las ventanas. Respeta la zona de la barra.
PanelWindow {
    id: panel

    property string posicion: "centro"
    readonly property bool arriba: posicion.startsWith("arriba")
    readonly property bool abajo: posicion.startsWith("abajo")
    readonly property bool izquierda: posicion.endsWith("izquierda")
    readonly property bool derecha: posicion.endsWith("derecha")

    readonly property var componentes: ({
        reloj: "Reloj.qml", musica: "Musica.qml", tiempo: "Tiempo.qml",
        sonido: "Sonido.qml", sistema: "Sistema.qml", calendario: "Calendario.qml"
    })

    anchors.top: arriba
    anchors.bottom: abajo
    anchors.left: izquierda
    anchors.right: derecha
    margins.top: 16
    margins.bottom: 16
    margins.left: 16
    margins.right: 16

    WlrLayershell.layer: WlrLayer.Bottom
    WlrLayershell.namespace: "jaime0-widgets"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    exclusionMode: ExclusionMode.Normal
    exclusiveZone: 0
    color: "transparent"

    // Un widget oculto (musica sin reproductor) no ocupa sitio. El panel no se oculta aunque
    // se quede vacio: con la ventana oculta Qt no recalcula el contenido y nunca volveria a
    // aparecer. Vacio mide 1x1 px y es transparente.
    implicitWidth: Math.max(1, columna.implicitWidth)
    implicitHeight: Math.max(1, columna.implicitHeight)

    Column {
        id: columna
        width: implicitWidth
        spacing: 12

        Repeater {
            model: Estado.claves.filter(c => Estado.widgets[c] === panel.posicion)

            Loader {
                required property string modelData
                source: panel.componentes[modelData]
                // "mostrar" y no "visible": item.visible incluye la del propio Loader y la
                // dependencia circular lo dejaria oculto para siempre.
                visible: item !== null && item.mostrar
                x: panel.derecha ? columna.width - width
                   : (panel.izquierda ? 0 : Math.round((columna.width - width) / 2))
            }
        }
    }
}
