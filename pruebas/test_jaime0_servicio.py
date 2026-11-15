#!/usr/bin/env python3
"""Pruebas de jaime0-servicio y jaime0-salud con una raiz falsa (JAIME0_RAIZ) y un
directorio de ejecucion temporal (JAIME0_RUNTIME). No necesitan gi, D-Bus ni sockets.

    python3 -m unittest discover -s pruebas -v
"""
import contextlib
import copy
import datetime
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import shutil
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


S = cargar("jaime0_servicio_pruebas", "jaime0-servicio")
H = cargar("jaime0_salud_pruebas", "jaime0-salud")


class Base(unittest.TestCase):
    """Crea una raiz falsa y un directorio de ejecucion por prueba."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jaime0-serv-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.raiz = os.path.join(self.tmp, "raiz")
        self.rt = os.path.join(self.tmp, "rt")
        self.estado = os.path.join(self.tmp, "estado")
        os.makedirs(self.raiz)
        os.makedirs(self.rt)
        p = mock.patch.dict(os.environ, {"JAIME0_RAIZ": self.raiz, "JAIME0_RUNTIME": self.rt,
                                         "JAIME0_ESTADO": self.estado})
        p.start()
        self.addCleanup(p.stop)

    def escribir(self, rel, texto):
        p = os.path.join(self.raiz, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        return p


def leer_json(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def instante_base(**cambios):
    inst = {"v": 1, "t": int(time.time()), "intervalo": 10,
            "cpu": {"total": 10.0, "nucleos": [10.0], "mhz": None, "temp": 50.0},
            "ram": {"usada": 4000, "total": 16000, "swap": 0, "swap_total": 8000, "presion": 0.0},
            "temp": [], "gpu": {"nvidia": None, "temp": None},
            "disco": [{"punto": "/", "usado": 100.0, "total": 500.0, "lectura": None, "escritura": None}],
            "bateria": None, "cargador": None, "uptime": 100, "procesos": None, "fallidas": None,
            "estado": "ONLINE", "alertas": 0}
    inst.update(cambios)
    return inst


class PruebasMedicion(Base):
    def test_ruta_antepone_la_raiz_falsa(self):
        self.assertEqual(S.ruta("proc", "stat"), os.path.join(self.raiz, "proc", "stat"))
        self.assertEqual(os.path.normpath(S.ruta("/proc/stat")), os.path.join(self.raiz, "proc", "stat"))

    def test_directorio_de_ejecucion_se_crea(self):
        d = os.path.join(self.tmp, "nuevo", "jaime0")
        with mock.patch.dict(os.environ, {"JAIME0_RUNTIME": d}):
            self.assertEqual(S.directorio_ejecucion(), d)
        self.assertTrue(os.path.isdir(d))

    def test_cpu_por_deltas(self):
        a = S.parsear_cpu_stat("cpu  100 0 100 700 100 0 0 0 0 0\ncpu0 50 0 50 350 50 0 0 0 0 0\n"
                               "cpu1 50 0 50 350 50 0 0 0 0 0\nintr 5\n")
        b = S.parsear_cpu_stat("cpu  200 0 200 750 150 0 0 0 0 0\ncpu0 100 0 100 375 75 0 0 0 0 0\n"
                               "cpu1 100 0 100 375 75 0 0 0 0 0\n")
        # total: +100 user +100 sys, +50 idle +50 iowait => 200 activos de 300
        self.assertAlmostEqual(S.porcentaje_cpu(a[0], b[0]), 66.7)
        self.assertEqual(sorted(a[1]), [0, 1])
        self.assertAlmostEqual(S.porcentaje_cpu(a[1][0], b[1][0]), 66.7)
        self.assertIsNone(S.porcentaje_cpu(a[0], a[0]))

    def test_muestreador_con_raiz_falsa(self):
        self.escribir("proc/stat", "cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 100 0 100 800 0 0 0 0 0 0\n")
        self.escribir("sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", "2600000\n")
        m = S.Muestreador()
        m.base()
        self.escribir("proc/stat", "cpu  150 0 150 900 0 0 0 0 0 0\ncpu0 150 0 150 900 0 0 0 0 0 0\n")
        med = m.muestrear()
        self.assertEqual(med["cpu"]["total"], 50.0)
        self.assertEqual(med["cpu"]["nucleos"], [50.0])
        self.assertEqual(med["cpu"]["mhz"], [2600])
        self.assertIsNone(med["cpu"]["temp"])
        self.assertIsNone(med["bateria"])
        self.assertIsNone(med["cargador"])
        self.assertIsNone(med["gpu"]["nvidia"])
        self.assertIsNone(med["gpu"]["temp"])

    def test_frecuencia_inexistente_es_null(self):
        self.escribir("proc/stat", "cpu  1 0 1 8 0 0 0 0 0 0\ncpu0 1 0 1 8 0 0 0 0 0 0\n")
        m = S.Muestreador()
        m.base()
        self.assertIsNone(m.muestrear()["cpu"]["mhz"])

    def test_ram_y_presion(self):
        self.escribir("proc/meminfo", "MemTotal: 16384000 kB\nMemFree: 1000 kB\nMemAvailable: 12288000 kB\n"
                                      "SwapTotal: 8192000 kB\nSwapFree: 7168000 kB\n")
        self.escribir("proc/pressure/memory", "some avg10=1.50 avg60=0.50 avg300=0.10 total=123\n"
                                              "full avg10=0.20 avg60=0.00 avg300=0.00 total=5\n")
        r = S.leer_ram()
        self.assertEqual(r["total"], 16000)
        self.assertEqual(r["usada"], 4000)
        self.assertEqual(r["swap"], 1000)
        self.assertEqual(r["swap_total"], 8000)
        self.assertEqual(r["presion"], 1.5)

    def test_ram_sin_presion_ni_meminfo(self):
        self.assertIsNone(S.leer_ram())
        self.escribir("proc/meminfo", "MemTotal: 1024 kB\nMemAvailable: 512 kB\n")
        self.assertIsNone(S.leer_ram()["presion"])

    def test_temperaturas_y_cpu_temp_coretemp(self):
        self.escribir("sys/class/hwmon/hwmon0/name", "coretemp\n")
        self.escribir("sys/class/hwmon/hwmon0/temp1_input", "48000\n")
        self.escribir("sys/class/hwmon/hwmon0/temp1_label", "Package id 0\n")
        self.escribir("sys/class/hwmon/hwmon0/temp2_input", "52000\n")
        self.escribir("sys/class/hwmon/hwmon0/temp2_label", "Core 0\n")
        self.escribir("sys/class/hwmon/hwmon1/name", "nvme\n")
        self.escribir("sys/class/hwmon/hwmon1/temp1_input", "36900\n")   # sin etiqueta: temp1
        t = S.leer_temperaturas()
        self.assertIn({"id": "coretemp/Package id 0", "c": 48.0}, t)
        self.assertIn({"id": "coretemp/Core 0", "c": 52.0}, t)
        self.assertIn({"id": "nvme/temp1", "c": 36.9}, t)
        self.assertEqual(S.temperatura_cpu(t), 48.0)

    def test_cpu_temp_alternativas_y_ausencia(self):
        self.assertIsNone(S.temperatura_cpu([]))
        self.assertIsNone(S.temperatura_cpu([{"id": "nvme/Composite", "c": 40.0}]))
        self.assertEqual(S.temperatura_cpu([{"id": "k10temp/Tctl", "c": 61.0}, {"id": "nvme/x", "c": 70.0}]), 61.0)
        self.assertEqual(S.temperatura_cpu([{"id": "coretemp/Core 0", "c": 50.0},
                                            {"id": "coretemp/Core 1", "c": 57.0}]), 57.0)
        self.assertEqual(S.leer_temperaturas(), [])

    def test_bateria_descargando_con_estimacion(self):
        b = "sys/class/power_supply/BAT0/"
        self.escribir(b + "type", "Battery\n")
        self.escribir(b + "status", "Discharging\n")
        self.escribir(b + "capacity", "83\n")
        self.escribir(b + "power_now", "10000000\n")        # 10 W
        self.escribir(b + "energy_now", "40000000\n")       # 40 Wh -> 240 min
        self.escribir(b + "energy_full", "45500000\n")
        self.escribir(b + "energy_full_design", "50000000\n")
        r = S.leer_bateria()
        self.assertEqual(r, {"nivel": 83, "estado": "descargando", "vatios": 10.0,
                             "minutos_estimados": 240, "salud": 91.0, "estimado": True})

    def test_bateria_con_corriente_y_tension(self):
        b = "sys/class/power_supply/BAT0/"
        self.escribir(b + "type", "Battery\n")
        self.escribir(b + "status", "Discharging\n")
        self.escribir(b + "capacity", "50\n")
        self.escribir(b + "current_now", "1000000\n")       # 1 A
        self.escribir(b + "voltage_now", "11000000\n")      # 11 V -> 11 W
        self.escribir(b + "charge_now", "2000000\n")        # 2 Ah -> 120 min
        self.escribir(b + "charge_full", "4000000\n")
        self.escribir(b + "charge_full_design", "5000000\n")
        r = S.leer_bateria()
        self.assertEqual(r["vatios"], 11.0)
        self.assertEqual(r["minutos_estimados"], 120)
        self.assertEqual(r["salud"], 80.0)

    def test_bateria_cargando_sin_estimacion(self):
        b = "sys/class/power_supply/BAT0/"
        self.escribir(b + "type", "Battery\n")
        self.escribir(b + "status", "Charging\n")
        self.escribir(b + "capacity", "40\n")
        self.escribir(b + "power_now", "20000000\n")
        self.escribir(b + "energy_now", "20000000\n")
        r = S.leer_bateria()
        self.assertEqual(r["estado"], "cargando")
        self.assertEqual(r["vatios"], 20.0)
        self.assertIsNone(r["minutos_estimados"])
        self.assertIsNone(r["salud"])

    def test_estados_de_bateria_traducidos(self):
        b = "sys/class/power_supply/BAT0/"
        self.escribir(b + "type", "Battery\n")
        self.escribir(b + "capacity", "100\n")
        for original, esperado in (("Full", "llena"), ("Not charging", "sin-cargar"), ("Unknown", "desconocido")):
            self.escribir(b + "status", original + "\n")
            self.assertEqual(S.leer_bateria()["estado"], esperado)

    def test_sin_bateria_es_null_y_cargador(self):
        self.assertIsNone(S.leer_bateria())
        self.assertIsNone(S.leer_cargador())
        self.escribir("sys/class/power_supply/AC/type", "Mains\n")
        self.escribir("sys/class/power_supply/AC/online", "0\n")
        self.assertFalse(S.leer_cargador())
        self.escribir("sys/class/power_supply/AC/online", "1\n")
        self.assertTrue(S.leer_cargador())

    def _gpu(self, runtime=None, driver=True, vendor="0x10de", clase="0x030000"):
        d = "sys/bus/pci/devices/0000-01-00.0/"
        self.escribir(d + "vendor", vendor + "\n")
        self.escribir(d + "class", clase + "\n")
        if runtime:
            self.escribir(d + "power/runtime_status", runtime + "\n")
        if driver:
            os.makedirs(os.path.join(self.raiz, "sys/bus/pci/devices/0000-01-00.0/driver"), exist_ok=True)

    def test_nvidia_suspendida_activa_sin_driver_y_ausente(self):
        self.assertIsNone(S.estado_nvidia())
        self._gpu(runtime="suspended")
        self.assertEqual(S.estado_nvidia(), "suspendida")
        self._gpu(runtime="active")
        self.assertEqual(S.estado_nvidia(), "activa")
        shutil.rmtree(os.path.join(self.raiz, "sys"))
        self._gpu(runtime="active", driver=False)
        self.assertEqual(S.estado_nvidia(), "sin-driver")

    def test_nvidia_ignora_otros_fabricantes_y_clases(self):
        self._gpu(runtime="active", vendor="0x8086")
        self.assertIsNone(S.estado_nvidia())
        shutil.rmtree(os.path.join(self.raiz, "sys"))
        self._gpu(runtime="active", clase="0x040300")     # audio de la NVIDIA, no la GPU
        self.assertIsNone(S.estado_nvidia())
        shutil.rmtree(os.path.join(self.raiz, "sys"))
        self._gpu(runtime="suspended", clase="0x030200")  # 3D controller
        self.assertEqual(S.estado_nvidia(), "suspendida")

    def test_disco_en_gib_y_diskstats(self):
        v = mock.Mock(f_blocks=1000, f_bfree=400, f_frsize=1024 ** 3 // 10)
        with mock.patch.object(S.os, "statvfs", create=True, return_value=v):
            u = S.uso_disco("/")
        self.assertEqual(u, {"punto": "/", "usado": 60.0, "total": 100.0})
        d = S.parsear_diskstats("   8       0 sda 10 0 2000 5 20 0 4000 9 0 0 0\n"
                                "   8       1 sda1 5 0 1000 2 10 0 3000 4 0 0 0\n")
        self.assertEqual(d["sda"], (2000, 4000))
        # 2000 sectores en 1 s = 1,024 MB/s
        self.assertEqual(S.io_disco((0, 0), (2000, 4000), 1.0), (1.02, 2.05))
        self.assertEqual(S.io_disco(None, (1, 1), 1.0), (None, None))

    def test_procesos_top_y_desaparecidos(self):
        def proc(pid, nombre, ut, st, rss=None):
            self.escribir(f"proc/{pid}/stat", f"{pid} ({nombre} x) S 1 1 1 0 -1 0 0 0 0 0 {ut} {st} 0 0 20 0 1 0 1 1 1\n")
            if rss:
                self.escribir(f"proc/{pid}/status", f"Name: {nombre}\nVmRSS:\t{rss} kB\n")
        proc(10, "alfa", 100, 0, 2048)
        proc(11, "beta", 0, 0)
        proc(12, "gamma", 5, 5)
        antes = S.leer_procesos()
        self.assertEqual(antes[10], (100, "alfa x"))
        proc(10, "alfa", 150, 50, 2048)    # +100 tics
        proc(11, "beta", 0, 1)
        shutil.rmtree(os.path.join(self.raiz, "proc", "12"))    # desaparece
        proc(13, "nuevo", 500, 0)                                # sin muestra previa
        self.escribir("proc/basura", "no es un pid")
        with mock.patch.object(S, "tics_por_segundo", return_value=100):
            top = S.procesos_top(antes, S.leer_procesos(), 1.0)
        self.assertEqual([p["pid"] for p in top], [10, 11])
        self.assertEqual(top[0], {"pid": 10, "nombre": "alfa x", "cpu": 100.0, "ram": 2})
        self.assertIsNone(top[1]["ram"])

    def test_uptime(self):
        self.assertIsNone(S.leer_uptime())
        self.escribir("proc/uptime", "12345.67 9999.00\n")
        self.assertEqual(S.leer_uptime(), 12345)


class PruebasEvaluar(unittest.TestCase):
    def comp(self, inst, estado, gravedad=None, componente=None):
        e, motivos = S.evaluar(inst, S.UMBRALES)
        self.assertEqual(e, estado, motivos)
        if componente:
            self.assertIn((gravedad, componente), [(m["gravedad"], m["componente"]) for m in motivos])
        return motivos

    def test_online(self):
        self.assertEqual(S.evaluar(instante_base(), S.UMBRALES), ("ONLINE", []))

    def test_datos_ausentes_no_alertan(self):
        i = instante_base(cpu={"total": None, "nucleos": None, "mhz": None, "temp": None},
                          ram=None, disco=None, bateria=None)
        self.assertEqual(S.evaluar(i), ("ONLINE", []))

    def test_temperatura(self):
        i = instante_base()
        i["cpu"]["temp"] = 85.0
        self.comp(i, "WARNING", "WARNING", "cpu")
        i["cpu"]["temp"] = 95.0
        m = self.comp(i, "CRITICAL", "CRITICAL", "cpu")
        self.assertEqual(len(m), 1)
        self.assertIn("95", m[0]["texto"])

    def test_disco(self):
        i = instante_base(disco=[{"punto": "/home", "usado": 91.0, "total": 100.0}])
        m = self.comp(i, "WARNING", "WARNING", "disco")
        self.assertEqual(m[0]["texto"], "Disco /home al 91 %")
        i["disco"][0]["usado"] = 95.0
        self.comp(i, "CRITICAL", "CRITICAL", "disco")

    def test_bateria_solo_si_descarga(self):
        bat = {"nivel": 15, "estado": "descargando", "vatios": 5.0, "minutos_estimados": 10, "salud": None,
               "estimado": True}
        self.comp(instante_base(bateria=bat), "WARNING", "WARNING", "bateria")
        self.comp(instante_base(bateria=dict(bat, nivel=5)), "CRITICAL", "CRITICAL", "bateria")
        self.comp(instante_base(bateria=dict(bat, nivel=3, estado="cargando")), "ONLINE")
        self.comp(instante_base(bateria=dict(bat, nivel=16)), "ONLINE")

    def test_ram_disponible_critica(self):
        i = instante_base(ram={"usada": 15300, "total": 16000, "swap": 0, "swap_total": 0, "presion": None})
        self.comp(i, "CRITICAL", "CRITICAL", "ram")
        i["ram"]["usada"] = 15200        # justo 5 % disponible: no es critico
        self.comp(i, "ONLINE")

    def test_swap_y_presion(self):
        i = instante_base()
        i["ram"]["swap"] = 4001
        self.comp(i, "WARNING", "WARNING", "swap")
        i["ram"]["swap"] = 4000          # no supera el 50 %
        self.comp(i, "ONLINE")
        i["ram"].update(swap=100, swap_total=0)   # sin swap, no se evalua
        self.comp(i, "ONLINE")
        i["ram"]["presion"] = 20.5
        self.comp(i, "WARNING", "WARNING", "ram")
        i["ram"]["presion"] = 20.0
        self.comp(i, "ONLINE")

    def test_unidades_fallidas(self):
        m = self.comp(instante_base(fallidas=["ufw.service"]), "WARNING", "WARNING", "systemd")
        self.assertIn("ufw.service", m[0]["texto"])
        self.comp(instante_base(fallidas=[]), "ONLINE")
        self.comp(instante_base(fallidas=None), "ONLINE")

    def test_lo_critico_domina_y_se_acumulan_motivos(self):
        i = instante_base(fallidas=["x.service"])
        i["cpu"]["temp"] = 96.0
        e, m = S.evaluar(i)
        self.assertEqual(e, "CRITICAL")
        self.assertEqual(len(m), 2)

    def test_evaluar_no_modifica_el_instante(self):
        i = instante_base(fallidas=["x"])
        copia = copy.deepcopy(i)
        S.evaluar(i)
        self.assertEqual(i, copia)

    def test_motivos_con_el_formato_pedido(self):
        i = instante_base()
        i["cpu"]["temp"] = 90.0
        for m in S.evaluar(i)[1]:
            self.assertEqual(sorted(m), ["componente", "gravedad", "texto"])


class PruebasPrivacidad(Base):
    def test_sin_ufw_conf_no_disponible(self):
        r = S.resumen_privacidad(True)
        self.assertEqual(r["estado"], "UNAVAILABLE")
        self.assertTrue(r["detalles"])

    def test_desactivado_es_warning(self):
        self.escribir("etc/ufw/ufw.conf", "# comentario\nENABLED=no\nLOGLEVEL=low\n")
        self.assertEqual(S.resumen_privacidad(True)["estado"], "WARNING")

    def test_activado_con_servicio_activo_es_secure(self):
        self.escribir("etc/ufw/ufw.conf", "ENABLED=yes\n")
        self.escribir("etc/default/ufw", 'DEFAULT_INPUT_POLICY="DROP"\n')
        r = S.resumen_privacidad(True)
        self.assertEqual(r["estado"], "SECURE")
        self.assertEqual(r["detalles"], ["Cortafuegos activo: entrante denegado por defecto"])

    def test_secure_sin_politica_conocida_no_la_afirma(self):
        self.escribir("etc/ufw/ufw.conf", "ENABLED=yes\n")
        self.assertEqual(S.resumen_privacidad(True)["detalles"], ["Cortafuegos activo"])

    def test_activado_pero_servicio_parado_o_desconocido_es_warning(self):
        self.escribir("etc/ufw/ufw.conf", "ENABLED=yes\n")
        self.assertEqual(S.resumen_privacidad(False)["estado"], "WARNING")
        self.assertEqual(S.resumen_privacidad(None)["estado"], "WARNING")


class PruebasInstanteYServicio(Base):
    def test_escritura_atomica_con_v1(self):
        destino = os.path.join(self.rt, "instante.json")
        S.escribir_json(destino, {"v": 1, "x": None})
        self.assertEqual(leer_json(destino), {"v": 1, "x": None})
        self.assertEqual(os.listdir(self.rt), ["instante.json"])      # sin temporales
        S.escribir_json(destino, {"v": 1, "x": 2})
        self.assertEqual(leer_json(destino)["x"], 2)

    def test_ciclo_de_muestreo_escribe_ambos_archivos(self):
        self.escribir("proc/stat", "cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 100 0 100 800 0 0 0 0 0 0\n")
        sv = S.Servicio(directorio=self.rt)
        sv.muestreador.base()
        self.escribir("proc/stat", "cpu  150 0 150 900 0 0 0 0 0 0\ncpu0 150 0 150 900 0 0 0 0 0 0\n")
        sv.muestrear()
        inst = leer_json(os.path.join(self.rt, "instante.json"))
        est = leer_json(os.path.join(self.rt, "estado.json"))
        self.assertEqual(inst["v"], 1)
        self.assertEqual(inst["cpu"]["total"], 50.0)
        self.assertIsNone(inst["ram"])
        self.assertIsNone(inst["bateria"])
        self.assertEqual(inst["estado"], "ONLINE")
        self.assertEqual(inst["alertas"], 0)
        self.assertEqual(est["v"], 1)
        self.assertEqual(est["estado"], "ONLINE")
        self.assertEqual(est["servicio"]["pid"], os.getpid())
        self.assertEqual(est["perfil"], {"activo": None, "nombre": None, "anterior": None, "origen": None,
                                         "energia": None, "retencion": None, "degradado": None, "fallos": []})
        self.assertEqual(est["privacidad"]["estado"], "UNAVAILABLE")
        self.assertEqual(est["actividad"][0]["texto"], "Servicio iniciado")
        self.assertEqual(len(sv.anillo), 1)
        # Fase 3: una clave por metrica del historico (la especificacion fija este conjunto)
        self.assertEqual(set(sv.anillo[0]), {"t"} | set(S.METRICAS))

    def test_actividad_registra_cambios_de_estado_y_perfil(self):
        sv = S.Servicio(directorio=self.rt)
        sv.instante = instante_base()
        sv.publicar("ONLINE", [])
        sv.publicar("WARNING", [{"gravedad": "WARNING", "componente": "cpu", "texto": "x"}])
        sv.poner_energia("performance")
        textos = [e["texto"] for e in sv.actividad]
        self.assertIn("Estado: ONLINE → WARNING", textos)
        self.assertIn("Perfil de energía: performance", textos)
        self.assertLessEqual(sv.actividad.maxlen, 20)

    def test_modo_rapido(self):
        sv = S.Servicio(directorio=self.rt)
        self.assertEqual(sv.intervalo_actual(), 10)
        intervalo, hasta = sv.rapido()
        self.assertEqual(intervalo, 2)
        self.assertGreater(hasta, time.time() + 10)
        self.assertEqual(sv.intervalo_actual(), 2)

    def test_medir_devuelve_instante_completo(self):
        self.escribir("proc/stat", "cpu  1 0 1 8 0 0 0 0 0 0\ncpu0 1 0 1 8 0 0 0 0 0 0\n")
        with mock.patch.object(S.time, "sleep"):
            inst = S.medir()
        self.assertEqual(inst["v"], 1)
        for clave in ("cpu", "ram", "temp", "gpu", "disco", "bateria", "cargador", "uptime", "procesos",
                      "estado", "alertas"):
            self.assertIn(clave, inst)
        json.dumps(inst)


class ContextoFalso:
    def __init__(self, estado=None, instante=None):
        self._e, self._i, self.llamadas = estado, instante, 0

    def rapido(self):
        self.llamadas += 1
        return 2, 1763123471

    def estado_doc(self):
        return self._e

    def instante_doc(self):
        return self._i


class PruebasApi(unittest.TestCase):
    def pedir(self, linea, ctx=None):
        return json.loads(S.procesar_linea(linea, ctx or ContextoFalso()))

    def test_rapido(self):
        ctx = ContextoFalso()
        r = self.pedir('{"orden":"rapido"}', ctx)
        self.assertEqual(r, {"ok": True, "intervalo": 2, "hasta": 1763123471})
        self.assertEqual(ctx.llamadas, 1)

    def test_estado_e_instante(self):
        ctx = ContextoFalso(estado={"v": 1, "estado": "ONLINE"}, instante={"v": 1, "t": 5})
        self.assertEqual(self.pedir('{"orden":"estado"}', ctx), {"v": 1, "estado": "ONLINE"})
        self.assertEqual(self.pedir('{"orden":"instante"}', ctx), {"v": 1, "t": 5})

    def test_sin_datos_todavia(self):
        self.assertFalse(self.pedir('{"orden":"estado"}')["ok"])

    def test_orden_desconocida(self):
        self.assertEqual(self.pedir('{"orden":"borrar"}'), {"ok": False, "error": "orden desconocida"})
        self.assertEqual(self.pedir('{}'), {"ok": False, "error": "orden desconocida"})

    def test_json_roto_y_no_objeto(self):
        self.assertFalse(self.pedir("{esto no es json")["ok"])
        self.assertFalse(self.pedir("")["ok"])
        self.assertFalse(self.pedir("[1,2]")["ok"])

    def test_fallo_interno_no_cae(self):
        class Roto(ContextoFalso):
            def rapido(self):
                raise RuntimeError("fallo")
        with mock.patch.object(S, "registrar"):
            r = self.pedir('{"orden":"rapido"}', Roto())
        self.assertFalse(r["ok"])

    def test_con_el_servicio_real(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        sv = S.Servicio(directorio=d, estado=os.path.join(d, "estado"))
        self.assertFalse(self.pedir('{"orden":"instante"}', sv)["ok"])
        self.assertTrue(self.pedir('{"orden":"rapido"}', sv)["ok"])


def PERFIL_ESTADO(activo, nombre, energia, retencion=None):
    return {"activo": activo, "nombre": nombre, "anterior": None, "origen": "usuario", "energia": energia,
            "retencion": retencion, "degradado": None, "fallos": []}


class PruebasSalud(Base):
    def estado_json(self, **cambios):
        e = {"v": 1, "t": int(time.time()), "estado": "ONLINE", "motivos": [],
             "perfil": {"activo": "balanced", "nombre": "BALANCED", "anterior": None, "origen": "inicio",
                        "energia": "balanced", "retencion": None, "degradado": None, "fallos": []},
             "privacidad": {"estado": "SECURE", "detalles": []}, "actividad": [],
             "servicio": {"pid": 1, "desde": 0, "intervalo": 10}}
        e.update(cambios)
        self.escribir_rt("estado.json", e)

    def escribir_rt(self, nombre, doc):
        with open(os.path.join(self.rt, nombre), "w", encoding="utf-8") as f:
            json.dump(doc, f)

    def test_barra_online(self):
        self.estado_json()
        r = H.barra()
        self.assertEqual(r["class"], "online")
        self.assertEqual(r["text"], "\U000f0f85 ")
        self.assertEqual(r["tooltip"].splitlines()[0], "Jaime0 · SYSTEM ONLINE")
        self.assertIn("Perfil: BALANCED · energía balanced", r["tooltip"])
        self.assertTrue(r["tooltip"].endswith("Clic: Control Center"))

    def test_barra_warning_con_icono_de_alerta_y_motivos_maximo_4(self):
        motivos = [{"gravedad": "WARNING", "componente": "x", "texto": f"motivo {i}"} for i in range(6)]
        self.estado_json(estado="WARNING", motivos=motivos,
                         perfil=PERFIL_ESTADO("performance", "PERFORMANCE", "performance"))
        r = H.barra()
        self.assertEqual(r["class"], "warning")
        self.assertEqual(r["text"], "\U000f04c5 \U000f0026 ")
        self.assertIn("motivo 3", r["tooltip"])
        self.assertNotIn("motivo 4", r["tooltip"])

    def test_barra_critical_y_perfil_desconocido(self):
        self.estado_json(estado="CRITICAL", perfil={"activo": None, "energia": None})
        r = H.barra()
        self.assertEqual(r["class"], "critical")
        self.assertTrue(r["text"].startswith("\U000f0f85"))
        self.assertIn("SYSTEM CRITICAL", r["tooltip"])

    def test_barra_power_saver(self):
        self.estado_json(perfil=PERFIL_ESTADO("power-saver", "POWER SAVER", "power-saver"))
        self.assertEqual(H.barra()["text"], "\U000f0f86 ")

    def test_barra_parado_con_estado_viejo(self):
        self.estado_json(t=int(time.time()) - 120)
        with mock.patch.object(H, "perfil_actual_sin_servicio", return_value="power-saver"):
            r = H.barra()
        self.assertEqual(r["class"], "parado")
        self.assertEqual(r["text"], "\U000f0f86 ")
        self.assertTrue(r["tooltip"].startswith("Servicio de Jaime0 parado"))

    def test_barra_parado_sin_estado_y_sin_powerprofilesctl(self):
        with mock.patch.object(H.subprocess, "run", side_effect=FileNotFoundError):
            r = H.barra()
        self.assertEqual(r["class"], "parado")
        self.assertEqual(r["text"], "\U000f0f85 ")
        json.dumps(r)

    def test_barra_estado_roto_cuenta_como_parado(self):
        with open(os.path.join(self.rt, "estado.json"), "w") as f:
            f.write("{no json")
        with mock.patch.object(H, "perfil_actual_sin_servicio", return_value=None):
            self.assertEqual(H.barra()["class"], "parado")

    def test_obtener_usa_archivos_frescos(self):
        self.estado_json()
        self.escribir_rt("instante.json", instante_base())
        i, e, parado = H.obtener()
        self.assertFalse(parado)
        self.assertEqual(e["estado"], "ONLINE")
        txt = H.resumen(i, e, parado)
        self.assertIn("SYSTEM ONLINE", txt)
        self.assertIn("N/D", txt)       # batería ausente
        self.assertNotIn("Servicio parado", txt)

    def test_obtener_servicio_parado_hace_medicion_puntual(self):
        self.escribir_rt("instante.json", instante_base(t=int(time.time()) - 600))
        puntual = instante_base(bateria={"nivel": 80, "estado": "descargando", "vatios": 10.0,
                                         "minutos_estimados": 125, "salud": None, "estimado": True})
        with mock.patch.object(H, "medicion_puntual", return_value=puntual):
            i, e, parado = H.obtener()
        self.assertTrue(parado)
        self.assertIsNone(e)
        txt = H.resumen(i, e, parado)
        self.assertIn("Servicio parado: medición puntual", txt)
        self.assertIn("(estimado)", txt)
        self.assertIn("2 h 5 min", txt)

    def test_salida_con_error_si_no_hay_nada(self):
        with mock.patch.object(H, "medicion_puntual", return_value=None), \
                mock.patch.object(H.sys, "stderr"):
            self.assertEqual(H.main(["ahora"]), 1)


# ---------------------------------------------------------------------------
# Fase 3: historico, incidencias, eventos, umbrales, SMART, GPU y API nueva
# ---------------------------------------------------------------------------

BASE = 1_700_000_100 - (1_700_000_100 % 900)      # instante alineado a 15 minutos (y a 60 s)


def muestra(t, **v):
    m = {"t": t}
    for k in S.METRICAS:
        m[k] = v.get(k)
    return m


def agg(t, **v):
    return S.combinar([S.pseudo_agregado(muestra(t, **v))], t)


class PruebasHistorico(Base):
    def setUp(self):
        super().setUp()
        self.ahora = BASE + 5000
        self.eventos = S.collections.deque(maxlen=200)

    def nuevo(self, sub="salud"):
        carpeta = os.path.join(self.tmp, sub)

        def fn():
            os.makedirs(carpeta, exist_ok=True)
            return carpeta
        h = S.Historico(fn, reloj=lambda: self.ahora, eventos=self.eventos)
        h.dir = carpeta
        return h

    def archivo_dia(self, h, t):
        return os.path.join(h._carpeta(), time.strftime("%Y-%m-%d", time.localtime(t)) + ".jsonl")

    # -- agregacion ------------------------------------------------------------
    def test_agregado_de_minuto_min_media_max_con_null(self):
        h = self.nuevo()
        h.anadir(muestra(BASE, cpu=10.0, ram=50.0), 10)
        h.anadir(muestra(BASE + 10, cpu=20.0), 10)
        h.anadir(muestra(BASE + 20, cpu=None), 10)
        self.assertEqual(h.minutos, [], "el minuto en curso aun no se cierra")
        h.anadir(muestra(BASE + 60, cpu=40.0), 10)          # nuevo minuto: cierra el anterior
        a = h.minutos[0]
        self.assertEqual((a["v"], a["t"], a["n"]), (1, BASE, 3))
        self.assertEqual(a["cpu"], [10.0, 15.0, 20.0])      # el null no cuenta
        self.assertEqual(a["ram"], [50.0, 50.0, 50.0])
        self.assertIsNone(a["temp"], "todo null -> null")
        json.dumps(a)

    def test_agregado_de_15_minutos(self):
        h = self.nuevo()
        for i in range(17 * 6):                              # 17 minutos a 10 s
            h.anadir(muestra(BASE + i * 10, cpu=float(i // 6)), 10)
        self.assertEqual(len(h.cuartos), 1)
        q = h.cuartos[0]
        self.assertEqual((q["t"], q["n"]), (BASE, 90))
        self.assertEqual(q["cpu"], [0.0, 7.0, 14.0])
        self.assertIsNone(q["temp"])
        self.assertNotIn("eventos", q)

    def test_el_minuto_lleva_sus_eventos(self):
        h = self.nuevo()
        self.eventos.append(S.nuevo_evento(BASE + 5, "pico_cpu", "WARNING", "x", None))
        self.eventos.append(S.nuevo_evento(BASE + 100, "perfil", "INFO", "y", None))
        h.anadir(muestra(BASE, cpu=1.0), 10)
        h.anadir(muestra(BASE + 60, cpu=1.0), 10)
        self.assertEqual([e["tipo"] for e in h.minutos[0]["eventos"]], ["pico_cpu"])

    # -- disco -----------------------------------------------------------------
    def llenar(self, h, desde, hasta, paso=10):
        for t in range(desde, hasta, paso):
            h.anadir(muestra(t, cpu=float(t % 60)), paso)

    def test_volcado_y_lectura_con_linea_rota(self):
        h = self.nuevo()
        self.llenar(h, BASE, BASE + 120)                     # minutos 0 y 1; el 0 queda cerrado
        self.assertTrue(h.volcar())
        archivo = self.archivo_dia(h, BASE)
        self.assertEqual([d["t"] for d in S.leer_jsonl(archivo)], [BASE])
        with open(archivo, "a", encoding="utf-8") as f:
            f.write('{"v":1,"t":1,"cpu":[1,2')               # escritura cortada, sin salto de linea
        self.llenar(h, BASE + 120, BASE + 180)               # cierra el minuto 1
        h.volcar()
        self.assertEqual([d["t"] for d in S.leer_jsonl(archivo)], [BASE, BASE + 60],
                         "la linea rota se ignora y la nueva no se pega a ella")
        with open(archivo, encoding="utf-8") as f:
            self.assertEqual(len(f.read().splitlines()), 3)

    def test_leer_jsonl_tolera_basura(self):
        p = os.path.join(self.tmp, "x.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write('{"a":1}\n\nno json\n[1,2]\n{"b":2}\n')
        self.assertEqual(S.leer_jsonl(p), [{"a": 1}, {"b": 2}])
        self.assertEqual(S.leer_jsonl(os.path.join(self.tmp, "no-existe")), [])

    def test_retencion_borra_archivos_diarios_de_mas_de_dos_dias(self):
        h = self.nuevo()
        carpeta = h._carpeta()
        hoy = datetime.date.fromtimestamp(self.ahora)
        for dias in (0, 1, 2, 3, 10):
            with open(os.path.join(carpeta, (hoy - datetime.timedelta(days=dias)).isoformat() + ".jsonl"), "w") as f:
                f.write("")
        for otro in ("historico.jsonl", "notas.txt"):
            with open(os.path.join(carpeta, otro), "w") as f:
                f.write("")
        h.volcar()
        esperado = sorted([(hoy - datetime.timedelta(days=d)).isoformat() + ".jsonl" for d in (0, 1, 2)]
                          + ["historico.jsonl", "notas.txt"])
        self.assertEqual(sorted(os.listdir(carpeta)), esperado)

    def test_historico_se_recorta_por_dias_y_una_vez_al_dia(self):
        h = self.nuevo()
        h.dias = 90
        archivo = os.path.join(h._carpeta(), "historico.jsonl")
        viejo, reciente = self.ahora - 100 * 86400, self.ahora - 10 * 86400
        S.anexar_jsonl(archivo, [agg(viejo, cpu=1.0), agg(reciente, cpu=2.0),
                                 {"v": 1, "hueco": [viejo, viejo + 60]},
                                 {"v": 1, "hueco": [reciente, reciente + 60]}])
        with open(archivo, "a", encoding="utf-8") as f:
            f.write("linea rota sin cierre")
        h.volcar()
        docs = S.leer_jsonl(archivo)
        self.assertEqual([d.get("t") or d["hueco"][0] for d in docs], [reciente, reciente])
        with open(archivo, encoding="utf-8") as f:
            self.assertNotIn("rota", f.read())
        # el mismo dia no se vuelve a reescribir (aunque haya algo viejo)
        S.anexar_jsonl(archivo, [agg(viejo, cpu=9.0)])
        h.volcar()
        self.assertIn(viejo, [d.get("t") for d in S.leer_jsonl(archivo)])
        self.ahora += 86400 + 1
        h.volcar()
        self.assertNotIn(viejo, [d.get("t") for d in S.leer_jsonl(archivo)])

    def test_historial_dias_configurable(self):
        h = self.nuevo()
        h.dias = 7
        archivo = os.path.join(h._carpeta(), "historico.jsonl")
        S.anexar_jsonl(archivo, [agg(self.ahora - 8 * 86400), agg(self.ahora - 6 * 86400)])
        h.volcar()
        self.assertEqual(len(S.leer_jsonl(archivo)), 1)

    # -- huecos ----------------------------------------------------------------
    def test_hueco_por_salto_de_tiempo(self):
        h = self.nuevo()
        h.anadir(muestra(BASE), 10)
        h.anadir(muestra(BASE + 10), 10)
        h.anadir(muestra(BASE + 40), 10)                     # justo 3 x 10: no es hueco
        self.assertEqual(h.huecos, [])
        h.anadir(muestra(BASE + 71), 10)                     # 31 s > 30 s
        self.assertEqual(h.huecos, [[BASE + 40, BASE + 71]])
        self.assertIn({"v": 1, "hueco": [BASE + 40, BASE + 71]}, h.pend)
        h.anadir(muestra(BASE + 81), 10)
        self.assertEqual(len(h.huecos), 1)

    def test_cambio_de_intervalo_no_es_hueco(self):
        h = self.nuevo()
        h.anadir(muestra(BASE), 10)
        h.anadir(muestra(BASE + 8), 2)                       # la interfaz pidio muestreo rapido
        self.assertEqual(h.huecos, [])

    def test_hueco_se_escribe_en_el_dia_y_en_el_historico(self):
        h = self.nuevo()
        h.anadir(muestra(BASE), 10)
        h.anadir(muestra(BASE + 500), 10)
        h.volcar()
        esperado = {"v": 1, "hueco": [BASE, BASE + 500]}
        self.assertIn(esperado, S.leer_jsonl(self.archivo_dia(h, BASE + 500)))
        self.assertIn(esperado, S.leer_jsonl(os.path.join(h._carpeta(), "historico.jsonl")))

    def test_hueco_al_arrancar_con_datos_viejos(self):
        h = self.nuevo()
        viejo = agg(self.ahora - 3600 - (self.ahora - 3600) % 60, cpu=5.0)
        S.anexar_jsonl(self.archivo_dia(h, viejo["t"]), [viejo])
        h.cargar()
        self.assertEqual(h.huecos, [[viejo["t"] + 60, self.ahora]])
        self.assertEqual(len(h.minutos), 1)
        self.assertIn({"v": 1, "hueco": [viejo["t"] + 60, self.ahora]}, h.pend)

    def test_arranque_con_datos_recientes_no_abre_hueco(self):
        h = self.nuevo("b")
        reciente = agg(self.ahora - 60 - self.ahora % 60, cpu=5.0)       # termina a menos de 60 s
        S.anexar_jsonl(self.archivo_dia(h, reciente["t"]), [reciente])
        h.cargar()
        self.assertEqual(h.huecos, [])

    def test_parada_a_mitad_de_minuto_cuenta_desde_la_ultima_muestra(self):
        # Caso visto en la VM: el servicio para a los 5 s de un minuto y vuelve 45 s despues.
        # Con "fin del minuto" no saldria hueco; con la ultima muestra real (u), si.
        h = self.nuevo("d")
        t0 = self.ahora - 50 - (self.ahora - 50) % 60
        parcial = agg(t0, cpu=5.0)
        parcial["u"] = self.ahora - 45
        S.anexar_jsonl(self.archivo_dia(h, t0), [parcial])
        h.cargar()
        self.assertEqual(h.huecos, [[self.ahora - 45, self.ahora]])

    def test_cerrar_un_minuto_guarda_la_ultima_muestra(self):
        h = self.nuevo("e")
        t0 = self.ahora - self.ahora % 60
        for dt in (0, 10, 20):
            h.anadir({"t": t0 + dt, **{k: None for k in S.METRICAS}, "cpu": 1.0}, 10)
        h.volcar(cerrar_parcial=True)
        self.assertEqual(h.minutos[-1]["u"], t0 + 20)

    def test_arranque_sin_datos_no_inventa_huecos(self):
        h = self.nuevo("c")
        h.cargar()
        self.assertEqual((h.huecos, h.minutos, h.cuartos), ([], [], []))

    def test_reanudar_tras_suspender_cierra_el_hueco_una_sola_vez(self):
        h = self.nuevo()
        h.anadir(muestra(BASE), 10)
        h.cerrar_hueco(BASE + 5)                             # reanudacion inmediata: sin hueco
        self.assertEqual(h.huecos, [])
        h.cerrar_hueco(BASE + 600)
        self.assertEqual(h.huecos, [[BASE, BASE + 600]])
        h.anadir(muestra(BASE + 605), 10)                    # la siguiente muestra no lo duplica
        self.assertEqual(len(h.huecos), 1)

    def test_cargar_fusiona_minutos_repetidos_y_trae_huecos(self):
        h = self.nuevo()
        t = self.ahora - 120 - self.ahora % 60
        a, b = agg(t, cpu=10.0), agg(t, cpu=30.0)
        S.anexar_jsonl(self.archivo_dia(h, t), [a, b, {"v": 1, "hueco": [t - 500, t - 400]}])
        S.anexar_jsonl(os.path.join(h._carpeta(), "historico.jsonl"), [{"v": 1, "hueco": [t - 500, t - 400]}])
        h.cargar()
        self.assertEqual(len(h.minutos), 1)
        self.assertEqual((h.minutos[0]["n"], h.minutos[0]["cpu"]), (2, [10.0, 20.0, 30.0]))
        self.assertIn([t - 500, t - 400], h.huecos)
        self.assertEqual(sum(1 for x in h.huecos if x == [t - 500, t - 400]), 1, "sin duplicados")

    def test_parar_cierra_el_minuto_en_curso_y_lo_escribe(self):
        h = self.nuevo()
        h.anadir(muestra(BASE, cpu=10.0), 10)
        h.anadir(muestra(BASE + 10, cpu=20.0), 10)
        h.volcar(cerrar_parcial=True)
        docs = S.leer_jsonl(self.archivo_dia(h, BASE))
        self.assertEqual((docs[0]["t"], docs[0]["n"], docs[0]["cpu"]), (BASE, 2, [10.0, 15.0, 20.0]))
        self.assertEqual(len(S.leer_jsonl(os.path.join(h._carpeta(), "historico.jsonl"))), 1)

    # -- reduccion y disponibilidad ----------------------------------------------
    def test_reduccion_a_720_puntos(self):
        pts = [agg(BASE + i * 60, cpu=float(i)) for i in range(1440)]
        red, res = S.reducir(pts, 60)
        self.assertLessEqual(len(red), 720)
        self.assertEqual(res, 120)
        self.assertEqual((red[0]["t"], red[0]["n"], red[0]["cpu"]), (BASE, 2, [0.0, 0.5, 1.0]))
        self.assertEqual(red[-1]["cpu"], [1438.0, 1438.5, 1439.0])
        mismos, res = S.reducir(pts[:720], 60)
        self.assertEqual((len(mismos), res), (720, 60))

    def test_reduccion_con_huecos_sigue_dentro_del_maximo(self):
        pts = [agg(BASE + i * 60, cpu=1.0) for i in range(400)]
        pts += [agg(BASE + 5000 * 60 + i * 60, cpu=2.0) for i in range(400)]
        red, _ = S.reducir(pts, 60)
        self.assertLessEqual(len(red), 720)
        self.assertEqual(red[0]["cpu"][0], 1.0)
        self.assertEqual(red[-1]["cpu"][2], 2.0)

    def anillo(self, desde, hasta, paso=1, **v):
        return S.collections.deque(muestra(t, **v) for t in range(desde, hasta + 1, paso))

    def test_disponibilidad_de_cada_rango(self):
        h, a = self.nuevo(), self.ahora
        vacio = {"5m": False, "1h": False, "24h": False, "historia": False}
        self.assertEqual(h.disponibilidad(S.collections.deque(), a), vacio)
        self.assertEqual(h.disponibilidad(self.anillo(a - 59, a), a)["5m"], False)
        self.assertEqual(h.disponibilidad(self.anillo(a - 60, a), a)["5m"], True)
        self.assertEqual(h.disponibilidad(self.anillo(a - 299, a), a)["1h"], False)
        d = h.disponibilidad(self.anillo(a - 300, a), a)
        self.assertEqual((d["5m"], d["1h"]), (True, True))
        h.minutos = [agg(a - 60 * (i + 1)) for i in range(59)]
        self.assertFalse(h.disponibilidad(S.collections.deque(), a)["24h"])
        h.minutos.append(agg(a - 60 * 60))
        self.assertTrue(h.disponibilidad(S.collections.deque(), a)["24h"])
        h.minutos = [agg(a - 86400 - 60 * i) for i in range(100)]          # viejos: no cuentan
        self.assertFalse(h.disponibilidad(S.collections.deque(), a)["24h"])
        h.cuartos = [agg(BASE), agg(BASE + 86399)]
        self.assertFalse(h.disponibilidad(S.collections.deque(), a)["historia"])
        h.cuartos = [agg(BASE), agg(BASE + 86400)]
        self.assertTrue(h.disponibilidad(S.collections.deque(), a)["historia"])

    # -- series ------------------------------------------------------------------
    def test_serie_5m_y_1h_con_solo_med(self):
        h, a = self.nuevo(), self.ahora
        anillo = self.anillo(a - 399, a, cpu=25.0, temp=50.0)
        r = h.serie("5m", anillo, a)
        self.assertTrue(r["ok"])
        self.assertEqual((r["v"], r["rango"], r["resolucion"], r["desde"], r["hasta"]), (1, "5m", 1, a - 300, a))
        self.assertEqual(len(r["t"]), 301)
        self.assertEqual(r["metricas"]["cpu"], {"med": [25.0] * 301})
        self.assertEqual(r["metricas"]["gpu_temp"], {"med": [None] * 301})
        self.assertEqual(set(r["metricas"]), set(S.METRICAS))
        self.assertEqual(r["disponible"], {"5m": True, "1h": True, "24h": False, "historia": False})
        self.assertEqual(r["huecos"], [])
        json.dumps(r)
        r1 = h.serie("1h", anillo, a)
        self.assertEqual((len(r1["t"]), r1["resolucion"]), (400, 1))

    def test_serie_1h_se_reduce_a_720(self):
        h, a = self.nuevo(), self.ahora
        r = h.serie("1h", self.anillo(a - 3599, a, cpu=10.0), a)
        self.assertLessEqual(len(r["t"]), 720)
        self.assertEqual(r["resolucion"], 5)
        self.assertEqual(len(r["metricas"]["cpu"]["med"]), len(r["t"]))

    def test_serie_24h_incluye_el_minuto_en_curso(self):
        h = self.nuevo()
        minuto = self.ahora - self.ahora % 60
        h.minutos = [agg(minuto - 60 * (100 - i), cpu=float(i)) for i in range(100)]
        h.anadir(muestra(minuto + 5, cpu=77.0), 10)
        r = h.serie("24h", S.collections.deque(), minuto + 20)
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["rango"], r["resolucion"]), ("24h", 60))
        self.assertEqual(len(r["t"]), 101)
        self.assertEqual(r["t"][-1], minuto)
        self.assertEqual(sorted(r["metricas"]["cpu"]), ["max", "med", "min"])
        self.assertEqual((r["metricas"]["cpu"]["min"][-1], r["metricas"]["cpu"]["max"][-1]), (77.0, 77.0))
        self.assertEqual(r["metricas"]["cpu"]["med"][0], 0.0)
        self.assertTrue(r["disponible"]["24h"])

    def test_serie_historia(self):
        h = self.nuevo()
        h.cuartos = [agg(BASE + 900 * i, cpu=float(i)) for i in range(100)]
        r = h.serie("historia", S.collections.deque(), self.ahora)
        self.assertTrue(r["ok"])
        self.assertEqual((r["resolucion"], r["desde"], len(r["t"])), (900, BASE, 100))
        h.cuartos = [agg(BASE + 900 * i, cpu=float(i % 50)) for i in range(8640)]      # 90 dias
        r = h.serie("historia", S.collections.deque(), BASE + 900 * 8640)
        self.assertLessEqual(len(r["t"]), 720)
        self.assertEqual(r["resolucion"], 10800)

    def test_serie_sin_datos_suficientes_y_rango_invalido(self):
        h, a = self.nuevo(), self.ahora
        r = h.serie("5m", self.anillo(a - 30, a), a)
        self.assertEqual((r["ok"], r["error"]), (False, "sin datos suficientes"))
        self.assertEqual(set(r["disponible"]), {"5m", "1h", "24h", "historia"})
        for rango in ("24h", "historia", "1h"):
            self.assertFalse(h.serie(rango, S.collections.deque(), a)["ok"])
        r = h.serie("7d", S.collections.deque(), a)
        self.assertFalse(r["ok"])
        self.assertFalse(h.serie(None, S.collections.deque(), a)["ok"])

    def test_serie_incluye_huecos_recortados_y_eventos_del_rango(self):
        h, a = self.nuevo(), self.ahora
        h.huecos = [[a - 400, a - 200], [a - 1000, a - 900], [a - 100000, a - 99000]]
        self.eventos.append(S.nuevo_evento(a - 100, "pico_cpu", "WARNING", "dentro", {"nombre": "x", "cpu": 90.0}))
        self.eventos.append(S.nuevo_evento(a - 5000, "perfil", "INFO", "fuera", None))
        r = h.serie("5m", self.anillo(a - 399, a), a)
        self.assertEqual(r["huecos"], [[a - 300, a - 200]])
        self.assertEqual([e["texto"] for e in r["eventos"]], ["dentro"])
        self.assertEqual(r["eventos"][0]["proceso"], {"nombre": "x", "cpu": 90.0})


def inst_temp(temp, **cambios):
    i = instante_base(**cambios)
    i["cpu"]["temp"] = temp
    return i


class PruebasIncidencias(unittest.TestCase):
    def correr(self, inc, temps, t0=1000, u=None):
        lineas = []
        for i, tmp in enumerate(temps):
            lineas += inc.observar(inst_temp(tmp), u or S.UMBRALES, t0 + i * 10)
        return lineas

    def test_una_muestra_suelta_no_abre_incidencia(self):
        inc = S.Incidencias()
        self.assertEqual(self.correr(inc, [90, 50, 50, 50, 90, 50, 90, 90, 50, 90]), [])
        self.assertEqual(inc.abiertas(), [])

    def test_abre_a_la_tercera_muestra_con_el_formato_pedido(self):
        inc = S.Incidencias()
        self.assertEqual(self.correr(inc, [90, 90]), [])
        lineas = self.correr(inc, [90], t0=1020)
        self.assertEqual(len(lineas), 1)
        l = lineas[0]
        self.assertEqual(sorted(l), ["componente", "descripcion", "diagnostico", "gravedad", "recomendacion",
                                     "t", "v", "valor"])
        self.assertEqual((l["v"], l["t"], l["gravedad"], l["componente"], l["valor"]), (1, 1020, "WARNING", "cpu-temp", 90))
        self.assertIn("90", l["descripcion"])
        self.assertIn("Temperatura sostenida por encima del umbral", l["diagnostico"])
        self.assertIn("TOP PROCESSES", l["recomendacion"])
        self.assertIn("rejillas de ventilación", l["recomendacion"])
        self.assertEqual(inc.abiertas(), [{"componente": "cpu-temp", "gravedad": "WARNING"}])
        self.assertEqual(self.correr(inc, [90, 91, 92]), [], "mientras sigue abierta no se repite")

    def test_escala_de_warning_a_critical(self):
        inc = S.Incidencias()
        lineas = self.correr(inc, [90, 90, 90, 96, 96, 90, 96, 96, 96])
        self.assertEqual([l["gravedad"] for l in lineas], ["WARNING", "CRITICAL"])
        self.assertEqual(inc.abiertas(), [{"componente": "cpu-temp", "gravedad": "CRITICAL"}])

    def test_critical_directo_y_mezcla_abre_como_warning(self):
        self.assertEqual([l["gravedad"] for l in self.correr(S.Incidencias(), [96, 96, 96])], ["CRITICAL"])
        self.assertEqual([l["gravedad"] for l in self.correr(S.Incidencias(), [90, 96, 96])], ["WARNING"])

    def test_cierra_con_normal_a_la_tercera_muestra_y_sin_falsos_cierres(self):
        inc = S.Incidencias()
        self.assertEqual(len(self.correr(inc, [90, 90, 90])), 1)
        self.assertEqual(self.correr(inc, [50, 50, 90, 50, 50]), [], "una muestra mala reinicia la cuenta")
        cierre = self.correr(inc, [50])
        self.assertEqual(len(cierre), 1)
        self.assertEqual((cierre[0]["gravedad"], cierre[0]["componente"]), ("NORMAL", "cpu-temp"))
        self.assertTrue(cierre[0]["descripcion"].startswith("Recuperado: "))
        self.assertEqual(inc.abiertas(), [])
        self.assertEqual(self.correr(inc, [50, 50, 50]), [])

    def test_baja_de_critical_a_warning_sin_linea_nueva(self):
        inc = S.Incidencias()
        self.assertEqual(len(self.correr(inc, [96, 96, 96, 90, 90, 90])), 1)
        self.assertEqual(inc.abiertas(), [{"componente": "cpu-temp", "gravedad": "WARNING"}])

    def test_sin_dato_no_abre_ni_cierra(self):
        inc = S.Incidencias()
        self.correr(inc, [90, 90, 90])
        self.assertEqual(self.correr(inc, [None] * 6), [])
        self.assertEqual(len(inc.abiertas()), 1)
        self.assertEqual(self.correr(S.Incidencias(), [None] * 6), [])

    def test_systemd_y_smart_con_una_sola_muestra(self):
        inc = S.Incidencias()
        a = inc.observar(instante_base(fallidas=["ufw.service"]), S.UMBRALES, 10)
        self.assertEqual([(l["componente"], l["gravedad"]) for l in a], [("systemd", "WARNING")])
        self.assertIn("ufw.service", a[0]["descripcion"])
        self.assertIn("systemctl --failed", a[0]["recomendacion"])
        c = inc.observar(instante_base(fallidas=[]), S.UMBRALES, 20)
        self.assertEqual([(l["componente"], l["gravedad"]) for l in c], [("systemd", "NORMAL")])
        malo = {"disco": "KINGSTON X", "tipo": "nvme", "estado": "FALLO", "temperatura": 40.0, "horas": 5,
                "avisos": ["Espacio de reserva por debajo del umbral"]}
        s = inc.observar(instante_base(smart=[malo]), S.UMBRALES, 30)
        self.assertEqual([(l["componente"], l["gravedad"], l["valor"]) for l in s],
                         [("smart", "CRITICAL", ["KINGSTON X"])])
        self.assertIn("KINGSTON X", s[0]["descripcion"])
        self.assertIn("copia de seguridad", s[0]["recomendacion"])
        self.assertEqual(inc.observar(instante_base(smart=[dict(malo, estado="OK")]), S.UMBRALES, 40)[0]["gravedad"],
                         "NORMAL")

    def test_el_resto_de_componentes(self):
        casos = [
            ({"disco": [{"punto": "/", "usado": 96.0, "total": 100.0}]}, "disco", "CRITICAL"),
            ({"disco": [{"punto": "/", "usado": 90.0, "total": 100.0}]}, "disco", "WARNING"),
            ({"bateria": {"nivel": 10, "estado": "descargando"}}, "bateria", "WARNING"),
            ({"bateria": {"nivel": 4, "estado": "descargando"}}, "bateria", "CRITICAL"),
            ({"ram": {"usada": 15500, "total": 16000, "swap": 0, "swap_total": 0, "presion": None}}, "ram", "CRITICAL"),
            ({"ram": {"usada": 100, "total": 16000, "swap": 5000, "swap_total": 8000, "presion": None}}, "swap", "WARNING"),
            ({"ram": {"usada": 100, "total": 16000, "swap": 0, "swap_total": 0, "presion": 25.0}}, "presion", "WARNING"),
            ({"gpu": {"nvidia": "activa", "temp": 97.0}}, "gpu", "CRITICAL"),
        ]
        for cambios, comp, grav in casos:
            inc = S.Incidencias()
            lineas = []
            for i in range(3):
                lineas += inc.observar(instante_base(**cambios), S.UMBRALES, i)
            self.assertEqual([(l["componente"], l["gravedad"]) for l in lineas], [(comp, grav)], cambios)
            self.assertTrue(lineas[0]["descripcion"] and lineas[0]["diagnostico"] and lineas[0]["recomendacion"])

    def test_bateria_cargando_no_es_incidencia(self):
        inc = S.Incidencias()
        for i in range(5):
            self.assertEqual(inc.observar(instante_base(bateria={"nivel": 3, "estado": "cargando"}), S.UMBRALES, i), [])

    def test_umbrales_propios(self):
        u = dict(S.UMBRALES, temp_aviso=70.0)
        self.assertEqual(len(self.correr(S.Incidencias(), [75, 75, 75], u=u)), 1)
        self.assertEqual(self.correr(S.Incidencias(), [75, 75, 75]), [])


class PruebasServicioFase3(Base):
    def servicio(self, **k):
        return S.Servicio(directorio=self.rt, estado=self.estado, **k)

    def poner_temperatura(self, grados):
        self.escribir("sys/class/hwmon/hwmon0/name", "coretemp\n")
        self.escribir("sys/class/hwmon/hwmon0/temp1_input", f"{int(grados * 1000)}\n")
        self.escribir("sys/class/hwmon/hwmon0/temp1_label", "Package id 0\n")

    def test_muestrear_abre_la_incidencia_a_la_tercera_muestra(self):
        self.poner_temperatura(96)
        sv = self.servicio()
        sv.muestreador.base()
        for _ in range(2):
            sv.muestrear()
        self.assertFalse(os.path.exists(os.path.join(self.estado, "incidencias.jsonl")))
        sv.muestrear()
        docs = S.leer_jsonl(os.path.join(self.estado, "incidencias.jsonl"))
        self.assertEqual([(d["componente"], d["gravedad"]) for d in docs], [("cpu-temp", "CRITICAL")])
        est = sv.estado_doc()
        self.assertEqual(est["incidencias_abiertas"], [{"componente": "cpu-temp", "gravedad": "CRITICAL"}])
        self.assertEqual(set(est["disponible"]), {"5m", "1h", "24h", "historia"})
        self.assertEqual(len(sv.anillo), 3)
        self.assertEqual(oct(os.stat(self.estado).st_mode & 0o777) if os.name == "posix" else "0o700", "0o700")

    def test_reiniciar_el_servicio_no_duplica_una_incidencia_abierta(self):
        self.poner_temperatura(96)
        sv = self.servicio()
        sv.muestreador.base()
        for _ in range(3):
            sv.muestrear()
        archivo = os.path.join(self.estado, "incidencias.jsonl")
        self.assertEqual(len(S.leer_jsonl(archivo)), 1)
        # Servicio nuevo (reinicio) con la condicion aun presente: recupera la incidencia
        # abierta y no escribe otra linea igual.
        sv2 = self.servicio()
        self.assertEqual(sv2.incidencias_estado.abiertas(), [{"componente": "cpu-temp", "gravedad": "CRITICAL"}])
        sv2.muestreador.base()
        for _ in range(3):
            sv2.muestrear()
        self.assertEqual(len(S.leer_jsonl(archivo)), 1)

    def test_incidencias_se_recortan_a_500_lineas(self):
        sv = self.servicio()
        lineas = [{"v": 1, "t": i, "gravedad": "WARNING", "componente": "disco", "descripcion": "d",
                   "diagnostico": "x", "recomendacion": "r", "valor": 90.0} for i in range(600)]
        sv.anotar_incidencias(lineas[:300])
        sv.anotar_incidencias(lineas[300:])
        docs = S.leer_jsonl(os.path.join(self.estado, "incidencias.jsonl"))
        self.assertEqual((len(docs), docs[0]["t"], docs[-1]["t"]), (500, 100, 599))
        self.assertEqual(len(sv.incidencias(50)), 50)
        self.assertEqual(sv.incidencias(50)[0]["t"], 599, "las mas recientes primero")

    def test_el_anillo_solo_guarda_una_hora(self):
        sv = self.servicio()
        for t in (1000, 2000, 5000):
            S.anillo_agregar(sv.anillo, instante_base(t=t))
        self.assertEqual([m["t"] for m in sv.anillo], [2000, 5000])
        m = sv.anillo[0]
        self.assertEqual(sorted(m), sorted(["t"] + list(S.METRICAS)))

    def test_muestra_desde_instante(self):
        i = instante_base(
            cpu={"total": 12.5, "nucleos": None, "mhz": None, "temp": 48.0},
            ram={"usada": 4000, "total": 16000, "swap": 2000, "swap_total": 8000, "presion": 1.5},
            gpu={"nvidia": "activa", "temp": 55.0},
            disco=[{"punto": "/home", "usado": 1.0, "total": 2.0},
                   {"punto": "/", "usado": 100.0, "total": 400.0, "lectura": 1.5, "escritura": 0.2}],
            bateria={"nivel": 80, "estado": "descargando", "vatios": 9.5})
        m = S.muestra_desde_instante(i)
        self.assertEqual((m["cpu"], m["ram"], m["swap"], m["presion"], m["temp"], m["gpu_temp"]),
                         (12.5, 25.0, 25.0, 1.5, 48.0, 55.0))
        self.assertEqual((m["bateria"], m["vatios"], m["lectura"], m["escritura"], m["disco"]),
                         (80, 9.5, 1.5, 0.2, 25.0))
        vacio = S.muestra_desde_instante(instante_base(cpu=None, ram=None, disco=None, bateria=None, gpu=None))
        self.assertEqual([k for k in S.METRICAS if vacio[k] is not None], [])

    def test_eventos_de_perfil_estado_y_cargador(self):
        sv = self.servicio()
        self.assertEqual(sv.eventos.maxlen, 200)
        sv.instante = instante_base(cargador=False)
        sv.publicar("ONLINE", [])
        sv.instante = instante_base(cargador=True)
        sv.publicar("CRITICAL", [{"gravedad": "CRITICAL", "componente": "cpu", "texto": "x"}])
        sv.poner_energia("power-saver")
        tipos = [(e["tipo"], e["gravedad"]) for e in sv.eventos]
        self.assertIn(("estado", "CRITICAL"), tipos)
        self.assertIn(("cargador", "INFO"), tipos)
        self.assertIn(("perfil", "INFO"), tipos)
        for e in sv.eventos:
            self.assertEqual(sorted(e), ["gravedad", "proceso", "t", "texto", "tipo"])

    def test_pico_de_cpu_con_el_proceso_en_el_servicio(self):
        sv = self.servicio()
        sv.detector.cpu_altas = 1                                         # ya hubo una muestra alta
        self.escribir("proc/stat", "cpu  95 0 0 105 0 0 0 0 0 0\ncpu0 95 0 0 105 0 0 0 0 0 0\n")
        self.escribir("proc/4/stat", "4 (compilador) S 1 1 1 0 -1 0 0 0 0 0 0 0 0 0 20 0 1 0 1 1 1\n")
        with mock.patch.object(S, "tics_por_segundo", return_value=100), \
                mock.patch.object(S.time, "monotonic", side_effect=[1.0, 2.0]):
            sv.muestreador.previa = sv.muestreador.crudo()
            self.escribir("proc/4/stat", "4 (compilador) S 1 1 1 0 -1 0 0 0 0 0 90 0 0 0 20 0 1 0 1 1 1\n")
            self.escribir("proc/stat", "cpu  190 0 0 110 0 0 0 0 0 0\ncpu0 190 0 0 110 0 0 0 0 0 0\n")
            sv.muestrear()
        picos = [e for e in sv.eventos if e["tipo"] == "pico_cpu"]
        self.assertEqual(len(picos), 1, list(sv.eventos))
        self.assertEqual(picos[0]["proceso"], {"nombre": "compilador", "cpu": 90.0})


class PruebasEventos(unittest.TestCase):
    def inst(self, t, cpu=10.0, procesos=None, **cambios):
        i = instante_base(t=t, procesos=procesos, **cambios)
        i["cpu"]["total"] = cpu
        return i

    PROCS = [{"pid": 1, "nombre": "firefox", "cpu": 88.0, "ram": 500}, {"pid": 2, "nombre": "otro", "cpu": 3.0, "ram": 5}]

    def test_pico_de_cpu_necesita_dos_muestras_y_lleva_el_proceso(self):
        d = S.Detector()
        self.assertEqual(d.procesar(self.inst(100, 90.0, self.PROCS)), [])
        ev = d.procesar(self.inst(110, 91.0, self.PROCS))
        self.assertEqual(len(ev), 1)
        e = ev[0]
        self.assertEqual(sorted(e), ["gravedad", "proceso", "t", "texto", "tipo"])
        self.assertEqual((e["t"], e["tipo"], e["gravedad"]), (110, "pico_cpu", "WARNING"))
        self.assertEqual(e["proceso"], {"nombre": "firefox", "cpu": 88.0})
        self.assertIn("91", e["texto"])
        self.assertEqual(d.procesar(self.inst(120, 95.0, self.PROCS)), [], "mismo episodio: no se repite")
        self.assertEqual(d.procesar(self.inst(130, 20.0)), [])
        self.assertEqual(d.procesar(self.inst(140, 90.0, self.PROCS)), [])
        self.assertEqual(len(d.procesar(self.inst(150, 90.0, self.PROCS))), 1, "episodio nuevo")

    def test_una_muestra_alta_suelta_no_es_pico_y_85_exacto_cuenta(self):
        d = S.Detector()
        for t, cpu in ((0, 90.0), (10, 10.0), (20, 90.0), (30, 10.0)):
            self.assertEqual(d.procesar(self.inst(t, cpu)), [])
        d = S.Detector()
        d.procesar(self.inst(0, 85.0))
        self.assertEqual(len(d.procesar(self.inst(10, 85.0))), 1)

    def test_pico_de_cpu_sin_procesos(self):
        d = S.Detector()
        d.procesar(self.inst(0, 99.0))
        e = d.procesar(self.inst(10, 99.0))[0]
        self.assertIsNone(e["proceso"])

    def test_pico_de_ram(self):
        d = S.Detector()
        alta = {"usada": 14500, "total": 16000, "swap": 0, "swap_total": 0, "presion": None}
        baja = dict(alta, usada=5000)
        self.assertEqual([e["tipo"] for e in d.procesar(self.inst(0, ram=alta))], ["pico_ram"])
        self.assertEqual(d.procesar(self.inst(10, ram=alta)), [])
        self.assertEqual(d.procesar(self.inst(20, ram=baja)), [])
        self.assertEqual([e["tipo"] for e in d.procesar(self.inst(30, ram=alta))], ["pico_ram"])
        self.assertEqual(S.Detector().procesar(self.inst(0, ram=dict(alta, usada=14399))), [])

    def test_salto_de_temperatura(self):
        d = S.Detector()
        self.assertEqual(d.procesar(inst_temp(50.0, t=100)), [])
        ev = d.procesar(inst_temp(65.0, t=110))
        self.assertEqual([(e["tipo"], e["gravedad"]) for e in ev], [("salto_temp", "WARNING")])
        self.assertIn("65", ev[0]["texto"])
        d = S.Detector()
        d.procesar(inst_temp(50.0, t=100))
        self.assertEqual(d.procesar(inst_temp(65.0, t=111)), [], "intervalo mayor de 10 s")
        d = S.Detector()
        d.procesar(inst_temp(50.0, t=100))
        self.assertEqual(d.procesar(inst_temp(64.0, t=105)), [], "subida menor de 15 grados")
        d = S.Detector()
        d.procesar(inst_temp(None, t=100))
        self.assertEqual(d.procesar(inst_temp(70.0, t=105)), [])


class PruebasUmbrales(Base):
    def doc(self, **v):
        d = {"umbral_temp_aviso": "85", "umbral_temp_critico": "95", "umbral_disco_aviso": "85",
             "umbral_disco_critico": "95", "umbral_bateria_aviso": "15", "umbral_bateria_critico": "5",
             "historial_dias": "90"}
        d.update({k: str(x) for k, x in v.items()})
        return {"ajustes": [{"clave": k, "valor": x} for k, x in d.items()] + [{"clave": "borde", "valor": "2"}]}

    def test_traduccion_de_ajustes_a_umbrales(self):
        u = S.umbrales_desde_ajustes(self.doc(umbral_temp_aviso=70, umbral_bateria_aviso=20, historial_dias=30))
        self.assertEqual((u["temp_aviso"], u["temp_critico"], u["bateria_aviso"], u["historial_dias"]),
                         (70.0, 95.0, 20, 30))
        self.assertEqual(u["ram_libre_critico"], S.UMBRALES["ram_libre_critico"])
        self.assertEqual(S.umbrales_desde_ajustes(self.doc()), S.UMBRALES)

    def test_pares_incoherentes_vuelven_a_fabrica(self):
        u = S.umbrales_desde_ajustes(self.doc(umbral_temp_aviso=99, umbral_temp_critico=80,
                                              umbral_bateria_critico=30, umbral_bateria_aviso=10))
        self.assertEqual((u["temp_aviso"], u["temp_critico"]), (85.0, 95.0))
        self.assertEqual((u["bateria_aviso"], u["bateria_critico"]), (15, 5))

    def test_documento_roto_usa_los_de_fabrica(self):
        for doc in (None, [], {"ajustes": "x"}, {"ajustes": [{"clave": "umbral_temp_aviso", "valor": "caliente"}]}):
            self.assertEqual(S.umbrales_desde_ajustes(doc), S.UMBRALES, doc)

    def test_cargar_umbrales_llama_a_ajustes_con_timeout(self):
        llamadas = []

        def falso(cmd, **k):
            llamadas.append((cmd, k))
            return mock.Mock(returncode=0, stdout=json.dumps(self.doc(umbral_disco_aviso=70)))
        u = S.cargar_umbrales(falso)
        self.assertEqual(u["disco_aviso"], 70.0)
        cmd, k = llamadas[0]
        self.assertEqual(cmd[-2:], ["ver", "--json"])
        self.assertTrue(cmd[-3].endswith("jaime0-ajustes"))
        self.assertEqual(k["timeout"], 5)

    def test_si_ajustes_falla_se_usan_los_de_fabrica(self):
        self.assertEqual(S.cargar_umbrales(lambda c, **k: mock.Mock(returncode=1, stdout="")), S.UMBRALES)
        self.assertEqual(S.cargar_umbrales(lambda c, **k: mock.Mock(returncode=0, stdout="no json")), S.UMBRALES)

        def tarda(c, **k):
            raise S.subprocess.TimeoutExpired(c, 5)

        def no_existe(c, **k):
            raise FileNotFoundError
        self.assertEqual(S.cargar_umbrales(tarda), S.UMBRALES)
        self.assertEqual(S.cargar_umbrales(no_existe), S.UMBRALES)

    def test_con_el_jaime0_ajustes_real(self):
        config = os.path.join(self.tmp, "config")
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": config, "PYTHONIOENCODING": "utf-8"}):
            self.assertEqual(S.cargar_umbrales(), S.UMBRALES, "valores de fabrica = los de la prueba")
            os.makedirs(os.path.join(config, "jaime0"))
            with open(os.path.join(config, "jaime0", "ajustes"), "w", encoding="utf-8") as f:
                f.write("umbral_temp_aviso = 70\nhistorial_dias = 30\numbral_bateria_aviso = 20\n")
            u = S.cargar_umbrales()
        self.assertEqual((u["temp_aviso"], u["historial_dias"], u["bateria_aviso"]), (70.0, 30, 20))

    def test_el_servicio_usa_los_umbrales_leidos(self):
        self.escribir("sys/class/hwmon/hwmon0/name", "coretemp\n")
        self.escribir("sys/class/hwmon/hwmon0/temp1_input", "75000\n")
        self.escribir("sys/class/hwmon/hwmon0/temp1_label", "Package id 0\n")
        sv = S.Servicio(directorio=self.rt, estado=self.estado,
                        leer_umbrales=lambda: S.umbrales_desde_ajustes(self.doc(umbral_temp_aviso=70, historial_dias=30)))
        sv.muestreador.base()
        sv.muestrear()
        self.assertEqual(sv.estado, "ONLINE", "aun no se han leido los ajustes: 75 < 85")
        sv.recargar_umbrales()
        self.assertEqual(sv.historico.dias, 30)
        sv.muestrear()
        self.assertEqual(sv.estado, "WARNING")
        self.assertEqual(sv.motivos[0]["componente"], "cpu")

    def test_si_la_lectura_de_ajustes_falla_el_servicio_sigue_con_los_de_fabrica(self):
        sv = S.Servicio(directorio=self.rt, estado=self.estado, leer_umbrales=lambda: dict(S.UMBRALES))
        sv.recargar_umbrales()
        self.assertEqual(sv.umbrales, S.UMBRALES)
        sv2 = S.Servicio(directorio=self.rt, estado=self.estado, leer_umbrales=lambda: None)
        sv2.recargar_umbrales()
        self.assertEqual(sv2.umbrales, S.UMBRALES)


class PruebasSmart(Base):
    def drive(self, modelo="SAMSUNG 980", **extra):
        return {"org.freedesktop.UDisks2.Drive": {"Model": modelo, "Id": modelo.replace(" ", "-")}, **extra}

    def nvme(self, **p):
        base = {"SmartCriticalWarning": [], "SmartTemperature": 313, "SmartPowerOnHours": 1234,
                "SmartUpdated": 1763123456}
        base.update(p)
        return {"org.freedesktop.UDisks2.NVMe.Controller": base}

    def ata(self, **p):
        base = {"SmartSupported": True, "SmartEnabled": True, "SmartFailing": False, "SmartTemperature": 305.15,
                "SmartPowerOnSeconds": 7200 * 3600 // 2, "SmartUpdated": 1763123456}
        base.update(p)
        return {"org.freedesktop.UDisks2.Drive.Ata": base}

    def objetos(self, *drives):
        return {f"/org/freedesktop/UDisks2/drives/d{i}": d for i, d in enumerate(drives)}

    def test_nvme_ok(self):
        r = S.parsear_smart(self.objetos(self.drive(**self.nvme())))
        self.assertEqual(r, [{"disco": "SAMSUNG 980", "tipo": "nvme", "estado": "OK", "temperatura": 39.9,
                              "horas": 1234, "avisos": []}])

    def test_nvme_con_aviso_critico_es_fallo(self):
        r = S.parsear_smart(self.objetos(self.drive(**self.nvme(SmartCriticalWarning=["spare", "raro"]))))
        self.assertEqual(r[0]["estado"], "FALLO")
        self.assertEqual(len(r[0]["avisos"]), 2)
        self.assertIn("reserva", r[0]["avisos"][0])
        self.assertEqual(r[0]["avisos"][1], "raro")

    def test_nvme_sin_lectura_es_nd(self):
        r = S.parsear_smart(self.objetos(self.drive(**self.nvme(SmartUpdated=0, SmartTemperature=0))))
        self.assertEqual((r[0]["estado"], r[0]["temperatura"], r[0]["horas"]), ("N/D", None, None))

    def test_ata_ok_failing_y_no_soportado(self):
        ok = S.parsear_smart(self.objetos(self.drive("WDC", **self.ata())))[0]
        self.assertEqual((ok["tipo"], ok["estado"], ok["temperatura"], ok["horas"]), ("ata", "OK", 32.0, 3600))
        mal = S.parsear_smart(self.objetos(self.drive("WDC", **self.ata(SmartFailing=True))))[0]
        self.assertEqual(mal["estado"], "FALLO")
        self.assertTrue(mal["avisos"])
        nd = S.parsear_smart(self.objetos(self.drive("WDC", **self.ata(SmartSupported=False))))[0]
        self.assertEqual((nd["estado"], nd["avisos"]), ("N/D", []))

    def test_varios_discos_ordenados_y_objetos_ajenos_ignorados(self):
        objetos = self.objetos(self.drive("ZZZ", **self.ata()), self.drive("AAA", **self.nvme()),
                               self.drive("DVD"), {"org.freedesktop.UDisks2.Block": {}})
        self.assertEqual([d["disco"] for d in S.parsear_smart(objetos)], ["AAA", "ZZZ"])
        self.assertEqual(S.parsear_smart({}), [])

    def test_lectores_opticos_no_son_discos(self):
        # VirtualBox publica su CD-ROM como Drive.Ata; no debe salir en STORAGE.
        cd = {"org.freedesktop.UDisks2.Drive": {"Model": "VBOX CD-ROM", "Optical": False,
                                                 "MediaCompatibility": ["optical_cd", "optical_dvd"]},
              **self.ata(SmartSupported=False)}
        cd2 = {"org.freedesktop.UDisks2.Drive": {"Model": "Grabadora", "Optical": True}, **self.ata()}
        disco = self.drive("VBOX HARDDISK", **self.ata(SmartSupported=False))
        self.assertEqual([d["disco"] for d in S.parsear_smart(self.objetos(cd, cd2, disco))], ["VBOX HARDDISK"])

    def test_sin_udisks2_el_resultado_es_null(self):
        recibido = []

        class GioSinBus:
            class BusType:
                SYSTEM = 1

            @staticmethod
            def bus_get_sync(*a):
                raise RuntimeError("sin bus")
        with mock.patch.object(S, "_gi", return_value=(None, GioSinBus)):
            S.consultar_smart(recibido.append)
        self.assertEqual(recibido, [None])
        # hay bus pero udisks2 no contesta: _llamar da None
        recibido.clear()

        class GioConBus(GioSinBus):
            @staticmethod
            def bus_get_sync(*a):
                return object()
        with mock.patch.object(S, "_gi", return_value=(None, GioConBus)), \
                mock.patch.object(S, "_llamar", side_effect=lambda *a: a[-1](None)):
            S.consultar_smart(recibido.append)
        self.assertEqual(recibido, [None])

    def test_con_udisks2_se_pide_get_managed_objects_sin_smart_update(self):
        recibido, pedidos = [], []

        class Gio:
            class BusType:
                SYSTEM = 1

            @staticmethod
            def bus_get_sync(*a):
                return object()

        def llamar(con, destino, objeto, interfaz, metodo, params, cb):
            pedidos.append((destino, objeto, interfaz, metodo))
            cb((self.objetos(self.drive(**self.nvme())),))
        with mock.patch.object(S, "_gi", return_value=(None, Gio)), mock.patch.object(S, "_llamar", llamar):
            S.consultar_smart(recibido.append)
        self.assertEqual(pedidos, [("org.freedesktop.UDisks2", "/org/freedesktop/UDisks2",
                                    "org.freedesktop.DBus.ObjectManager", "GetManagedObjects")])
        self.assertEqual(recibido[0][0]["estado"], "OK")

    def test_smart_va_en_el_instante_y_se_conserva(self):
        sv = S.Servicio(directorio=self.rt, estado=self.estado)
        sv.smart = [{"disco": "X", "tipo": "nvme", "estado": "OK", "temperatura": 40.0, "horas": 1, "avisos": []}]
        sv.muestreador.base()
        sv.muestrear()
        sv.muestrear()
        self.assertEqual(leer_json(os.path.join(self.rt, "instante.json"))["smart"], sv.smart)
        sv.smart = None
        sv.muestrear()
        self.assertIsNone(leer_json(os.path.join(self.rt, "instante.json"))["smart"])

    # -- NVIDIA ----------------------------------------------------------------
    def gpu(self, runtime):
        d = "sys/bus/pci/devices/0000-01-00.0/"
        self.escribir(d + "vendor", "0x10de\n")
        self.escribir(d + "class", "0x030000\n")
        if runtime:
            self.escribir(d + "power/runtime_status", runtime + "\n")
        os.makedirs(os.path.join(self.raiz, "sys/bus/pci/devices/0000-01-00.0/driver"), exist_ok=True)

    def test_nvidia_smi_solo_con_la_gpu_activa(self):
        ejecutar = mock.Mock(return_value=mock.Mock(returncode=0, stdout="47\n"))
        self.gpu("active")
        self.assertEqual(S.temperatura_nvidia(ejecutar), 47.0)
        self.assertEqual(ejecutar.call_args[0][0],
                         ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"])
        self.assertEqual(ejecutar.call_args[1]["timeout"], 3)

    def test_nvidia_smi_no_se_ejecuta_con_la_gpu_dormida_o_sin_estado(self):
        for runtime in ("suspended", "resuming", "suspending", None):
            shutil.rmtree(os.path.join(self.raiz, "sys"), ignore_errors=True)
            self.gpu(runtime)
            ejecutar = mock.Mock()
            self.assertIsNone(S.temperatura_nvidia(ejecutar), runtime)
            ejecutar.assert_not_called()
        shutil.rmtree(os.path.join(self.raiz, "sys"), ignore_errors=True)
        ejecutar = mock.Mock()
        self.assertIsNone(S.temperatura_nvidia(ejecutar), "sin GPU")
        ejecutar.assert_not_called()

    def test_nvidia_smi_con_fallos(self):
        self.gpu("active")
        self.assertIsNone(S.temperatura_nvidia(mock.Mock(return_value=mock.Mock(returncode=9, stdout=""))))
        self.assertIsNone(S.temperatura_nvidia(mock.Mock(return_value=mock.Mock(returncode=0, stdout="N/A\n"))))
        self.assertIsNone(S.temperatura_nvidia(mock.Mock(side_effect=S.subprocess.TimeoutExpired("x", 3))))
        self.assertIsNone(S.temperatura_nvidia(mock.Mock(side_effect=FileNotFoundError)))

    def test_gpu_suspendida_siempre_null_en_el_instante(self):
        sv = S.Servicio(directorio=self.rt, estado=self.estado)
        sv.gpu_temp = 60.0                                   # lectura vieja de cuando estaba activa
        self.gpu("suspended")
        sv.muestreador.base()
        sv.muestrear()
        self.assertIsNone(sv.instante["gpu"]["temp"])
        self.assertEqual(sv.instante["gpu"]["nvidia"], "suspendida")
        self.assertIsNone(sv.gpu_temp)
        shutil.rmtree(os.path.join(self.raiz, "sys"))
        self.gpu("active")
        sv.gpu_temp = 61.0
        sv.muestrear()
        self.assertEqual(sv.instante["gpu"]["temp"], 61.0)


class ContextoFase3(ContextoFalso):
    def __init__(self):
        super().__init__()
        self.pedidos = []

    def serie(self, rango):
        self.pedidos.append(rango)
        return {"ok": True, "v": 1, "rango": rango}

    def incidencias(self, limite):
        self.pedidos.append(limite)
        return [{"componente": "disco"}]

    def eventos_lista(self):
        return [{"tipo": "perfil"}]


class PruebasApiFase3(Base):
    def pedir(self, linea, ctx):
        return json.loads(S.procesar_linea(linea, ctx))

    def test_serie_pasa_el_rango(self):
        ctx = ContextoFase3()
        self.assertEqual(self.pedir('{"orden":"serie","rango":"1h"}', ctx), {"ok": True, "v": 1, "rango": "1h"})
        self.assertEqual(ctx.pedidos, ["1h"])

    def test_limite_de_incidencias(self):
        for linea, esperado in (('{"orden":"incidencias"}', 50), ('{"orden":"incidencias","limite":7}', 7),
                                ('{"orden":"incidencias","limite":9999}', 500), ('{"orden":"incidencias","limite":0}', 50),
                                ('{"orden":"incidencias","limite":"x"}', 50), ('{"orden":"incidencias","limite":true}', 50)):
            ctx = ContextoFase3()
            r = self.pedir(linea, ctx)
            self.assertEqual(r, {"ok": True, "v": 1, "incidencias": [{"componente": "disco"}]})
            self.assertEqual(ctx.pedidos, [esperado], linea)

    def test_eventos(self):
        self.assertEqual(self.pedir('{"orden":"eventos"}', ContextoFase3()),
                         {"ok": True, "v": 1, "eventos": [{"tipo": "perfil"}]})

    def test_con_el_servicio_real(self):
        sv = S.Servicio(directorio=self.rt, estado=self.estado, reloj=lambda: BASE + 5000)
        r = self.pedir('{"orden":"serie","rango":"5m"}', sv)
        self.assertEqual((r["ok"], r["error"]), (False, "sin datos suficientes"))
        self.assertEqual(r["disponible"], {"5m": False, "1h": False, "24h": False, "historia": False})
        self.assertEqual(self.pedir('{"orden":"serie","rango":"mal"}', sv)["error"], "rango no válido")
        self.assertEqual(self.pedir('{"orden":"serie"}', sv)["error"], "rango no válido")
        self.assertEqual(self.pedir('{"orden":"incidencias"}', sv)["incidencias"], [])
        S.anexar_jsonl(os.path.join(self.estado, "incidencias.jsonl"),
                       [{"v": 1, "t": i, "gravedad": "WARNING", "componente": "disco"} for i in (1, 2, 3)])
        self.assertEqual([d["t"] for d in self.pedir('{"orden":"incidencias","limite":2}', sv)["incidencias"]], [3, 2])
        sv.evento("uno", "perfil")
        sv.evento("dos", "estado", "WARNING")
        ev = self.pedir('{"orden":"eventos"}', sv)["eventos"]
        self.assertEqual([e["texto"] for e in ev], ["dos", "uno"], "las mas recientes primero")
        sv.anillo.extend(muestra(BASE + 5000 - 120 + i, cpu=float(i)) for i in range(121))
        r = self.pedir('{"orden":"serie","rango":"5m"}', sv)
        self.assertTrue(r["ok"])
        self.assertEqual(r["metricas"]["cpu"]["med"][-1], 120.0)
        sv.estado = "ONLINE"
        self.assertEqual(sorted(sv.estado_doc()["disponible"]), ["1h", "24h", "5m", "historia"])
        self.assertEqual(sv.estado_doc()["incidencias_abiertas"], [])

    def test_respuesta_grande_cabe_en_una_linea(self):
        sv = S.Servicio(directorio=self.rt, estado=self.estado, reloj=lambda: BASE + 90000)
        sv.historico.cuartos = [agg(BASE + 900 * i, cpu=float(i), ram=50.0, temp=60.0) for i in range(8640)]
        texto = S.procesar_linea('{"orden":"serie","rango":"historia"}', sv)
        self.assertNotIn("\n", texto)
        self.assertGreater(len(texto), 60000)
        self.assertLessEqual(len(json.loads(texto)["t"]), 720)


class PruebasSaludFase3(Base):
    def incidencia(self, t, gravedad="WARNING", comp="cpu-temp", rec="Revisa la ventilación"):
        return {"v": 1, "t": t, "gravedad": gravedad, "componente": comp, "descripcion": f"desc {t}",
                "diagnostico": "diag", "recomendacion": rec, "valor": 90}

    def correr(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = H.main(list(argv))
            except SystemExit as e:
                rc = e.code
        return rc, out.getvalue(), err.getvalue()

    def escribir_incidencias(self, docs, rota=True):
        os.makedirs(self.estado, exist_ok=True)
        with open(os.path.join(self.estado, "incidencias.jsonl"), "w", encoding="utf-8") as f:
            for d in docs:
                f.write(json.dumps(d) + "\n")
            if rota:
                f.write('{"v":1,"t":9,"grav')

    def test_incidencias_del_archivo_si_el_servicio_no_corre(self):
        self.escribir_incidencias([self.incidencia(1763123000), self.incidencia(1763123500, "CRITICAL", "disco"),
                                   self.incidencia(1763124000, "NORMAL", "disco", "")])
        with mock.patch.object(H, "pedir_socket", side_effect=FileNotFoundError):
            rc, out, _ = self.correr("incidencias")
        self.assertEqual(rc, 0)
        lineas = out.splitlines()
        self.assertIn("NORMAL", lineas[0])
        self.assertIn("desc 1763124000", lineas[0])
        self.assertIn("CRITICAL", lineas[1])
        self.assertIn("disco", lineas[1])
        self.assertIn("Recomendación: Revisa la ventilación", lineas[2])
        self.assertRegex(lineas[0], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}  ")
        self.assertEqual(len([l for l in lineas if "desc " in l]), 3, "la linea rota se ignora")

    def test_incidencias_limite_y_json(self):
        self.escribir_incidencias([self.incidencia(100 + i) for i in range(10)])
        with mock.patch.object(H, "pedir_socket", side_effect=OSError):
            rc, out, _ = self.correr("incidencias", "--json", "-n", "3")
        self.assertEqual(rc, 0)
        self.assertEqual([d["t"] for d in json.loads(out)], [109, 108, 107])

    def test_incidencias_sin_nada(self):
        with mock.patch.object(H, "pedir_socket", side_effect=OSError):
            rc, out, _ = self.correr("incidencias")
        self.assertEqual((rc, out.strip()), (0, "No hay incidencias registradas."))

    def test_incidencias_prefiere_al_servicio(self):
        respuesta = {"ok": True, "v": 1, "incidencias": [self.incidencia(1763123000, comp="gpu")]}
        with mock.patch.object(H, "pedir_socket", return_value=respuesta) as p:
            rc, out, _ = self.correr("incidencias", "-n", "5")
        self.assertIn("gpu", out)
        self.assertEqual(p.call_args[0][0], {"orden": "incidencias", "limite": 5})

    def test_serie_sin_servicio_da_un_error_claro(self):
        with mock.patch.object(H, "pedir_socket", side_effect=FileNotFoundError):
            rc, out, err = self.correr("serie", "5m")
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("no está en marcha", err)

    def test_serie_resumen_y_json(self):
        serie = {"ok": True, "v": 1, "rango": "24h", "resolucion": 60, "desde": 0, "hasta": 1, "t": [0, 60, 120],
                 "metricas": {k: {"min": [None] * 3, "med": [None] * 3, "max": [None] * 3} for k in S.METRICAS},
                 "huecos": [[1, 2]], "eventos": [], "disponible": {}}
        serie["metricas"]["cpu"] = {"min": [1.0, 2.0, 3.0], "med": [10.0, 20.0, 30.0], "max": [50.0, 60.0, 70.0]}
        with mock.patch.object(H, "pedir_socket", return_value=serie) as p:
            rc, out, _ = self.correr("serie", "24h")
            rc2, out2, _ = self.correr("serie", "24h", "--json")
        self.assertEqual(p.call_args[0][0], {"orden": "serie", "rango": "24h"})
        self.assertEqual(rc, 0)
        self.assertIn("3 puntos", out)
        self.assertIn("CPU: mín 1 · media 20.0 · máx 70 %", out)
        self.assertIn("Temperatura CPU: N/D", out)
        self.assertIn("Huecos (sin datos): 1", out)
        self.assertEqual(json.loads(out2), serie)

    def test_serie_sin_datos_suficientes_y_rango_invalido(self):
        malo = {"ok": False, "error": "sin datos suficientes", "disponible": {}}
        with mock.patch.object(H, "pedir_socket", return_value=malo):
            rc, _, err = self.correr("serie", "historia")
        self.assertEqual(rc, 1)
        self.assertIn("sin datos suficientes", err)
        self.assertEqual(self.correr("serie", "7d")[0], 2)

    def test_pedir_socket_sin_servicio_lanza_oserror(self):
        with self.assertRaises(OSError):
            H.pedir_socket({"orden": "estado"})


if __name__ == "__main__":
    unittest.main()
