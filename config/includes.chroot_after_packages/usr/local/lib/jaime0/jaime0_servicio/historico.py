# jaime0_servicio.historico: archivos JSONL (leer, anexar, reescribir), agregados de minuto y
# de 15 minutos, huecos y la clase Historico. Depende de: base.

import collections
import datetime
import json
import math
import os
import re
import time

from .base import (
    VERSION_DATOS, INTERVALO_NORMAL, FACTOR_HUECO, RETENCION_MINUTOS, MAX_PUNTOS, MAX_EVENTOS,
    RANGOS, METRICAS, registrar
)

__all__ = [
    "leer_jsonl", "anexar_jsonl", "reescribir_jsonl", "pseudo_agregado", "combinar",
    "agregado_valido", "hueco_valido", "fusionar_duplicados", "reducir", "Historico"
]


# ---------------------------------------------------------------------------
# Historico: agregados de minuto y de 15 minutos, huecos, JSONL
# ---------------------------------------------------------------------------

def leer_jsonl(archivo):
    """Documentos (dict) de un JSONL. Las lineas rotas o vacias se ignoran."""
    docs = []
    try:
        with open(archivo, encoding="utf-8", errors="replace") as f:
            for linea in f:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    d = json.loads(linea)
                except ValueError:
                    continue
                if isinstance(d, dict):
                    docs.append(d)
    except OSError:
        pass
    return docs


def anexar_jsonl(archivo, docs):
    """Anexa lineas completas con una sola escritura. Si el archivo no termina en salto de
    linea (escritura cortada), empieza por uno para no pegarse a la linea rota."""
    if not docs:
        return
    texto = "".join(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n" for d in docs)
    prefijo = ""
    try:
        with open(archivo, "rb") as f:
            f.seek(0, os.SEEK_END)
            if f.tell() > 0:
                f.seek(-1, os.SEEK_END)
                if f.read(1) != b"\n":
                    prefijo = "\n"
    except OSError:
        pass
    with open(archivo, "a", encoding="utf-8", newline="\n") as f:
        f.write(prefijo + texto)


def reescribir_jsonl(archivo, docs):
    """Reescritura atomica (temporal y os.replace)."""
    tmp = archivo + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.replace(tmp, archivo)


def pseudo_agregado(m):
    """Una muestra como agregado de un solo punto: cada metrica [v, v, v] o None."""
    p = {"t": m["t"], "n": 1}
    for k in METRICAS:
        v = m.get(k)
        p[k] = None if v is None else [v, v, v]
    return p


def combinar(items, t0):
    """Agrega agregados (o pseudo-agregados) en uno: minimo de los minimos, media de las
    medias ponderada por n y maximo de los maximos, ignorando None (todo None -> None)."""
    out = {"v": VERSION_DATOS, "t": int(t0), "n": sum(int(i.get("n", 1)) for i in items)}
    for k in METRICAS:
        con = [i for i in items if i.get(k) is not None]
        if not con:
            out[k] = None
            continue
        pesos = [max(1, int(i.get("n", 1))) for i in con]
        media = sum(i[k][1] * p for i, p in zip(con, pesos)) / sum(pesos)
        out[k] = [round(min(i[k][0] for i in con), 2), round(media, 2), round(max(i[k][2] for i in con), 2)]
    return out


def agregado_valido(d):
    """Normaliza un agregado leido del disco; None si no sirve."""
    if not isinstance(d.get("t"), (int, float)) or isinstance(d.get("t"), bool):
        return None
    out = {"v": VERSION_DATOS, "t": int(d["t"]), "n": d["n"] if isinstance(d.get("n"), int) and d["n"] > 0 else 1}
    for k in METRICAS:
        v = d.get(k)
        ok = (isinstance(v, list) and len(v) == 3
              and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v))
        out[k] = v if ok else None
    if isinstance(d.get("eventos"), list):
        out["eventos"] = [e for e in d["eventos"] if isinstance(e, dict) and isinstance(e.get("t"), (int, float))]
    if isinstance(d.get("u"), (int, float)) and not isinstance(d.get("u"), bool):
        out["u"] = int(d["u"])
    return out


def hueco_valido(d):
    h = d.get("hueco")
    if (isinstance(h, list) and len(h) == 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in h)
            and h[0] < h[1]):
        return [int(h[0]), int(h[1])]
    return None


def fusionar_duplicados(agregados):
    """Ordena por t y une los que comparten t (un minuto cortado por una suspension)."""
    salida = []
    for a in sorted(agregados, key=lambda x: x["t"]):
        if salida and salida[-1]["t"] == a["t"]:
            previo = salida[-1]
            union = combinar([previo, a], a["t"])
            ultimas = [x["u"] for x in (previo, a) if "u" in x]
            if ultimas:
                union["u"] = max(ultimas)
            evs = previo.get("eventos", []) + a.get("eventos", [])
            if evs:
                union["eventos"] = evs
            salida[-1] = union
        else:
            salida.append(a)
    return salida


def reducir(puntos, resolucion, maximo=MAX_PUNTOS):
    """Si hay mas de `maximo` puntos, los agrupa por tiempo (min de los min, media de las
    medias, max de los max). Devuelve (puntos, resolucion)."""
    if len(puntos) <= maximo:
        return puntos, resolucion
    t0 = puntos[0]["t"]
    span = puntos[-1]["t"] - t0 + resolucion
    k = max(2, int(math.ceil(span / float(resolucion * maximo))))
    tam = resolucion * k
    grupos = collections.OrderedDict()
    for p in puntos:
        grupos.setdefault(int((p["t"] - t0) // tam), []).append(p)
    return [combinar(g, t0 + i * tam) for i, g in grupos.items()], tam


class Historico:
    """Minutos y cuartos de hora en RAM y en disco, y la lista de huecos.

    Disco (carpeta salud/): AAAA-MM-DD.jsonl con los minutos y huecos de cada dia (48 h) e
    historico.jsonl con los cuartos de hora (historial_dias). Siempre por anexado de lineas
    completas; solo historico.jsonl se reescribe (una vez al dia, para recortarlo)."""

    def __init__(self, carpeta, reloj=time.time, eventos=None, dias=90):
        self._carpeta = carpeta         # callable -> carpeta (creada si falta)
        self.reloj = reloj
        self.eventos = eventos if eventos is not None else collections.deque(maxlen=MAX_EVENTOS)
        self.dias = dias
        self.minutos, self.cuartos, self.huecos = [], [], []
        self.actual_t, self.actual = None, []
        self.cuarto_t, self.cuarto_items = None, []
        self.pend, self.pend_hist = [], []
        self.ultimo_t, self.ultimo_intervalo = None, INTERVALO_NORMAL
        self.intervalo = INTERVALO_NORMAL       # intervalo efectivo en segundo plano (ajustes)
        self.ultimo_recorte = 0

    # -- entrada -------------------------------------------------------------
    def anadir(self, m, intervalo):
        t = m["t"]
        if self.ultimo_t is not None and t - self.ultimo_t > FACTOR_HUECO * max(intervalo, self.ultimo_intervalo):
            self._hueco(self.ultimo_t, t)
        b = t - t % 60
        if self.actual_t is not None and b != self.actual_t:
            self._cerrar_minuto()
        self.actual_t = b
        self.actual.append(m)
        self.ultimo_t, self.ultimo_intervalo = t, intervalo

    def cerrar_hueco(self, ahora):
        """Al reanudar tras suspender: cierra el hueco desde la ultima muestra hasta ahora."""
        if self.ultimo_t is not None and ahora - self.ultimo_t > FACTOR_HUECO * self.ultimo_intervalo:
            self._hueco(self.ultimo_t, ahora)
            self.ultimo_t = ahora

    def _hueco(self, ini, fin):
        h = [int(ini), int(fin)]
        if h[0] >= h[1] or (self.huecos and self.huecos[-1] == h):
            return
        self.huecos.append(h)
        linea = {"v": VERSION_DATOS, "hueco": h}
        self.pend.append(linea)
        self.pend_hist.append(linea)

    def _cerrar_minuto(self):
        if not self.actual:
            self.actual_t = None
            return
        t0 = self.actual_t
        agg = combinar([pseudo_agregado(m) for m in self.actual], t0)
        # Hora de la ultima muestra real del minuto: un minuto cerrado a medias (parada,
        # suspension) no debe contar como si llegara hasta su final al buscar huecos.
        agg["u"] = int(max(m["t"] for m in self.actual))
        evs = [e for e in list(self.eventos) if t0 <= e["t"] < t0 + 60]
        if evs:
            agg["eventos"] = evs
        self.actual, self.actual_t = [], None
        self.minutos.append(agg)
        self.pend.append(agg)
        qt = t0 - t0 % 900
        if self.cuarto_t is not None and qt != self.cuarto_t:
            self._cerrar_cuarto()
        self.cuarto_t = qt
        self.cuarto_items.append(agg)

    def _cerrar_cuarto(self):
        if self.cuarto_items:
            agg = combinar(self.cuarto_items, self.cuarto_t)
            self.cuartos.append(agg)
            self.pend_hist.append(agg)
        self.cuarto_items, self.cuarto_t = [], None

    # -- disco ---------------------------------------------------------------
    @staticmethod
    def _nombre_dia(t):
        return time.strftime("%Y-%m-%d", time.localtime(t))

    def volcar(self, cerrar_parcial=False):
        """Escribe lo pendiente. cerrar_parcial (suspension, parada): cierra tambien el minuto
        y el cuarto de hora en curso. Lo que no se pueda escribir se reintenta luego."""
        if cerrar_parcial:
            self._cerrar_minuto()
            self._cerrar_cuarto()
        carpeta = self._carpeta()
        por_dia, pendiente = {}, []
        for d in self.pend:
            fin = d["hueco"][1] if "hueco" in d else d["t"]
            por_dia.setdefault(self._nombre_dia(fin), []).append(d)
        for dia, docs in por_dia.items():
            try:
                anexar_jsonl(os.path.join(carpeta, dia + ".jsonl"), docs)
            except OSError:
                pendiente += docs
                registrar("no se pudo escribir el historico de " + dia)
        self.pend = pendiente
        try:
            anexar_jsonl(os.path.join(carpeta, "historico.jsonl"), self.pend_hist)
            self.pend_hist = []
        except OSError:
            registrar("no se pudo escribir historico.jsonl")
        self._retencion(carpeta)
        return not self.pend and not self.pend_hist

    def _retencion(self, carpeta):
        ahora = self.reloj()
        limite_dia = (datetime.date.fromtimestamp(ahora) - datetime.timedelta(days=2)).isoformat()
        for nombre in os.listdir(carpeta):
            m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.jsonl", nombre)
            if m and m.group(1) < limite_dia:
                try:
                    os.remove(os.path.join(carpeta, nombre))
                except OSError:
                    pass
        self.minutos = [a for a in self.minutos if a["t"] >= ahora - RETENCION_MINUTOS]
        if ahora - self.ultimo_recorte >= 86400:
            self.recortar_historico(carpeta, ahora)

    def recortar_historico(self, carpeta, ahora):
        """Quita de historico.jsonl lo anterior a historial_dias (y las lineas rotas):
        reescritura atomica, solo si hay algo que quitar."""
        limite = ahora - int(self.dias) * 86400
        archivo = os.path.join(carpeta, "historico.jsonl")
        docs = leer_jsonl(archivo)

        def vigente(d):
            h = hueco_valido(d)
            if h:
                return h[1] >= limite
            a = agregado_valido(d)
            return a is not None and a["t"] >= limite

        quedan = [d for d in docs if vigente(d)]
        if len(quedan) != len(docs) or self._lineas(archivo) != len(docs):
            reescribir_jsonl(archivo, quedan)
        self.cuartos = [a for a in self.cuartos if a["t"] >= limite]
        self.huecos = [h for h in self.huecos if h[1] >= limite]
        self.ultimo_recorte = ahora

    @staticmethod
    def _lineas(archivo):
        try:
            with open(archivo, "rb") as f:
                return sum(1 for l in f if l.strip())
        except OSError:
            return 0

    def cargar(self):
        """Lee lo que hay en disco y, si el ultimo dato es antiguo, anota el hueco hasta ahora."""
        ahora = self.reloj()
        carpeta = self._carpeta()
        minutos, cuartos, huecos = [], [], set()
        limite_h = ahora - int(self.dias) * 86400
        for nombre in sorted(os.listdir(carpeta)):
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.jsonl", nombre):
                continue
            for d in leer_jsonl(os.path.join(carpeta, nombre)):
                h = hueco_valido(d)
                if h:
                    if h[1] >= limite_h:
                        huecos.add(tuple(h))
                    continue
                a = agregado_valido(d)
                if a and a["t"] >= ahora - RETENCION_MINUTOS:
                    minutos.append(a)
        for d in leer_jsonl(os.path.join(carpeta, "historico.jsonl")):
            h = hueco_valido(d)
            if h:
                if h[1] >= limite_h:
                    huecos.add(tuple(h))
                continue
            a = agregado_valido(d)
            if a and a["t"] >= limite_h:
                a.pop("eventos", None)
                cuartos.append(a)
        self.minutos = fusionar_duplicados(minutos)
        self.cuartos = fusionar_duplicados(cuartos)
        self.huecos = [list(h) for h in sorted(huecos)]
        ultimo = None
        if self.minutos:
            # La ultima muestra real si se conoce; si no (datos antiguos), el final del minuto.
            ultimo = max(m.get("u", m["t"] + 60) for m in self.minutos[-2:])
        elif self.cuartos:
            ultimo = self.cuartos[-1]["t"] + 900
        if ultimo is not None and ahora - ultimo > FACTOR_HUECO * self.intervalo:
            self._hueco(ultimo, ahora)

    # -- consulta ------------------------------------------------------------
    def _minuto_en_curso(self):
        return combinar([pseudo_agregado(m) for m in self.actual], self.actual_t) if self.actual else None

    def disponibilidad(self, anillo, ahora):
        def cubre(ventana, minimo):
            ts = [m["t"] for m in anillo if m["t"] >= ahora - ventana]
            return bool(ts) and max(ts) - min(ts) >= minimo

        return {"5m": cubre(300, 60), "1h": cubre(3600, 300),
                "24h": sum(1 for a in self.minutos if a["t"] >= ahora - 86400) >= 60,
                "historia": len(self.cuartos) >= 2 and self.cuartos[-1]["t"] - self.cuartos[0]["t"] >= 86400}

    def serie(self, rango, anillo, ahora):
        """Respuesta de la orden 'serie' (ver docs/control-center.md)."""
        disp = self.disponibilidad(anillo, ahora)
        if rango not in disp:
            return {"ok": False, "error": "rango no válido", "disponible": disp}
        if not disp[rango]:
            return {"ok": False, "error": "sin datos suficientes", "disponible": disp}
        solo_med = rango in ("5m", "1h")
        if solo_med:
            desde = ahora - RANGOS[rango]
            puntos = [pseudo_agregado(m) for m in anillo if m["t"] >= desde]
            difs = sorted(b["t"] - a["t"] for a, b in zip(puntos, puntos[1:]) if b["t"] > a["t"])
            resolucion = max(1, int(round(difs[len(difs) // 2]))) if difs else self.intervalo
        elif rango == "24h":
            desde, resolucion = ahora - 86400, 60
            puntos = [a for a in self.minutos if a["t"] >= desde]
            actual = self._minuto_en_curso()
            if actual:
                if puntos and puntos[-1]["t"] == actual["t"]:
                    puntos[-1] = combinar([puntos[-1], actual], actual["t"])
                else:
                    puntos.append(actual)
        else:
            puntos, resolucion = list(self.cuartos), 900
            desde = puntos[0]["t"]
        puntos, resolucion = reducir(puntos, resolucion)
        metricas = {}
        for k in METRICAS:
            col = [p.get(k) for p in puntos]
            if solo_med:
                metricas[k] = {"med": [c[1] if c else None for c in col]}
            else:
                metricas[k] = {"min": [c[0] if c else None for c in col],
                               "med": [c[1] if c else None for c in col],
                               "max": [c[2] if c else None for c in col]}
        huecos = [[max(a, int(desde)), min(b, int(ahora))] for a, b in self.huecos
                  if b > desde and a < ahora]
        vistos = {}
        fuentes = list(self.eventos) + [e for a in (self.minutos if rango != "historia" else [])
                                        for e in a.get("eventos", [])]
        for e in fuentes:
            if desde <= e["t"] <= ahora:
                vistos[(e["t"], e.get("tipo"), e.get("texto"))] = e
        eventos = [vistos[k] for k in sorted(vistos, key=lambda k: (k[0], str(k[1]), str(k[2])))]
        return {"ok": True, "v": VERSION_DATOS, "rango": rango, "resolucion": resolucion,
                "desde": int(desde), "hasta": int(ahora), "metricas": metricas,
                "t": [p["t"] for p in puntos], "huecos": huecos, "eventos": eventos, "disponible": disp}
