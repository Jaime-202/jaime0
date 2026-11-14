import QtQuick
import Quickshell
import Quickshell.Io

// Una peticion al servicio por su socket local: abre, envia una linea JSON, recibe la
// respuesta (otra linea) y cierra. pedir() puede llamarse cuantas veces haga falta.
Socket {
    id: consulta

    property string peticion: ""
    property bool ocupada: false
    signal respuesta(var datos)

    path: (Quickshell.env("XDG_RUNTIME_DIR") || "/tmp") + "/jaime0/control.sock"

    function pedir(objeto) {
        peticion = JSON.stringify(objeto);
        ocupada = true;
        connected = false;
        connected = true;
    }

    parser: SplitParser {
        onRead: linea => {
            let datos = null;
            try { datos = JSON.parse(linea); } catch (e) { datos = null; }
            consulta.ocupada = false;
            consulta.connected = false;
            if (datos) consulta.respuesta(datos);
        }
    }
    onConnectedChanged: {
        if (connected && peticion !== "") {
            write(peticion + "\n");
            flush();
        }
        if (!connected)
            ocupada = false;
    }
}
