import QtQuick
import Quickshell.Io

// Ejecuta una orden y avisa cuando ha terminado y se han leido su salida y sus errores.
Process {
    id: orden

    signal terminado(int codigo, string salida, string errores)

    property int fases: 0
    property int codigo: 0

    function lanzar(argumentos) {
        fases = 0;
        codigo = 0;
        command = argumentos;
        running = true;
    }

    function paso() {
        fases += 1;
        if (fases === 3)
            terminado(codigo, salida.text, errores.text);
    }

    stdout: StdioCollector {
        id: salida
        onStreamFinished: orden.paso()
    }
    stderr: StdioCollector {
        id: errores
        onStreamFinished: orden.paso()
    }
    onExited: (codigoSalida, estado) => {
        orden.codigo = codigoSalida;
        orden.paso();
    }
}
