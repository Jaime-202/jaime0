import QtQuick

// Traza en tiempo real sobre una rejilla tecnica. Solo dibuja muestras reales (las que
// llegan mientras la ventana esta abierta); con menos de dos muestras no hay linea.
// "muestras" es una lista de numeros 0..100; null marca un hueco.
Canvas {
    id: traza

    property var muestras: []
    property color linea: Tema.verde
    property int maximo: 60           // puntos visibles

    onMuestrasChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    onPaint: {
        const c = getContext("2d");
        c.reset();
        const w = width, h = height;
        // Rejilla: 4 lineas horizontales (25 %) y verticales cada 10 muestras.
        c.strokeStyle = Tema.rejilla;
        c.lineWidth = 1;
        c.beginPath();
        for (let i = 1; i < 4; i++) {
            const y = Math.round(h * i / 4) + 0.5;
            c.moveTo(0, y); c.lineTo(w, y);
        }
        for (let i = 1; i < maximo / 10; i++) {
            const x = Math.round(w * i * 10 / maximo) + 0.5;
            c.moveTo(x, 0); c.lineTo(x, h);
        }
        c.stroke();

        const datos = (muestras || []).slice(-maximo);
        if (datos.length < 2)
            return;
        const paso = w / (maximo - 1);
        const x0 = w - (datos.length - 1) * paso;
        const yDe = v => h - Math.max(0, Math.min(100, v)) / 100 * (h - 2) - 1;

        // Relleno muy tenue bajo la curva y la linea encima.
        c.beginPath();
        let abierto = false;
        for (let i = 0; i < datos.length; i++) {
            if (datos[i] === null) { abierto = false; continue; }
            const x = x0 + i * paso, y = yDe(datos[i]);
            if (!abierto) { c.moveTo(x, y); abierto = true; } else c.lineTo(x, y);
        }
        c.strokeStyle = linea;
        c.lineWidth = 1.5;
        c.stroke();

        // Punto de la ultima muestra.
        const ultimo = datos[datos.length - 1];
        if (ultimo !== null) {
            c.fillStyle = linea;
            c.beginPath();
            c.arc(w - 1.5, yDe(ultimo), 2.5, 0, Math.PI * 2);
            c.fill();
        }
    }
}
