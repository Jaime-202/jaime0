#!/usr/bin/env python3
"""Pruebas de jaime0-anclar con aplicaciones .desktop de mentira. Sin sesion grafica:
no abre ni enfoca nada, solo comprueba la lista, la resolucion de nombres y el estado
que lee la barra.

    python3 -m unittest discover -s pruebas -v
"""
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
REPO = pathlib.Path(__file__).resolve().parent.parent
INCLUDES = REPO / "config/includes.chroot_after_packages"
PROGRAMA = INCLUDES / "usr/local/bin/jaime0-anclar"
PREDETERMINADOS = INCLUDES / "usr/share/jaime0/ajustes.predeterminados"

DESKTOP = {
    "kitty": "Name=kitty\nExec=kitty\nCategories=System;TerminalEmulator;\n",
    "thunar": "Name=Thunar File Manager\nName[es]=Administrador de archivos Thunar\nExec=thunar %F\nCategories=FileManager;\n",
    "firefox-esr": "Name=Firefox ESR\nExec=/usr/lib/firefox-esr/firefox-esr %u\nStartupWMClass=firefox-esr\nCategories=Network;WebBrowser;\n",
    "btop": "Name=btop++\nExec=btop\nTerminal=true\nCategories=System;Monitor;\n",
    "org.pulseaudio.pavucontrol": "Name=Volume Control\nName[es]=Control de volumen\nExec=pavucontrol\nCategories=AudioVideo;\n",
    "code": "Name=Visual Studio Code\nExec=/usr/share/code/code --unity-launch %F\nStartupWMClass=Code\n",
    "oculta": "Name=Oculta\nExec=oculta\nNoDisplay=true\n",
    "nvim-qt": "Name=Neovim Qt\nExec=nvim-qt\n",
    "nvim-gtk": "Name=Neovim GTK\nExec=nvim-gtk\n",
    "rara": "Name=Rara\nExec=rara\nCategories=Utility;\n",
}


class Escenario:
    def __init__(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="jaime0-anclar-"))
        self.raiz = self.tmp / "raiz"
        self.casa = self.tmp / "casa"
        self.run = self.tmp / "run"
        apps = self.raiz / "usr/share/applications"
        apps.mkdir(parents=True)
        for ident, cuerpo in DESKTOP.items():
            (apps / f"{ident}.desktop").write_text(f"[Desktop Entry]\nType=Application\n{cuerpo}", encoding="utf-8")
        destino = self.raiz / "usr/share/jaime0/ajustes.predeterminados"
        destino.parent.mkdir(parents=True)
        fondo = self.raiz / "usr/share/backgrounds/jaime0/jaime0.png"
        fondo.parent.mkdir(parents=True)
        fondo.write_bytes(b"png")
        destino.write_text(PREDETERMINADOS.read_text(encoding="utf-8").replace(
            "/usr/share/backgrounds/jaime0/jaime0.png", fondo.as_posix()), encoding="utf-8")
        self.casa.mkdir()
        self.run.mkdir()
        self.env = dict(os.environ, JAIME0_RAIZ=str(self.raiz), HOME=str(self.casa),
                        XDG_CONFIG_HOME=str(self.casa / ".config"),
                        XDG_DATA_HOME=str(self.casa / ".local/share"),
                        XDG_DATA_DIRS="/usr/share", XDG_RUNTIME_DIR=str(self.run),
                        PYTHONIOENCODING="utf-8")
        self.env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)

    def ejecutar(self, *args):
        r = subprocess.run([sys.executable, str(PROGRAMA), *args], env=self.env,
                           capture_output=True, text=True, encoding="utf-8")
        return r.returncode, r.stdout, r.stderr

    def ancladas(self):
        rc, out, err = self.ejecutar("lista", "--json")
        assert rc == 0, err
        return [a["id"] for a in json.loads(out)]

    def estado(self, n):
        return json.loads((self.run / "jaime0/anclas" / f"{n}.json").read_text(encoding="utf-8"))

    def modulo(self):
        """jaime0-anclar importado con el entorno del escenario."""
        viejo = dict(os.environ)
        os.environ.clear()
        os.environ.update(self.env)
        try:
            cargador = importlib.machinery.SourceFileLoader("jaime0_anclar_pruebas", str(PROGRAMA))
            spec = importlib.util.spec_from_loader(cargador.name, cargador)
            m = importlib.util.module_from_spec(spec)
            cargador.exec_module(m)
            return m, viejo
        except BaseException:
            os.environ.clear()
            os.environ.update(viejo)
            raise

    def limpiar(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class PruebasAnclar(unittest.TestCase):
    def setUp(self):
        self.e = Escenario()
        self.addCleanup(self.e.limpiar)

    def test_predeterminadas(self):
        self.assertEqual(self.e.ancladas(), ["kitty", "thunar"])

    def test_anclar_resuelve_nombres(self):
        self.assertEqual(self.e.ejecutar("firefox")[0], 0)            # firefox -> firefox-esr
        self.assertEqual(self.e.ejecutar("pavucontrol")[0], 0)        # org.pulseaudio.pavucontrol
        self.assertEqual(self.e.ejecutar("btop.desktop")[0], 0)
        self.assertEqual(self.e.ancladas(), ["kitty", "thunar", "firefox-esr", "org.pulseaudio.pavucontrol", "btop"])
        rc, out, _ = self.e.ejecutar("firefox")
        self.assertEqual(rc, 0)
        self.assertIn("ya está anclada", out)

    def test_errores(self):
        rc, _, err = self.e.ejecutar("noexiste")
        self.assertEqual(rc, 1)
        self.assertIn("No encuentro", err)
        rc, _, err = self.e.ejecutar("nvim")                        # nvim-qt y nvim-gtk
        self.assertEqual(rc, 1)
        self.assertIn("nvim-gtk", err)
        self.assertEqual(self.e.ejecutar("oculta")[0], 1)          # NoDisplay
        self.assertEqual(self.e.ejecutar("quitar", "code")[0], 1)  # no anclada
        self.assertEqual(self.e.ejecutar("--rara")[0], 2)

    def test_maximo_seis(self):
        for app in ("firefox-esr", "btop", "code", "rara"):
            self.assertEqual(self.e.ejecutar(app)[0], 0, app)
        rc, _, err = self.e.ejecutar("nvim-qt")
        self.assertEqual(rc, 1)
        self.assertIn("Ya hay 6", err)
        self.assertEqual(len(self.e.ancladas()), 6)

    def test_quitar_y_mover(self):
        self.e.ejecutar("firefox-esr")
        self.e.ejecutar("btop")
        self.assertEqual(self.e.ejecutar("mover", "btop", "1")[0], 0)
        self.assertEqual(self.e.ancladas(), ["btop", "kitty", "thunar", "firefox-esr"])
        self.assertEqual(self.e.ejecutar("quitar", "firefox")[0], 0)  # tambien por nombre corto
        self.assertEqual(self.e.ejecutar("quitar", "kitty")[0], 0)
        self.assertEqual(self.e.ancladas(), ["btop", "thunar"])
        self.assertEqual(self.e.ejecutar("quitar", "btop")[0], 0)
        self.assertEqual(self.e.ejecutar("quitar", "thunar")[0], 0)
        self.assertEqual(self.e.ancladas(), [])
        texto = (self.e.casa / ".config/jaime0/ajustes").read_text(encoding="utf-8")
        self.assertIn("anclas = \n", texto)  # vacia, no la predeterminada

    def test_volver_a_las_predeterminadas_no_guarda_nada(self):
        self.e.ejecutar("btop")
        self.e.ejecutar("quitar", "btop")
        texto = (self.e.casa / ".config/jaime0/ajustes").read_text(encoding="utf-8")
        self.assertNotIn("anclas", texto.replace("(ajuste \"anclas\")", ""))

    def test_refrescar_escribe_seis_huecos(self):
        self.e.ejecutar("btop")
        self.assertEqual(self.e.ejecutar("refrescar", "--sin-senal")[0], 0)
        self.assertEqual(self.e.estado(1)["class"], ["ancla"])
        self.assertEqual(self.e.estado(2)["tooltip"], "Administrador de archivos Thunar")
        self.assertTrue(self.e.estado(3)["text"])
        for n in (4, 5, 6):
            self.assertEqual(self.e.estado(n)["text"], "", n)  # hueco vacio: Waybar lo oculta

    def test_aplicacion_desinstalada_no_se_muestra(self):
        self.e.ejecutar("btop")
        (self.e.raiz / "usr/share/applications/btop.desktop").unlink()
        self.e.ejecutar("refrescar", "--sin-senal")
        self.assertEqual(self.e.estado(3)["text"], "")
        rc, out, _ = self.e.ejecutar("lista")
        self.assertIn("no instalada", out)

    def test_estado_abierta_y_activa(self):
        m, viejo = self.e.modulo()
        try:
            apps = m.aplicaciones()
            ids = ["kitty", "firefox-esr", "btop", "code"]
            # btop va en kitty con su propia clase: no debe contar como kitty.
            textos = [json.loads(t) for t in m.estado(ids, apps, {"firefox-esr", "btop", "code"}, "btop")]
        finally:
            os.environ.clear()
            os.environ.update(viejo)
        self.assertEqual(textos[0]["class"], ["ancla"])
        self.assertEqual(textos[1]["class"], ["ancla", "abierta"])
        self.assertEqual(textos[2]["class"], ["ancla", "abierta", "activa"])
        self.assertEqual(textos[3]["class"], ["ancla", "abierta"])      # StartupWMClass=Code
        self.assertEqual(apps["btop"]["orden"][:3], ["kitty", "--class", "btop"])
        self.assertEqual(apps["thunar"]["orden"], ["thunar"])          # sin %F
        self.assertEqual(textos[4]["text"], "")

    def test_ajuste_anclas_valida(self):
        ajustes = INCLUDES / "usr/local/bin/jaime0-ajustes"
        def poner(*args):
            return subprocess.run([sys.executable, str(ajustes), "poner", *args], env=self.e.env,
                                  capture_output=True, text=True, encoding="utf-8").returncode
        self.assertEqual(poner("anclas", "a b c d e f g"), 1)
        self.assertEqual(poner("anclas", "kitty; rm"), 1)
        self.assertEqual(poner("anclas", "kitty,thunar kitty"), 0)  # comas y repetidas
        self.assertEqual(self.e.ancladas(), ["kitty", "thunar"])


if __name__ == "__main__":
    unittest.main()
