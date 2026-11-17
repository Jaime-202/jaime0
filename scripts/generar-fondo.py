#!/usr/bin/env python3
# Genera el fondo propio de ZYRON (2560x1440, PNG) de forma determinista.
#
#   python3 scripts/generar-fondo.py [destino]
#
# Destino por defecto: config/includes.chroot_after_packages/usr/share/backgrounds/jaime0/jaime0.png
# Solo necesita Python 3 y Pillow, y se ejecuta en la maquina de desarrollo: el PNG resultante
# se guarda en el repositorio, asi que la compilacion de la ISO no descarga ni instala nada.
#
# Composicion (de abajo arriba), todo con muy poco contraste:
#   1. Base negra #080b0d con un degradado radial casi imperceptible.
#   2. Malla digital: lineas cada 40 px y algo mas marcadas cada 200 px, que se apagan
#      hacia los bordes.
#   3. Unas pocas lineas geometricas finas (diagonales y dos arcos) en gris de borde.
#   4. Trazas cortas sobre la malla, como pistas de un circuito, en gris.
#   5. Puntos verdes pequenos en algunos cruces de la malla; unos pocos con un halo suave.
#   6. Marcas en cruz diminutas en algunos cruces principales.
# La semilla es fija: el resultado es siempre el mismo.

import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ANCHO, ALTO = 2560, 1440
SEMILLA = 20260
CELDA = 40           # malla fina
CELDA_MAYOR = 200    # malla principal (5 celdas)

# Paleta jaime0
NEGRO = (8, 11, 13)          # #080b0d
NEGRO_CENTRO = (12, 16, 19)  # centro del degradado, apenas mas claro que #101519
BORDE = (38, 52, 58)         # #26343a
GRIS = (113, 129, 140)       # #71818c
VERDE = (84, 229, 138)       # #54e58a

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(RAIZ, "config", "includes.chroot_after_packages", "usr", "share",
                       "backgrounds", "jaime0", "jaime0.png")


def radial(ancho, alto, cx, cy, interior, exterior, potencia=1.6):
    """Degradado radial suave: se calcula pequeno y se amplia (rapido y sin bandas)."""
    pw, ph = 320, 180
    peq = Image.new("RGB", (pw, ph))
    px = peq.load()
    rmax = math.hypot(max(cx, 1 - cx) * pw, max(cy, 1 - cy) * ph)
    for y in range(ph):
        for x in range(pw):
            d = min(1.0, math.hypot(x - cx * pw, y - cy * ph) / rmax) ** potencia
            px[x, y] = tuple(round(a + (b - a) * d) for a, b in zip(interior, exterior))
    return peq.resize((ancho, alto), Image.BICUBIC)


def mascara_radial(ancho, alto, cx, cy, centro, borde, potencia=1.4):
    """Mascara en escala de grises (0-255) para apagar capas hacia los bordes."""
    pw, ph = 320, 180
    peq = Image.new("L", (pw, ph))
    px = peq.load()
    rmax = math.hypot(max(cx, 1 - cx) * pw, max(cy, 1 - cy) * ph)
    for y in range(ph):
        for x in range(pw):
            d = min(1.0, math.hypot(x - cx * pw, y - cy * ph) / rmax) ** potencia
            px[x, y] = round(centro + (borde - centro) * d)
    return peq.resize((ancho, alto), Image.BICUBIC)


def aplicar_mascara(capa, mascara):
    r, g, b, a = capa.split()
    a = ImageChops.multiply(a, mascara)
    return Image.merge("RGBA", (r, g, b, a))


def main():
    destino = sys.argv[1] if len(sys.argv) > 1 else DESTINO
    azar = random.Random(SEMILLA)

    # 1. Base
    fondo = radial(ANCHO, ALTO, 0.42, 0.38, NEGRO_CENTRO, NEGRO).convert("RGBA")

    # 2. Malla digital
    malla = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    d = ImageDraw.Draw(malla)
    for x in range(0, ANCHO + 1, CELDA):
        alfa = 52 if x % CELDA_MAYOR == 0 else 22
        d.line([(x, 0), (x, ALTO)], fill=BORDE + (alfa,), width=1)
    for y in range(0, ALTO + 1, CELDA):
        alfa = 52 if y % CELDA_MAYOR == 0 else 22
        d.line([(0, y), (ANCHO, y)], fill=BORDE + (alfa,), width=1)
    malla = aplicar_mascara(malla, mascara_radial(ANCHO, ALTO, 0.42, 0.38, 255, 70))
    fondo = Image.alpha_composite(fondo, malla)

    # 3. Lineas geometricas finas
    geo = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    d = ImageDraw.Draw(geo)
    for x0, pendiente in ((-400, 0.58), (900, 0.58), (2300, -0.58), (3400, -0.58)):
        d.line([(x0, 0), (x0 + ALTO / pendiente, ALTO)], fill=BORDE + (70,), width=1)
    cx, cy = int(ANCHO * 0.80), int(ALTO * 0.78)
    for radio in (420, 640):
        d.arc([cx - radio, cy - radio, cx + radio, cy + radio], 180, 300, fill=BORDE + (85,), width=1)
    fondo = Image.alpha_composite(fondo, geo)

    # 4. Trazas de circuito sobre la malla fina
    trazas = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    d = ImageDraw.Draw(trazas)
    finales = []
    for _ in range(18):
        x = azar.randrange(2, ANCHO // CELDA - 2) * CELDA
        y = azar.randrange(2, ALTO // CELDA - 2) * CELDA
        puntos = [(x, y)]
        direccion = azar.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
        for _ in range(azar.randint(2, 4)):
            pasos = azar.randint(1, 4)
            x = min(max(x + direccion[0] * pasos * CELDA, CELDA), ANCHO - CELDA)
            y = min(max(y + direccion[1] * pasos * CELDA, CELDA), ALTO - CELDA)
            puntos.append((x, y))
            # Giro de 90 grados
            direccion = azar.choice(((direccion[1], direccion[0]), (-direccion[1], -direccion[0])))
        d.line(puntos, fill=BORDE + (125,), width=1)
        for px, py in (puntos[0], puntos[-1]):
            d.ellipse([px - 2, py - 2, px + 2, py + 2], outline=BORDE + (160,), width=1)
        finales.append(puntos[-1])
    fondo = Image.alpha_composite(fondo, trazas)

    # 5. Puntos verdes: casi todos tenues; algunos al final de una traza, con halo
    puntos = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    halos = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    dp = ImageDraw.Draw(puntos)
    dh = ImageDraw.Draw(halos)
    for _ in range(90):
        x = azar.randrange(1, ANCHO // CELDA) * CELDA
        y = azar.randrange(1, ALTO // CELDA) * CELDA
        r = azar.choice((1, 1, 1, 2))
        dp.ellipse([x - r, y - r, x + r, y + r], fill=VERDE + (azar.randint(40, 110),))
    for x, y in azar.sample(finales, 8):
        dp.ellipse([x - 2, y - 2, x + 2, y + 2], fill=VERDE + (210,))
        dh.ellipse([x - 9, y - 9, x + 9, y + 9], fill=VERDE + (40,))
    halos = halos.filter(ImageFilter.GaussianBlur(6))
    fondo = Image.alpha_composite(fondo, halos)
    fondo = Image.alpha_composite(fondo, puntos)

    # 6. Marcas en cruz en algunos cruces principales
    cruces = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    d = ImageDraw.Draw(cruces)
    for _ in range(12):
        x = azar.randrange(1, ANCHO // CELDA_MAYOR) * CELDA_MAYOR
        y = azar.randrange(1, ALTO // CELDA_MAYOR + 1) * CELDA_MAYOR
        d.line([(x - 5, y), (x + 5, y)], fill=GRIS + (70,), width=1)
        d.line([(x, y - 5), (x, y + 5)], fill=GRIS + (70,), width=1)
    fondo = Image.alpha_composite(fondo, cruces)

    fondo = fondo.convert("RGB")
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    fondo.save(destino, "PNG", optimize=True)
    print(f"{destino}: {fondo.size[0]}x{fondo.size[1]}, {os.path.getsize(destino) / 1024:.0f} KiB")


if __name__ == "__main__":
    main()
