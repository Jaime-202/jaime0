import QtQuick
import QtQuick.Layouts

// AUTOMATION: reglas CUANDO → SI → HACER del servicio (ordenes "reglas", "regla_guardar",
// "regla_activar", "regla_borrar", "regla_probar", "reglas_historial"). El editor se arma
// con el catalogo que envia el servicio: solo ofrece eventos, condiciones y acciones que
// existen y estan disponibles en este equipo.
Item {
    id: vista

    property var datos: null
    property var historial: []
    property string mensaje: ""
    property bool mensajeError: false
    property var borrador: null           // regla en edicion (null = editor cerrado)
    property string porBorrar: ""          // id pendiente de confirmar

    readonly property var reglas: datos ? datos.reglas : []
    readonly property var catalogo: datos ? datos.catalogo : null
    readonly property var aplicaciones: datos && datos.aplicaciones ? datos.aplicaciones : []
    readonly property var dias: ["L", "M", "X", "J", "V", "S", "D"]

    function buscar(lista, id) { return (lista || []).find(x => x.id === id) || null; }
    function nombreDe(lista, id) { const d = buscar(lista, id); return d ? d.nombre : id; }
    function clonar(o) { return JSON.parse(JSON.stringify(o)); }
    function hora(t) {
        const f = new Date(t * 1000);
        const p = n => String(n).padStart(2, "0");
        return p(f.getDate()) + "/" + p(f.getMonth() + 1) + " " + p(f.getHours()) + ":" + p(f.getMinutes());
    }
    function resumen(r) {
        const c = vista.catalogo;
        if (!c) return "";
        const ev = "CUANDO " + nombreDe(c.eventos, r.cuando.evento);
        const si = r.si && r.si.length ? "  →  SI " + r.si.map(x => nombreDe(c.condiciones, x.condicion)).join(" y ") : "";
        const hacer = "  →  HACER " + (r.hacer || []).map(x => nombreDe(c.acciones, x.accion)).join(", ");
        return ev + si + hacer;
    }
    function colorResultado(res) { return res === "ok" ? Tema.verde : res === "fallo" ? Tema.rojo : Tema.ambar; }

    // Valores por defecto de un elemento del catalogo.
    function nuevoElemento(tipoClave, definicion) {
        const o = {};
        o[tipoClave] = definicion.id;
        for (const p of definicion.parametros || [])
            if (p.defecto !== undefined && p.defecto !== null) o[p.clave] = p.defecto;
        return o;
    }
    function nuevaRegla() {
        const ev = (vista.catalogo.eventos || []).find(e => e.disponible) || vista.catalogo.eventos[0];
        const ac = (vista.catalogo.acciones || []).find(a => a.disponible) || vista.catalogo.acciones[0];
        const cuando = nuevoElemento("evento", ev);
        return { nombre: "Nueva regla", activa: true, prioridad: "normal", cuando: cuando, si: [], hacer: [nuevoElemento("accion", ac)] };
    }
    // Cambia un valor dentro del borrador y lo reasigna para que la vista se actualice.
    function poner(seccion, indice, clave, valor) {
        const b = clonar(vista.borrador);
        if (seccion === "cuando") b.cuando[clave] = valor;
        else if (seccion === "regla") b[clave] = valor;
        else b[seccion][indice][clave] = valor;
        vista.borrador = b;
    }
    // Para lo que se escribe tecla a tecla: cambia el valor sin reasignar el borrador. Si se
    // reasignara, el editor se reconstruiria y el campo perderia el foco tras cada letra.
    function ponerTexto(seccion, indice, clave, valor) {
        if (seccion === "cuando") vista.borrador.cuando[clave] = valor;
        else if (seccion === "regla") vista.borrador[clave] = valor;
        else vista.borrador[seccion][indice][clave] = valor;
    }
    function cambiarTipo(seccion, indice, tipoClave, definicion) {
        const b = clonar(vista.borrador);
        const nuevo = nuevoElemento(tipoClave, definicion);
        if (seccion === "cuando") b.cuando = nuevo; else b[seccion][indice] = nuevo;
        vista.borrador = b;
    }

    function leer() {
        consulta.pedir({ orden: "reglas" });
        consultaHistorial.pedir({ orden: "reglas_historial", limite: 40 });
    }
    function avisar(texto, error) { vista.mensaje = texto; vista.mensajeError = !!error; }

    Consulta {
        id: consulta
        onRespuesta: d => { if (d.ok !== false) vista.datos = d; else vista.avisar(d.error || "sin respuesta", true); }
    }
    Consulta {
        id: consultaHistorial
        onRespuesta: d => { if (d.ok !== false) vista.historial = d.ejecuciones || d.historial || []; }
    }
    Consulta {
        id: orden
        onRespuesta: d => {
            if (d.ok === false) vista.avisar(d.error || "no se pudo hacer", true);
            else if (d.resultado) vista.avisar("Prueba: " + d.resultado + (d.detalle ? " · " + d.detalle : ""), d.resultado !== "ok");
            else vista.avisar("Hecho", false);
            if (d.ok !== false && vista.borrador && d.regla) vista.borrador = null;
            vista.leer();
        }
    }
    Component.onCompleted: leer()
    Timer { interval: 15000; running: true; repeat: true; onTriggered: vista.leer() }

    // ── Editor de parametros de un elemento (evento, condicion o accion) ────────
    component Parametros: Column {
        id: params
        width: editor.width
        property var definicion: null
        property var objeto: ({})
        property string seccion: ""
        property int indice: -1
        spacing: 4
        Repeater {
            model: params.definicion ? params.definicion.parametros || [] : []
            Row {
                id: filaParam
                required property var modelData
                spacing: 8
                Text {
                    width: 110
                    anchors.verticalCenter: parent.verticalCenter
                    text: (filaParam.modelData.texto || filaParam.modelData.clave).toUpperCase()
                    color: Tema.apagado
                    font.family: Tema.mono
                    font.pixelSize: Tema.letraMini
                    elide: Text.ElideRight
                }
                Loader {
                    readonly property var p: filaParam.modelData
                    readonly property var valor: params.objeto[p.clave]
                    sourceComponent: p.opciones ? editorOpciones
                                   : /dias/.test(p.tipo) ? editorDias
                                   : /aplic/.test(p.tipo) ? editorAplicacion
                                   : /bool|sino/.test(p.tipo) ? editorBooleano
                                   : editorTexto
                    Component {
                        id: editorOpciones
                        Opciones {
                            ancho: params.width - 120
                            opciones: parent.p.opciones.map(o => typeof o === "object" ? { valor: String(o.valor), texto: String(o.texto || o.valor).toUpperCase() } : { valor: String(o), texto: String(o).toUpperCase() })
                            valor: String(parent.valor)
                            onElegido: v => vista.poner(params.seccion, params.indice, parent.p.clave, v)
                        }
                    }
                    Component {
                        id: editorBooleano
                        Opciones {
                            ancho: params.width - 120
                            opciones: [{ valor: "true", texto: "SÍ" }, { valor: "false", texto: "NO" }]
                            valor: String(parent.valor)
                            onElegido: v => vista.poner(params.seccion, params.indice, parent.p.clave, v === "true")
                        }
                    }
                    Component {
                        id: editorDias
                        Row {
                            spacing: 3
                            Repeater {
                                model: 7
                                Rectangle {
                                    required property int index
                                    readonly property var sel: parent.parent.valor || []
                                    readonly property bool activo: sel.indexOf(index) >= 0
                                    width: 20; height: 20
                                    color: activo ? Tema.cian : "transparent"
                                    border.color: activo ? Tema.cian : Tema.borde
                                    Text { anchors.centerIn: parent; text: vista.dias[index]; color: parent.activo ? Tema.fondo : Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                                    Pulsar {
                                        onPulsado: {
                                            const s = (parent.sel || []).slice();
                                            const i = s.indexOf(parent.index);
                                            if (i >= 0) s.splice(i, 1); else s.push(parent.index);
                                            s.sort();
                                            vista.poner(params.seccion, params.indice, parent.parent.parent.p.clave, s);
                                        }
                                    }
                                }
                            }
                        }
                    }
                    Component {
                        id: editorAplicacion
                        Flow {
                            width: 300
                            spacing: 3
                            Repeater {
                                model: vista.aplicaciones.slice(0, 24)
                                Rectangle {
                                    required property var modelData
                                    readonly property bool activo: parent.parent.valor === modelData.id
                                    width: t.implicitWidth + 10; height: 18
                                    color: activo ? Tema.cian : "transparent"
                                    border.color: activo ? Tema.cian : Tema.borde
                                    Text { id: t; anchors.centerIn: parent; text: modelData.nombre; color: parent.activo ? Tema.fondo : Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                                    Pulsar { onPulsado: vista.poner(params.seccion, params.indice, parent.parent.parent.p.clave, parent.modelData.id) }
                                }
                            }
                        }
                    }
                    Component {
                        id: editorTexto
                        Entrada {
                            width: 180
                            readonly property bool numero: /entero|numero|int/.test(parent.p.tipo)
                            texto: parent.valor === undefined || parent.valor === null ? "" : String(parent.valor)
                            pista: parent.p.min !== undefined ? parent.p.min + "–" + parent.p.max : parent.p.tipo === "hora" ? "HH:MM" : ""
                            validar: t => !numero ? true : /^-?\d+$/.test(t) && (parent.p.min === undefined || (Number(t) >= parent.p.min && Number(t) <= parent.p.max))
                            onEditado: t => vista.ponerTexto(params.seccion, params.indice, parent.p.clave, numero && /^-?\d+$/.test(t) ? Number(t) : t)
                        }
                    }
                }
            }
        }
    }

    // ── Distribucion ─────────────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10

            // Lista de reglas
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 3
                ident: "A1"
                readonly property var res: vista.datos && vista.datos.resumen ? vista.datos.resumen : null
                etiqueta: Tema.producto + " RULES · " + (res ? res.activas + " ACTIVAS · " + res.desactivadas + " DESACTIVADAS"
                                                     + (res.por_revisar ? " · " + res.por_revisar + " POR REVISAR" : "")
                                                     + (res.con_fallo ? " · " + res.con_fallo + " CON FALLO" : "")
                                                     + (res.conflictos ? " · " + res.conflictos + " CONFLICTOS" : "")
                                               : vista.reglas.length + " REGLAS")
                acento: Tema.verde

                Row {
                    id: barraReglas
                    spacing: 10
                    Rectangle {
                        width: tNueva.implicitWidth + 16; height: 22
                        color: "transparent"; border.color: Tema.verde; border.width: 1
                        Text { id: tNueva; anchors.centerIn: parent; text: "+ NUEVA REGLA"; color: Tema.verde; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1 }
                        Pulsar { enabled: vista.catalogo !== null; onPulsado: vista.borrador = vista.nuevaRegla() }
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: vista.mensaje !== ""
                        text: (vista.mensajeError ? "△ " : "✓ ") + vista.mensaje
                        color: vista.mensajeError ? Tema.ambar : Tema.verde
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                    }
                }
                Flickable {
                    anchors.top: barraReglas.bottom
                    anchors.topMargin: 10
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    contentHeight: listaReglas.implicitHeight
                    clip: true
                    Column {
                        id: listaReglas
                        width: parent.width
                        spacing: 6
                        Text {
                            visible: vista.reglas.length === 0
                            width: parent.width
                            text: "Sin reglas todavía. Ejemplo: CUANDO la batería baje del 20 % → HACER perfil POWER SAVER."
                            color: Tema.apagado
                            font.family: Tema.mono
                            font.pixelSize: Tema.letraMini
                            wrapMode: Text.WordWrap
                        }
                        Repeater {
                            model: vista.datos && vista.datos.errores ? vista.datos.errores : []
                            Text {
                                required property var modelData
                                width: listaReglas.width
                                text: "✕ Regla no cargada (" + (modelData.id || modelData.indice) + "): " + modelData.error
                                color: Tema.rojo
                                font.family: Tema.mono
                                font.pixelSize: Tema.letraMini
                                wrapMode: Text.WordWrap
                            }
                        }
                        Repeater {
                            model: vista.reglas
                            Rectangle {
                                id: fila
                                required property var modelData
                                width: listaReglas.width
                                height: Math.max(58, datosFila.implicitHeight + 16)
                                color: vista.borrador && vista.borrador.id === modelData.id ? "#0f171b" : Tema.panel2
                                border.color: modelData.activa ? Tema.borde : Tema.rejilla
                                border.width: 1
                                // Interruptor
                                Rectangle {
                                    x: 10; y: 10
                                    width: 34; height: 16
                                    color: fila.modelData.activa ? Tema.verde : "transparent"
                                    border.color: fila.modelData.activa ? Tema.verde : Tema.borde
                                    Text { anchors.centerIn: parent; text: fila.modelData.activa ? "ON" : "OFF"; color: fila.modelData.activa ? Tema.fondo : Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                                    Pulsar { onPulsado: orden.pedir({ orden: "regla_activar", id: fila.modelData.id, activa: !fila.modelData.activa }) }
                                }
                                Column {
                                    id: datosFila
                                    x: 56; y: 8
                                    width: fila.width - 56 - acciones.width - 16
                                    spacing: 3
                                    Row {
                                        spacing: 8
                                        Text { text: fila.modelData.nombre; color: fila.modelData.activa ? Tema.texto : Tema.apagado; font.family: Tema.mono; font.pixelSize: 13 }
                                        Text { visible: !!fila.modelData.revisar; text: "REVISAR"; color: Tema.ambar; font.family: Tema.mono; font.pixelSize: Tema.letraMini; anchors.verticalCenter: parent.verticalCenter }
                                        Text {
                                            visible: (fila.modelData.prioridad || "normal") !== "normal"
                                            text: "PRIORIDAD " + String(fila.modelData.prioridad || "").toUpperCase()
                                            color: fila.modelData.prioridad === "alta" ? Tema.cian : Tema.secundario
                                            font.family: Tema.mono; font.pixelSize: Tema.letraMini; anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                    Text {
                                        width: parent.width
                                        text: vista.resumen(fila.modelData)
                                        color: Tema.secundario
                                        font.family: Tema.mono
                                        font.pixelSize: Tema.letraMini
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        width: parent.width
                                        readonly property var u: fila.modelData.ultima
                                        text: u ? "ÚLTIMA  " + vista.hora(u.t) + "  " + u.resultado.toUpperCase() + (u.detalle ? " · " + u.detalle : "") : "SIN EJECUCIONES"
                                        color: u ? vista.colorResultado(u.resultado) : Tema.apagado
                                        font.family: Tema.mono
                                        font.pixelSize: Tema.letraMini
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        visible: !!fila.modelData.proxima
                                        text: "PRÓXIMA  " + (fila.modelData.proxima ? vista.hora(fila.modelData.proxima) : "")
                                        color: Tema.cian
                                        font.family: Tema.mono
                                        font.pixelSize: Tema.letraMini
                                    }
                                    Repeater {
                                        model: fila.modelData.choca_con || []
                                        Text {
                                            required property var modelData
                                            width: datosFila.width
                                            text: "△ PUEDE CHOCAR CON «" + modelData.nombre + "» (" + modelData.recurso + ") si se disparan a la vez"
                                            color: Tema.ambar
                                            font.family: Tema.mono
                                            font.pixelSize: Tema.letraMini
                                            elide: Text.ElideRight
                                        }
                                    }
                                }
                                Row {
                                    id: acciones
                                    anchors.right: parent.right
                                    anchors.rightMargin: 10
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 6
                                    Repeater {
                                        model: [
                                            { t: "PROBAR", c: Tema.cian, f: () => orden.pedir({ orden: "regla_probar", id: fila.modelData.id }) },
                                            { t: "EDITAR", c: Tema.cian, f: () => vista.borrador = vista.clonar(fila.modelData) },
                                            { t: vista.porBorrar === fila.modelData.id ? "¿BORRAR?" : "BORRAR", c: Tema.rojo,
                                              f: () => {
                                                  if (vista.porBorrar === fila.modelData.id) { vista.porBorrar = ""; orden.pedir({ orden: "regla_borrar", id: fila.modelData.id }); }
                                                  else vista.porBorrar = fila.modelData.id;
                                              } }
                                        ]
                                        Rectangle {
                                            required property var modelData
                                            width: tb.implicitWidth + 12; height: 20
                                            color: "transparent"; border.color: modelData.c; border.width: 1
                                            Text { id: tb; anchors.centerIn: parent; text: modelData.t; color: modelData.c; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                                            Pulsar { onPulsado: parent.modelData.f() }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Editor
            Marco {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 2
                visible: vista.borrador !== null
                ident: "A2"
                etiqueta: vista.borrador && vista.borrador.id ? "EDITAR REGLA" : "NUEVA REGLA"
                acento: Tema.cian

                Flickable {
                    anchors.fill: parent
                    anchors.bottomMargin: 30
                    contentHeight: editor.implicitHeight
                    clip: true
                    Column {
                        id: editor
                        width: parent.width
                        spacing: 8
                        visible: vista.borrador !== null && vista.catalogo !== null

                        Row {
                            spacing: 8
                            Text { width: 70; anchors.verticalCenter: parent.verticalCenter; text: "NOMBRE"; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                            Entrada {
                                width: editor.width - 80
                                maximo: 60
                                texto: vista.borrador ? vista.borrador.nombre : ""
                                onEditado: t => vista.ponerTexto("regla", -1, "nombre", t)
                            }
                        }

                        Row {
                            spacing: 8
                            Text { width: 70; anchors.verticalCenter: parent.verticalCenter; text: "PRIORIDAD"; color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                            Opciones {
                                opciones: [{ valor: "alta", texto: "ALTA" }, { valor: "normal", texto: "NORMAL" }, { valor: "baja", texto: "BAJA" }]
                                valor: vista.borrador ? (vista.borrador.prioridad || "normal") : "normal"
                                onElegido: v => vista.poner("regla", -1, "prioridad", v)
                            }
                        }
                        Text {
                            width: editor.width
                            text: "Si otra regla se dispara a la vez y pide otro valor para lo mismo (perfil, volumen, no molestar…), gana la de prioridad más alta; a igualdad, la que va antes en la lista."
                            color: Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini; wrapMode: Text.WordWrap
                        }

                        // CUANDO
                        Text { text: "CUANDO"; color: Tema.verde; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 2 }
                        Flow {
                            width: editor.width
                            spacing: 3
                            Repeater {
                                model: vista.catalogo ? vista.catalogo.eventos : []
                                Rectangle {
                                    required property var modelData
                                    readonly property bool activo: vista.borrador && vista.borrador.cuando.evento === modelData.id
                                    width: te.implicitWidth + 10; height: 18
                                    color: activo ? Tema.verde : "transparent"
                                    border.color: activo ? Tema.verde : modelData.disponible ? Tema.borde : Tema.rejilla
                                    Text { id: te; anchors.centerIn: parent; text: modelData.nombre; color: parent.activo ? Tema.fondo : modelData.disponible ? Tema.secundario : Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                                    Pulsar { enabled: parent.modelData.disponible; onPulsado: vista.cambiarTipo("cuando", -1, "evento", parent.modelData) }
                                }
                            }
                        }
                        Parametros {
                            definicion: vista.borrador ? vista.buscar(vista.catalogo.eventos, vista.borrador.cuando.evento) : null
                            objeto: vista.borrador ? vista.borrador.cuando : ({})
                            seccion: "cuando"
                        }

                        // SI
                        Row {
                            spacing: 10
                            Text { text: "SI (opcional)"; color: Tema.cian; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 2 }
                            Text {
                                text: "+ AÑADIR"
                                color: Tema.cian
                                font.family: Tema.mono
                                font.pixelSize: Tema.letraMini
                                Pulsar {
                                    onPulsado: {
                                        const b = vista.clonar(vista.borrador);
                                        b.si = (b.si || []).concat([vista.nuevoElemento("condicion", vista.catalogo.condiciones[0])]);
                                        vista.borrador = b;
                                    }
                                }
                            }
                        }
                        Repeater {
                            model: vista.borrador ? vista.borrador.si || [] : []
                            Column {
                                id: cond
                                required property var modelData
                                required property int index
                                width: editor.width
                                spacing: 4
                                Flow {
                                    width: parent.width
                                    spacing: 3
                                    Repeater {
                                        model: vista.catalogo.condiciones
                                        Rectangle {
                                            required property var modelData
                                            readonly property bool activo: cond.modelData.condicion === modelData.id
                                            width: tc.implicitWidth + 10; height: 18
                                            color: activo ? Tema.cian : "transparent"
                                            border.color: activo ? Tema.cian : Tema.borde
                                            Text { id: tc; anchors.centerIn: parent; text: modelData.nombre; color: parent.activo ? Tema.fondo : Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                                            Pulsar { onPulsado: vista.cambiarTipo("si", cond.index, "condicion", parent.modelData) }
                                        }
                                    }
                                    Text {
                                        text: "✕ QUITAR"; color: Tema.rojo; font.family: Tema.mono; font.pixelSize: Tema.letraMini
                                        Pulsar { onPulsado: { const b = vista.clonar(vista.borrador); b.si.splice(cond.index, 1); vista.borrador = b; } }
                                    }
                                }
                                Parametros {
                                    definicion: vista.buscar(vista.catalogo.condiciones, cond.modelData.condicion)
                                    objeto: cond.modelData
                                    seccion: "si"
                                    indice: cond.index
                                }
                            }
                        }

                        // HACER
                        Row {
                            spacing: 10
                            Text { text: "HACER"; color: Tema.verde; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 2 }
                            Text {
                                visible: vista.borrador && (vista.borrador.hacer || []).length < 5
                                text: "+ AÑADIR"
                                color: Tema.cian
                                font.family: Tema.mono
                                font.pixelSize: Tema.letraMini
                                Pulsar {
                                    onPulsado: {
                                        const b = vista.clonar(vista.borrador);
                                        const ac = vista.catalogo.acciones.find(a => a.disponible) || vista.catalogo.acciones[0];
                                        b.hacer = (b.hacer || []).concat([vista.nuevoElemento("accion", ac)]);
                                        vista.borrador = b;
                                    }
                                }
                            }
                        }
                        Repeater {
                            model: vista.borrador ? vista.borrador.hacer || [] : []
                            Column {
                                id: acc
                                required property var modelData
                                required property int index
                                width: editor.width
                                spacing: 4
                                Flow {
                                    width: parent.width
                                    spacing: 3
                                    Repeater {
                                        model: vista.catalogo.acciones
                                        Rectangle {
                                            required property var modelData
                                            readonly property bool activo: acc.modelData.accion === modelData.id
                                            width: ta.implicitWidth + 10; height: 18
                                            color: activo ? Tema.verde : "transparent"
                                            border.color: activo ? Tema.verde : modelData.disponible ? Tema.borde : Tema.rejilla
                                            Text { id: ta; anchors.centerIn: parent; text: modelData.nombre; color: parent.activo ? Tema.fondo : modelData.disponible ? Tema.secundario : Tema.apagado; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                                            Pulsar { enabled: parent.modelData.disponible; onPulsado: vista.cambiarTipo("hacer", acc.index, "accion", parent.modelData) }
                                        }
                                    }
                                    Text {
                                        visible: (vista.borrador.hacer || []).length > 1
                                        text: "✕ QUITAR"; color: Tema.rojo; font.family: Tema.mono; font.pixelSize: Tema.letraMini
                                        Pulsar { onPulsado: { const b = vista.clonar(vista.borrador); b.hacer.splice(acc.index, 1); vista.borrador = b; } }
                                    }
                                }
                                Parametros {
                                    definicion: vista.buscar(vista.catalogo.acciones, acc.modelData.accion)
                                    objeto: acc.modelData
                                    seccion: "hacer"
                                    indice: acc.index
                                }
                            }
                        }
                    }
                }
                Row {
                    anchors.bottom: parent.bottom
                    anchors.right: parent.right
                    spacing: 8
                    Rectangle {
                        width: tCancelar.implicitWidth + 16; height: 22
                        color: "transparent"; border.color: Tema.borde; border.width: 1
                        Text { id: tCancelar; anchors.centerIn: parent; text: "CANCELAR"; color: Tema.secundario; font.family: Tema.mono; font.pixelSize: Tema.letraMini }
                        Pulsar { onPulsado: vista.borrador = null }
                    }
                    Rectangle {
                        width: tGuardar.implicitWidth + 16; height: 22
                        color: Tema.verde
                        Text { id: tGuardar; anchors.centerIn: parent; text: "GUARDAR REGLA"; color: Tema.fondo; font.family: Tema.mono; font.pixelSize: Tema.letraMini; font.letterSpacing: 1 }
                        Pulsar { onPulsado: orden.pedir({ orden: "regla_guardar", regla: vista.borrador }) }
                    }
                }
            }
        }

        // Historial de ejecuciones
        Marco {
            Layout.fillWidth: true
            Layout.preferredHeight: 130
            ident: "A3"
            etiqueta: "EXECUTION HISTORY"
            Flickable {
                anchors.fill: parent
                contentHeight: listaHist.implicitHeight
                clip: true
                Column {
                    id: listaHist
                    width: parent.width
                    spacing: 2
                    Repeater {
                        model: vista.datos && vista.datos.conflictos ? vista.datos.conflictos : []
                        Text {
                            required property var modelData
                            width: listaHist.width
                            elide: Text.ElideRight
                            text: vista.hora(modelData.t) + "  CONFLICTO " + modelData.recurso + ": gana «" + modelData.ganadora.nombre
                                  + "» sobre «" + modelData.perdedora.nombre + "» (" + modelData.motivo + ")  ·  " + modelData.evento
                            color: Tema.ambar
                            font.family: Tema.mono
                            font.pixelSize: Tema.letraMini
                        }
                    }
                    Text {
                        visible: vista.historial.length === 0
                        text: "Ninguna regla se ha ejecutado todavía."
                        color: Tema.apagado
                        font.family: Tema.mono
                        font.pixelSize: Tema.letraMini
                    }
                    Repeater {
                        model: vista.historial
                        Text {
                            required property var modelData
                            width: listaHist.width
                            elide: Text.ElideRight
                            text: vista.hora(modelData.t) + "  " + modelData.resultado.toUpperCase().padEnd(8) + " " + (modelData.nombre || modelData.regla)
                                  + "  ·  " + (modelData.evento || "") + (modelData.detalle ? "  ·  " + modelData.detalle : "")
                            color: vista.colorResultado(modelData.resultado)
                            font.family: Tema.mono
                            font.pixelSize: Tema.letraMini
                        }
                    }
                }
            }
        }
    }
}
