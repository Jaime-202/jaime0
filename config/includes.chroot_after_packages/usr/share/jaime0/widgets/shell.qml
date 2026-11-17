//@ pragma Env QT_QUICK_BACKEND=software
// Widgets de escritorio de ZYRON. Los arranca y para "jaime0-widgets" segun los ajustes:
//   quickshell -p /usr/share/jaime0/widgets/shell.qml
// Lee ~/.config/jaime0/generado/widgets.json (lo escribe jaime0-ajustes) y se reconfigura
// en caliente cuando cambia. Un panel por cada posicion usada, en la capa de debajo de las
// ventanas. Se dibuja por software: son pocos elementos y casi siempre quietos.

import QtQuick
import QtQml
import Quickshell
import Quickshell.Io

ShellRoot {
    settings.watchFiles: false

    FileView {
        path: (Quickshell.env("XDG_CONFIG_HOME") || (Quickshell.env("HOME") + "/.config"))
              + "/jaime0/generado/widgets.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: Estado.cargar(text())
        onLoadFailed: Estado.cargar("")
    }

    Instantiator {
        model: Estado.posiciones.filter(p => Object.values(Estado.widgets).indexOf(p) >= 0)
        delegate: Panel {
            required property string modelData
            posicion: modelData
        }
    }
}
