# Ajustes: `jaime0-ajustes`

Los ajustes visuales de Jaime0 están en un solo sitio. Se cambian con una orden y se aplican al momento, sin editar a mano la configuración de Hyprland, Waybar o rofi.

| Archivo | De quién es | Qué contiene |
|---|---|---|
| `/usr/share/jaime0/ajustes.predeterminados` | Del sistema: una ISO nueva lo sustituye | Valores de fábrica y temas de acento |
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
| `animaciones` | `no` / `sutil` / `suave` | `sutil` | Animaciones de Hyprland, notificaciones, widgets y Control Center (`si` se lee como `sutil`; en una máquina virtual Hyprland las apaga siempre). Si el escritorio pide no animar (`gsettings get org.gnome.desktop.interface enable-animations` = `false`, p. ej. desde nwg-look), notificaciones, widgets y Control Center usan `no` al entrar en la sesión. Con `sutil` nada se mueve en bucle; el barrido de la cabecera y el latido de un estado en alerta solo están con `suave` |
| `cc_intervalo` | `5` / `10` / `30` | `10` | Segundos entre medidas del Control Center en segundo plano |
| `cc_intervalo_rapido` | `1` / `2` / `5` | `2` | Segundos entre medidas con la ventana del Control Center abierta |
| `cc_notificar` | `todas` / `criticas` / `ninguna` | `criticas` | Avisos de escritorio de incidencias nuevas |
| `cc_escala` | `90` / `100` / `115` / `130` | `100` | Tamaño de toda la ventana del Control Center (texto, botones y gráficas). Si no cabe en la pantalla, se reduce lo justo (nunca por debajo del 75 %) |
| `control_atajo` | atajo | `SUPER+I` | Atajo que abre el Control Center (modificadores y una tecla) |
| `inactividad_bloqueo` | 0-120 (0 = nunca) | `10` | Minutos sin actividad hasta bloquear la sesión |
| `inactividad_pantalla` | 0-120 (0 = nunca) | `11` | Minutos sin actividad hasta apagar la pantalla |
| `inactividad_suspender` | 0-240 (0 = nunca) | `30` | Minutos sin actividad hasta suspender |
| `suspender_con_cargador` | `si` / `no` | `si` | Con `no`, no se suspende por inactividad con el cargador conectado. Los cuatro se aplican con hypridle salvo que hayas personalizado `~/.config/hypr/hypridle.conf` (ver [energia.md](energia.md)) |
| `barra_altura` | 20-48 | `26` | Altura de Waybar |
| `barra_posicion` | `arriba` / `abajo` | `arriba` | Posición de Waybar |
| `anclas` | Hasta 6 identificadores de aplicación (nombre del `.desktop`) | `kitty thunar` | Aplicaciones ancladas en el centro de la barra. Mejor con `jaime0-anclar` |
| `widget_reloj`, `widget_musica`, `widget_tiempo`, `widget_sonido`, `widget_sistema`, `widget_calendario` | `no` o `arriba-izquierda`, `arriba-centro`, `arriba-derecha`, `centro`, `abajo-izquierda`, `abajo-centro`, `abajo-derecha` | `no` | Widgets de escritorio y su posición |
| `widgets_tarjetas` | `si` / `no` | `si` | Widgets sobre una tarjeta oscura o directamente sobre el fondo |
| `reloj_formato` | `24h` / `12h` | `24h` | Formato del widget del reloj |
| `tiempo_ciudad` | Nombre de un lugar (por ejemplo `Valencia, España`) | vacía | Ciudad del widget del tiempo |

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

## Widgets de escritorio

```bash
jaime0-ajustes poner widget_reloj arriba-izquierda widget_tiempo arriba-derecha tiempo_ciudad Madrid
```

| Widget | Muestra |
|---|---|
| Reloj | Hora grande y fecha |
| Música | Carátula, título, artista, progreso y controles de cualquier reproductor MPRIS (Spotify, mpv, navegadores). Sin reproductor no se ve |
| Tiempo | Temperatura, estado, máxima y mínima de `tiempo_ciudad` |
| Volumen y brillo | Deslizadores de volumen (PipeWire) y brillo (solo si la pantalla lo permite) |
| Sistema | CPU, RAM, disco, temperatura y batería (lo que el equipo no tenga no se muestra) |
| Calendario | Mes actual, con el día de hoy en el color de acento |

Cómo funcionan:

- Vienen todos apagados: el escritorio empieza vacío y sin ningún proceso de widgets.
- Todos van en un solo proceso de Quickshell, que `jaime0-widgets` arranca solo si hay alguno activado y para si se desactivan todos. Los cambios de posición, acento, formato o tarjeta se aplican en caliente, sin reiniciar.
- Si Quickshell falla o no está instalado, el escritorio sigue igual: los widgets son lo único que no aparece.
- Están en la capa de debajo de las ventanas: no tapan nada y respetan la barra.
- **Tiempo:** `jaime0-tiempo` consulta [Open-Meteo](https://open-meteo.com/) (datos con licencia CC BY 4.0). Solo envía el nombre de la ciudad que escribas y, después, sus coordenadas; nunca la IP ni la ubicación del equipo. Consulta como mucho cada 25 minutos y, sin red, muestra el último dato de hasta 6 horas.

Consumo medido en la VM de pruebas (sesión en vivo, VirtualBox, dibujo por software):

| Widgets activos | Memoria (PSS) | CPU media en reposo (60 s) |
|---|---|---|
| Ninguno | 0 (no hay proceso) | 0 |
| Solo el reloj | 84 MB | 0,02 % |
| Los 6 (música en pausa) | 107 MB | 0,22 % |

## Límites conocidos

- El acento aún no cambia el día de hoy del calendario de la barra, swaylock (solo de respaldo), kitty, btop ni GTK: siguen en verde.
- Una altura de barra distinta de 26 mueve los módulos: `scripts/coords-barra.sh` mide a 26 px.
- Los widgets se muestran en la pantalla principal; con varios monitores no se pueden repartir entre pantallas.
- El reloj de 12 horas escribe AM/PM, sin traducir.
- Una aplicación anclada que se desinstala desaparece de la barra, pero sigue en la lista (`jaime0-anclar` la marca como no instalada) por si se vuelve a instalar.
- La aplicación se reconoce por la clase de su ventana (`StartupWMClass`, el nombre del `.desktop` o el del programa). Si alguna usa una clase distinta, el punto no aparecerá.
