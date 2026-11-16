# jaime0_servicio.privacidad: PRIVACY & SECURITY (cortafuegos, puertos, dispositivos, Flatpak,
# grupos, servicios, telemetria y su historial). Depende de: base, medicion (leer), historico
# (JSONL) y sistema (programa_hermano).

import glob
import ipaddress
import json
import os
import re
import subprocess
import sys
import threading
import time

from .base import VERSION_DATOS, ruta
from .medicion import leer
from .historico import leer_jsonl, anexar_jsonl, reescribir_jsonl
from .sistema import programa_hermano

__all__ = [
    "AYUDANTE_UFW", "TIMEOUT_REGLAS", "MAX_HISTORIAL_PRIVACIDAD", "DISPOSITIVOS_CADA_RAPIDO",
    "MAX_DESTINOS", "TEXTO_SIN_FLATPAK", "PALABRAS_PANTALLA", "POLITICAS_UFW",
    "POLITICAS_ESTADO_UFW", "GRUPOS_PODER", "SERVICIOS_PRIVACIDAD", "_AUTO", "parsear_conf",
    "leer_conf_ufw", "politicas_ufw", "estado_cortafuegos", "parsear_regla_ufw",
    "parsear_ufw_estado", "consultar_ufw_reglas", "separar_direccion", "direccion_expuesta",
    "parsear_ss", "puertos_expuestos", "agrupar_conexiones", "consultar_puertos",
    "_nombre_aplicacion", "_entero", "parsear_pw_dump", "camaras_en_uso", "dispositivos_en_uso",
    "info_flatpak", "nombres_de_grupos", "grupos_privilegiados", "servicios_privacidad",
    "ciudad_del_tiempo", "telemetria", "eventos_privacidad", "HistorialPrivacidad"
]


# ---------------------------------------------------------------------------
# Privacidad (Fase 5): modulo propio, separado de la salud, los perfiles y la API. Todo es
# sin root salvo leer las reglas de UFW, que solo se pide cuando el usuario lo solicita (un
# ayudante de solo lectura con pkexec). Cada consulta recibe `ejecutar` (subprocess.run, o
# uno falso en las pruebas). Nada de esto se guarda en disco salvo el historial de acciones
# relevantes (sin direcciones remotas ni datos personales). No se resuelven nombres (DNS).
# ---------------------------------------------------------------------------

AYUDANTE_UFW = "/usr/local/libexec/jaime0-ufw-estado"
TIMEOUT_REGLAS = 120                # el usuario puede tardar en escribir su contraseña
MAX_HISTORIAL_PRIVACIDAD = 300      # lineas de privacidad.jsonl
DISPOSITIVOS_CADA_RAPIDO = 10       # segundos entre consultas de dispositivos con la ventana abierta
MAX_DESTINOS = 20                   # destinos listados por proceso en las conexiones
TEXTO_SIN_FLATPAK = ("Flatpak no está instalado en Jaime0: no hay permisos por aplicación. Los programas "
                     "de Debian se ejecutan con el acceso de tu usuario (tus carpetas, tus dispositivos).")
PALABRAS_PANTALLA = ("xdph", "xdg-desktop-portal", "screencast")
POLITICAS_UFW = {"DEFAULT_INPUT_POLICY": "entrante", "DEFAULT_OUTPUT_POLICY": "saliente",
                 "DEFAULT_FORWARD_POLICY": "enrutado"}
POLITICAS_ESTADO_UFW = {"deny": "DROP", "reject": "REJECT", "allow": "ACCEPT", "disabled": "DISABLED"}
GRUPOS_PODER = (
    ("sudo", "puede ejecutar órdenes como administrador con su contraseña"),
    ("adm", "puede leer los registros del sistema"),
    ("lpadmin", "puede administrar impresoras"),
    ("docker", "equivale a ser administrador: los contenedores pueden acceder a todo el sistema"),
    ("libvirt", "puede crear y controlar máquinas virtuales"),
    ("kvm", "puede usar la virtualización por hardware"),
    ("plugdev", "puede usar dispositivos extraíbles y USB"),
    ("netdev", "puede gestionar conexiones de red"),
    ("bluetooth", "puede usar dispositivos Bluetooth"),
    ("video", "puede acceder directamente a la cámara y a la tarjeta gráfica"),
    ("audio", "puede acceder directamente al audio, incluido el micrófono"),
    ("render", "puede usar la aceleración gráfica (GPU)"),
    ("input", "puede leer directamente teclado y ratón"),
)
SERVICIOS_PRIVACIDAD = (
    ("ssh", "ssh.service", "Servidor SSH: permite la entrada remota al equipo"),
    ("avahi-daemon", "avahi-daemon.service", "Anuncia el equipo y sus servicios en la red local"),
    ("cups", "cups.service", "Servicio de impresión; puede compartir impresoras por la red"),
    ("bluetooth", "bluetooth.service", "Bluetooth: el equipo puede ser visible y aceptar conexiones cercanas"),
    ("NetworkManager", "NetworkManager.service", "Gestiona las conexiones de red (cable, Wi-Fi, VPN)"),
)
_AUTO = object()


def parsear_conf(texto):
    """CLAVE=valor de un archivo de configuracion (comentarios fuera, sin comillas)."""
    d = {}
    for linea in (texto or "").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        d[k.strip()] = v.strip().strip("\"'")
    return d


def leer_conf_ufw():
    """ufw.conf como dict, o None si UFW no esta instalado."""
    texto = leer("etc", "ufw", "ufw.conf")
    return None if texto is None else parsear_conf(texto)


def politicas_ufw():
    """Politicas por defecto de /etc/default/ufw (legible por todos): DROP, REJECT, ACCEPT o None."""
    d = parsear_conf(leer("etc", "default", "ufw"))
    return {nombre: (d[clave].upper() or None) if clave in d else None
            for clave, nombre in POLITICAS_UFW.items()}


def estado_cortafuegos(unidad_activa=None):
    """Cortafuegos sin root: lo que dicen ufw.conf, /etc/default/ufw y la unidad. Las reglas
    no se leen sin autorizacion (ver consultar_ufw_reglas)."""
    conf = leer_conf_ufw()
    if conf is None:
        return {"instalado": False, "activo": False, "unidad_activa": None, "registro": None,
                "politicas": {"entrante": None, "saliente": None, "enrutado": None}}
    return {"instalado": True,
            "activo": conf.get("ENABLED", "").lower() == "yes" and unidad_activa is True,
            "unidad_activa": unidad_activa, "registro": conf.get("LOGLEVEL") or None,
            "politicas": politicas_ufw()}


# -- reglas de UFW (con autorizacion) -------------------------------------------

def parsear_regla_ufw(linea):
    """Una linea de la tabla de 'ufw status verbose': destino, accion, origen, ipv6, comentario."""
    cuerpo, comentario = linea.strip(), ""
    m = re.match(r"^(.*?)\s+#\s?(.*)$", cuerpo)
    if m:
        cuerpo, comentario = m.group(1), m.group(2).strip()
    partes = re.split(r"\s{2,}", cuerpo)
    if len(partes) < 3:
        return None
    destino, accion, origen = partes[0], partes[1], " ".join(partes[2:])
    limpiar = lambda x: re.sub(r"\s*\((?:v6|out)\)", "", x).strip()
    return {"destino": limpiar(destino), "accion": accion.strip(), "origen": limpiar(origen),
            "ipv6": "(v6)" in destino or "(v6)" in origen, "comentario": comentario}


def parsear_ufw_estado(texto):
    """Interpreta la salida de 'ufw status verbose'. Devuelve activo, registro, politicas,
    reglas y los puertos permitidos (ALLOW y LIMIT de entrada) y bloqueados (DENY y REJECT)."""
    activo, registro = False, None
    politicas = {"entrante": None, "saliente": None, "enrutado": None}
    reglas, en_tabla = [], False
    for linea in (texto or "").splitlines():
        s = linea.strip()
        if s.lower().startswith("status:"):
            activo = s.split(":", 1)[1].strip().lower() == "active"
        elif s.lower().startswith("logging:"):
            registro = s.split(":", 1)[1].strip() or None
        elif s.lower().startswith("default:"):
            for m in re.finditer(r"([a-z]+)\s*\((incoming|outgoing|routed)\)", s.lower()):
                clave = {"incoming": "entrante", "outgoing": "saliente", "routed": "enrutado"}[m.group(2)]
                politicas[clave] = POLITICAS_ESTADO_UFW.get(m.group(1), m.group(1).upper())
        elif re.match(r"^To\s+Action\s+From", s):
            en_tabla = True
        elif en_tabla and s and not set(s) <= set("- "):
            regla = parsear_regla_ufw(linea)
            if regla:
                reglas.append(regla)
    permitidos, bloqueados = [], []
    for r in reglas:
        accion = r["accion"].upper()
        if accion.endswith((" OUT", " FWD")) or not re.match(r"^\d[\d,:]*(/(tcp|udp))?$", r["destino"]):
            continue
        lista = permitidos if accion.startswith(("ALLOW", "LIMIT")) else (
            bloqueados if accion.startswith(("DENY", "REJECT")) else None)
        if lista is not None and r["destino"] not in lista:
            lista.append(r["destino"])
    return {"ok": True, "activo": activo, "registro": registro, "politicas": politicas, "reglas": reglas,
            "puertos_permitidos": permitidos, "puertos_bloqueados": bloqueados}


def consultar_ufw_reglas(ejecutar=None):
    """Reglas de UFW con pkexec y el ayudante de solo lectura. Bloquea hasta que el usuario
    responde (hasta 120 s): hay que llamarla desde un hilo. Nunca guarda la salida."""
    ejecutar = ejecutar or subprocess.run
    try:
        r = ejecutar(["pkexec", AYUDANTE_UFW], capture_output=True, text=True, timeout=TIMEOUT_REGLAS)
    except FileNotFoundError:
        return {"ok": False, "error": "no hay agente de autorización (polkit): falta pkexec"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "se agotó el tiempo de espera de la autorización"}
    except OSError:
        return {"ok": False, "error": "no se pudo pedir la autorización"}
    if r.returncode == 126:
        return {"ok": False, "error": "autorización cancelada"}
    if r.returncode == 127:
        return {"ok": False, "error": "no hay agente de autorización (polkit)"}
    if r.returncode != 0:
        return {"ok": False, "error": f"no se pudieron leer las reglas (código {r.returncode})"}
    if "status:" not in (r.stdout or "").lower():
        return {"ok": False, "error": "respuesta inesperada de ufw"}
    return parsear_ufw_estado(r.stdout)


# -- puertos y conexiones (ss) ---------------------------------------------------

def separar_direccion(texto):
    """'127.0.0.1:631', '[::]:22', '*:8080' o '[fe80::1]%eth0:546' -> (direccion, puerto)."""
    direccion, _, puerto = texto.rpartition(":")
    if "]" in direccion:
        direccion = direccion[direccion.index("[") + 1:direccion.index("]")]
    else:
        direccion = direccion.split("%")[0]
    return direccion, int(puerto) if puerto.isdigit() else puerto


def direccion_expuesta(direccion):
    """False para bucle (127.0.0.0/8, ::1) y enlace local IPv6 (fe80::/10); True para el resto
    (incluida la direccion no especificada: 0.0.0.0, :: o *)."""
    if direccion in ("", "*", "0.0.0.0", "::"):
        return True
    try:
        ip = ipaddress.ip_address(direccion)
    except ValueError:
        return True
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if ip.is_loopback:
        return False
    return not (ip.version == 6 and ip in ipaddress.ip_network("fe80::/10"))


def parsear_ss(texto):
    """Lineas de 'ss -tulnpH' o 'ss -tunpH': protocolo, estado, direccion, puerto, remoto,
    proceso y pid (None si no es del propio usuario), expuesto (solo tiene sentido en escucha)."""
    entradas = []
    for linea in (texto or "").splitlines():
        i = linea.find("users:(")
        c = (linea if i < 0 else linea[:i]).split()
        if len(c) < 6:
            continue
        proceso = pid = None
        if i >= 0:
            m = re.search(r'\("((?:[^"\\]|\\.)*)",pid=(\d+)', linea[i:])
            if m:
                proceso, pid = m.group(1), int(m.group(2))
        direccion, puerto = separar_direccion(c[4])
        entradas.append({"protocolo": c[0], "estado": c[1], "direccion": direccion, "puerto": puerto,
                         "remoto": c[5], "proceso": proceso, "pid": pid,
                         "expuesto": direccion_expuesta(direccion)})
    return entradas


def puertos_expuestos(puertos):
    """{(puerto, protocolo): proceso} de los puertos en escucha abiertos a la red."""
    d = {}
    for p in puertos or []:
        if p.get("expuesto"):
            clave = (p["puerto"], p["protocolo"])
            if d.get(clave) is None:
                d[clave] = p.get("proceso")
    return d


def agrupar_conexiones(entradas):
    """Conexiones establecidas agrupadas por proceso: numero y destinos (direccion:puerto).
    Sin proceso visible (de otros usuarios) van juntas con proceso None."""
    grupos = {}
    for e in entradas:
        if e["estado"] in ("LISTEN", "UNCONN"):
            continue
        g = grupos.setdefault(e["proceso"], {"proceso": e["proceso"], "pid": e["pid"],
                                             "conexiones": 0, "destinos": []})
        g["conexiones"] += 1
        if e["remoto"] not in g["destinos"] and len(g["destinos"]) < MAX_DESTINOS:
            g["destinos"].append(e["remoto"])
    return sorted(grupos.values(), key=lambda g: (-g["conexiones"], g["proceso"] or ""))


def consultar_puertos(ejecutar=None):
    """(puertos_en_escucha, conexiones_por_proceso); cada uno None si ss no responde."""
    ejecutar = ejecutar or subprocess.run

    def ss(argumento):
        try:
            r = ejecutar(["ss", argumento], capture_output=True, text=True, timeout=3)
            return parsear_ss(r.stdout) if r.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    escucha = ss("-tulnpH")
    establecidas = ss("-tunpH")
    return escucha, None if establecidas is None else agrupar_conexiones(establecidas)


# -- dispositivos en uso (PipeWire y /proc) --------------------------------------

def _nombre_aplicacion(props):
    return (props.get("application.name") or props.get("application.process.binary")
            or props.get("node.name") or "desconocida")


def _entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def parsear_pw_dump(texto):
    """Micrófono y captura de pantalla en uso a partir del JSON de pw-dump; None si no es JSON
    de pw-dump. Solo cuentan los nodos en marcha (info.state == 'running')."""
    try:
        objetos = json.loads(texto)
    except (TypeError, ValueError):
        return None
    if not isinstance(objetos, list):
        return None
    microfono, pantalla = [], []
    for o in objetos:
        if not isinstance(o, dict) or not isinstance(o.get("info"), dict):
            continue
        info = o["info"]
        props = info.get("props")
        if not isinstance(props, dict) or info.get("state") != "running":
            continue
        clase = props.get("media.class")
        if clase == "Stream/Input/Audio":
            e = {"aplicacion": _nombre_aplicacion(props), "pid": _entero(props.get("application.process.id"))}
            if e not in microfono:
                microfono.append(e)
        elif clase in ("Video/Source", "Stream/Input/Video"):
            nombres = f"{props.get('node.name', '')} {props.get('application.name', '')}".lower()
            if props.get("media.role") == "Screen" or any(p in nombres for p in PALABRAS_PANTALLA):
                e = {"aplicacion": _nombre_aplicacion(props)}
                if e not in pantalla:
                    pantalla.append(e)
    return {"microfono": microfono, "pantalla": pantalla}


def camaras_en_uso(leer_enlace=os.readlink):
    """Procesos con un descriptor abierto a /dev/video*: recorre /proc/[pid]/fd (solo los del
    propio usuario son legibles; el resto se salta)."""
    salida = []
    for carpeta in sorted(glob.glob(ruta("proc", "[0-9]*", "fd"))):
        pid = os.path.basename(os.path.dirname(carpeta))
        try:
            fds = os.listdir(carpeta)
        except OSError:
            continue
        for fd in fds:
            try:
                destino = leer_enlace(os.path.join(carpeta, fd))
            except OSError:
                continue
            if destino.startswith("/dev/video"):
                nombre = (leer("proc", pid, "comm") or "").strip() or "desconocida"
                e = {"aplicacion": nombre, "pid": int(pid), "dispositivo": destino}
                if e not in salida:
                    salida.append(e)
    return salida


def dispositivos_en_uso(ejecutar=None, leer_enlace=os.readlink):
    """{"microfono", "camara", "pantalla"}; microfono y pantalla son None si pw-dump no esta."""
    ejecutar = ejecutar or subprocess.run
    pw = None
    try:
        r = ejecutar(["pw-dump"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            pw = parsear_pw_dump(r.stdout)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {"microfono": pw["microfono"] if pw else None, "camara": camaras_en_uso(leer_enlace),
            "pantalla": pw["pantalla"] if pw else None}


# -- aplicaciones y privilegios ---------------------------------------------------

def info_flatpak(ejecutar=None):
    """Flatpak solo lectura: aplicaciones y permisos. Sin Flatpak, UNAVAILABLE con la explicacion."""
    if not os.path.exists(ruta("usr", "bin", "flatpak")):
        return {"estado": "UNAVAILABLE", "texto": TEXTO_SIN_FLATPAK}
    ejecutar = ejecutar or subprocess.run
    try:
        r = ejecutar(["flatpak", "list", "--app", "--columns=application"],
                     capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            raise OSError("flatpak list")
        apps = []
        for app in [l.strip() for l in r.stdout.splitlines() if l.strip()][:50]:
            p = ejecutar(["flatpak", "info", "--show-permissions", app],
                         capture_output=True, text=True, timeout=10)
            apps.append({"aplicacion": app,
                         "permisos": [l.rstrip() for l in p.stdout.splitlines() if l.strip()]
                         if p.returncode == 0 else None})
        return {"estado": "AVAILABLE", "aplicaciones": apps}
    except (OSError, subprocess.TimeoutExpired):
        return {"estado": "UNAVAILABLE", "texto": "No se pudieron consultar las aplicaciones de Flatpak"}


def nombres_de_grupos():
    """Nombres de los grupos del usuario (os.getgrouplist); lista vacia si no se puede."""
    try:
        import grp
        import pwd
        usuario = pwd.getpwuid(os.getuid())
        return [grp.getgrgid(g).gr_name for g in os.getgrouplist(usuario.pw_name, usuario.pw_gid)]
    except (ImportError, AttributeError, KeyError, OSError):
        return []


def grupos_privilegiados(nombres=None):
    """Grupos con poder a los que pertenece el usuario, cada uno con su explicacion."""
    nombres = set(nombres_de_grupos() if nombres is None else nombres)
    return [{"grupo": g, "texto": f"{g}: {t}"} for g, t in GRUPOS_PODER if g in nombres]


def servicios_privacidad(ejecutar=None):
    """Servicios relacionados con la privacidad: activo, inactivo o no instalado."""
    ejecutar = ejecutar or subprocess.run
    salida = []
    for nombre, unidad, texto in SERVICIOS_PRIVACIDAD:
        estado = "desconocido"
        try:
            r = ejecutar(["systemctl", "show", "-p", "LoadState", "-p", "ActiveState", unidad],
                         capture_output=True, text=True, timeout=3)
            d = dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)
            if d.get("LoadState") == "not-found":
                estado = "no instalado"
            elif d.get("ActiveState") == "active":
                estado = "activo"
            elif d.get("ActiveState"):
                estado = "inactivo"
        except (OSError, subprocess.TimeoutExpired):
            pass
        salida.append({"nombre": nombre, "estado": estado,
                       "texto": "No instalado en este sistema" if estado == "no instalado" else texto})
    return salida


def ciudad_del_tiempo(ejecutar=None):
    """tiempo_ciudad de jaime0-ajustes (cadena, posiblemente vacia) o None si no se pudo leer."""
    ejecutar = ejecutar or subprocess.run
    try:
        programa = programa_hermano("jaime0-ajustes")
        if not programa:
            return None
        r = ejecutar([sys.executable, "-I", programa, "ver", "--json"],
                     capture_output=True, text=True, timeout=5)
        for a in (json.loads(r.stdout) if r.returncode == 0 else {}).get("ajustes") or []:
            if isinstance(a, dict) and a.get("clave") == "tiempo_ciudad":
                return str(a.get("valor") or "").strip()
    except (OSError, ValueError, subprocess.TimeoutExpired, AttributeError):
        pass
    return None


def telemetria(ejecutar=None, ciudad=_AUTO):
    """Comprobaciones reales, sin red, de lo que podria enviar datos fuera del equipo.
    ciudad: la de los ajustes (se lee con jaime0-ajustes si no se da); None = no se pudo leer."""
    ejecutar = ejecutar or subprocess.run
    lista = [{"elemento": "Jaime0", "estado": "NINGUNA", "texto": "Sin telemetría: nada sale del equipo"}]
    instalado = False
    try:
        r = ejecutar(["dpkg-query", "-W", "-f=${Status}", "popularity-contest"],
                     capture_output=True, text=True, timeout=5)
        instalado = r.returncode == 0 and "install ok installed" in (r.stdout or "")
    except (OSError, subprocess.TimeoutExpired):
        pass
    if not instalado:
        lista.append({"elemento": "popularity-contest", "estado": "NO INSTALADO",
                      "texto": "No instalado: no se envían estadísticas de paquetes a Debian"})
    elif parsear_conf(leer("etc", "popularity-contest.conf")).get("PARTICIPATE", "").lower() == "yes":
        lista.append({"elemento": "popularity-contest", "estado": "ACTIVO",
                      "texto": "Instalado y participando: envía a Debian estadísticas de paquetes"})
    else:
        lista.append({"elemento": "popularity-contest", "estado": "INACTIVO",
                      "texto": "Instalado pero sin participar: no envía nada"})
    if any(os.path.exists(ruta("usr", d, "debsecan")) for d in ("bin", "sbin")):
        lista.append({"elemento": "debsecan", "estado": "INSTALADO",
                      "texto": "Consulta la lista pública de vulnerabilidades de Debian "
                               "(security-tracker.debian.org); no envía datos del equipo"})
    else:
        lista.append({"elemento": "debsecan", "estado": "NO INSTALADO", "texto": "No instalado"})
    if ciudad is _AUTO:
        ciudad = ciudad_del_tiempo(ejecutar)
    if ciudad is None:
        lista.append({"elemento": "Widget del tiempo", "estado": "DESCONOCIDO",
                      "texto": "No se pudo leer el ajuste de la ciudad"})
    elif ciudad:
        lista.append({"elemento": "Widget del tiempo", "estado": "ACTIVO",
                      "texto": "Conecta con Open-Meteo con la ciudad que escribiste"})
    else:
        lista.append({"elemento": "Widget del tiempo", "estado": "INACTIVO",
                      "texto": "Sin ciudad configurada: no se conecta a ningún servicio"})
    if any(os.path.exists(ruta(*p)) for p in (("usr", "bin", "brave-browser"), ("usr", "bin", "brave"),
                                              ("opt", "brave.com", "brave", "brave"))):
        lista.append({"elemento": "Brave", "estado": "INSTALADO",
                      "texto": "Tiene sus propias opciones de privacidad y estadísticas (P3A): "
                               "revísalas en brave://settings/privacy"})
    else:
        lista.append({"elemento": "Brave", "estado": "NO INSTALADO", "texto": "No instalado"})
    return lista


# -- historial de acciones relevantes ----------------------------------------------

def eventos_privacidad(antes, ahora):
    """Cambios relevantes entre dos instantaneas (lista de (tipo, texto)). Una clave que falta
    en `antes` es la primera lectura: no genera eventos. Sin direcciones remotas."""
    ev = []
    a, b = (antes or {}).get("fw"), (ahora or {}).get("fw")
    if a is not None and b is not None:
        if a["activo"] != b["activo"]:
            ev.append(("cortafuegos", "Cortafuegos activado" if b["activo"] else "Cortafuegos desactivado"))
        for clave in ("entrante", "saliente", "enrutado"):
            if a["politicas"].get(clave) != b["politicas"].get(clave):
                ev.append(("cortafuegos", f"Política {clave} del cortafuegos: "
                                          f"{a['politicas'].get(clave) or 'N/D'} → {b['politicas'].get(clave) or 'N/D'}"))
    a, b = (antes or {}).get("puertos"), (ahora or {}).get("puertos")
    if a is not None and b is not None:
        def puerto(clave, proceso):
            return f"{clave[0]}/{clave[1]} ({proceso or 'proceso no identificado'})"
        for clave in sorted(set(b) - set(a), key=str):
            ev.append(("puerto", f"Puerto expuesto: {puerto(clave, b[clave])}"))
        for clave in sorted(set(a) - set(b), key=str):
            ev.append(("puerto", f"Puerto ya no expuesto: {puerto(clave, a[clave])}"))
    textos = {"microfono": ("Micrófono: {} empieza a usarlo", "Micrófono: {} deja de usarlo"),
              "camara": ("Cámara: {} empieza a usarla", "Cámara: {} deja de usarla"),
              "pantalla": ("Captura de pantalla: {} empieza a capturar", "Captura de pantalla: {} deja de capturar")}
    for tipo, (inicio, fin) in textos.items():
        a, b = (antes or {}).get(tipo), (ahora or {}).get(tipo)
        if a is not None and b is not None:
            ev += [(tipo, inicio.format(x)) for x in sorted(b - a)]
            ev += [(tipo, fin.format(x)) for x in sorted(a - b)]
    return ev


class HistorialPrivacidad:
    """privacidad.jsonl: {"v":1,"t","tipo","texto"}, recortado a `maximo` lineas."""

    def __init__(self, archivo, maximo=MAX_HISTORIAL_PRIVACIDAD, reloj=time.time):
        self.archivo, self.maximo, self.reloj = archivo, maximo, reloj
        self.n = None
        self.cerrojo = threading.Lock()

    def anotar(self, tipo, texto):
        with self.cerrojo:
            archivo = self.archivo()
            anexar_jsonl(archivo, [{"v": VERSION_DATOS, "t": int(self.reloj()), "tipo": tipo, "texto": texto}])
            self.n = (len(leer_jsonl(archivo)) if self.n is None else self.n + 1)
            if self.n > self.maximo:
                docs = leer_jsonl(archivo)[-self.maximo:]
                reescribir_jsonl(archivo, docs)
                self.n = len(docs)

    def ultimos(self, limite):
        """Los `limite` mas recientes, el ultimo primero."""
        with self.cerrojo:
            return [d for d in leer_jsonl(self.archivo()) if "texto" in d][-limite:][::-1]
