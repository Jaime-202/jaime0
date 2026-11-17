import QtQuick

// Grafica tecnica de ZYRON (HEALTH). Dibuja SOLO datos reales:
//   t        lista de tiempos (epoch, s), uno por punto
//   series   [{nombre, color, med:[...], min:[...]?, max:[...]?}]  (null = sin dato)
//   huecos   [[ini, fin], ...]   tramos sin datos: se rayan, nunca se rellenan
//   eventos  [{t, gravedad, texto}]  marcadores en la parte superior
//   umbrales [{valor, color, etiqueta}] lineas de referencia
// Interaccion: al pasar el cursor, cruz con el valor exacto, fecha y hora; arrastrar
// selecciona un tramo y lo amplia; doble clic vuelve a la vista completa.
Item {
    id: grafica

    property var t: []
    property var series: []
    property var huecos: []
    property var eventos: []
    property var umbrales: []
    property string unidad: "%"
    property real minimo: 0
    property real maximo: 100           // si autoescala, se calcula con los datos
    property bool autoescala: false
    property int decimales: 1
    property bool mostrarBanda: true
    // Sin etiquetas de ejes en las graficas pequenas: no caben y se amontonan.
    property bool compacta: height < 110

    // Ventana de tiempo visible (ampliacion). null = todo.
    property var vistaDesde: null
    property var vistaHasta: null
    readonly property bool ampliada: vistaDesde !== null

    readonly property int margenIzq: compacta ? 4 : 42
    readonly property int margenDer: compacta ? 4 : 10
    readonly property int margenSup: compacta ? 4 : 14
    readonly property int margenInf: compacta ? 4 : 20
    readonly property real anchoUtil: Math.max(1, width - margenIzq - margenDer)
    readonly property real altoUtil: Math.max(1, height - margenSup - margenInf)

    readonly property real tIni: vistaDesde !== null ? vistaDesde : (t.length ? t[0] : 0)
    readonly property real tFin: vistaHasta !== null ? vistaHasta : (t.length ? t[t.length - 1] : 1)

    readonly property real escalaMax: {
        if (!autoescala) return maximo;
        let m = minimo + 1;
        for (const s of series)
            for (const v of (s.max || s.med || []))
                if (v !== null && v > m) m = v;
        return Math.ceil(m * 1.1);
    }

    function xDe(tt) {
        const span = Math.max(1, tFin - tIni);
        return margenIzq + (tt - tIni) / span * anchoUtil;
    }
    function yDe(v) {
        const r = Math.max(0.0001, escalaMax - minimo);
        const k = Math.max(0, Math.min(1, (v - minimo) / r));
        return margenSup + altoUtil - k * altoUtil;
    }
    function hora(tt, segundos) {
        const f = new Date(tt * 1000);
        const p = n => String(n).padStart(2, "0");
        return p(f.getHours()) + ":" + p(f.getMinutes()) + (segundos ? ":" + p(f.getSeconds()) : "");
    }
    function fecha(tt) {
        const f = new Date(tt * 1000);
        const p = n => String(n).padStart(2, "0");
        return p(f.getDate()) + "/" + p(f.getMonth() + 1) + " " + hora(tt, true);
    }
    function indiceCercano(tt) {
        if (!t.length) return -1;
        let lo = 0, hi = t.length - 1;
        while (hi - lo > 1) {
            const mid = (lo + hi) >> 1;
            if (t[mid] < tt) lo = mid; else hi = mid;
        }
        return Math.abs(t[lo] - tt) <= Math.abs(t[hi] - tt) ? lo : hi;
    }
    function repintar() { base.requestPaint(); capa.requestPaint(); }

    onTChanged: repintar()
    onSeriesChanged: repintar()
    onHuecosChanged: repintar()
    onEventosChanged: repintar()
    onUmbralesChanged: repintar()
    onWidthChanged: repintar()
    onHeightChanged: repintar()
    onVistaDesdeChanged: repintar()

    // ── Capa base: rejilla, umbrales, huecos, banda, linea y eventos ─────────────
    Canvas {
        id: base
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        onPaint: {
            const c = getContext("2d");
            c.reset();
            const g = grafica;
            const x0 = g.margenIzq, y0 = g.margenSup, w = g.anchoUtil, h = g.altoUtil;

            // Rejilla tecnica: 4 divisiones de valor y marcas de tiempo.
            c.lineWidth = 1;
            c.strokeStyle = Tema.rejilla;
            c.beginPath();
            for (let i = 0; i <= 4; i++) {
                const y = Math.round(y0 + h * i / 4) + 0.5;
                c.moveTo(x0, y); c.lineTo(x0 + w, y);
            }
            const marcas = g.compacta ? 4 : Math.max(2, Math.floor(w / 110));
            for (let i = 0; i <= marcas; i++) {
                const x = Math.round(x0 + w * i / marcas) + 0.5;
                c.moveTo(x, y0); c.lineTo(x, y0 + h);
            }
            c.stroke();

            if (!g.compacta) {
                c.font = "10px '" + Tema.mono + "'";
                c.fillStyle = Tema.apagado;
                c.textAlign = "right";
                for (let i = 0; i <= 4; i++) {
                    const v = g.escalaMax - (g.escalaMax - g.minimo) * i / 4;
                    c.fillText(v.toFixed(0) + (g.unidad === "%" ? "%" : ""), x0 - 6, y0 + h * i / 4 + 3);
                }
                if (g.t.length > 1) {
                    c.textAlign = "center";
                    for (let i = 0; i <= marcas; i++) {
                        const tt = g.tIni + (g.tFin - g.tIni) * i / marcas;
                        c.fillText(g.hora(tt, (g.tFin - g.tIni) < 600), x0 + w * i / marcas, y0 + h + 14);
                    }
                }
            }

            // Umbrales: lineas discontinuas con su etiqueta.
            for (const u of g.umbrales) {
                if (u.valor < g.minimo || u.valor > g.escalaMax) continue;
                const y = Math.round(g.yDe(u.valor)) + 0.5;
                c.strokeStyle = u.color;
                c.globalAlpha = 0.55;
                c.setLineDash([4, 4]);
                c.beginPath(); c.moveTo(x0, y); c.lineTo(x0 + w, y); c.stroke();
                c.setLineDash([]);
                if (!g.compacta && u.etiqueta) {
                    c.globalAlpha = 0.8;
                    c.fillStyle = u.color;
                    c.textAlign = "right";
                    c.fillText(u.etiqueta, x0 + w - 4, y - 4);
                }
                c.globalAlpha = 1;
            }

            // Huecos: tramo rayado, sin datos inventados.
            for (const hu of g.huecos) {
                const a = Math.max(x0, g.xDe(hu[0])), b = Math.min(x0 + w, g.xDe(hu[1]));
                if (b <= a) continue;
                c.save();
                c.beginPath(); c.rect(a, y0, b - a, h); c.clip();
                c.strokeStyle = Tema.borde;
                c.beginPath();
                for (let k = a - h; k < b; k += 6) { c.moveTo(k, y0 + h); c.lineTo(k + h, y0); }
                c.stroke();
                c.restore();
                if (!g.compacta && b - a > 40) {
                    c.fillStyle = Tema.apagado;
                    c.textAlign = "center";
                    c.fillText("SIN DATOS", (a + b) / 2, y0 + 12);
                }
            }

            if (g.t.length < 2)
                return;

            // Recorta al area util (la ampliacion deja puntos fuera).
            c.save();
            c.beginPath(); c.rect(x0, y0 - 2, w, h + 4); c.clip();

            for (const s of g.series) {
                const med = s.med || [];
                // Banda min-max de los agregados (24 h e historico).
                if (g.mostrarBanda && s.min && s.max) {
                    c.fillStyle = s.color;
                    c.globalAlpha = 0.10;
                    let abierto = false, inicio = 0;
                    const cerrar = hasta => {
                        for (let j = hasta; j >= inicio; j--)
                            if (s.min[j] !== null) c.lineTo(g.xDe(g.t[j]), g.yDe(s.min[j]));
                        c.closePath(); c.fill();
                    };
                    for (let i = 0; i < g.t.length; i++) {
                        if (s.max[i] === null || s.min[i] === null) {
                            if (abierto) { cerrar(i - 1); abierto = false; }
                            continue;
                        }
                        if (!abierto) { c.beginPath(); c.moveTo(g.xDe(g.t[i]), g.yDe(s.max[i])); abierto = true; inicio = i; }
                        else c.lineTo(g.xDe(g.t[i]), g.yDe(s.max[i]));
                    }
                    if (abierto) cerrar(g.t.length - 1);
                    c.globalAlpha = 1;
                }
                // Relleno muy tenue bajo la linea principal.
                c.fillStyle = s.color;
                c.globalAlpha = 0.06;
                let tramo = false, primero = 0;
                c.beginPath();
                for (let i = 0; i < g.t.length; i++) {
                    if (med[i] === null) {
                        if (tramo) { c.lineTo(g.xDe(g.t[i - 1]), y0 + h); c.lineTo(g.xDe(g.t[primero]), y0 + h); c.closePath(); tramo = false; }
                        continue;
                    }
                    if (!tramo) { c.moveTo(g.xDe(g.t[i]), g.yDe(med[i])); tramo = true; primero = i; }
                    else c.lineTo(g.xDe(g.t[i]), g.yDe(med[i]));
                }
                if (tramo) { c.lineTo(g.xDe(g.t[g.t.length - 1]), y0 + h); c.lineTo(g.xDe(g.t[primero]), y0 + h); c.closePath(); }
                c.fill();
                c.globalAlpha = 1;

                // Linea: una pasada ancha y tenue (brillo moderado) y otra fina encima.
                for (const pasada of [[4, 0.18], [1.5, 1]]) {
                    c.strokeStyle = s.color;
                    c.lineWidth = pasada[0];
                    c.globalAlpha = pasada[1];
                    c.beginPath();
                    let pluma = false;
                    for (let i = 0; i < g.t.length; i++) {
                        if (med[i] === null) { pluma = false; continue; }
                        const x = g.xDe(g.t[i]), y = g.yDe(med[i]);
                        if (!pluma) { c.moveTo(x, y); pluma = true; } else c.lineTo(x, y);
                    }
                    c.stroke();
                }
                c.globalAlpha = 1;
            }
            c.restore();

            // Eventos: marca en lo alto y una linea vertical muy tenue.
            for (const e of g.eventos) {
                const x = g.xDe(e.t);
                if (x < x0 || x > x0 + w) continue;
                const col = Tema.colorEstado(e.gravedad === "INFO" ? "" : e.gravedad);
                c.strokeStyle = col;
                c.globalAlpha = 0.25;
                c.beginPath(); c.moveTo(Math.round(x) + 0.5, y0); c.lineTo(Math.round(x) + 0.5, y0 + h); c.stroke();
                c.globalAlpha = 1;
                c.fillStyle = col;
                c.beginPath(); c.moveTo(x - 4, y0 - 1); c.lineTo(x + 4, y0 - 1); c.lineTo(x, y0 + 5); c.closePath(); c.fill();
            }
        }
    }

    // ── Capa de interaccion: cruz, lectura y seleccion ───────────────────────────
    property real cursorX: -1
    property real selIni: -1
    property real selFin: -1

    Canvas {
        id: capa
        anchors.fill: parent
        onPaint: {
            const c = getContext("2d");
            c.reset();
            const g = grafica;
            const x0 = g.margenIzq, y0 = g.margenSup, w = g.anchoUtil, h = g.altoUtil;
            if (g.selIni >= 0 && g.selFin >= 0) {
                c.fillStyle = Tema.cian;
                c.globalAlpha = 0.08;
                c.fillRect(Math.min(g.selIni, g.selFin), y0, Math.abs(g.selFin - g.selIni), h);
                c.globalAlpha = 1;
            }
            if (g.cursorX < x0 || g.cursorX > x0 + w || g.t.length < 2)
                return;
            const tt = g.tIni + (g.cursorX - x0) / w * (g.tFin - g.tIni);
            const i = g.indiceCercano(tt);
            if (i < 0) return;
            const x = Math.round(g.xDe(g.t[i])) + 0.5;
            c.strokeStyle = Tema.secundario;
            c.globalAlpha = 0.6;
            c.setLineDash([2, 3]);
            c.beginPath(); c.moveTo(x, y0); c.lineTo(x, y0 + h); c.stroke();
            c.setLineDash([]);
            c.globalAlpha = 1;
            for (const s of g.series) {
                const v = (s.med || [])[i];
                if (v === null || v === undefined) continue;
                c.fillStyle = Tema.fondo;
                c.strokeStyle = s.color;
                c.lineWidth = 1.5;
                c.beginPath(); c.arc(x, g.yDe(v), 3.5, 0, Math.PI * 2); c.fill(); c.stroke();
            }
        }
    }

    // Lectura del punto bajo el cursor.
    Rectangle {
        id: lectura
        readonly property int i: {
            if (grafica.cursorX < 0 || grafica.t.length < 2) return -1;
            const tt = grafica.tIni + (grafica.cursorX - grafica.margenIzq) / grafica.anchoUtil * (grafica.tFin - grafica.tIni);
            return grafica.indiceCercano(tt);
        }
        visible: i >= 0 && grafica.cursorX >= grafica.margenIzq && grafica.cursorX <= grafica.margenIzq + grafica.anchoUtil
        x: Math.min(grafica.width - width - 4, Math.max(4, grafica.cursorX + 12))
        y: grafica.margenSup + 4
        width: textoLectura.implicitWidth + 16
        height: textoLectura.implicitHeight + 10
        color: Tema.fondo
        border.color: Tema.borde
        border.width: 1
        Text {
            id: textoLectura
            anchors.centerIn: parent
            color: Tema.texto
            font.family: Tema.mono
            font.pixelSize: Tema.letraMini
            lineHeight: 1.25
            text: {
                const i = lectura.i;
                if (i < 0) return "";
                const lineas = [grafica.fecha(grafica.t[i])];
                for (const s of grafica.series) {
                    const v = (s.med || [])[i];
                    let txt = s.nombre + "  " + (v === null || v === undefined ? "N/D" : Number(v).toFixed(grafica.decimales) + " " + grafica.unidad);
                    if (s.min && s.max && s.min[i] !== null && s.max[i] !== null)
                        txt += "  [" + Number(s.min[i]).toFixed(grafica.decimales) + "–" + Number(s.max[i]).toFixed(grafica.decimales) + "]";
                    lineas.push(txt);
                }
                // Eventos cercanos (± 2 % del ancho visible).
                const margen = (grafica.tFin - grafica.tIni) * 0.02;
                for (const e of grafica.eventos)
                    if (Math.abs(e.t - grafica.t[i]) <= margen)
                        lineas.push("▼ " + e.texto);
                return lineas.join("\n");
            }
        }
    }

    Text {
        anchors.right: parent.right
        anchors.rightMargin: grafica.margenDer + 4
        y: grafica.margenSup + 2
        visible: grafica.ampliada && !lectura.visible
        text: "AMPLIADA · doble clic: ver todo"
        color: Tema.cian
        font.family: Tema.mono
        font.pixelSize: Tema.letraMini
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        enabled: true
        onPositionChanged: mouse => {
            grafica.cursorX = mouse.x;
            if (pressed) grafica.selFin = mouse.x;
            capa.requestPaint();
        }
        onExited: { grafica.cursorX = -1; capa.requestPaint(); }
        onPressed: mouse => { grafica.selIni = mouse.x; grafica.selFin = mouse.x; }
        onReleased: mouse => {
            const a = Math.min(grafica.selIni, grafica.selFin), b = Math.max(grafica.selIni, grafica.selFin);
            if (b - a > 12) {
                const aT = grafica.tIni + (a - grafica.margenIzq) / grafica.anchoUtil * (grafica.tFin - grafica.tIni);
                const bT = grafica.tIni + (b - grafica.margenIzq) / grafica.anchoUtil * (grafica.tFin - grafica.tIni);
                grafica.vistaHasta = bT;
                grafica.vistaDesde = aT;
            }
            grafica.selIni = -1;
            grafica.selFin = -1;
            capa.requestPaint();
        }
        onDoubleClicked: { grafica.vistaHasta = null; grafica.vistaDesde = null; }
    }

    // Leyenda con el nombre de cada serie: el color solo no basta para distinguirlas.
    Row {
        visible: !grafica.compacta && grafica.series.length > 1
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.rightMargin: grafica.margenDer
        spacing: 10
        Repeater {
            model: grafica.series
            Text {
                required property var modelData
                text: "■ " + modelData.nombre
                color: modelData.color
                font.family: Tema.mono
                font.pixelSize: Tema.letraMini
            }
        }
    }
}
