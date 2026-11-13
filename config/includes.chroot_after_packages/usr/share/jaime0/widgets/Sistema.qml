import QtQuick
import Quickshell.Io

// CPU, RAM, disco, temperatura y bateria. CPU y RAM cada 5 s; temperatura cada 10 s;
// disco y bateria cada minuto. Lo que el equipo no tiene (sensores, bateria) no se muestra.
Tarjeta {
    id: sistema

    property real cpu: 0
    property var cpuAnterior: null
    property real ram: 0
    property string ramTexto: ""
    property real disco: 0
    property string discoTexto: ""
    property real temperatura: -1
    property int bateria: -1
    property string bateriaEstado: ""

    ancho: 240

    FileView {
        id: stat
        path: "/proc/stat"
        blockLoading: true
        printErrors: false
    }
    FileView {
        id: meminfo
        path: "/proc/meminfo"
        blockLoading: true
        printErrors: false
    }

    function leerCpuRam() {
        stat.reload();
        const campos = stat.text().split("\n")[0].trim().split(/\s+/).slice(1).map(Number);
        const inactivo = campos[3] + (campos[4] || 0);
        const total = campos.reduce((a, b) => a + b, 0);
        if (cpuAnterior) {
            const dt = total - cpuAnterior.total;
            cpu = dt > 0 ? 1 - (inactivo - cpuAnterior.inactivo) / dt : 0;
        }
        cpuAnterior = { total: total, inactivo: inactivo };

        meminfo.reload();
        const m = {};
        for (const linea of meminfo.text().split("\n")) {
            const p = linea.split(/:\s+/);
            if (p.length === 2)
                m[p[0]] = parseInt(p[1]);
        }
        if (m.MemTotal > 0) {
            const usada = m.MemTotal - (m.MemAvailable || 0);
            ram = usada / m.MemTotal;
            ramTexto = (usada / 1048576).toFixed(1) + " / " + (m.MemTotal / 1048576).toFixed(1) + " GB";
        }
    }

    Timer {
        interval: 5000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: sistema.leerCpuRam()
    }

    Process {
        id: df
        command: ["df", "-P", "-B1", "/"]
        stdout: StdioCollector {
            onStreamFinished: {
                const p = text.trim().split("\n").pop().split(/\s+/);
                if (p.length >= 4 && Number(p[1]) > 0) {
                    sistema.disco = Number(p[2]) / Number(p[1]);
                    sistema.discoTexto = (Number(p[3]) / 1e9).toFixed(0) + " GB libres";
                }
            }
        }
    }
    Process {
        id: bat
        command: ["sh", "-c", "for b in /sys/class/power_supply/BAT*; do [ -r \"$b/capacity\" ] && echo $(cat $b/capacity) $(cat $b/status) && break; done"]
        stdout: StdioCollector {
            onStreamFinished: {
                const p = text.trim().split(" ");
                sistema.bateria = p[0] !== "" && !isNaN(Number(p[0])) ? Number(p[0]) : -1;
                sistema.bateriaEstado = p[1] || "";
            }
        }
    }
    Timer {
        interval: 60000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: { df.running = true; bat.running = true; }
    }

    Process {
        id: temp
        command: ["sh", "-c", "cat /sys/class/thermal/thermal_zone*/temp /sys/class/hwmon/hwmon*/temp*_input 2>/dev/null | sort -n | tail -n 1"]
        stdout: StdioCollector {
            onStreamFinished: {
                const v = Number(text.trim());
                sistema.temperatura = text.trim() !== "" && v > 0 ? v / 1000 : -1;
            }
        }
    }
    Timer {
        interval: 10000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: temp.running = true
    }

    component Fila: Column {
        property string glifo
        property string nombre
        property string valor
        property real fraccion: 0
        property bool aviso: false
        width: parent.width
        spacing: 4
        Item {
            width: parent.width
            height: etiqueta.implicitHeight
            Texto { id: etiqueta; text: glifo + "  " + nombre }
            Texto { anchors.right: parent.right; tenue: true; text: valor }
        }
        Barra {
            width: parent.width
            valor: fraccion
            color: aviso ? Estado.rojo : Estado.acento
        }
    }

    Fila { glifo: "\u{f0ee0}"; nombre: "CPU"; valor: Math.round(sistema.cpu * 100) + "%"; fraccion: sistema.cpu; aviso: sistema.cpu > 0.9 }
    Fila { glifo: "\u{f035b}"; nombre: "RAM"; valor: sistema.ramTexto; fraccion: sistema.ram; aviso: sistema.ram > 0.9 }
    Fila { glifo: "\u{f02ca}"; nombre: "Disco"; valor: sistema.discoTexto; fraccion: sistema.disco; aviso: sistema.disco > 0.9; visible: sistema.discoTexto !== "" }
    Fila {
        visible: sistema.temperatura > 0
        glifo: "\u{f050f}"; nombre: "Temperatura"; valor: Math.round(sistema.temperatura) + " °C"
        fraccion: Math.min(1, sistema.temperatura / 100); aviso: sistema.temperatura >= 85
    }
    Fila {
        visible: sistema.bateria >= 0
        glifo: sistema.bateriaEstado === "Charging" ? "\u{f0084}" : "\u{f0079}"
        nombre: "Batería"; valor: sistema.bateria + "%"
        fraccion: sistema.bateria / 100; aviso: sistema.bateria <= 15 && sistema.bateriaEstado !== "Charging"
    }
}
