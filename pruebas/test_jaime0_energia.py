#!/usr/bin/env python3
"""Pruebas de POWER (jaime0_servicio.energia, evolucion fase 6): bateria en detalle, graficas,
CPU, suspension, inactividad, historico por perfil de energia, la orden "energia" y los ajustes
de inactividad de jaime0-ajustes. Con la raiz falsa de test_jaime0_servicio.

    python3 -m unittest discover -s pruebas -v
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_jaime0_servicio import Base, S, cargar, instante_base  # noqa: E402

BAT = "sys/class/power_supply/BAT0/"


def minuto(t, cargador=0, vatios=None, bateria=None, eventos=None):
    a = {"t": t, "n": 6, "cargador": None if cargador is None else [cargador, cargador, cargador],
         "vatios": None if vatios is None else [vatios, vatios, vatios],
         "bateria": None if bateria is None else [bateria, bateria, bateria]}
    if eventos:
        a["eventos"] = eventos
    return a


def cambio(t, valor):
    return {"t": t, "tipo": "perfil", "gravedad": "INFO", "texto": f"Perfil de energía: {valor}",
            "proceso": None, "valor": valor}


class PruebasBateria(Base):
    def bateria(self, **campos):
        self.escribir(BAT + "type", "Battery\n")
        for k, v in campos.items():
            self.escribir(BAT + k, f"{v}\n")

    def test_sin_bateria(self):
        self.assertIsNone(S.detalle_bateria())

    def test_energia_en_wh_con_origen_de_cada_dato(self):
        self.bateria(status="Discharging", capacity=80, power_now=12500000, energy_now=40000000,
                     energy_full=45000000, energy_full_design=50000000, voltage_now=11400000,
                     cycle_count=212, technology="Li-ion", manufacturer="SMP", model_name="AP18E8M")
        b = S.detalle_bateria()
        self.assertEqual((b["unidad"], b["estado"]), ("Wh", "descargando"))
        self.assertEqual(b["nivel"], {"valor": 80, "origen": "medido"})
        self.assertEqual(b["capacidad_diseno"], {"valor": 50.0, "origen": "medido"})
        self.assertEqual(b["capacidad_actual"]["valor"], 45.0)
        self.assertEqual(b["salud"], {"valor": 90.0, "origen": "calculado"})
        self.assertEqual(b["potencia"], {"valor": 12.5, "origen": "medido"})
        self.assertEqual(b["autonomia_min"], {"valor": 192, "origen": "estimado"})     # 40 Wh / 12,5 W
        self.assertEqual(b["hasta_llena_min"]["origen"], "no_disponible")
        self.assertEqual((b["ciclos"]["valor"], b["ciclos_sin_contar"]), (212, False))
        self.assertEqual(b["voltaje"]["valor"], 11.4)
        self.assertEqual((b["tecnologia"], b["modelo"]), ("Li-ion", "AP18E8M"))
        self.assertEqual(b["limite_carga"]["origen"], "no_disponible")

    def test_carga_en_mah_potencia_calculada_y_tiempo_hasta_llena(self):
        self.bateria(status="Charging", capacity=50, current_now=2000000, voltage_now=12000000,
                     charge_now=2000000, charge_full=4000000, charge_full_design=5000000, cycle_count=0,
                     charge_control_end_threshold=80)
        b = S.detalle_bateria()
        self.assertEqual(b["unidad"], "mAh")
        self.assertEqual(b["potencia"], {"valor": 24.0, "origen": "calculado"})
        self.assertEqual(b["hasta_llena_min"], {"valor": 60, "origen": "estimado"})   # 2000 mAh a 2000 mA
        self.assertEqual(b["autonomia_min"]["valor"], None)
        self.assertTrue(b["ciclos_sin_contar"])
        self.assertEqual(b["limite_carga"], {"valor": 80, "origen": "medido"})

    def test_lo_que_no_da_el_firmware_es_no_disponible(self):
        self.bateria(status="Unknown", capacity=100)
        b = S.detalle_bateria()
        for clave in ("capacidad_diseno", "capacidad_actual", "salud", "potencia", "ciclos", "autonomia_min",
                      "descarga_pct_h"):
            self.assertEqual(b[clave], {"valor": None, "origen": "no_disponible"}, clave)

    def test_velocidad_de_descarga_solo_con_tramo_suficiente(self):
        m = lambda t, b, c=0: {"t": t, "bateria": b, "cargador": c}
        # 20 min sin cargador, de 80 a 76 %: 12 %/h
        self.assertEqual(S.descarga_por_hora([m(-60, 90, 1)] + [m(60 * i, 80 - i // 5) for i in range(0, 21)]), 12.0)
        self.assertIsNone(S.descarga_por_hora([m(0, 80), m(300, 79)]))              # menos de 10 min
        self.assertIsNone(S.descarga_por_hora([m(0, 80), m(900, 80)]))              # no ha bajado
        self.assertIsNone(S.descarga_por_hora([m(0, 80), m(900, 70, 1)]))           # ahora carga
        self.assertIsNone(S.descarga_por_hora([m(0, 80, None), m(900, 70, None)]))  # sin dato del cargador


class PruebasGraficas(Base):
    def grafica(self, pci, fabricante, principal, driver=None, energia="active", clase="0x030000"):
        d = f"sys/bus/pci/devices/{pci}/"
        self.escribir(d + "class", clase + "\n")
        self.escribir(d + "vendor", fabricante + "\n")
        self.escribir(d + "boot_vga", ("1" if principal else "0") + "\n")
        self.escribir(d + "power/runtime_status", energia + "\n")
        self.escribir(d + "power/control", "auto\n")
        if driver:
            destino = os.path.join(self.raiz, "sys", "bus", "pci", "drivers", driver)
            os.makedirs(destino, exist_ok=True)
            try:
                os.symlink(destino, os.path.join(self.raiz, *d.split("/"), "driver"))
            except (OSError, NotImplementedError):
                self.skipTest("este sistema no permite enlaces simbólicos")

    def test_hibrida_intel_y_nvidia_dormida_sin_despertarla(self):
        self.grafica("a-00-02.0", "0x8086", True, "i915")
        self.grafica("b-01-00.0", "0x10de", False, "nvidia", energia="suspended", clase="0x030200")
        self.escribir("sys/module/nvidia/version", "550.163.01\n")
        llamadas = []
        g = S.graficas(ejecutar=lambda *a, **k: llamadas.append(a), ver_procesos=lambda: {"procesos": [], "parcial": True})
        self.assertEqual(g["prime"], "offload")
        intel, nvidia = g["graficas"]
        self.assertEqual((intel["rol"], intel["driver"], intel["principal"]), ("integrada", "i915", True))
        self.assertEqual((nvidia["rol"], nvidia["driver"], nvidia["energia"]), ("dedicada", "nvidia", "suspended"))
        self.assertEqual(nvidia["modulo"], "550.163.01")
        self.assertIsNone(nvidia["medidas"])
        self.assertEqual(llamadas, [], "con la NVIDIA dormida no se ejecuta nvidia-smi")

    def test_nvidia_despierta_se_mide_y_dice_quien_la_usa(self):
        self.grafica("a-00-02.0", "0x8086", True, "i915")
        self.grafica("b-01-00.0", "0x10de", False, "nvidia")
        r = mock.Mock(returncode=0, stdout="14.52, 47, 3\n")
        g = S.graficas(ejecutar=lambda *a, **k: r,
                       ver_procesos=lambda: {"procesos": [{"pid": 10, "nombre": "mpv"}], "parcial": False})
        nvidia = g["graficas"][1]
        self.assertEqual(nvidia["medidas"]["vatios"], {"valor": 14.52, "origen": "medido"})
        self.assertEqual(nvidia["medidas"]["temp"]["valor"], 47.0)
        self.assertEqual(nvidia["uso"]["procesos"], [{"pid": 10, "nombre": "mpv"}])

    def test_nvidia_sin_driver_y_maquina_virtual(self):
        self.grafica("a-00-02.0", "0x80ee", True, None)
        self.assertEqual(S.graficas()["graficas"][0]["rol"], "virtual")
        self.assertIsNone(S.graficas()["prime"])
        self.grafica("b-01-00.0", "0x10de", False, None)
        g = S.graficas(ejecutar=lambda *a, **k: self.fail("sin driver no se llama a nvidia-smi"))
        self.assertEqual(g["prime"], "sin_driver")
        self.assertIsNone(g["graficas"][1]["uso"])

    def test_medidas_de_nvidia_con_campos_no_disponibles(self):
        r = mock.Mock(returncode=0, stdout="[N/A], 51, [N/A]\n")
        m = S.medidas_nvidia(lambda *a, **k: r)
        self.assertEqual(m["vatios"], {"valor": None, "origen": "no_disponible"})
        self.assertEqual(m["temp"]["valor"], 51.0)
        self.assertIsNone(S.medidas_nvidia(lambda *a, **k: mock.Mock(returncode=9, stdout="")))
        self.assertIsNone(S.medidas_nvidia(mock.Mock(side_effect=OSError)))

    def test_procesos_que_abren_la_nvidia(self):
        for pid, nombre, dispositivo in ((10, "mpv", "/dev/nvidia0"), (11, "kitty", "/dev/pts/1"),
                                         (12, "x", "/dev/nvidiactl")):
            self.escribir(f"proc/{pid}/comm", nombre + "\n")
            fd = os.path.join(self.raiz, "proc", str(pid), "fd")
            os.makedirs(fd)
            try:
                os.symlink(dispositivo, os.path.join(fd, "3"))
            except (OSError, NotImplementedError):
                self.skipTest("este sistema no permite enlaces simbólicos")
        self.assertEqual(S.procesos_nvidia(), {"procesos": [{"pid": 10, "nombre": "mpv"}], "parcial": False})


class PruebasCpuYSuspension(Base):
    def test_cpu_con_intel_pstate(self):
        c = "sys/devices/system/cpu/"
        self.escribir(c + "cpu0/cpufreq/scaling_driver", "intel_pstate\n")
        self.escribir(c + "cpu0/cpufreq/scaling_governor", "powersave\n")
        self.escribir(c + "cpu0/cpufreq/energy_performance_preference", "balance_performance\n")
        self.escribir(c + "cpu0/cpufreq/energy_performance_available_preferences",
                      "default performance balance_performance balance_power power\n")
        self.escribir(c + "intel_pstate/status", "active\n")
        self.escribir(c + "intel_pstate/no_turbo", "0\n")
        r = S.cpu_energia()
        self.assertEqual((r["driver"], r["gobernador"], r["epp"], r["turbo"]),
                         ("intel_pstate", "powersave", "balance_performance", True))
        self.assertEqual(len(r["epp_opciones"]), 5)

    def test_cpu_sin_datos_en_una_maquina_virtual(self):
        r = S.cpu_energia()
        self.assertEqual((r["driver"], r["epp"], r["turbo"], r["epp_opciones"]), (None, None, None, []))

    def test_logind_predeterminado_y_ordenes_de_prioridad(self):
        v = S.leer_logind()
        self.assertEqual(v["valores"]["HandleLidSwitch"], "suspend")
        self.assertEqual(v["valores"]["HandleLidSwitchExternalPower"], "suspend")
        self.assertEqual(v["fijados"], [])
        self.escribir("etc/systemd/logind.conf", "[Login]\n#HandleLidSwitch=ignore\nHandleLidSwitch=lock\n")
        self.escribir("usr/lib/systemd/logind.conf.d/10-a.conf", "[Login]\nHandleLidSwitch=poweroff\n")
        self.escribir("etc/systemd/logind.conf.d/20-b.conf", "[Login]\nHandleLidSwitchExternalPower=ignore\n")
        v = S.leer_logind()["valores"]
        self.assertEqual((v["HandleLidSwitch"], v["HandleLidSwitchExternalPower"]), ("poweroff", "ignore"))

    def test_suspension(self):
        self.escribir("sys/power/mem_sleep", "s2idle [deep]\n")
        self.escribir("sys/power/state", "freeze mem disk\n")
        r = S.suspension()
        self.assertEqual((r["modo"], r["modos"], r["puede_suspender"], r["puede_hibernar"]),
                         ("deep", ["s2idle", "deep"], True, True))
        self.assertEqual(r["tapa"], "suspend")

    def test_inactividad_y_hypridle_personalizado(self):
        ajustes = {"ajustes": [{"clave": "inactividad_bloqueo", "valor": "10"},
                               {"clave": "inactividad_pantalla", "valor": "0"},
                               {"clave": "inactividad_suspender", "valor": "30"},
                               {"clave": "suspender_con_cargador", "valor": "no"}]}
        inicio = os.path.join(self.tmp, "casa")
        r = S.inactividad(ajustes, inicio)
        self.assertEqual((r["bloqueo"], r["pantalla"], r["suspender"], r["con_cargador"], r["personalizado"]),
                         (10, 0, 30, False, False))
        self.escribir("etc/skel/.config/hypr/hypridle.conf", "original\n")
        propio = os.path.join(inicio, ".config", "hypr", "hypridle.conf")
        os.makedirs(os.path.dirname(propio))
        with open(propio, "w", newline="\n") as f:
            f.write("original\n")
        self.assertFalse(S.inactividad(ajustes, inicio)["personalizado"])
        with open(propio, "w", newline="\n") as f:
            f.write("mio\n")
        self.assertTrue(S.inactividad(ajustes, inicio)["personalizado"])
        self.assertIsNone(S.inactividad(None, inicio)["bloqueo"])


class PruebasHistorialEnergia(unittest.TestCase):
    def test_tiempo_con_cargador(self):
        mins = [minuto(0, 1), minuto(60, 1), minuto(120, 0), minuto(180, None), minuto(240, 0.5)]
        self.assertEqual(S.tiempo_con_cargador(mins, 0), {"minutos": 4, "conectado": 2})
        self.assertEqual(S.tiempo_con_cargador(mins, 200), {"minutos": 1, "conectado": 0})

    def test_comparar_perfiles_solo_con_datos_reales(self):
        mins = [minuto(0, 0, 9.0, 90)]                                         # antes del primer evento: no cuenta
        mins.append(minuto(60, 0, 9.0, 90, [cambio(70, "power-saver")]))        # minuto del cambio: no cuenta
        mins += [minuto(60 * i, 0, 6.0, 90 - (i - 2) * 0.1) for i in range(2, 32)]   # 30 min en ahorro
        mins.append(minuto(60 * 32, 1, 20.0, 87, [cambio(1930, "performance")]))
        mins += [minuto(60 * i, 0, 15.0, 87) for i in range(33, 38)]           # 5 min: pocos
        r = {p["perfil"]: p for p in S.comparar_perfiles(mins)}
        self.assertEqual(r["power-saver"]["minutos"], 30)
        self.assertEqual(r["power-saver"]["vatios"], {"valor": 6.0, "origen": "calculado"})
        self.assertEqual(r["power-saver"]["descarga_pct_h"]["valor"], 6.0)     # 0,1 % por minuto
        self.assertEqual(r["performance"]["minutos"], 5)
        self.assertEqual(r["performance"]["vatios"]["origen"], "no_disponible")
        self.assertNotIn("balanced", r)

    def test_un_hueco_corta_la_descarga_y_el_cargador_excluye(self):
        mins = [minuto(0, 0, None, None, [cambio(0, "balanced")])]
        mins += [minuto(60 * i, 0, 8.0, 80) for i in range(1, 12)]
        mins += [minuto(60 * i, 0, 8.0, 70) for i in range(20, 31)]            # hueco de 8 min
        mins += [minuto(60 * 40, 0.5, 8.0, 50)]                                # medio minuto cargando
        r = S.comparar_perfiles(mins)[0]
        self.assertEqual(r["minutos"], 22)
        self.assertEqual(r["descarga_pct_h"]["origen"], "no_disponible", "la caida del hueco no cuenta")

    def test_reglas_de_energia(self):
        reglas = [{"id": "a", "nombre": "Ahorro", "activa": True, "cuando": {"evento": "cargador"},
                   "hacer": [{"accion": "perfil"}]},
                  {"id": "b", "nombre": "Noche", "activa": True, "cuando": {"evento": "hora"},
                   "si": [{"condicion": "bateria_menor"}], "hacer": [{"accion": "modo_noche"}]},
                  {"id": "c", "nombre": "Otra", "activa": False, "cuando": {"evento": "hora"}, "hacer": []}]
        r = S.reglas_energia(reglas)
        self.assertEqual([x["id"] for x in r], ["a", "b"])
        self.assertEqual(r[0]["acciones"], ["perfil"])


class PruebasOrdenEnergia(Base):
    def test_orden_energia_completa(self):
        self.escribir(BAT + "type", "Battery\n")
        self.escribir(BAT + "capacity", "64\n")
        self.escribir(BAT + "status", "Discharging\n")
        sv = S.Servicio(directorio=self.rt, estado=self.estado)
        sv.instante = instante_base(cargador=False)
        sv.poner_energia("power-saver")
        with mock.patch.object(S.servicio_mod, "leer_ajustes", return_value={"ajustes": []}):
            doc = json.loads(S.procesar_linea(json.dumps({"orden": "energia"}), sv))
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["bateria"]["nivel"]["valor"], 64)
        self.assertIs(doc["cargador"], False)
        self.assertEqual(doc["perfil"]["energia"], "power-saver")
        ids = [p["id"] for p in doc["perfiles"]]
        self.assertEqual(ids, ["balanced", "performance", "power-saver", "focus", "multimedia", "custom"])
        multimedia = next(p for p in doc["perfiles"] if p["id"] == "multimedia")
        self.assertTrue(multimedia["inhibe"])
        self.assertIsNone(doc["inactividad"]["inhibida_por"])
        self.assertEqual(set(doc["historial"]), {"desde", "cargador_24h", "perfiles"})
        self.assertEqual(doc["reglas"], [])
        self.assertIn("prime", doc["graficas"])

    def test_la_muestra_guarda_el_cargador(self):
        self.assertEqual(S.muestra_desde_instante(instante_base(cargador=True))["cargador"], 1)
        self.assertEqual(S.muestra_desde_instante(instante_base(cargador=False))["cargador"], 0)
        self.assertIsNone(S.muestra_desde_instante(instante_base(cargador=None))["cargador"])
        self.assertIn("cargador", S.METRICAS)


class PruebasAjustesInactividad(unittest.TestCase):
    A = cargar("jaime0_ajustes_energia", "jaime0-ajustes")

    def valores(self, **cambios):
        return dict(self.A.RESERVA, **cambios)

    def test_los_valores_de_fabrica_son_los_de_siempre(self):
        texto = self.A.hypridle_conf(self.valores())
        for linea in ("timeout = 300", "on-timeout = jaime0-reglas evento inactivo", "timeout = 600",
                      "timeout = 660", "timeout = 1800", "on-timeout = systemctl suspend"):
            self.assertIn(linea, texto)
        self.assertEqual(texto.count("listener {"), 4)

    def test_cero_quita_la_accion_y_el_cargador_la_condiciona(self):
        texto = self.A.hypridle_conf(self.valores(inactividad_bloqueo="0", inactividad_pantalla="0",
                                                  suspender_con_cargador="no"))
        self.assertEqual(texto.count("listener {"), 2)
        self.assertIn("on-timeout = inactividad suspender", texto)
        self.assertNotIn("timeout = 600", texto)
        self.assertEqual(self.A.hypridle_conf(self.valores(inactividad_suspender="0")).count("suspend\n"), 0)

    def test_esquema_y_limites(self):
        self.assertEqual(self.A.ESQUEMA["inactividad_suspender"]["max"], 240)
        self.assertEqual(self.A.validar("inactividad_bloqueo", "0", {}), "0")
        with self.assertRaises(self.A.Error):
            self.A.validar("inactividad_pantalla", "121", {})
        with self.assertRaises(self.A.Error):
            self.A.validar("suspender_con_cargador", "quizas", {})


if __name__ == "__main__":
    unittest.main()
