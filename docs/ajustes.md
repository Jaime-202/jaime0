# Ajustes: `jaime0-ajustes`

Los ajustes visuales de Jaime0 están en un solo sitio. Se cambian con una orden y se aplican al momento, sin editar a mano la configuración de Hyprland, Waybar o rofi.

| Archivo | De quién es | Qué contiene |
|---|---|---|
| `/usr/share/jaime0/ajustes.predeterminados` | Del sistema: `jaime0-update` lo sustituye | Valores de fábrica y temas de acento |
| `~/.config/jaime0/ajustes` | Tuyo: ninguna actualización lo toca | Solo lo que has cambiado |
| `~/.config/jaime0/generado/` | Se rehace siempre | Lo que leen Waybar (`waybar.json`, `waybar.css`) y rofi (`rofi.rasi`). No lo edites |

Hyprland lee los dos primeros directamente desde `~/.config/hypr/hyprland.lua`. Un valor mal escrito a mano se ignora y se usa el predeterminado, así que un error nunca impide abrir la sesión.

## Uso

```bash
jaime0-ajustes ver
```
```bash
jaime0-ajustes poner acento cian
```
```bash
jaime0-ajustes poner esquinas 6 borde 1
```
```bash
jaime0-ajustes restablecer acento
```

| Orden | Para qué |
|---|---|
| `jaime0-ajustes` | Abre la aplicación de ajustes; si no está disponible, muestra la lista |
| `jaime0-ajustes ver [--json]` | Ajustes actuales; `*` marca los que has cambiado |
| `jaime0-ajustes poner CLAVE VALOR [...]` | Cambia uno o varios ajustes y los aplica. Si un valor no es válido, no cambia ninguno |
| `jaime0-ajustes restablecer CLAVE [...]` / `--todo` | Vuelve al valor predeterminado |
| `jaime0-ajustes aplicar` | Aplica lo que hayas editado a mano en `~/.config/jaime0/ajustes` |

Al aplicar, se recarga Hyprland (`hyprctl reload`), Waybar relee su configuración (señal `USR2`) y, si cambia el fondo, se reinicia `swaybg`. Si el fondo elegido no existe, se mantiene el que hay.

## Aplicación de ajustes

`jaime0-ajustes` sin argumentos abre una ventana hecha con Quickshell (`/usr/share/jaime0/ajustes-gui/`). Llama a las mismas órdenes `ver --json`, `poner` y `restablecer`, así que valida igual y muestra el error si un valor no sirve. Los deslizadores aplican al soltar. Si cambias algo desde la terminal, la ventana se actualiza sola. Se cierra con `Escape`.

- Se dibuja por software (`QT_QUICK_BACKEND=software`): es una ventana pequeña, gasta menos memoria y funciona en máquinas virtuales donde OpenGL de Quickshell falla.
- Consumo medido en la VM de pruebas (sesión en vivo, VirtualBox): unos 83 MB (PSS) con la ventana abierta y casi 0 % de CPU en reposo. Abre en unos 250 ms. Cerrada no consume nada: no queda ningún proceso.
- Quickshell no es imprescindible. Si falta, `jaime0-ajustes` muestra la lista y se usa desde la terminal.

## Ajustes disponibles

| Clave | Valores | Predeterminado | Afecta a |
|---|---|---|---|
| `acento` | `verde`, `cian`, `azul`, `violeta`, `ambar`, `rosa` o `#rrggbb` | `verde` | Borde de la ventana activa, logo, escritorio activo y campana de la barra, selección de rofi, centro de notificaciones, campo de la pantalla de bloqueo e indicador de volumen y brillo |
| `fondo` | Ruta a una imagen PNG o JPEG | `/usr/share/backgrounds/jaime0/jaime0.png` | Fondo de escritorio y, difuminado, de la pantalla de bloqueo |
| `separacion_interior` | 0-40 | `4` | Hueco entre ventanas |
| `separacion_exterior` | 0-60 | `8` | Margen con el borde de la pantalla |
| `borde` | 0-6 | `2` | Grosor del borde de las ventanas |
| `esquinas` | 0-20 | `8` | Redondeo de las ventanas |
| `opacidad_inactiva` | 0.6-1.0 | `1.0` | Opacidad de las ventanas sin foco. Pantalla completa y vídeo siempre opacos |
| `desenfoque` | `si` / `no` | `si` | Blur detrás de lo translúcido: kitty, rofi y notificaciones (en una máquina virtual, siempre apagado) |
| `animaciones` | `si` / `no` | `si` | Animaciones de Hyprland (en una máquina virtual, siempre apagadas) |
| `barra_altura` | 20-48 | `26` | Altura de Waybar |
| `barra_posicion` | `arriba` / `abajo` | `arriba` | Posición de Waybar |
| `anclas` | Hasta 6 identificadores de aplicación (nombre del `.desktop`) | `kitty thunar` | Aplicaciones ancladas en el centro de la barra. Mejor con `jaime0-anclar` |

Los fondos que ofrece la aplicación son los de `/usr/share/backgrounds/jaime0` y los que pongas en `~/.local/share/backgrounds`.

## Aplicaciones ancladas

```bash
jaime0-anclar firefox
```

| Orden | Para qué |
|---|---|
| `jaime0-anclar APLICACIÓN` | La ancla al final. Acepta el nombre corto (`firefox` → `firefox-esr`, `pavucontrol` → `org.pulseaudio.pavucontrol`) |
| `jaime0-anclar quitar APLICACIÓN` | La quita |
| `jaime0-anclar mover APLICACIÓN POSICIÓN` | La cambia de sitio (1 = la primera) |
| `jaime0-anclar` / `lista [--json]` | Las ancladas, en orden |
| `jaime0-anclar disponibles [--json]` | Las que se pueden anclar (`*` = anclada) |
| `jaime0-anclar abrir N` | Lo que hace la barra al pulsar: enfoca la ventana; si ya tiene el foco y hay varias, pasa a la siguiente; si no está abierta, la inicia |

Cómo funciona, sin sondeo:

- La lista es el ajuste `anclas`. Se guarda en `~/.config/jaime0/ajustes` y ninguna actualización la toca.
- `jaime0-anclar vigilar` arranca con la sesión y escucha los eventos de Hyprland: abrir, cerrar y cambiar el foco de una ventana. Con ellos escribe el estado de los 6 huecos en `$XDG_RUNTIME_DIR/jaime0/anclas/` y avisa a Waybar con la señal 9. Cada hueco solo lee su archivo.
- Si `vigilar` no está en marcha, los iconos siguen abriendo y enfocando; solo el punto deja de actualizarse.
- Las aplicaciones de terminal, como `btop`, se abren en Kitty con su propia clase de ventana, para no confundirlas con Kitty.
- Iconos monocromos de la fuente Nerd Font, como el resto de la barra. Se eligen por el nombre de la aplicación o, si no se conoce, por su categoría.
- Consumo medido en la VM de pruebas: `vigilar` ocupa unos 15 MB (PSS) y no gasta CPU en reposo.

## Límites conocidos

- El acento aún no cambia el día de hoy del calendario de la barra, swaylock (solo de respaldo), kitty, btop ni GTK: siguen en verde.
- Si modificaste a mano `~/.config/hypr/hyprland.lua`, `~/.config/waybar/*` o `~/.config/rofi/jaime0.rasi` antes de la 0.2, `jaime0-update` conserva tu versión (conflicto) y los ajustes no tendrán efecto en ese programa hasta que aceptes la nueva (`jaime0-update resolver RUTA --usar-nueva`).
- Una altura de barra distinta de 26 mueve los módulos: `scripts/coords-barra.sh` mide a 26 px.
- Una aplicación anclada que se desinstala desaparece de la barra, pero sigue en la lista (`jaime0-anclar` la marca como no instalada) por si se vuelve a instalar.
- La aplicación se reconoce por la clase de su ventana (`StartupWMClass`, el nombre del `.desktop` o el del programa). Si alguna usa una clase distinta, el punto no aparecerá.
