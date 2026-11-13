#!/usr/bin/env python3
"""Pruebas de jaime0-tiempo con respuestas de Open-Meteo de mentira (file://). Sin red.

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
PROGRAMA = INCLUDES / "usr/local/bin/jaime0-tiempo"
PREDETERMINADOS = INCLUDES / "usr/share/jaime0/ajustes.predeterminados"

GEO = {"results": [
    {"name": "Valencia", "latitude": 10.16, "longitude": -68.0, "country": "Venezuela", "country_code": "VE", "admin1": "Carabobo"},
    {"name": "Valencia", "latitude": 39.47, "longitude": -0.38, "country": "España", "country_code": "ES", "admin1": "Comunidad Valenciana"},
]}
PREVISION = {
    "current": {"time": "2026-11-12T19:00", "temperature_2m": 14.26, "apparent_temperature": 13.1,
                "weather_code": 0, "wind_speed_10m": 11.6, "is_day": 0},
    "daily": {"temperature_2m_max": [18.4], "temperature_2m_min": [9.2]},
}


class Escenario:
    def __init__(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="jaime0-tiempo-"))
        self.raiz = self.tmp / "raiz"
        self.casa = self.tmp / "casa"
        (self.raiz / "usr/share/jaime0").mkdir(parents=True)
        shutil.copy(PREDETERMINADOS, self.raiz / "usr/share/jaime0/ajustes.predeterminados")
        self.casa.mkdir()
        self.geo = self.tmp / "geo.json"
        self.prevision = self.tmp / "prevision.json"
        self.geo.write_text(json.dumps(GEO), encoding="utf-8")
        self.prevision.write_text(json.dumps(PREVISION), encoding="utf-8")
        self.env = dict(os.environ, JAIME0_RAIZ=str(self.raiz), HOME=str(self.casa),
                        XDG_CONFIG_HOME=str(self.casa / ".config"), XDG_CACHE_HOME=str(self.casa / ".cache"),
                        JAIME0_TIEMPO_GEO=self.geo.as_uri(), JAIME0_TIEMPO_PREVISION=self.prevision.as_uri(),
                        PYTHONIOENCODING="utf-8")

    def ciudad(self, texto):
        a = self.casa / ".config/jaime0/ajustes"
        a.parent.mkdir(parents=True, exist_ok=True)
        a.write_text(f"tiempo_ciudad = {texto}\n", encoding="utf-8")

    def ejecutar(self):
        r = subprocess.run([sys.executable, str(PROGRAMA)], env=self.env, capture_output=True,
                           text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)

    def limpiar(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class PruebasTiempo(unittest.TestCase):
    def setUp(self):
        self.e = Escenario()
        self.addCleanup(self.e.limpiar)

    def test_sin_ciudad_no_consulta(self):
        self.e.geo.unlink()  # si intentara consultar, fallaria de otra forma
        d = self.e.ejecutar()
        self.assertFalse(d["ok"])
        self.assertIn("ciudad", d["error"])

    def test_tiempo_y_homonimos(self):
        self.e.ciudad("Valencia, España")
        d = self.e.ejecutar()
        self.assertTrue(d["ok"])
        self.assertEqual(d["ciudad"], "Valencia, España")
        self.assertEqual(d["temperatura"], 14.3)
        self.assertEqual((d["maxima"], d["minima"], d["viento"]), (18, 9, 12))
        self.assertEqual(d["descripcion"], "Despejado")
        self.assertEqual(d["icono"], "\U000f0594")  # de noche, luna
        self.assertEqual(d["actualizado"], "19:00")

    def test_cache_y_sin_red(self):
        self.e.ciudad("Valencia")
        primero = self.e.ejecutar()
        self.assertEqual(primero["ciudad"], "Valencia, Venezuela")  # sin pista: el primero
        # Sin "red": la cache reciente se usa sin consultar.
        self.e.geo.unlink()
        self.e.prevision.unlink()
        self.assertEqual(self.e.ejecutar(), primero)
        # Cache caducada y sin red: el dato viejo, marcado como antiguo.
        cache = self.e.casa / ".cache/jaime0/tiempo.json"
        c = json.loads(cache.read_text(encoding="utf-8"))
        c["hora"] -= 3600
        cache.write_text(json.dumps(c), encoding="utf-8")
        d = self.e.ejecutar()
        self.assertTrue(d["ok"] and d.get("antiguo"))
        # Muy antigua: error.
        c["hora"] -= 7 * 3600
        cache.write_text(json.dumps(c), encoding="utf-8")
        d = self.e.ejecutar()
        self.assertFalse(d["ok"])
        self.assertIn("conexión", d["error"])

    def test_ciudad_desconocida(self):
        self.e.geo.write_text(json.dumps({"generationtime_ms": 0.1}), encoding="utf-8")
        self.e.ciudad("Inventadópolis")
        d = self.e.ejecutar()
        self.assertFalse(d["ok"])
        self.assertIn("Inventadópolis", d["error"])

    def test_cambiar_de_ciudad_vuelve_a_buscar(self):
        self.e.ciudad("Valencia")
        self.e.ejecutar()
        self.e.ciudad("Valencia, ES")
        self.assertEqual(self.e.ejecutar()["ciudad"], "Valencia, España")


if __name__ == "__main__":
    unittest.main()
