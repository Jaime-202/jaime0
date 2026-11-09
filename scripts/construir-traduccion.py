#!/usr/bin/env python3
# Corrige la traduccion al espanol del instalador. Uso: construir-traduccion.py entrada.ts salida.ts
# Despues: lrelease salida.ts -qm calamares_es.qm
# El instalador carga /usr/share/calamares/lang/calamares_es.qm antes que su copia interna.
import re, sys, xml.etree.ElementTree as ET

entrada, salida = sys.argv[1], sys.argv[2]
arbol = ET.parse(entrada)
raiz = arbol.getroot()

# Texto original exacto -> traduccion. Una lista traduce los plurales.
CAMBIOS = {
    "Go &Back": "&Atrás",
    "&Back": "&Atrás",
    "&Next": "&Siguiente",
    "&Done": "&Hecho",
    "&Cancel": "&Cancelar",
    "&Install": "&Instalar",
    "Install": "Instalar",
    "En&crypt system": "C&ifrar el disco",
    "<strong>Select a partition to shrink, then drag the bottom bar to resize</strong>": "<strong>Elige la partición a reducir y arrastra la barra inferior</strong>",
    "Waiting for %n module(s)…": ["Comprobando tu equipo…", "Comprobando tu equipo…"],
    "(%n second(s))": [" ", " "],
    "<h1>Welcome to the %1 installer</h1>": "<h1>Te damos la bienvenida a %1</h1>",
    "<h1>Welcome to %1 setup</h1>": "<h1>Te damos la bienvenida a %1</h1>",
    "<h1>Welcome to the Calamares installer for %1</h1>": "<h1>Te damos la bienvenida a %1</h1>",
    "<h1>Welcome to the Calamares setup program for %1</h1>": "<h1>Te damos la bienvenida a %1</h1>",
    "Please ensure the system has at least %1 GiB available drive space.": "Al menos %1 GiB de espacio en disco",
    "has at least %1 GiB working memory": "Al menos %1 GiB de memoria RAM",
    "is plugged in to a power source": "Conectado a la corriente",
    "is connected to the Internet": "Conexión a Internet",
    "is running the installer as an administrator (root)": "Permisos de administrador",
    "has at least one disk device available.": "Al menos un disco disponible",
    "There is not enough drive space. At least %1 GiB is required.": "No hay espacio suficiente: se necesitan al menos %1 GiB en disco",
    "The system does not have enough working memory. At least %1 GiB is required.": "No hay memoria suficiente: se necesitan al menos %1 GiB de RAM",
    "The system is not plugged in to a power source.": "Sin corriente: conviene conectar el cargador antes de instalar",
    "The system is not connected to the Internet.": "Sin Internet: la instalación funciona igual sin conexión",
    "The installer is not running with administrator rights.": "El instalador no tiene permisos de administrador",
    "<h1>Installation Failed</h1><br/>%1 has not been installed on your computer.<br/>The error message was: %2.": "<h1>La instalación no se ha completado</h1><br/>%1 no se ha instalado en tu equipo.<br/>Motivo: %2.<br/><br/>Al cerrar esta ventana encontrarás el registro completo en <code>~/instalador.log</code>.",
}

# Cualquier otra aparicion del nombre interno del programa se sustituye por "el instalador".
SUSTITUCIONES = [
    (re.compile(r"\bde Calamares\b"), "del instalador"),
    (re.compile(r"\ba Calamares\b"), "al instalador"),
    (re.compile(r"\bCalamares\b"), "el instalador"),
    (re.compile(r"Instalación paralela"), "Junto a otro sistema"),
    (re.compile(r"El instalador %1 "), "El instalador de %1 "),
    (re.compile(r"^tiene al menos un dispositivo de disco disponible\.?$"), "Al menos un disco disponible"),
]

cambiados = 0
pendientes = []
for mensaje in raiz.iter("message"):
    origen = mensaje.findtext("source") or ""
    trad = mensaje.find("translation")
    if trad is None:
        continue
    if origen in CAMBIOS:
        valor = CAMBIOS[origen]
        if isinstance(valor, list):
            formas = trad.findall("numerusform")
            for forma, texto in zip(formas, valor):
                forma.text = texto
        else:
            trad.text = valor
        trad.attrib.pop("type", None)
        cambiados += 1
        continue
    if trad.findall("numerusform"):
        continue
    texto = trad.text or ""
    nuevo = texto
    for patron, reemplazo in SUSTITUCIONES:
        nuevo = patron.sub(reemplazo, nuevo)
    # Elimina espacios al final, que descuadran los botones
    nuevo = nuevo.rstrip() if not texto.endswith("\n") else nuevo
    if nuevo != texto:
        trad.text = nuevo
        cambiados += 1
    if "%R" in nuevo or re.search(r"(^|\s)%[A-Za-zÁ-ú]", nuevo):
        pendientes.append(nuevo)

arbol.write(salida, encoding="utf-8", xml_declaration=True)
print("cambiados:", cambiados)
for texto in pendientes:
    print("REVISAR:", texto[:120])
