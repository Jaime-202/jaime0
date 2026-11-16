#!/usr/bin/env python3
"""Integridad del repositorio (evolucion, fase 8): lo que puede romper el instalador o dejar
una ISO defectuosa sin que falle ninguna prueba de un programa concreto. Sin ISO ni VM: lee
los archivos del repositorio. Lo ejecuta GitHub Actions (scripts/validar-repo.sh).

  - Instalador: cada paso de Calamares existe y lo que ejecuta esta en la imagen; lo que
    desinstala al terminar no lo necesita nada de Jaime0.
  - Dependencias: cada programa externo que usa Jaime0 viene de un paquete de las listas.
  - Unidades de systemd propias: lo que arrancan existe.
  - Inventario: secciones del Control Center, ordenes del servicio, programas y ajustes que
    no pueden desaparecer sin que alguien lo decida (y cambie esta lista).
  - QML del Control Center: cada componente usado existe.

    python3 -m unittest discover -s pruebas -v
"""
import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
I = REPO / "config/includes.chroot_after_packages"
CALAMARES = I / "etc/calamares"
LISTAS = REPO / "config/package-lists"


def leer(p):
    return pathlib.Path(p).read_text(encoding="utf-8")


def paquetes():
    """Todos los paquetes de config/package-lists (sin comentarios)."""
    salida = set()
    for f in LISTAS.glob("*.list.chroot"):
        for linea in leer(f).splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#"):
                salida.add(linea)
    return salida


def programas():
    """Programas de Jaime0 (los que van en la imagen) con su texto."""
    salida = {}
    for carpeta in ("usr/local/bin", "usr/local/sbin", "usr/local/libexec"):
        for f in sorted((I / carpeta).iterdir()):
            if f.is_file():
                salida[str(f.relative_to(I))] = leer(f)
    for f in sorted((I / "usr/local/lib/jaime0/jaime0_servicio").glob("*.py")):
        salida[str(f.relative_to(I))] = leer(f)
    return salida


# Paquetes que siempre estan en un Debian (prioridad required/important o arrastrados por
# systemd y apt): no hace falta listarlos.
BASE = {"dpkg", "apt", "coreutils", "util-linux", "systemd", "procps", "grep", "sed", "findutils",
        "gzip", "tar", "mount", "login", "passwd", "debianutils", "bash", "dash"}

# Programa externo -> paquete que lo trae. Si un programa de Jaime0 usa uno nuevo, se anade
# aqui con su paquete (y el paquete a una lista): asi no queda una dependencia implicita.
COMANDOS = {
    "notify-send": "libnotify-bin", "swaync-client": "sway-notification-center", "hyprctl": "hyprland",
    "kitty": "kitty", "rofi": "rofi", "waybar": "waybar", "wob": "wob", "brightnessctl": "brightnessctl",
    "playerctl": "playerctl", "grim": "grim", "slurp": "slurp", "wl-copy": "wl-clipboard",
    "hyprpicker": "hyprpicker", "swaybg": "swaybg", "swaylock": "swaylock", "hyprlock": "hyprlock",
    "hypridle": "hypridle", "hyprsunset": "hyprsunset", "debsecan": "debsecan", "ufw": "ufw",
    "pkexec": "pkexec", "ss": "iproute2", "wpctl": "wireplumber", "pw-dump": "pipewire",
    "lspci": "pciutils", "lsusb": "usbutils", "smartctl": "smartmontools",
    "powerprofilesctl": "power-profiles-daemon", "nvidia-smi": "nvidia-smi", "dkms": "dkms",
    "mokutil": "mokutil", "nmcli": "network-manager", "bluetoothctl": "bluez", "btop": "btop",
    "thunar": "thunar", "nwg-displays": "nwg-displays", "cliphist": "cliphist", "snapper": "snapper",
    "cryptsetup": "cryptsetup", "quickshell": "quickshell", "journalctl": "systemd",
    "loginctl": "systemd", "systemctl": "systemd", "dpkg-query": "dpkg", "apt-get": "apt",
}
# Usados solo si existen, con un mensaje claro si faltan: no son dependencias.
OPCIONALES = {"flatpak": "Flatpak no viene en Jaime0; PRIVACY lo da como NOT APPLICABLE",
              "swayidle": "alternativa de inactividad si faltara hypridle; avisa si tampoco esta"}


class PruebasInstalador(unittest.TestCase):
    def setUp(self):
        self.settings = leer(CALAMARES / "settings.conf")

    def instancias(self):
        return dict(re.findall(r"- id: (\S+)\n\s+module: shellprocess\n\s+config: (\S+)", self.settings))

    def test_cada_paso_shellprocess_tiene_su_instancia_y_su_configuracion(self):
        usados = re.findall(r"- shellprocess@(\S+)", self.settings)
        self.assertTrue(usados)
        inst = self.instancias()
        for u in usados:
            self.assertIn(u, inst, f"shellprocess@{u} sin instancia en settings.conf")
            self.assertTrue((CALAMARES / "modules" / inst[u]).is_file(), f"falta modules/{inst[u]}")

    def test_lo_que_ejecuta_cada_paso_esta_en_la_imagen(self):
        for conf in self.instancias().values():
            for orden in re.findall(r'^\s+- "([^"]+)"', leer(CALAMARES / "modules" / conf), flags=re.M):
                programa = orden.split()[0]
                self.assertTrue(programa.startswith("/usr/local/"), f"{conf}: {programa} no es de Jaime0")
                f = I / programa.lstrip("/")
                self.assertTrue(f.is_file(), f"{conf} ejecuta {programa}, que no está en la imagen")
                self.assertTrue(leer(f).startswith("#!"), f"{programa} sin #!")

    def test_los_modulos_configurados_existen(self):
        exec_ = self.settings.split("- exec:")[1].split("- show:")[0]
        for m in re.findall(r"^\s+- (\S+)$", exec_, flags=re.M):
            if "@" in m:
                continue
            conf = CALAMARES / "modules" / f"{m}.conf"
            # Los modulos sin archivo usan la configuracion de Calamares; los que Jaime0 cambia
            # deben tener el suyo.
            if m in ("partition", "mount", "unpackfs", "fstab", "users", "services-systemd", "bootloader",
                     "packages", "plymouthcfg", "machineid", "locale"):
                self.assertTrue(conf.is_file(), f"falta modules/{m}.conf")

    def test_los_modulos_de_calamares_tienen_sus_herramientas(self):
        """Pasos de Calamares que ejecutan un programa en el sistema instalado: el paquete que lo
        trae debe estar en las listas (si no, el paso falla en silencio, como hwclock)."""
        necesita = {"hwclock": "util-linux-extra", "luksbootkeyfile": "cryptsetup",
                    "initramfs": "initramfs-tools", "grubcfg": "grub-common", "plymouthcfg": "plymouth"}
        exec_ = self.settings.split("- exec:")[1].split("- show:")[0]
        for m in re.findall(r"^\s+- (\S+)$", exec_, flags=re.M):
            if m in necesita:
                self.assertIn(necesita[m], paquetes(), f"el paso {m} necesita {necesita[m]}")

    def test_las_unidades_que_activa_vienen_de_paquetes_de_la_imagen(self):
        de = {"greetd.service": "greetd", "NetworkManager.service": "network-manager", "bluetooth.service": "bluez"}
        unidades = re.findall(r"- name: (\S+)", leer(CALAMARES / "modules/services-systemd.conf"))
        self.assertIn("greetd.service", unidades)
        for u in unidades:
            self.assertIn(u, de, f"unidad {u}: añade de qué paquete viene")
            self.assertIn(de[u], paquetes())

    def test_lo_que_desinstala_al_terminar_no_lo_usa_jaime0(self):
        quita = set(re.findall(r"^\s+- ([a-z0-9][a-z0-9.+-]*)\s*$", leer(CALAMARES / "modules/packages.conf"), flags=re.M))
        self.assertIn("calamares", quita)
        imprescindibles = {"python3", "python3-gi", "quickshell", "hyprland", "qml6-module-qtquick",
                           "qml6-module-qtquick-layouts", "greetd", "network-manager", "pipewire"}
        self.assertFalse(quita & imprescindibles, f"el instalador quita {quita & imprescindibles}")
        # Un import de QML cuyo paquete se desinstala rompe la ventana en el sistema instalado.
        modulo_de = {"QtQuick.Effects": "qml6-module-qtquick-effects",
                     "Qt5Compat.GraphicalEffects": "qml6-module-qt5compat-graphicaleffects",
                     "QtQuick.Controls": "qml6-module-qtquick-controls"}
        for f in list((I / "usr/share/jaime0").rglob("*.qml")) + list((I / "etc/skel").rglob("*.qml")):
            for imp in re.findall(r"^import ([A-Za-z0-9_.]+)", leer(f), flags=re.M):
                if modulo_de.get(imp) in quita:
                    self.fail(f"{f.relative_to(REPO)} importa {imp}, cuyo paquete desinstala el instalador")


class PruebasDependencias(unittest.TestCase):
    def test_cada_programa_externo_viene_de_un_paquete_listado(self):
        lista, textos = paquetes() | BASE, programas()
        for comando, paquete in COMANDOS.items():
            patron = re.compile(r"(?<![\w./-])" + re.escape(comando) + r"(?![\w-])")
            usado = [p for p, t in textos.items() if patron.search(t)]
            if usado:
                self.assertIn(paquete, lista, f"{comando} (usado en {usado[0]}) viene de {paquete}, que no está en las listas")

    def test_jaime0_servicio_tiene_gi(self):
        self.assertIn("python3-gi", paquetes(), "jaime0-servicio importa gi: python3-gi debe estar en una lista")

    def test_los_opcionales_avisan_si_faltan(self):
        inactividad = leer(I / "usr/local/bin/inactividad")
        self.assertIn("command -v swayidle", inactividad)
        for comando in OPCIONALES:
            self.assertNotIn(comando, paquetes(), f"{comando} está en las listas: ya no es opcional")


class PruebasUnidades(unittest.TestCase):
    def test_lo_que_arranca_cada_unidad_existe(self):
        unidades = list((I / "usr/lib/systemd").rglob("*.service")) + list((I / "etc/systemd").rglob("*.conf"))
        self.assertTrue(unidades)
        for u in unidades:
            for programa in re.findall(r"^ExecStart=-?(/\S+)", leer(u), flags=re.M):
                if programa.startswith("/usr/local/"):
                    self.assertTrue((I / programa.lstrip("/")).is_file(), f"{u.name}: falta {programa}")


class PruebasInventario(unittest.TestCase):
    """Lo que no puede desaparecer sin una decision explicita (cambiando esta lista)."""

    SECCIONES = ["SYSTEM", "PERFORMANCE", "PROFILES", "AUTOMATION", "PRIVACY & SECURITY", "HEALTH",
                 "SETTINGS", "UPDATES", "DIAGNOSTICS", "POWER"]
    VISTAS = ["Sistema", "Rendimiento", "Perfiles", "Automatizacion", "Privacidad", "Salud", "Preferencias",
              "Actualizaciones", "Diagnosticos", "Energia"]
    ORDENES = ["rapido", "estado", "instante", "serie", "incidencias", "eventos", "perfiles", "perfil",
               "perfil_anterior", "personalizado", "privacidad", "ufw_reglas", "privacidad_historial",
               "actualizaciones", "actualizaciones_comprobar", "diagnostico", "diagnostico_ejecutar",
               "diagnostico_historial", "energia", "procesos", "proceso", "hardware", "reglas", "regla_guardar",
               "reglas_importar", "regla_activar", "regla_borrar", "regla_probar", "reglas_historial", "evento"]
    PROGRAMAS = ["jaime0-servicio", "jaime0-salud", "jaime0-control", "jaime0-perfil", "jaime0-privacidad",
                 "jaime0-reglas", "jaime0-ajustes", "jaime0-update", "jaime0-diagnostico", "jaime0-nvidia",
                 "jaime0-anclar", "jaime0-widgets", "jaime0-tiempo", "jaime0-osd", "actualizaciones",
                 "inactividad", "bloquear", "prime-run", "instalar-sistema"]
    AJUSTES = ["acento", "fondo", "animaciones", "cc_intervalo", "cc_intervalo_rapido", "cc_notificar",
               "control_atajo", "umbral_temp_aviso", "umbral_bateria_aviso", "historial_dias",
               "inactividad_bloqueo", "inactividad_pantalla", "inactividad_suspender", "suspender_con_cargador"]

    def test_secciones_del_control_center(self):
        shell = leer(I / "usr/share/jaime0/control/shell.qml")
        ids = re.findall(r'\{ id: "([^"]+)", titulo:', shell)
        self.assertEqual(ids, self.SECCIONES)
        for v in self.VISTAS:
            self.assertTrue((I / f"usr/share/jaime0/control/{v}.qml").is_file(), v)
            self.assertRegex(shell, r"\b" + v + r" \{", f"shell.qml no carga {v}")

    def test_ordenes_del_servicio(self):
        api = leer(I / "usr/local/lib/jaime0/jaime0_servicio/api.py")
        atendidas = set(re.findall(r'"([a-z_]+)"', " ".join(re.findall(r"orden (?:==|in) [^:]+:", api))))
        atendidas |= {"reglas", "regla_guardar", "reglas_importar", "regla_activar", "regla_borrar",
                      "regla_probar", "reglas_historial", "evento"} if "_orden_reglas" in api else set()
        faltan = [o for o in self.ORDENES if o not in atendidas]
        self.assertEqual(faltan, [], "órdenes que ya no se atienden")

    def test_programas(self):
        for p in self.PROGRAMAS:
            self.assertTrue((I / "usr/local/bin" / p).is_file(), p)

    def test_ajustes(self):
        texto = leer(I / "usr/local/bin/jaime0-ajustes")
        predeterminados = leer(I / "usr/share/jaime0/ajustes.predeterminados")
        for a in self.AJUSTES:
            self.assertIn(f'"{a}":', texto, a)
            self.assertRegex(predeterminados, rf"(?m)^{a} = ", f"{a} sin valor en ajustes.predeterminados")


class PruebasQmlControlCenter(unittest.TestCase):
    """Cada tipo que se instancia en el Control Center es de Qt o Quickshell, un archivo de la
    carpeta o un componente definido dentro del mismo archivo."""

    DE_QT = {"Item", "Rectangle", "Text", "Column", "Row", "RowLayout", "ColumnLayout", "GridLayout", "Grid",
             "Flow", "Repeater", "Flickable", "ListView", "Timer", "TapHandler", "MouseArea", "HoverHandler",
             "Canvas", "Loader", "Component", "Connections", "NumberAnimation", "ParallelAnimation",
             "SequentialAnimation", "ColorAnimation", "PauseAnimation", "Behavior", "TextInput", "Image",
             "QtObject", "ShellRoot", "FloatingWindow", "PanelWindow", "Process", "StdioCollector",
             "SplitParser", "Socket", "FileView", "Singleton", "Scope", "Variants", "WlrLayershell", "Shortcut",
             "Keys", "Gradient", "GradientStop", "Instantiator", "PropertyAnimation", "Translate", "Scale",
             "FontMetrics", "TextMetrics", "WheelHandler", "DragHandler", "Path", "PathLine", "Shape", "ShapePath"}

    def test_componentes(self):
        carpeta = I / "usr/share/jaime0/control"
        archivos = {f.stem for f in carpeta.glob("*.qml")}
        for f in carpeta.glob("*.qml"):
            texto = leer(f)
            propios = set(re.findall(r"^\s*component (\w+)\s*:", texto, flags=re.M))
            for tipo in set(re.findall(r"^\s*([A-Z]\w+)\s*\{", texto, flags=re.M)):
                if tipo in self.DE_QT or tipo in archivos or tipo in propios:
                    continue
                self.fail(f"{f.name}: usa {tipo}, que no es de Qt ni un archivo del Control Center")


if __name__ == "__main__":
    unittest.main()
