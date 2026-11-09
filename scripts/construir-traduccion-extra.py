#!/usr/bin/env python3
# Genera los nombres de regiones horarias en espanol y ajusta los textos de los pasos de instalacion.
# Uso: construir-traduccion-extra.py tz_en.ts tz_es.ts python.po python-salida.po
import re, sys, xml.etree.ElementTree as ET

REGIONES = {
    "Africa": "África", "America": "América", "Antarctica": "Antártida", "Arctic": "Ártico",
    "Asia": "Asia", "Atlantic": "Atlántico", "Australia": "Australia", "Europe": "Europa",
    "Indian": "Índico", "Pacific": "Pacífico", "Etc": "Otros",
}
arbol = ET.parse(sys.argv[1])
raiz = arbol.getroot()
raiz.set("language", "es")
for mensaje in raiz.iter("message"):
    origen = mensaje.findtext("source") or ""
    if origen in REGIONES:
        trad = mensaje.find("translation")
        trad.text = REGIONES[origen]
        trad.attrib.pop("type", None)
arbol.write(sys.argv[2], encoding="utf-8", xml_declaration=True)

PASOS = {
    "Filling up filesystems.": "Copiando los archivos del sistema.",
    "Unmounting file systems.": "Terminando de escribir en el disco.",
    "Install bootloader.": "Instalando el arranque del sistema.",
    "Configuring initramfs.": "Preparando el arranque del sistema.",
    "Removing live user from the target system": "Quitando el usuario temporal.",
}
texto = open(sys.argv[3], encoding="utf-8").read()
for msgid, msgstr in PASOS.items():
    texto, n = re.subn(r'(msgid "' + re.escape(msgid) + r'"\nmsgstr )"[^"]*"', lambda m: m.group(1) + '"' + msgstr + '"', texto)
    print(msgid, "->", n)
open(sys.argv[4], "w", encoding="utf-8").write(texto)
