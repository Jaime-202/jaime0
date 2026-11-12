#!/usr/bin/env python3
"""Pruebas de jaime0-ajustes sobre un sistema de mentira (JAIME0_RAIZ) y una carpeta
personal temporal. No necesitan sesion grafica: en modo de prueba no se recarga nada.

    python3 -m unittest discover -s pruebas -v
"""
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
PROGRAMA = INCLUDES / "usr/local/bin/jaime0-ajustes"
PREDETERMINADOS = INCLUDES / "usr/share/jaime0/ajustes.predeterminados"


class Escenario:
    def __init__(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="jaime0-ajustes-"))
        self.raiz = self.tmp / "raiz"
        self.casa = self.tmp / "casa"
        destino = self.raiz / "usr/share/jaime0/ajustes.predeterminados"
        destino.parent.mkdir(parents=True)
        # El fondo predeterminado apunta a la raiz falsa, para que exista.
        self.fondos = self.raiz / "usr/share/backgrounds/jaime0"
        self.fondos.mkdir(parents=True)
        (self.fondos / "jaime0.png").write_bytes(b"png")
        texto = PREDETERMINADOS.read_text(encoding="utf-8").replace(
            "/usr/share/backgrounds/jaime0/jaime0.png", (self.fondos / "jaime0.png").as_posix())
        destino.write_text(texto, encoding="utf-8")
        self.casa.mkdir()
        self.config = self.casa / ".config"

    @property
    def archivo(self):
        return self.config / "jaime0" / "ajustes"

    def generado(self, nombre):
        return (self.config / "jaime0" / "generado" / nombre).read_text(encoding="utf-8")

    def ejecutar(self, *args):
        env = dict(os.environ, JAIME0_RAIZ=str(self.raiz), HOME=str(self.casa),
                   XDG_CONFIG_HOME=str(self.config), XDG_DATA_HOME=str(self.casa / ".local/share"),
                   PYTHONIOENCODING="utf-8")
        env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)
        r = subprocess.run([sys.executable, str(PROGRAMA), *args], env=env,
                           capture_output=True, text=True, encoding="utf-8")
        return r.returncode, r.stdout, r.stderr

    def ver(self):
        rc, out, err = self.ejecutar("ver", "--json")
        assert rc == 0, err
        d = json.loads(out)
        return {a["clave"]: a for a in d["ajustes"]}, d

    def limpiar(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class PruebasAjustes(unittest.TestCase):
    def setUp(self):
        self.e = Escenario()
        self.addCleanup(self.e.limpiar)

    def test_predeterminados_sin_archivo_de_usuario(self):
        ajustes, d = self.e.ver()
        self.assertEqual(ajustes["borde"]["valor"], "2")
        self.assertEqual(ajustes["esquinas"]["valor"], "8")
        self.assertEqual(ajustes["acento"]["valor"], "verde")
        self.assertEqual(ajustes["acento"]["color"], "#54e58a")
        self.assertEqual(ajustes["barra_altura"]["valor"], "26")
        self.assertFalse(any(a["propio"] for a in ajustes.values()))
        self.assertEqual(d["temas"]["cian"], "#55cde0")
        self.assertIn((self.e.fondos / "jaime0.png").as_posix(), [pathlib.Path(f).as_posix() for f in d["fondos"]])
        self.assertFalse(self.e.archivo.exists(), "ver no debe crear el archivo del usuario")

    def test_poner_guarda_solo_lo_cambiado_y_genera(self):
        rc, out, err = self.e.ejecutar("poner", "acento", "cian", "barra_altura", "30")
        self.assertEqual(rc, 0, err)
        texto = self.e.archivo.read_text(encoding="utf-8")
        claves = [l.split("=")[0].strip() for l in texto.splitlines() if l and not l.startswith("#")]
        self.assertEqual(sorted(claves), ["acento", "barra_altura"])
        self.assertIn("@define-color acento #55cde0;", self.e.generado("waybar.css"))
        self.assertIn("acento: #55cde0;", self.e.generado("rofi.rasi"))
        self.assertEqual(json.loads(self.e.generado("waybar.json")), {"height": 30, "position": "top"})
        ajustes, _ = self.e.ver()
        self.assertTrue(ajustes["acento"]["propio"])
        self.assertFalse(ajustes["borde"]["propio"])

    def test_acento_en_bloqueo_notificaciones_y_osd(self):
        propio = self.e.casa / "fondo.png"
        propio.write_bytes(b"png")
        self.assertEqual(self.e.ejecutar("poner", "acento", "ambar", "fondo", str(propio))[0], 0)
        hyprlock = self.e.generado("hyprlock.conf")
        self.assertIn("$acento = rgb(e0b050)", hyprlock)
        imagen = [l for l in hyprlock.splitlines() if l.startswith("$imagen = ")]
        self.assertEqual(len(imagen), 1)
        self.assertTrue(imagen[0].endswith("fondo.png"))
        self.assertIn("@define-color acento #e0b050;", self.e.generado("swaync.css"))
        wob = self.e.generado("wob.ini")
        self.assertIn("bar_color = e0b050ff", wob)
        self.assertNotIn("[", wob, "wob: las claves por defecto van sin cabecera de seccion")

    def test_valores_invalidos_no_cambian_nada(self):
        self.e.ejecutar("poner", "borde", "1")
        antes = self.e.archivo.read_text(encoding="utf-8")
        for args in (("borde", "99"), ("esquinas", "abc"), ("acento", "rojizo"), ("acento", "#12345"),
                     ("barra_posicion", "izquierda"), ("desenfoque", "quizas"), ("no_existe", "1"),
                     ("opacidad_inactiva", "0.2"), ("fondo", "/no/existe.png"),
                     ("esquinas", "6", "borde", "50")):  # todo o nada
            rc, _, err = self.e.ejecutar("poner", *args)
            self.assertEqual(rc, 1, args)
            self.assertTrue(err.strip(), args)
            self.assertEqual(self.e.archivo.read_text(encoding="utf-8"), antes, args)

    def test_normaliza_valores(self):
        self.assertEqual(self.e.ejecutar("poner", "opacidad_inactiva", "0,85")[0], 0)
        self.assertEqual(self.e.ejecutar("poner", "desenfoque", "NO")[0], 0)
        self.assertEqual(self.e.ejecutar("poner", "acento", "#ABCDEF")[0], 0)
        ajustes, _ = self.e.ver()
        self.assertEqual(ajustes["opacidad_inactiva"]["valor"], "0.85")
        self.assertEqual(ajustes["desenfoque"]["valor"], "no")
        self.assertEqual(ajustes["acento"]["color"], "#abcdef")
        self.assertIn("#abcdef", self.e.generado("waybar.css"))

    def test_conserva_comentarios_y_quita_duplicados(self):
        self.e.archivo.parent.mkdir(parents=True)
        self.e.archivo.write_text("# mis notas\nborde = 1\n# otra\nborde = 3\nesquinas = 4\n", encoding="utf-8")
        self.assertEqual(self.e.ejecutar("poner", "borde", "4")[0], 0)
        self.assertEqual(self.e.archivo.read_text(encoding="utf-8"),
                         "# mis notas\nborde = 4\n# otra\nesquinas = 4\n")

    def test_poner_el_predeterminado_no_lo_guarda(self):
        self.e.ejecutar("poner", "barra_altura", "30")
        self.assertEqual(self.e.ejecutar("poner", "barra_altura", "26")[0], 0)
        ajustes, _ = self.e.ver()
        self.assertFalse(ajustes["barra_altura"]["propio"])
        self.assertNotIn("barra_altura", self.e.archivo.read_text(encoding="utf-8"))

    def test_restablecer(self):
        self.e.ejecutar("poner", "borde", "1", "esquinas", "4", "acento", "ambar")
        self.assertEqual(self.e.ejecutar("restablecer", "borde")[0], 0)
        ajustes, _ = self.e.ver()
        self.assertEqual(ajustes["borde"]["valor"], "2")
        self.assertFalse(ajustes["borde"]["propio"])
        self.assertEqual(ajustes["esquinas"]["valor"], "4")
        self.assertEqual(self.e.ejecutar("restablecer", "--todo")[0], 0)
        ajustes, _ = self.e.ver()
        self.assertFalse(any(a["propio"] for a in ajustes.values()))
        self.assertIn("#54e58a", self.e.generado("waybar.css"))
        self.assertTrue(self.e.archivo.read_text(encoding="utf-8").startswith("#"), "la cabecera se conserva")
        self.assertEqual(self.e.ejecutar("restablecer", "inventado")[0], 1)

    def test_edicion_a_mano_invalida_se_ignora(self):
        self.e.archivo.parent.mkdir(parents=True)
        self.e.archivo.write_text("borde = muchos\nesquinas = 3\nbasura sin igual\nclave_rara = 1\n", encoding="utf-8")
        rc, _, err = self.e.ejecutar("aplicar")
        self.assertEqual(rc, 0)
        self.assertIn("borde", err)
        self.assertIn("clave_rara", err)
        ajustes, d = self.e.ver()
        self.assertEqual(ajustes["borde"]["valor"], "2")
        self.assertEqual(ajustes["esquinas"]["valor"], "3")
        self.assertEqual(len(d["avisos"]), 2)

    def test_fondo_y_barra_abajo(self):
        propio = self.e.casa / "mi fondo.jpg"
        propio.write_bytes(b"jpg")
        self.assertEqual(self.e.ejecutar("poner", "fondo", str(propio), "barra_posicion", "abajo")[0], 0)
        self.assertEqual(pathlib.Path(self.e.generado("fondo").strip()), propio.resolve())
        self.assertEqual(json.loads(self.e.generado("waybar.json"))["position"], "bottom")
        self.assertEqual(self.e.ejecutar("poner", "fondo", str(self.e.casa / "texto.txt"))[0], 1)

    def test_generar_es_idempotente(self):
        self.assertEqual(self.e.ejecutar("generar")[0], 0)
        css = self.e.config / "jaime0/generado/waybar.css"
        os.utime(css, (1, 1))
        self.assertEqual(self.e.ejecutar("generar")[0], 0)
        self.assertEqual(css.stat().st_mtime, 1, "no debe reescribir lo que no cambia")

    def test_cada_ajuste_tiene_predeterminado_valido(self):
        # El archivo real del repositorio: todas las claves del esquema, con valores validos.
        claves = {l.split("=")[0].strip() for l in PREDETERMINADOS.read_text(encoding="utf-8").splitlines()
                  if "=" in l and not l.lstrip().startswith("#") and not l.startswith("tema.")}
        ajustes, d = self.e.ver()
        self.assertEqual(claves, set(ajustes))
        self.assertEqual(d["avisos"], [])
        for a in ajustes.values():
            self.assertEqual(a["valor"], a["predeterminado"])

    def test_orden_desconocida(self):
        self.assertEqual(self.e.ejecutar("inventada")[0], 2)
        self.assertEqual(self.e.ejecutar("--help")[0], 0)


if __name__ == "__main__":
    unittest.main()
