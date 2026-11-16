#!/usr/bin/env python3
"""Accesibilidad del Control Center (evolucion, fase 9): contraste de la paleta, tamano
minimo de letra, que todo lo pulsable funcione con teclado, que no haya parpadeos salvo con
animaciones "suave", y los ajustes de escala y de animaciones del sistema. Lee los QML y
prueba jaime0-ajustes; no necesita Quickshell.

    python3 -m unittest discover -s pruebas -v
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_jaime0_servicio import cargar  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
CONTROL = REPO / "config/includes.chroot_after_packages/usr/share/jaime0/control"
AJUSTES = REPO / "config/includes.chroot_after_packages/usr/local/bin/jaime0-ajustes"


def luminancia(color):
    c = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contraste(a, b):
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def qml():
    return {f.name: f.read_text(encoding="utf-8") for f in sorted(CONTROL.glob("*.qml"))}


class PruebasContraste(unittest.TestCase):
    def setUp(self):
        texto = (CONTROL / "Tema.qml").read_text(encoding="utf-8")
        self.colores = dict(re.findall(r'property color (\w+): "(#[0-9a-fA-F]{6})"', texto))

    def test_todo_color_de_texto_supera_4_5_sobre_los_fondos(self):
        for texto in ("texto", "secundario", "apagado", "verde", "cian", "ambar", "rojo"):
            for fondo in ("fondo", "panel", "panel2"):
                r = contraste(self.colores[texto], self.colores[fondo])
                self.assertGreaterEqual(r, 4.5, f"{texto} sobre {fondo}: {r:.2f}:1")

    def test_la_jerarquia_se_mantiene(self):
        sobre = lambda c: contraste(self.colores[c], self.colores["panel"])
        self.assertGreater(sobre("texto"), sobre("secundario"))
        self.assertGreater(sobre("secundario"), sobre("apagado"))

    def test_las_lineas_no_se_usan_como_texto(self):
        for nombre, texto in qml().items():
            for n, linea in enumerate(texto.splitlines(), 1):
                if re.search(r"\bText\s*\{", linea) and re.search(r"(?<!border\.)color: [^;]*Tema\.(rejilla|borde)\b", linea):
                    self.fail(f"{nombre}:{n}: texto con color de línea (rejilla o borde)")


class PruebasLetra(unittest.TestCase):
    def test_ningun_texto_por_debajo_de_10_px(self):
        for nombre, texto in qml().items():
            for tam in re.findall(r"pixelSize: (\d+)", texto):
                self.assertGreaterEqual(int(tam), 10, f"{nombre}: texto de {tam} px")
        tema = (CONTROL / "Tema.qml").read_text(encoding="utf-8")
        self.assertGreaterEqual(int(re.search(r"letraMini: (\d+)", tema).group(1)), 10)


class PruebasTeclado(unittest.TestCase):
    def test_todo_lo_pulsable_funciona_con_teclado(self):
        """Nada usa un TapHandler suelto: todo va por Pulsar (Tab, Intro y Espacio)."""
        for nombre, texto in qml().items():
            if nombre in ("Pulsar.qml", "Grafica.qml"):
                continue
            self.assertNotIn("TapHandler", texto, f"{nombre}: usa TapHandler en vez de Pulsar")

    def test_pulsar_se_enfoca_se_ve_y_se_activa(self):
        p = (CONTROL / "Pulsar.qml").read_text(encoding="utf-8")
        for necesario in ("activeFocusOnTab: enabled", "Keys.onReturnPressed", "Keys.onSpacePressed",
                          "visible: pulsar.activeFocus", "Accessible.role: Accessible.Button"):
            self.assertIn(necesario, p)

    def test_navegacion_entre_secciones(self):
        s = (CONTROL / "shell.qml").read_text(encoding="utf-8")
        for necesario in ("Qt.Key_Tab", "Qt.Key_Backtab", "Qt.Key_PageDown", "Qt.Key_PageUp", "Qt.Key_0",
                          "lienzo.forceActiveFocus()", "CTRL+TAB"):
            self.assertIn(necesario, s)


class PruebasMovimiento(unittest.TestCase):
    def test_lo_que_se_repite_sin_fin_solo_con_suave(self):
        for nombre, texto in qml().items():
            for m in re.finditer(r"loops: Animation\.Infinite", texto):
                bloque = texto[max(0, m.start() - 400):m.start()]
                self.assertIn('Tema.nivel === "suave"', bloque, f"{nombre}: animación sin fin fuera de \"suave\"")

    def test_el_barrido_de_la_cabecera_solo_con_suave(self):
        s = (CONTROL / "shell.qml").read_text(encoding="utf-8")
        self.assertRegex(s, r'interval: 10000\n\s+// [^\n]*\n\s+running: Tema\.nivel === "suave"')


class PruebasAjustes(unittest.TestCase):
    A = cargar("jaime0_ajustes_accesibilidad", "jaime0-ajustes")

    def test_escala_valida_y_en_control_json(self):
        self.assertEqual(self.A.validar("cc_escala", "115", {}), "115")
        with self.assertRaises(self.A.Error):
            self.A.validar("cc_escala", "200", {})
        raiz = tempfile.mkdtemp(prefix="jaime0-acc-")
        self.addCleanup(shutil.rmtree, raiz, ignore_errors=True)
        destino = pathlib.Path(raiz) / "usr/share/jaime0"
        destino.mkdir(parents=True)
        shutil.copy(AJUSTES.parent.parent.parent / "share/jaime0/ajustes.predeterminados", destino)
        entorno = dict(os.environ, JAIME0_RAIZ=raiz, XDG_CONFIG_HOME=os.path.join(raiz, "config"), HOME=raiz)
        for orden in (["poner", "cc_escala", "130"], ["generar"]):
            r = subprocess.run([sys.executable, str(AJUSTES)] + orden, env=entorno, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
        control = json.loads((pathlib.Path(raiz) / "config/jaime0/generado/control.json").read_text(encoding="utf-8"))
        self.assertEqual(control["escala"], 130)

    def test_la_preferencia_del_sistema_de_no_animar_se_respeta(self):
        self.assertEqual(self.A.nivel_animaciones("suave", sistema=False), "no")
        self.assertEqual(self.A.nivel_animaciones("sutil", sistema=True), "sutil")
        self.assertEqual(self.A.nivel_animaciones("no", sistema=True), "no")
        self.assertEqual(self.A.nivel_animaciones("suave", sistema=None) if self.A.MODO_PRUEBA else "suave", "suave")

    def test_lectura_de_gsettings(self):
        r = lambda salida, rc=0: (lambda *a, **k: mock.Mock(returncode=rc, stdout=salida))
        self.assertIs(self.A.animaciones_del_sistema(r("false\n")), False)
        self.assertIs(self.A.animaciones_del_sistema(r("true\n")), True)
        self.assertIsNone(self.A.animaciones_del_sistema(r("", 1)))
        self.assertIsNone(self.A.animaciones_del_sistema(mock.Mock(side_effect=OSError)))


if __name__ == "__main__":
    unittest.main()
