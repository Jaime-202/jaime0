#!/usr/bin/env python3
"""Pruebas de la capa de deteccion de hardware (jaime0_servicio.hardware, evolucion fase 8):
portatil hibrido con NVIDIA, solo grafica integrada, maquina virtual, sensores (tambien
ventiladores y voltajes), errores de lectura y que un fallo nunca tumbe la deteccion. Con la
raiz falsa de test_jaime0_servicio.

    python3 -m unittest discover -s pruebas -v
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_jaime0_servicio import Base, S  # noqa: E402


class Hw(Base):
    def gpu(self, pci, fab, principal, driver=None):
        d = f"sys/bus/pci/devices/{pci}/"
        self.escribir(d + "class", "0x030000\n")
        self.escribir(d + "vendor", fab + "\n")
        self.escribir(d + "boot_vga", ("1" if principal else "0") + "\n")
        if driver:
            destino = os.path.join(self.raiz, "sys", "bus", "pci", "drivers", driver)
            os.makedirs(destino, exist_ok=True)
            try:
                os.symlink(destino, os.path.join(self.raiz, *d.split("/"), "driver"))
            except (OSError, NotImplementedError):
                self.skipTest("este sistema no permite enlaces simbólicos")

    def estados(self, lista):
        return {c["id"]: c["estado"] for c in lista}


class PruebasGraficas(Hw):
    def test_portatil_hibrido_con_nvidia_lista(self):
        self.gpu("a-02", "0x8086", True, "i915")
        self.gpu("b-01", "0x10de", False, "nvidia")
        self.escribir("sys/module/nvidia/version", "550.163.01\n")
        with mock.patch.object(S.hardware_mod.shutil, "which", return_value="/usr/bin/nvidia-smi"):
            e = {c["id"]: c for c in S.detectar_graficas()}
        self.assertEqual((e["gpu_integrada"]["estado"], e["gpu_dedicada"]["estado"]), ("compatible", "compatible"))
        self.assertIn("550.163.01", e["gpu_dedicada"]["detalle"])

    def test_nvidia_sin_controlador_o_con_nouveau_es_detectada(self):
        self.gpu("a-02", "0x8086", True, "i915")
        self.gpu("b-01", "0x10de", False)
        self.assertEqual(self.estados(S.detectar_graficas())["gpu_dedicada"], "detectado")

    def test_solo_integrada_no_supone_nvidia(self):
        self.gpu("a-02", "0x8086", True, "i915")
        e = {c["id"]: c for c in S.detectar_graficas()}
        self.assertEqual(e["gpu_dedicada"]["estado"], "no_disponible")
        self.assertIn("sin prime-run", e["gpu_dedicada"]["detalle"])

    def test_maquina_virtual(self):
        self.gpu("a-02", "0x15ad", True, "vmwgfx")
        e = {c["id"]: c for c in S.detectar_graficas()}
        self.assertEqual((e["gpu_integrada"]["nombre"], e["gpu_integrada"]["estado"]), ("Gráfica virtual", "compatible"))
        self.assertEqual(e["gpu_dedicada"]["estado"], "no_disponible")


class PruebasSensores(Hw):
    def test_cpu_ventiladores_y_voltajes(self):
        h = "sys/class/hwmon/hwmon0/"
        self.escribir(h + "name", "coretemp\n")
        self.escribir(h + "temp1_input", "52000\n")
        self.escribir(h + "temp1_label", "Package id 0\n")
        h = "sys/class/hwmon/hwmon1/"
        self.escribir(h + "name", "acer\n")
        self.escribir(h + "fan1_input", "2400\n")
        self.escribir(h + "in0_input", "12100\n")
        e = {c["id"]: c for c in S.detectar_sensores()}
        self.assertEqual(e["temp_cpu"]["valores"], [{"id": "coretemp/Package id 0", "valor": 52.0, "unidad": "°C"}])
        self.assertEqual(e["ventiladores"]["valores"][0]["valor"], 2400)
        self.assertEqual(e["voltajes"]["valores"][0], {"id": "acer/in0", "valor": 12.1, "unidad": "V"})
        self.assertEqual(e["temp_gpu"]["estado"], "no_disponible")

    def test_sin_sensores_no_se_inventa_nada(self):
        e = {c["id"]: c for c in S.detectar_sensores()}
        for clave in ("temp_cpu", "temp_gpu", "ventiladores", "voltajes"):
            self.assertEqual(e[clave]["estado"], "no_disponible", clave)
            self.assertEqual(e[clave]["valores"], [])

    def test_sensor_presente_que_no_se_lee_es_error_de_lectura(self):
        self.escribir("sys/class/hwmon/hwmon0/name", "acer\n")
        self.escribir("sys/class/hwmon/hwmon0/fan1_input", "no-numero\n")
        self.assertEqual(self.estados(S.detectar_sensores())["ventiladores"], "error_lectura")


class PruebasResto(Hw):
    def test_bateria(self):
        self.assertEqual(S.detectar_bateria()["estado"], "no_disponible")
        self.escribir("sys/class/power_supply/BAT1/type", "Battery\n")
        self.assertEqual(S.detectar_bateria()["estado"], "error_lectura")
        self.escribir("sys/class/power_supply/BAT1/capacity", "77\n")
        self.escribir("sys/class/power_supply/BAT1/energy_full_design", "1\n")
        self.escribir("sys/class/power_supply/BAT1/power_now", "1\n")
        b = S.detectar_bateria()
        self.assertEqual(b["estado"], "compatible")
        self.assertIn("capacidad de diseño, consumo", b["detalle"])

    def test_cargador(self):
        self.assertEqual(S.detectar_cargador()["estado"], "no_disponible")
        self.escribir("sys/class/power_supply/ACAD/type", "Mains\n")
        self.assertEqual(S.detectar_cargador()["estado"], "error_lectura")
        self.escribir("sys/class/power_supply/ACAD/online", "1\n")
        self.assertEqual(S.detectar_cargador()["detalle"], "Conectado")

    def test_brillo_wifi_bluetooth_y_suspension(self):
        self.assertEqual(S.detectar_retroiluminacion()["estado"], "no_disponible")
        self.escribir("sys/class/backlight/intel_backlight/brightness", "50\n")
        self.escribir("sys/class/backlight/intel_backlight/max_brightness", "100\n")
        with mock.patch.object(S.hardware_mod.shutil, "which", return_value="/usr/bin/x"):
            self.assertEqual(S.detectar_retroiluminacion()["detalle"], "intel_backlight al 50 %")
            os.makedirs(os.path.join(self.raiz, "sys", "class", "net", "wlan0", "wireless"))
            self.assertEqual(S.detectar_red_inalambrica()["estado"], "compatible")
            self.escribir("sys/class/rfkill/rfkill0/type", "wlan\n")
            self.escribir("sys/class/rfkill/rfkill0/hard", "1\n")
            self.assertEqual(S.detectar_red_inalambrica()["estado"], "detectado")
            self.assertEqual(S.detectar_bluetooth()["estado"], "no_disponible")
            os.makedirs(os.path.join(self.raiz, "sys", "class", "bluetooth", "hci0"))
            self.assertEqual(S.detectar_bluetooth()["estado"], "compatible")
        self.assertEqual(S.detectar_suspension()["estado"], "error_lectura")
        self.escribir("sys/power/state", "freeze mem\n")
        self.escribir("sys/power/mem_sleep", "[s2idle] deep\n")
        self.assertEqual(S.detectar_suspension()["detalle"], "Modo s2idle")

    def test_perfiles_y_smart(self):
        self.assertEqual(S.detectar_perfiles_energia("balanced")["estado"], "compatible")
        with mock.patch.object(S.hardware_mod.shutil, "which", return_value=None):
            self.assertEqual(S.detectar_perfiles_energia(None)["estado"], "no_disponible")
        with mock.patch.object(S.hardware_mod.shutil, "which", return_value="/usr/bin/powerprofilesctl"):
            self.assertEqual(S.detectar_perfiles_energia(None)["estado"], "detectado")
        self.assertEqual(S.detectar_smart(None)["estado"], "no_disponible")
        self.assertEqual(S.detectar_smart([{"disco": "nvme0"}])["estado"], "compatible")

    def test_un_fallo_inesperado_es_error_de_lectura_de_ese_componente(self):
        with mock.patch.object(S.hardware_mod, "detectar_graficas", side_effect=RuntimeError("x")):
            doc = S.detectar_hardware()
        e = {c["id"]: c for c in doc["componentes"]}
        self.assertEqual(e["graficas"]["estado"], "error_lectura")
        self.assertIn("bateria", e)
        self.assertEqual(sum(doc["cuenta"].values()), len(doc["componentes"]))

    def test_orden_hardware(self):
        sv = S.Servicio(directorio=self.rt, estado=self.estado)
        doc = json.loads(S.procesar_linea(json.dumps({"orden": "hardware"}), sv))
        self.assertTrue(doc["ok"])
        self.assertEqual(set(doc["cuenta"]), set(S.ESTADOS_HARDWARE))
        ids = [c["id"] for c in doc["componentes"]]
        for clave in ("bateria", "cargador", "gpu_integrada", "gpu_dedicada", "temp_cpu", "ventiladores", "suspension"):
            self.assertIn(clave, ids)


if __name__ == "__main__":
    unittest.main()
