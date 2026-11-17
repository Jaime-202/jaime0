#!/usr/bin/env python3
"""Pruebas del motor de perfiles (Fase 4) de jaime0-servicio, del cliente jaime0-perfil y de la
barra de jaime0-salud. ppd, swaync, logind, hyprctl y modo-noche se simulan con un "sistema"
falso: no hay D-Bus, procesos ni sockets reales.

    python3 -m unittest discover -s pruebas -v
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.dont_write_bytecode = True
REPO = pathlib.Path(__file__).resolve().parent.parent
BIN = REPO / "config/includes.chroot_after_packages/usr/local/bin"


def cargar(nombre, programa):
    cargador = importlib.machinery.SourceFileLoader(nombre, str(BIN / programa))
    spec = importlib.util.spec_from_loader(cargador.name, cargador)
    modulo = importlib.util.module_from_spec(spec)
    cargador.exec_module(modulo)
    return modulo


S = cargar("jaime0_servicio_perfiles", "jaime0-servicio")
H = cargar("jaime0_salud_perfiles", "jaime0-salud")
P = cargar("jaime0_perfil_pruebas", "jaime0-perfil")


class SistemaFalso:
    """Imita lo que SistemaReal ofrece al motor y anota lo que se le pide."""

    def __init__(self, ppd=("balanced", "power-saver", "performance"), swaync=True, hypr=True, logind=True,
                 noche=True, dnd=False, modo_noche=False):
        self.ppd = None if ppd is None else list(ppd)
        self.swaync, self.hypr, self.logind, self.noche = swaync, hypr, logind, noche
        self.dnd, self.modo_noche = dnd, modo_noche
        self.retenciones, self._cookie = {}, 0
        self.hold_llamadas, self.release_llamadas = [], []
        self.dnd_escrituras, self.noche_escrituras = [], []
        self.recargas = 0
        self.fds_abiertos, self.motivos_inhibidor, self._fd = [], [], 100
        self.fallan = set()             # nombres de metodo que lanzan OSError
        self.degradado = None

    def _falla(self, nombre):
        if nombre in self.fallan:
            raise OSError(f"fallo simulado en {nombre}")

    def capacidades(self):
        return {"energia": [p for p in (self.ppd or []) if p in S.VALORES_AJUSTE["energia"]],
                "ppd": self.ppd is not None, "no_molestar": self.swaync, "animaciones": self.hypr,
                "inhibir_inactividad": self.logind, "modo_noche": self.noche}

    def ppd_retener(self, perfil):
        self._falla("ppd_retener")
        self._cookie += 1
        self.retenciones[self._cookie] = perfil
        self.hold_llamadas.append(perfil)
        return self._cookie

    def ppd_liberar(self, cookie):
        self._falla("ppd_liberar")
        self.release_llamadas.append(cookie)
        del self.retenciones[cookie]

    def ppd_degradado(self):
        return self.degradado

    def dnd_leer(self):
        self._falla("dnd_leer")
        return self.dnd

    def dnd_poner(self, activo):
        self._falla("dnd_poner")
        self.dnd = activo
        self.dnd_escrituras.append(activo)

    def hypr_disponible(self):
        return self.hypr

    def hypr_recargar(self):
        self._falla("hypr_recargar")
        self.recargas += 1

    def inhibir_abrir(self, motivo):
        self._falla("inhibir_abrir")
        self._fd += 1
        self.fds_abiertos.append(self._fd)
        self.motivos_inhibidor.append(motivo)
        return self._fd

    def inhibir_cerrar(self, fd):
        self.fds_abiertos.remove(fd)

    def noche_leer(self):
        self._falla("noche_leer")
        return self.modo_noche

    def noche_poner(self, activo):
        self._falla("noche_poner")
        self.modo_noche = activo
        self.noche_escrituras.append(activo)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jaime0-perfil-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.rt = os.path.join(self.tmp, "rt")
        self.estado = os.path.join(self.tmp, "estado")
        self.config = os.path.join(self.tmp, "config")
        os.makedirs(self.rt)
        p = mock.patch.dict(os.environ, {"JAIME0_RUNTIME": self.rt, "JAIME0_ESTADO": self.estado,
                                         "XDG_CONFIG_HOME": self.config})
        p.start()
        self.addCleanup(p.stop)
        self.sis = SistemaFalso()

    def servicio(self, sis=None):
        return S.Servicio(directorio=self.rt, estado=self.estado, sistema=sis or self.sis,
                          leer_umbrales=lambda: {})

    @property
    def capa(self):
        return os.path.join(self.rt, "perfil.ajustes")

    def leer_capa(self):
        try:
            with open(self.capa, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return None

    def leer_estado(self, nombre):
        with open(os.path.join(self.estado, nombre), encoding="utf-8") as f:
            return json.load(f)


def escribir_archivo_custom(base, texto):
    d = os.path.join(base, "jaime0")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "perfil-personalizado.json"), "w", encoding="utf-8") as f:
        f.write(texto)


class PruebasDefinicion(Base):
    def doc(self):
        return self.servicio().perfiles.perfiles_doc()

    def test_ids_nombres_y_orden(self):
        perfiles = self.doc()["perfiles"]
        self.assertEqual([p["id"] for p in perfiles],
                         ["balanced", "performance", "power-saver", "focus", "multimedia", "custom"])
        self.assertEqual([p["nombre"] for p in perfiles],
                         ["BALANCED", "PERFORMANCE", "POWER SAVER", "FOCUS", "MULTIMEDIA", "CUSTOM"])

    def test_ajustes_de_los_perfiles_fijos(self):
        por_id = {p["id"]: p for p in self.doc()["perfiles"]}
        self.assertEqual(por_id["balanced"]["ajustes"], {})
        self.assertEqual(por_id["performance"]["ajustes"], {"energia": "performance"})
        self.assertEqual(por_id["power-saver"]["ajustes"],
                         {"energia": "power-saver", "animaciones": "no", "desenfoque": "no"})
        self.assertEqual(por_id["focus"]["ajustes"], {"no_molestar": "si"})
        self.assertEqual(por_id["multimedia"]["ajustes"], {"inhibir_inactividad": "si", "no_molestar": "si"})
        self.assertEqual(por_id["custom"]["ajustes"], {})

    def test_descripciones_literales(self):
        por_id = {p["id"]: p["descripcion"] for p in self.doc()["perfiles"]}
        self.assertEqual(por_id["balanced"],
                         "Equilibrio entre rendimiento y consumo. Deja todo como lo tienes configurado.")
        self.assertEqual(por_id["focus"], "Menos distracciones: no molestar activado (las notificaciones "
                                          "se guardan en el centro sin aparecer).")

    def test_textos_de_cambios(self):
        por_id = {p["id"]: p["cambios"] for p in self.doc()["perfiles"]}
        self.assertEqual(por_id["balanced"], [])
        self.assertEqual(por_id["performance"], ["Energía: rendimiento"])
        self.assertEqual(por_id["power-saver"],
                         ["Energía: ahorro", "Animaciones: desactivadas", "Desenfoque: desactivado"])
        self.assertEqual(por_id["focus"], ["No molestar: activado"])
        self.assertEqual(S.textos_cambios({"energia": "balanced", "animaciones": "si", "desenfoque": "si",
                                           "no_molestar": "no", "modo_noche": "si", "animaciones_x": "x"}),
                         ["Energía: equilibrado", "Animaciones: activadas", "Desenfoque: activado",
                          "No molestar: desactivado", "Modo noche: activado"])
        self.assertEqual(S.textos_cambios({"animaciones": "base"}), [])

    def test_capacidades_y_campos(self):
        d = self.doc()
        self.assertTrue(d["ok"])
        self.assertEqual(d["capacidades"], {"energia": ["balanced", "power-saver", "performance"],
                                            "no_molestar": True, "animaciones": True,
                                            "inhibir_inactividad": True, "modo_noche": True})
        self.assertEqual(d["personalizado"], {"ajustes": {}, "error": None})
        for p in d["perfiles"]:
            self.assertEqual(sorted(p), ["ajustes", "cambios", "descripcion", "disponible", "id", "motivo", "nombre"])

    def test_normalizar_nombres(self):
        for texto in ("POWER SAVER", "power-saver", " Power_Saver "):
            self.assertEqual(S.normalizar_perfil(texto), "power-saver")


class PruebasDisponibilidad(Base):
    def disp(self, **kw):
        s = self.servicio(SistemaFalso(**kw))
        return {p["id"]: p for p in s.perfiles.perfiles_doc()["perfiles"]}

    def test_todo_disponible(self):
        self.assertTrue(all(p["disponible"] and p["motivo"] is None for p in self.disp().values()))

    def test_sin_performance_en_ppd(self):
        d = self.disp(ppd=("balanced", "power-saver"))
        self.assertFalse(d["performance"]["disponible"])
        self.assertIn("alto rendimiento", d["performance"]["motivo"])
        self.assertTrue(d["power-saver"]["disponible"])
        self.assertTrue(d["balanced"]["disponible"])

    def test_sin_ppd(self):
        d = self.disp(ppd=None)
        self.assertFalse(d["performance"]["disponible"])
        self.assertFalse(d["power-saver"]["disponible"])
        self.assertIn("power-profiles-daemon", d["performance"]["motivo"])
        self.assertTrue(d["focus"]["disponible"])

    def test_sin_swaync(self):
        d = self.disp(swaync=False)
        self.assertFalse(d["focus"]["disponible"])
        self.assertFalse(d["multimedia"]["disponible"])
        self.assertIn("swaync", d["focus"]["motivo"])
        self.assertTrue(d["performance"]["disponible"])

    def test_sin_hyprland(self):
        d = self.disp(hypr=False)
        self.assertFalse(d["power-saver"]["disponible"])
        self.assertIn("Hyprland", d["power-saver"]["motivo"])

    def test_sin_logind_solo_afecta_a_inhibir(self):
        d = self.disp(logind=False, swaync=False)
        self.assertIn("logind", d["multimedia"]["motivo"])
        self.assertIn("swaync", d["multimedia"]["motivo"])        # los dos motivos
        self.assertTrue(d["focus"]["disponible"] is False)         # por swaync
        self.assertTrue(d["balanced"]["disponible"])

    def test_no_se_aplica_un_perfil_no_disponible(self):
        sis = SistemaFalso(ppd=("balanced", "power-saver"))
        s = self.servicio(sis)
        r = s.perfiles.aplicar("performance")
        self.assertFalse(r["ok"])
        self.assertIn("PERFORMANCE", r["error"])
        self.assertIn("no está disponible", r["error"])
        self.assertEqual(sis.hold_llamadas, [])
        self.assertIsNone(s.perfiles.activo)

    def test_perfil_desconocido(self):
        r = self.servicio().perfiles.aplicar("turbo")
        self.assertFalse(r["ok"])
        self.assertIn("desconocido", r["error"])


class PruebasAplicar(Base):
    def test_focus_y_vuelta_restauran_no_molestar_real(self):
        s = self.servicio()
        self.assertTrue(s.perfiles.aplicar("balanced")["ok"])
        self.assertEqual(self.sis.dnd_escrituras, [])             # balanced no toca nada
        self.assertTrue(s.perfiles.aplicar("focus")["ok"])
        self.assertTrue(self.sis.dnd)
        self.assertEqual(s.perfiles.instantaneas, {"no_molestar": False})
        self.assertTrue(os.path.exists(os.path.join(self.rt, "perfil-instantaneas.json")))
        self.assertTrue(s.perfiles.aplicar("balanced")["ok"])
        self.assertFalse(self.sis.dnd)
        self.assertEqual(self.sis.dnd_escrituras, [True, False])
        self.assertEqual(s.perfiles.instantaneas, {})
        self.assertFalse(os.path.exists(os.path.join(self.rt, "perfil-instantaneas.json")))

    def test_si_no_molestar_ya_estaba_activado_sigue_activado_al_volver(self):
        self.sis.dnd = True
        s = self.servicio()
        s.perfiles.aplicar("focus")
        self.assertEqual(self.sis.dnd_escrituras, [])             # ya estaba: no se escribe
        s.perfiles.aplicar("balanced")
        self.assertTrue(self.sis.dnd)
        self.assertEqual(self.sis.dnd_escrituras, [])
        self.assertEqual(s.perfiles.instantaneas, {})

    def test_aplicar_es_idempotente(self):
        s = self.servicio()
        s.perfiles.aplicar("focus")
        s.perfiles.aplicar("focus")
        self.assertEqual(self.sis.dnd_escrituras, [True])
        s.perfiles.aplicar("balanced")
        self.assertEqual(self.sis.dnd_escrituras, [True, False])

    def test_del_usuario_a_otro_perfil_conserva_la_instantanea_original(self):
        s = self.servicio()
        s.perfiles.aplicar("focus")
        s.perfiles.aplicar("multimedia")       # sigue con no molestar: la instantanea no se pisa
        self.assertEqual(s.perfiles.instantaneas, {"no_molestar": False})
        s.perfiles.aplicar("performance")      # deja no molestar en base: restaura
        self.assertFalse(self.sis.dnd)

    def test_power_saver_escribe_la_capa_y_recarga(self):
        s = self.servicio()
        r = s.perfiles.aplicar("power-saver")
        self.assertTrue(r["ok"])
        self.assertEqual(self.leer_capa(), "animaciones = no\ndesenfoque = no\n")
        self.assertEqual(self.sis.recargas, 1)
        self.assertFalse(any(n.endswith(".tmp") for n in os.listdir(self.rt)))
        s.perfiles.aplicar("power-saver")                  # idempotente: ni escribe ni recarga
        self.assertEqual(self.sis.recargas, 1)

    def test_volver_a_balanced_borra_la_capa(self):
        s = self.servicio()
        s.perfiles.aplicar("power-saver")
        s.perfiles.aplicar("balanced")
        self.assertIsNone(self.leer_capa())
        self.assertEqual(self.sis.recargas, 2)
        s.perfiles.aplicar("balanced")
        self.assertEqual(self.sis.recargas, 2)

    def test_solo_las_claves_que_el_perfil_fija(self):
        s = self.servicio()
        escribir_archivo_custom(self.config, json.dumps({"v": 1, "ajustes": {"desenfoque": "si", "animaciones": "base"}}))
        s.perfiles.aplicar("custom")
        self.assertEqual(self.leer_capa(), "desenfoque = si\n")

    def capa_con_animaciones_si(self, usuario):
        """CUSTOM con animaciones = si, con `usuario` como ajuste efectivo del usuario."""
        s = S.Servicio(directorio=self.rt, estado=self.estado, sistema=self.sis, leer_umbrales=lambda: {})
        s.perfiles.animaciones_usuario = lambda: usuario
        escribir_archivo_custom(self.config, json.dumps({"v": 1, "ajustes": {"animaciones": "si"}}))
        self.assertTrue(s.perfiles.aplicar("custom")["ok"])

    def test_animaciones_si_no_rebaja_el_ajuste_del_usuario(self):
        for usuario in ("suave", "sutil"):
            self.capa_con_animaciones_si(usuario)
            self.assertIsNone(self.leer_capa(), usuario)       # que mande el ajuste del usuario

    def test_animaciones_si_con_el_usuario_en_no_escribe_sutil(self):
        self.capa_con_animaciones_si("no")
        self.assertEqual(self.leer_capa(), "animaciones = sutil\n")

    def test_el_ajuste_de_animaciones_del_usuario_sale_de_sus_archivos(self):
        os.makedirs(os.path.join(self.config, "jaime0"))
        archivo = os.path.join(self.config, "jaime0", "ajustes")
        for texto, esperado in (("animaciones = suave\n", "suave"), ("# animaciones = no\n", "sutil"),
                                ("animaciones = no\n", "no"), ("animaciones = si\n", "sutil"),
                                ("animaciones = raro\n", "sutil")):
            with open(archivo, "w", encoding="utf-8") as f:
                f.write(texto)
            self.assertEqual(S.nivel_animaciones_usuario(), esperado, texto)

    def test_animaciones_no_se_sigue_escribiendo_como_no(self):
        s = self.servicio()
        escribir_archivo_custom(self.config, json.dumps({"v": 1, "ajustes": {"animaciones": "no"}}))
        s.perfiles.aplicar("custom")
        self.assertEqual(self.leer_capa(), "animaciones = no\n")

    def test_sin_hyprland_no_se_toca_la_capa(self):
        s = self.servicio(SistemaFalso(hypr=False))
        self.assertTrue(s.perfiles.aplicar("focus")["ok"])
        self.assertIsNone(self.leer_capa())
        self.assertFalse(s.perfiles.aplicar("power-saver")["ok"])

    def test_retencion_de_energia(self):
        s = self.servicio()
        s.perfiles.aplicar("performance")
        self.assertEqual(self.sis.retenciones, {1: "performance"})
        self.assertEqual(s.perfiles.retencion, "performance")
        s.perfiles.aplicar("power-saver")                  # libera la anterior y retiene la nueva
        self.assertEqual(self.sis.retenciones, {2: "power-saver"})
        self.assertEqual(self.sis.release_llamadas, [1])
        s.perfiles.aplicar("power-saver")                  # idempotente
        self.assertEqual(self.sis.hold_llamadas, ["performance", "power-saver"])
        s.perfiles.aplicar("balanced")
        self.assertEqual(self.sis.retenciones, {})
        self.assertIsNone(s.perfiles.retencion)

    def test_balanced_sin_retencion_no_libera_nada(self):
        s = self.servicio()
        s.perfiles.aplicar("balanced")
        self.assertEqual(self.sis.release_llamadas, [])

    def test_inhibidor_abierto_y_cerrado(self):
        s = self.servicio()
        s.perfiles.aplicar("multimedia")
        self.assertEqual(len(self.sis.fds_abiertos), 1)
        self.assertEqual(self.sis.motivos_inhibidor, ["Perfil MULTIMEDIA: sin bloqueo ni apagado de pantalla"])
        s.perfiles.aplicar("multimedia")
        self.assertEqual(len(self.sis.fds_abiertos), 1)    # no se abre otro
        s.perfiles.aplicar("balanced")
        self.assertEqual(self.sis.fds_abiertos, [])
        s.perfiles.aplicar("multimedia")
        s.perfiles.aplicar("focus")
        self.assertEqual(self.sis.fds_abiertos, [])

    def test_modo_noche_con_instantanea(self):
        self.sis.modo_noche = True
        s = self.servicio()
        escribir_archivo_custom(self.config, json.dumps({"v": 1, "ajustes": {"modo_noche": "no"}}))
        s.perfiles.aplicar("custom")
        self.assertFalse(self.sis.modo_noche)
        s.perfiles.aplicar("balanced")
        self.assertTrue(self.sis.modo_noche)               # vuelve a como estaba

    def test_modo_noche_no_disponible_bloquea_el_perfil(self):
        s = self.servicio(SistemaFalso(noche=False))
        escribir_archivo_custom(self.config, json.dumps({"v": 1, "ajustes": {"modo_noche": "si"}}))
        r = s.perfiles.aplicar("custom")
        self.assertFalse(r["ok"])
        self.assertIn("modo noche", r["error"])

    def test_nunca_escribe_ajustes_de_usuario(self):
        s = self.servicio()
        for p in ("power-saver", "focus", "multimedia", "performance", "balanced"):
            s.perfiles.aplicar(p)
        self.assertFalse(os.path.exists(os.path.join(self.config, "jaime0", "ajustes")))


class PruebasFallos(Base):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(S.perfiles_mod, "registrar")      # los fallos simulados no ensucian la salida
        p.start()
        self.addCleanup(p.stop)

    def test_fallo_parcial_aplica_lo_demas(self):
        self.sis.fallan.add("dnd_poner")
        s = self.servicio()
        escribir_archivo_custom(self.config, json.dumps(
            {"v": 1, "ajustes": {"energia": "performance", "no_molestar": "si", "desenfoque": "no"}}))
        r = s.perfiles.aplicar("custom")
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["fallos"]), 1)
        self.assertTrue(r["fallos"][0].startswith("No molestar:"))
        self.assertEqual(self.sis.retenciones, {1: "performance"})
        self.assertEqual(self.leer_capa(), "desenfoque = no\n")
        self.assertEqual(s.perfiles.instantaneas, {})      # sin instantanea incoherente
        self.assertFalse(os.path.exists(os.path.join(self.rt, "perfil-instantaneas.json")))
        self.assertEqual(s.perfiles.fallos, r["fallos"])
        self.assertEqual(s.perfiles.doc_estado(None)["fallos"], r["fallos"])

    def test_fallo_al_leer_no_molestar_no_crea_instantanea(self):
        self.sis.fallan.add("dnd_leer")
        s = self.servicio()
        r = s.perfiles.aplicar("focus")
        self.assertTrue(r["ok"])
        self.assertTrue(r["fallos"][0].startswith("No molestar:"))
        self.assertEqual(self.sis.dnd_escrituras, [])
        self.assertEqual(s.perfiles.instantaneas, {})

    def test_si_falla_la_restauracion_se_conserva_la_instantanea(self):
        s = self.servicio()
        s.perfiles.aplicar("focus")
        self.sis.fallan.add("dnd_poner")
        r = s.perfiles.aplicar("balanced")
        self.assertEqual(len(r["fallos"]), 1)
        self.assertEqual(s.perfiles.instantaneas, {"no_molestar": False})
        self.sis.fallan.clear()
        s.perfiles.aplicar("balanced")                     # reintenta y restaura
        self.assertFalse(self.sis.dnd)
        self.assertEqual(s.perfiles.instantaneas, {})

    def test_fallo_de_hold_se_informa_y_no_deja_retencion(self):
        self.sis.fallan.add("ppd_retener")
        s = self.servicio()
        r = s.perfiles.aplicar("performance")
        self.assertTrue(r["ok"])
        self.assertTrue(r["fallos"][0].startswith("Energía:"))
        self.assertIsNone(s.perfiles.retencion)

    def test_fallo_de_recarga_se_reintenta(self):
        self.sis.fallan.add("hypr_recargar")
        s = self.servicio()
        r = s.perfiles.aplicar("power-saver")
        self.assertTrue(r["fallos"][0].startswith("Animaciones y desenfoque:"))
        self.sis.fallan.clear()
        s.perfiles.aplicar("power-saver")                  # el archivo no cambia, pero recarga pendiente
        self.assertEqual(self.sis.recargas, 1)

    def test_fallo_del_inhibidor(self):
        self.sis.fallan.add("inhibir_abrir")
        s = self.servicio()
        r = s.perfiles.aplicar("multimedia")
        self.assertTrue(r["fallos"][0].startswith("Inactividad:"))
        self.assertTrue(self.sis.dnd)                      # lo demas se aplico
        self.assertEqual(self.sis.fds_abiertos, [])


class PruebasPersistencia(Base):
    def test_guarda_activo_y_anterior(self):
        s = self.servicio()
        s.perfiles.aplicar("focus")
        s.perfiles.aplicar("multimedia")
        self.assertEqual(self.leer_estado("perfil.json"), {"v": 1, "activo": "multimedia", "anterior": "focus"})

    def test_reaplica_al_arrancar(self):
        self.servicio().perfiles.aplicar("power-saver")
        sis2 = SistemaFalso()
        s2 = self.servicio(sis2)
        s2.iniciar_perfiles()
        self.assertEqual(s2.perfiles.activo, "power-saver")
        self.assertEqual(s2.perfiles.origen, "inicio")
        self.assertEqual(sis2.retenciones, {1: "power-saver"})     # la retencion se vuelve a pedir
        self.assertEqual(self.leer_capa(), "animaciones = no\ndesenfoque = no\n")

    def test_la_instantanea_sobrevive_al_reinicio_del_servicio(self):
        s = self.servicio()
        s.perfiles.aplicar("focus")
        sis2 = SistemaFalso(dnd=True)                              # swaync sigue con no molestar
        s2 = self.servicio(sis2)
        s2.iniciar_perfiles()
        self.assertEqual(s2.perfiles.instantaneas, {"no_molestar": False})
        s2.perfiles.aplicar("balanced")
        self.assertEqual(sis2.dnd_escrituras, [False])

    def test_sin_guardado_arranca_en_balanced_sin_fallos(self):
        s = self.servicio()
        s.iniciar_perfiles()
        self.assertEqual((s.perfiles.activo, s.perfiles.fallos), ("balanced", []))
        self.assertEqual(s.perfiles.origen, "inicio")

    def test_guardado_no_disponible_aplica_balanced_y_anota_el_motivo(self):
        self.servicio().perfiles.aplicar("performance")
        s2 = self.servicio(SistemaFalso(ppd=("balanced", "power-saver")))
        s2.iniciar_perfiles()
        self.assertEqual(s2.perfiles.activo, "balanced")
        self.assertIn("PERFORMANCE", s2.perfiles.fallos[0])
        self.assertIn("no está disponible", s2.perfiles.fallos[0])
        self.assertEqual(self.leer_estado("perfil.json")["activo"], "performance")   # no se pierde la eleccion
        self.assertTrue(any("no aplicado" in e["texto"] for e in s2.actividad))

    def test_guardado_roto_aplica_balanced(self):
        os.makedirs(self.estado)
        with open(os.path.join(self.estado, "perfil.json"), "w") as f:
            f.write("{no json")
        s = self.servicio()
        s.iniciar_perfiles()
        self.assertEqual(s.perfiles.activo, "balanced")
        self.assertIn("guardado", s.perfiles.fallos[0])

    def test_guardado_con_id_desconocido(self):
        os.makedirs(self.estado)
        with open(os.path.join(self.estado, "perfil.json"), "w") as f:
            json.dump({"v": 1, "activo": "turbo", "anterior": None}, f)
        s = self.servicio()
        s.iniciar_perfiles()
        self.assertEqual(s.perfiles.activo, "balanced")
        self.assertTrue(s.perfiles.fallos)

    def test_el_arranque_conserva_el_anterior_guardado(self):
        s = self.servicio()
        s.perfiles.aplicar("focus")
        s.perfiles.aplicar("multimedia")
        s2 = self.servicio(SistemaFalso())
        s2.iniciar_perfiles()
        self.assertEqual((s2.perfiles.activo, s2.perfiles.anterior), ("multimedia", "focus"))


class PruebasAnterior(Base):
    def test_volver_al_anterior(self):
        s = self.servicio()
        s.perfiles.aplicar("focus")
        s.perfiles.aplicar("multimedia")
        r = s.perfiles.aplicar_anterior()
        self.assertTrue(r["ok"])
        self.assertEqual((s.perfiles.activo, s.perfiles.anterior), ("focus", "multimedia"))
        self.assertEqual(self.sis.fds_abiertos, [])               # multimedia deja el inhibidor
        s.perfiles.aplicar_anterior()
        self.assertEqual(s.perfiles.activo, "multimedia")

    def test_sin_anterior(self):
        s = self.servicio()
        s.perfiles.aplicar("focus")                    # primer perfil: no hay anterior
        r = s.perfiles.aplicar_anterior()
        self.assertFalse(r["ok"])
        self.assertIn("anterior", r["error"])

    def test_reaplicar_el_mismo_no_cambia_el_anterior(self):
        s = self.servicio()
        s.perfiles.aplicar("focus")
        s.perfiles.aplicar("balanced")
        s.perfiles.aplicar("balanced")
        self.assertEqual(s.perfiles.anterior, "focus")


class PruebasCustom(Base):
    def test_valido_se_guarda_y_se_aplica(self):
        s = self.servicio()
        r = s.perfiles.guardar_personalizado({"energia": "power-saver", "no_molestar": "si", "modo_noche": "base"})
        self.assertTrue(r["ok"])
        with open(os.path.join(self.config, "jaime0", "perfil-personalizado.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"v": 1, "ajustes": {"energia": "power-saver", "no_molestar": "si",
                                                                  "modo_noche": "base"}})
        self.assertTrue(s.perfiles.aplicar("custom")["ok"])
        self.assertEqual(self.sis.retenciones, {1: "power-saver"})
        self.assertTrue(self.sis.dnd)
        doc = s.perfiles.perfiles_doc()
        custom = doc["perfiles"][-1]
        self.assertEqual(custom["cambios"], ["Energía: ahorro", "No molestar: activado"])
        self.assertEqual(doc["personalizado"]["ajustes"]["energia"], "power-saver")

    def test_invalidos_se_rechazan_sin_escribir(self):
        s = self.servicio()
        for malo in ({"energia": "turbo"}, {"colores": "si"}, {"inhibir_inactividad": "base"},
                     {"no_molestar": True}, {"energia": None}, ["no_molestar"], "x", None):
            r = s.perfiles.guardar_personalizado(malo)
            self.assertFalse(r["ok"], malo)
            self.assertTrue(r["error"])
        self.assertFalse(os.path.exists(os.path.join(self.config, "jaime0", "perfil-personalizado.json")))

    def test_sin_archivo_es_todo_base_sin_error(self):
        s = self.servicio()
        self.assertEqual(s.perfiles.personalizado(), ({}, None))
        r = s.perfiles.aplicar("custom")
        self.assertTrue(r["ok"])
        self.assertEqual(r["fallos"], [])
        self.assertEqual(self.sis.dnd_escrituras, [])

    def test_archivo_invalido_es_todo_base_y_se_informa(self):
        for texto in ('{"v":1,"ajustes":{"energia":"turbo"}}', "{no json", '{"v":2,"ajustes":{}}',
                      '{"v":1,"ajustes":[]}', "[]"):
            escribir_archivo_custom(self.config, texto)
            s = self.servicio()
            aj, error = s.perfiles.personalizado()
            self.assertEqual(aj, {}, texto)
            self.assertTrue(error, texto)
            self.assertEqual(s.perfiles.perfiles_doc()["personalizado"]["error"], error)
            r = s.perfiles.aplicar("custom")
            self.assertTrue(r["ok"])
            self.assertEqual(r["fallos"], [error])
            self.assertEqual(self.sis.dnd_escrituras, [])

    def test_si_custom_esta_activo_se_reaplica_al_guardar(self):
        s = self.servicio()
        s.perfiles.guardar_personalizado({"no_molestar": "si"})
        s.perfiles.aplicar("custom")
        self.assertTrue(self.sis.dnd)
        r = s.perfiles.guardar_personalizado({})            # ya no menciona no molestar: restaura
        self.assertTrue(r["ok"])
        self.assertFalse(self.sis.dnd)

    def test_guardar_custom_no_activo_no_aplica_nada(self):
        s = self.servicio()
        s.perfiles.aplicar("focus")
        s.perfiles.guardar_personalizado({"energia": "performance"})
        self.assertEqual(self.sis.retenciones, {})


class PruebasEventosYEstado(Base):
    def test_evento_con_origen(self):
        s = self.servicio()
        s.perfiles.aplicar("focus", "regla")
        ev = [e for e in s.eventos if e["tipo"] == "perfil"]
        self.assertEqual(len(ev), 1)
        self.assertEqual((ev[0]["texto"], ev[0]["origen"], ev[0]["gravedad"]), ("Perfil: FOCUS", "regla", "INFO"))
        self.assertEqual(s.actividad[-1]["texto"], "Perfil: FOCUS")
        self.assertEqual(s.actividad[-1]["origen"], "regla")
        s.perfiles.aplicar("balanced")
        self.assertEqual([e["origen"] for e in s.eventos if e["tipo"] == "perfil"], ["regla", "usuario"])

    def test_reaplicar_el_mismo_no_repite_evento(self):
        s = self.servicio()
        s.perfiles.aplicar("focus")
        s.perfiles.aplicar("focus")
        self.assertEqual(len([e for e in s.eventos if e["tipo"] == "perfil"]), 1)

    def test_estado_json_con_el_perfil_de_jaime0_y_el_de_ppd(self):
        s = self.servicio()
        s.perfiles.aplicar("performance", "usuario")
        s.perfiles.aplicar("focus", "regla")
        s.perfiles.aplicar("performance", "usuario")
        s.poner_energia("performance")
        self.sis.degradado = "lap-detected"
        s.perfiles.refrescar_degradado()
        s.instante = {"v": 1, "t": int(time.time()), "intervalo": 10}
        s.publicar("ONLINE", [])
        with open(os.path.join(self.rt, "estado.json"), encoding="utf-8") as f:
            perfil = json.load(f)["perfil"]
        self.assertEqual(perfil, {"activo": "performance", "nombre": "PERFORMANCE", "anterior": "focus",
                                  "origen": "usuario", "energia": "performance", "retencion": "performance",
                                  "degradado": "lap-detected", "fallos": []})

    def test_cambiar_de_perfil_reescribe_estado_y_pide_aviso_a_waybar(self):
        s = self.servicio()
        s.instante = {"v": 1, "t": int(time.time()), "intervalo": 10}
        s.publicar("ONLINE", [])
        with mock.patch.object(S.servicio_mod, "avisar_barra") as aviso:
            s.perfiles.aplicar("focus")
            self.assertEqual(aviso.call_count, 1)
            s.perfiles.aplicar("focus")                      # nada cambia: sin aviso
            self.assertEqual(aviso.call_count, 1)
        with open(os.path.join(self.rt, "estado.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["perfil"]["activo"], "focus")

    def test_si_ppd_suelta_la_retencion_por_un_cambio_externo_se_vuelve_a_retener(self):
        s = self.servicio()
        s.perfiles.aplicar("performance")
        self.assertEqual(self.sis.hold_llamadas, ["performance"])
        s.poner_energia("performance")                    # el perfil activo coincide: la retencion vale
        self.assertIsNotNone(s.perfiles.cookie)
        s.poner_energia("balanced")                       # el usuario cambio la energia fuera: ppd soltó la retencion
        self.assertIsNone(s.perfiles.cookie)
        self.assertIsNone(s.perfiles.retencion)
        s.perfiles.aplicar("performance")                 # pedir lo mismo de nuevo debe retener otra vez
        self.assertEqual(self.sis.hold_llamadas, ["performance", "performance"])
        self.assertIsNotNone(s.perfiles.cookie)
        self.assertEqual(list(self.sis.retenciones.values()), ["performance"])

    def test_un_cambio_de_ppd_sin_retencion_nuestra_no_hace_nada(self):
        s = self.servicio()
        s.poner_energia("power-saver")
        self.assertEqual(self.sis.release_llamadas, [])

    def test_cambio_de_energia_de_ppd_no_toca_el_perfil_de_jaime0(self):
        s = self.servicio()
        s.perfiles.aplicar("focus")
        s.poner_energia("power-saver")
        self.assertEqual(s.perfiles.activo, "focus")
        self.assertEqual(s.perfiles.doc_estado(s.energia)["energia"], "power-saver")
        self.assertIn("Perfil de energía: power-saver", [e["texto"] for e in s.actividad])


class ContextoPerfiles:
    def __init__(self, motor):
        self.perfiles = motor


class PruebasApi(Base):
    def pedir(self, s, peticion):
        return json.loads(S.procesar_linea(json.dumps(peticion), ContextoPerfiles(s.perfiles)))

    def test_perfiles(self):
        s = self.servicio()
        r = self.pedir(s, {"orden": "perfiles"})
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["perfiles"]), 6)
        self.assertIn("capacidades", r)
        self.assertEqual(r["personalizado"], {"ajustes": {}, "error": None})
        self.assertIsNone(r["activo"])

    def test_perfil(self):
        s = self.servicio()
        r = self.pedir(s, {"orden": "perfil", "valor": "focus", "origen": "usuario"})
        self.assertEqual((r["ok"], r["activo"], r["fallos"]), (True, "focus", []))
        self.assertEqual(self.pedir(s, {"orden": "perfiles"})["activo"], "focus")

    def test_perfil_acepta_el_nombre_para_mostrar(self):
        s = self.servicio()
        r = self.pedir(s, {"orden": "perfil", "valor": "POWER SAVER"})
        self.assertEqual((r["ok"], r["activo"]), (True, "power-saver"))

    def test_perfil_errores(self):
        s = self.servicio()
        self.assertFalse(self.pedir(s, {"orden": "perfil", "valor": "turbo"})["ok"])
        self.assertFalse(self.pedir(s, {"orden": "perfil"})["ok"])
        self.assertFalse(self.pedir(s, {"orden": "perfil", "valor": 3})["ok"])
        self.assertFalse(self.pedir(s, {"orden": "perfil", "valor": "focus", "origen": "inicio"})["ok"])
        self.assertIsNone(s.perfiles.activo)
        s2 = self.servicio(SistemaFalso(swaync=False))
        r = self.pedir(s2, {"orden": "perfil", "valor": "focus"})
        self.assertFalse(r["ok"])
        self.assertIn("swaync", r["error"])

    def test_perfil_anterior(self):
        s = self.servicio()
        self.assertFalse(self.pedir(s, {"orden": "perfil_anterior"})["ok"])
        self.pedir(s, {"orden": "perfil", "valor": "focus"})
        self.pedir(s, {"orden": "perfil", "valor": "power-saver", "origen": "regla"})
        r = self.pedir(s, {"orden": "perfil_anterior"})
        self.assertEqual((r["ok"], r["activo"]), (True, "focus"))

    def test_personalizado(self):
        s = self.servicio()
        r = self.pedir(s, {"orden": "personalizado", "ajustes": {"no_molestar": "si"}})
        self.assertEqual((r["ok"], r["ajustes"]), (True, {"no_molestar": "si"}))
        self.assertFalse(self.pedir(s, {"orden": "personalizado", "ajustes": {"energia": "x"}})["ok"])
        self.assertFalse(self.pedir(s, {"orden": "personalizado"})["ok"])
        self.assertEqual(self.pedir(s, {"orden": "perfiles"})["personalizado"]["ajustes"], {"no_molestar": "si"})

    def test_la_respuesta_es_una_linea(self):
        s = self.servicio()
        self.assertNotIn("\n", S.procesar_linea('{"orden":"perfiles"}', ContextoPerfiles(s.perfiles)))


class RespuestaFalsa:
    def __init__(self, stdout="", returncode=0):
        self.stdout, self.returncode = stdout, returncode


class PruebasSistemaReal(unittest.TestCase):
    """SistemaReal con un `ejecutar` falso: lo que se lanza y como se interpreta."""

    def sistema(self, respuesta):
        self.llamadas = []

        def ejecutar(orden, **kw):
            self.llamadas.append((orden, kw))
            if isinstance(respuesta, Exception):
                raise respuesta
            return respuesta
        return S.SistemaReal(ejecutar)

    def test_dnd_leer(self):
        self.assertTrue(self.sistema(RespuestaFalsa("true\n")).dnd_leer())
        self.assertEqual(self.llamadas[0][0], ["swaync-client", "--get-dnd", "--skip-wait"])
        self.assertEqual(self.llamadas[0][1]["timeout"], 3)
        self.assertFalse(self.sistema(RespuestaFalsa("false\n")).dnd_leer())
        with self.assertRaises(OSError):
            self.sistema(RespuestaFalsa("", 1)).dnd_leer()
        with self.assertRaises(OSError):
            self.sistema(RespuestaFalsa("rareza")).dnd_leer()
        with self.assertRaises(OSError):
            self.sistema(subprocess.TimeoutExpired("swaync-client", 3)).dnd_leer()

    def test_dnd_poner(self):
        sis = self.sistema(RespuestaFalsa())
        sis.dnd_poner(True)
        sis.dnd_poner(False)
        self.assertEqual([c[0] for c in self.llamadas],
                         [["swaync-client", "--dnd-on", "--skip-wait"], ["swaync-client", "--dnd-off", "--skip-wait"]])
        with self.assertRaises(OSError):
            self.sistema(RespuestaFalsa("", 1)).dnd_poner(True)

    def test_hyprctl_reload(self):
        sis = self.sistema(RespuestaFalsa())
        sis.hypr_recargar()
        self.assertEqual(self.llamadas[0][0], ["hyprctl", "reload"])
        self.assertEqual(self.llamadas[0][1]["timeout"], 5)
        with self.assertRaises(OSError):
            self.sistema(RespuestaFalsa("", 1)).hypr_recargar()

    def test_hyprland_disponible_exige_la_firma_y_hyprctl(self):
        sis = S.SistemaReal(lambda *a, **k: None)
        with mock.patch.dict(os.environ, {"HYPRLAND_INSTANCE_SIGNATURE": "abc"}), \
                mock.patch.object(S.shutil, "which", return_value="/usr/bin/hyprctl"):
            self.assertTrue(sis.hypr_disponible())
        with mock.patch.dict(os.environ, {"HYPRLAND_INSTANCE_SIGNATURE": "", "XDG_RUNTIME_DIR": "/no/existe"}), \
                mock.patch.object(S.shutil, "which", return_value="/usr/bin/hyprctl"):
            self.assertFalse(sis.hypr_disponible())
        with mock.patch.dict(os.environ, {"HYPRLAND_INSTANCE_SIGNATURE": "abc"}), \
                mock.patch.object(S.shutil, "which", return_value=None):
            self.assertFalse(sis.hypr_disponible())

    def socket_de_hyprland(self, firma):
        tmp = tempfile.mkdtemp(prefix="jaime0-hypr-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        os.makedirs(os.path.join(tmp, "hypr", firma))
        with open(os.path.join(tmp, "hypr", firma, ".socket2.sock"), "w") as f:
            f.write("")
        return tmp

    def test_hyprland_disponible_resuelve_la_firma_en_cada_uso(self):
        # El servicio arranca a la vez que Hyprland: su entorno puede traer la firma vacia o la vieja.
        tmp = self.socket_de_hyprland("nueva")
        sis = S.SistemaReal(lambda *a, **k: None)
        for firma in ("", "vieja"):
            entorno = {"XDG_RUNTIME_DIR": tmp, "HYPRLAND_INSTANCE_SIGNATURE": firma}
            with mock.patch.dict(os.environ, entorno), \
                    mock.patch.object(S.shutil, "which", return_value="/usr/bin/hyprctl"):
                self.assertTrue(sis.hypr_disponible(), firma)

    def test_hyprctl_reload_lleva_la_firma_resuelta(self):
        tmp = self.socket_de_hyprland("nueva")
        sis = self.sistema(RespuestaFalsa())
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": tmp, "HYPRLAND_INSTANCE_SIGNATURE": "vieja"}):
            sis.hypr_recargar()
        self.assertEqual(self.llamadas[0][1]["env"]["HYPRLAND_INSTANCE_SIGNATURE"], "nueva")

    def test_modo_noche(self):
        with mock.patch.object(S.perfiles_mod, "programa_hermano", return_value="/bin/modo-noche"):
            self.assertTrue(self.sistema(RespuestaFalsa("encendido\n")).noche_leer())
            self.assertEqual(self.llamadas[0][0], ["/bin/modo-noche", "estado"])
            self.assertFalse(self.sistema(RespuestaFalsa("apagado\n")).noche_leer())
            with self.assertRaises(OSError):
                self.sistema(RespuestaFalsa("???")).noche_leer()
            sis = self.sistema(RespuestaFalsa())
            sis.noche_poner(True)
            sis.noche_poner(False)
            self.assertEqual([c[0][1] for c in self.llamadas], ["encender", "apagar"])
        with mock.patch.object(S.perfiles_mod, "programa_hermano", return_value=None):
            with self.assertRaises(OSError):
                S.SistemaReal().noche_leer()

    def test_swaync_ausente(self):
        with mock.patch.object(S.shutil, "which", return_value=None):
            self.assertFalse(S.SistemaReal().dnd_disponible())

    def test_sin_gi_ppd_y_logind_no_responden(self):
        sis = S.SistemaReal()
        with mock.patch.object(S.perfiles_mod, "_gi", side_effect=ImportError):
            self.assertIsNone(sis.ppd_perfiles())
            self.assertFalse(sis.inhibir_disponible())
            self.assertIsNone(sis.ppd_degradado())
            caps = sis.capacidades()
        self.assertEqual((caps["energia"], caps["ppd"], caps["inhibir_inactividad"]), ([], False, False))


class PruebasCliente(unittest.TestCase):
    DOC = {"ok": True, "v": 1, "activo": "focus", "anterior": "balanced",
           "perfiles": [
               {"id": "balanced", "nombre": "BALANCED", "descripcion": "Todo como lo tienes.", "cambios": [],
                "ajustes": {}, "disponible": True, "motivo": None},
               {"id": "performance", "nombre": "PERFORMANCE", "descripcion": "Rendimiento.",
                "cambios": ["Energía: rendimiento"], "ajustes": {"energia": "performance"},
                "disponible": False, "motivo": "este equipo no ofrece el perfil de energía de alto rendimiento"},
               {"id": "focus", "nombre": "FOCUS", "descripcion": "Menos distracciones.",
                "cambios": ["No molestar: activado"], "ajustes": {"no_molestar": "si"},
                "disponible": True, "motivo": None}],
           "capacidades": {}, "personalizado": {"ajustes": {"energia": "power-saver"}, "error": None}}

    def correr(self, argv, respuesta):
        enviadas = []

        def enviar(peticion):
            enviadas.append(peticion)
            if isinstance(respuesta, Exception):
                raise respuesta
            return respuesta
        salida, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error):
            codigo = P.main(argv, enviar)
        return codigo, salida.getvalue(), error.getvalue(), enviadas

    def test_listar(self):
        codigo, out, err, env = self.correr([], self.DOC)
        self.assertEqual((codigo, err, env), (0, "", [{"orden": "perfiles"}]))
        self.assertIn("Perfil activo: FOCUS", out)
        self.assertIn("* focus", out)
        self.assertIn("- No molestar: activado", out)
        self.assertIn("No disponible: este equipo no ofrece", out)
        self.assertIn("Menos distracciones.", out)

    def test_listar_json(self):
        codigo, out, _err, _env = self.correr(["--json"], self.DOC)
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(out), self.DOC)

    def test_poner_con_id_y_con_nombre_en_mayusculas(self):
        ok = {"ok": True, "activo": "power-saver", "nombre": "POWER SAVER", "fallos": []}
        codigo, out, _err, env = self.correr(["poner", "power-saver"], ok)
        self.assertEqual((codigo, env), (0, [{"orden": "perfil", "valor": "power-saver", "origen": "usuario"}]))
        self.assertIn("POWER SAVER", out)
        codigo, _out, _err, env = self.correr(["poner", "POWER", "SAVER"], ok)     # sin comillas
        self.assertEqual((codigo, env[0]["valor"]), (0, "POWER SAVER"))
        codigo, _out, _err, env = self.correr(["poner", "POWER SAVER"], ok)
        self.assertEqual(env[0]["valor"], "POWER SAVER")

    def test_poner_con_fallos_avisa_por_stderr(self):
        codigo, _out, err, _env = self.correr(["poner", "focus"], {"ok": True, "activo": "focus", "fallos": ["No molestar: x"]})
        self.assertEqual(codigo, 0)
        self.assertIn("No molestar: x", err)

    def test_poner_error_del_servicio(self):
        codigo, out, err, _env = self.correr(["poner", "performance"], {"ok": False, "error": "no está disponible"})
        self.assertEqual((codigo, out), (1, ""))
        self.assertIn("no está disponible", err)

    def test_poner_sin_id(self):
        codigo, _out, err, env = self.correr(["poner"], self.DOC)
        self.assertEqual((codigo, env), (1, []))
        self.assertIn("falta el perfil", err)

    def test_anterior(self):
        codigo, out, _err, env = self.correr(["anterior"], {"ok": True, "activo": "balanced", "nombre": "BALANCED",
                                                            "fallos": []})
        self.assertEqual((codigo, env), (0, [{"orden": "perfil_anterior", "origen": "usuario"}]))
        self.assertIn("BALANCED", out)

    def test_personalizado_guarda(self):
        codigo, out, _err, env = self.correr(["personalizado", "energia=power-saver", "no_molestar=si"],
                                             {"ok": True, "ajustes": {}, "fallos": []})
        self.assertEqual(codigo, 0)
        self.assertEqual(env, [{"orden": "personalizado", "ajustes": {"energia": "power-saver", "no_molestar": "si"}}])
        self.assertIn("guardado", out)

    def test_personalizado_error_y_sintaxis(self):
        codigo, _out, err, _env = self.correr(["personalizado", "energia=turbo"], {"ok": False, "error": "valor no válido"})
        self.assertEqual(codigo, 1)
        self.assertIn("valor no válido", err)
        codigo, _out, err, env = self.correr(["personalizado", "energia"], {"ok": True})
        self.assertEqual((codigo, env), (1, []))
        self.assertIn("clave=valor", err)

    def test_personalizado_sin_argumentos_lo_muestra(self):
        codigo, out, _err, _env = self.correr(["personalizado"], self.DOC)
        self.assertEqual(codigo, 0)
        self.assertIn("energia = power-saver", out)
        codigo, out, _err, _env = self.correr(["personalizado", "--json"], self.DOC)
        self.assertEqual(json.loads(out)["ajustes"], {"energia": "power-saver"})

    def test_sin_servicio(self):
        for argv in ([], ["poner", "focus"], ["anterior"], ["personalizado", "energia=balanced"], ["personalizado"]):
            codigo, out, err, _env = self.correr(argv, OSError("no hay socket"))
            self.assertEqual((codigo, out), (1, ""), argv)
            self.assertIn("el servicio de ZYRON no está en marcha: systemctl --user start jaime0-servicio", err)

    def test_respuesta_rota_cuenta_como_sin_servicio(self):
        codigo, _out, err, _env = self.correr([], ValueError("json"))
        self.assertEqual(codigo, 1)
        self.assertIn("no está en marcha", err)

    def test_orden_desconocida(self):
        codigo, _out, err, env = self.correr(["bailar"], self.DOC)
        self.assertEqual((codigo, env), (1, []))
        self.assertIn("desconocida", err)

    def test_pedir_socket_sin_servicio_lanza_oserror(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"JAIME0_RUNTIME": d}):
            with self.assertRaises(OSError):
                P.pedir_socket({"orden": "perfiles"}, timeout=1)


class PruebasBarra(Base):
    def estado_json(self, perfil, **cambios):
        e = {"v": 1, "t": int(time.time()), "estado": "ONLINE", "motivos": [], "perfil": perfil,
             "privacidad": {"estado": "SECURE", "detalles": []}, "actividad": [],
             "servicio": {"pid": 1, "desde": 0, "intervalo": 10}}
        e.update(cambios)
        with open(os.path.join(self.rt, "estado.json"), "w", encoding="utf-8") as f:
            json.dump(e, f)

    def perfil(self, activo, nombre, energia="balanced", retencion=None):
        return {"activo": activo, "nombre": nombre, "anterior": None, "origen": "usuario", "energia": energia,
                "retencion": retencion, "degradado": None, "fallos": []}

    def test_iconos_de_los_seis_perfiles(self):
        esperado = {"balanced": "\U000f0f85", "performance": "\U000f04c5", "power-saver": "\U000f0f86",
                    "focus": "\U000f0ef0", "multimedia": "\U000f075a", "custom": "\U000f0493"}
        self.assertEqual(H.ICONOS_PERFIL, esperado)
        for pid, icono in esperado.items():
            self.estado_json(self.perfil(pid, pid.upper()))
            self.assertEqual(H.barra()["text"], icono + " ", pid)

    def test_tooltip_con_perfil_y_energia(self):
        self.estado_json(self.perfil("focus", "FOCUS", "balanced"))
        r = H.barra()
        self.assertEqual(r["class"], "online")
        self.assertIn("Perfil: FOCUS · energía balanced", r["tooltip"].splitlines())
        self.assertNotIn("retenido", r["tooltip"])

    def test_tooltip_con_retencion(self):
        self.estado_json(self.perfil("performance", "PERFORMANCE", "performance", "performance"))
        self.assertIn("Perfil: PERFORMANCE · energía performance (retenido)", H.barra()["tooltip"])

    def test_tooltip_nombre_con_espacio_y_energia_desconocida(self):
        self.estado_json(self.perfil("power-saver", "POWER SAVER", None))
        self.assertIn("Perfil: POWER SAVER · energía N/D", H.barra()["tooltip"])

    def test_alerta_conserva_el_icono_del_perfil(self):
        self.estado_json(self.perfil("multimedia", "MULTIMEDIA"), estado="WARNING")
        self.assertEqual(H.barra()["text"], "\U000f075a \U000f0026 ")

    def test_perfil_aun_sin_aplicar(self):
        self.estado_json({"activo": None, "nombre": None, "anterior": None, "origen": None, "energia": None,
                          "retencion": None, "degradado": None, "fallos": []})
        r = H.barra()
        self.assertEqual(r["text"], "\U000f0f85 ")
        self.assertIn("Perfil: desconocido", r["tooltip"])

    def test_servicio_parado_sigue_como_antes(self):
        with mock.patch.object(H, "perfil_actual_sin_servicio", return_value="performance"):
            r = H.barra()
        self.assertEqual((r["class"], r["text"]), ("parado", "\U000f04c5 "))
        self.assertIn("Perfil: performance", r["tooltip"])

    def test_resumen_muestra_el_perfil(self):
        inst = {"estado": "ONLINE", "uptime": 5, "cpu": {}, "ram": None, "disco": [], "bateria": None, "alertas": 0}
        txt = H.resumen(inst, {"estado": "ONLINE", "perfil": self.perfil("focus", "FOCUS", "balanced")})
        self.assertIn("Perfil: FOCUS · energía balanced", txt)


if __name__ == "__main__":
    unittest.main()
