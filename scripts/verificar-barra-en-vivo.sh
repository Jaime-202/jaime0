#!/bin/bash
# Parte en vivo de verificar-barra.sh. Se ejecuta DENTRO del chroot como usuario sin
# privilegios: arranca Hyprland de verdad en la pantalla de la VM y hace clics reales.
# Requiere VM con 3D activado, seatd corriendo y wlrctl instalados en el chroot desechable,
# y /run/udev visible: sin un raton real el asiento no ofrece puntero a los clientes.
export XDG_RUNTIME_DIR=/tmp/vs4x HOME="$HOME_PRUEBA" LANG=es_ES.UTF-8 LC_ALL=C.UTF-8
export LIBSEAT_BACKEND=seatd SEATD_SOCK=/run/seatd.sock
export HYPRLAND_NO_CRASHREPORTER=1 HYPRLAND_NO_SD_NOTIFY=1
export PATH=/usr/local/bin:/usr/bin:/bin
# En el chroot no corre NetworkManager y nmtui se cerraria al instante: para probar el clic
# de la barra se usa un nmtui simulado que solo espera. El nmtui real se prueba en las VMs.
mkdir -p /tmp/vs4-falso
printf '#!/bin/sh\nsleep 60\n' > /tmp/vs4-falso/nmtui; chmod 755 /tmp/vs4-falso/nmtui
export PATH=/tmp/vs4-falso:$PATH

ok()    { echo "[OK]    $1"; }
fallo() { echo "[FALLO] $1"; }

mkdir -p "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"
cd "$HOME"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
dbus-daemon --session --address="$DBUS_SESSION_BUS_ADDRESS" --fork --nopidfile
(pipewire >/dev/null 2>&1 &)
(wireplumber >/dev/null 2>&1 &)
(pipewire-pulse >/dev/null 2>&1 &)
sleep 2

# Config real de /etc/skel. Sin --config explicito: la lee de ~/.config/hypr.
timeout 170 Hyprland > "$XDG_RUNTIME_DIR/hypr.log" 2>&1 &
sleep 15
export HYPRLAND_INSTANCE_SIGNATURE=$(ls "$XDG_RUNTIME_DIR/hypr" | head -1)
export WAYLAND_DISPLAY=$(ls "$XDG_RUNTIME_DIR" | grep -E '^wayland-[0-9]+$' | head -1)

[ -n "$HYPRLAND_INSTANCE_SIGNATURE" ] && hyprctl monitors | grep -q '^Monitor' && ok "Hyprland arranca en la VM" || fallo "Hyprland no arranca"
E=$(hyprctl configerrors | grep -v '^$' | grep -vi 'no errors' | head -3)
[ -z "$E" ] && ok "Hyprland sin errores de configuracion" || fallo "configerrors: $E"

# Escala 1: asi las coordenadas de los clics no dependen de la escala automatica.
hyprctl eval 'hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })' >/dev/null
sleep 2

# Waybar se relanza solo para capturar su log; swaync lo arranca hyprland.lua.
pkill -x waybar; sleep 1
waybar > "$XDG_RUNTIME_DIR/waybar.log" 2>&1 &
sleep 6

capas() { hyprctl layers | grep -oE 'namespace: [a-z-]+' | cut -d' ' -f2; }
. /tmp/coords-barra.sh
clientes() { hyprctl clients | grep -E '^[[:space:]]+class:' | awk '{print $2}'; }
activo() { hyprctl activeworkspace | head -1 | sed -E 's/^workspace (ID )?([0-9-]+).*/\2/'; }
clic() {
    hyprctl dispatch "hl.dsp.cursor.move({ x = $1, y = 13 })" >/dev/null
    wlrctl pointer move 1 0; wlrctl pointer move -1 0; sleep 0.5
    wlrctl pointer click left
}

capas | grep -qx waybar && ok "capa con nombre waybar" || fallo "falta la capa waybar"
pgrep -x swaync >/dev/null && ok "swaync arrancado por hyprland.lua" || fallo "swaync no arranco"
pgrep -x dunst >/dev/null && fallo "dunst en marcha junto a swaync" || ok "sin dunst"
pgrep -x nm-applet >/dev/null && fallo "nm-applet residente (debe gestionarse desde la barra)" || ok "sin nm-applet residente"
# El agente polkit necesita una sesion de logind, que el chroot no tiene: se prueba en las VMs.
grep -q "/usr/bin/lxpolkit" "$HOME/.config/hypr/hyprland.lua" && ok "hyprland.lua lanza lxpolkit (se prueba con una accion real en VM)" || fallo "hyprland.lua no lanza el agente polkit"
pgrep -x swaybg >/dev/null && ok "swaybg arrancado" || fallo "swaybg no arranco"

L="$XDG_RUNTIME_DIR/waybar.log"
grep -q 'Using configuration file .*/waybar/config.jsonc' "$L" && ok "waybar carga config.jsonc" || fallo "waybar no carga config.jsonc"
grep -q 'Using CSS file .*/waybar/style.css' "$L" && ok "waybar carga style.css" || fallo "waybar no carga style.css"
if grep -qiE 'parsing|style.css:[0-9]|config.*error' "$L"; then fallo "waybar con errores de sintaxis"; else ok "waybar sin errores de sintaxis"; fi
if grep -q 'Disabling module "clock"' "$L"; then fallo "modulo clock desactivado"; else ok "modulo clock activo"; fi
if grep -q 'Disabling module "pulseaudio"' "$L"; then fallo "modulo pulseaudio desactivado"; else ok "modulo pulseaudio activo"; fi
grep -E 'Disabling module|\[error\]' "$L" | cut -c1-150

notify-send -u normal "Prueba" "Notificación de prueba"; sleep 2
capas | grep -qx swaync-notification-window && ok "swaync muestra la notificacion" || fallo "swaync sin ventana de notificacion"
notificaciones panel; sleep 1
capas | grep -qx swaync-control-center && ok "centro de notificaciones abierto" || fallo "el centro no se abre"
notificaciones panel; sleep 1

# Clic real en un boton de escritorio: es lo que el waybar original no podia hacer.
hyprctl dispatch 'hl.dsp.focus({ workspace = 3 })' >/dev/null; sleep 1
kitty --class ventana-ws3 >/dev/null 2>&1 &
sleep 4
hyprctl dispatch 'hl.dsp.focus({ workspace = 1 })' >/dev/null; sleep 2
A=$(activo)
clic $X_ESC3; sleep 2
[ "$A" = "1" ] && [ "$(activo)" = "3" ] && ok "clic en boton de escritorio cambia de 1 a 3" || fallo "clic de escritorio: de $A a $(activo)"
grep -c 'Failed to dispatch' "$L" | grep -qx 0 && ok "waybar sin fallos de dispatch" || fallo "waybar con fallos de dispatch"
hyprctl dispatch 'hl.dsp.focus({ workspace = 1 })' >/dev/null; sleep 1
grim "$XDG_RUNTIME_DIR/s4-barra.png"

# El calendario ya no abre otro programa: es el tooltip del reloj.
hyprctl dispatch "hl.dsp.cursor.move({ x = $X_RELOJ, y = 13 })" >/dev/null
wlrctl pointer move 1 0; wlrctl pointer move -1 0; sleep 3
grim "$XDG_RUNTIME_DIR/s4-calendario.png"
clientes | grep -qi gsimplecal && fallo "sigue abriendose gsimplecal" || ok "el reloj no abre programas externos"

# btop desde CPU y RAM: ventana normal del mosaico; un segundo clic la enfoca, no abre otra
clic $X_CPU; sleep 5
clientes | grep -qx btop && ok "clic en cpu abre kitty con btop" || fallo "clic en cpu no abre btop"
hyprctl clients | grep -B8 'class: btop$' | grep -q 'floating: 0' && ok "btop en el mosaico (no flotante)" || fallo "btop flotante"
clic $X_RAM; sleep 4
[ "$(clientes | grep -cx btop)" -eq 1 ] && ok "clic en memory enfoca el btop abierto, sin abrir otro" || fallo "clic en memory abrio otro btop: $(clientes | grep -cx btop)"
pkill -x btop; sleep 2
clic $X_RAM; sleep 5
clientes | grep -qx btop && ok "clic en memory abre kitty con btop" || fallo "clic en memory no abre btop"
pkill -x btop; sleep 2

# Menu de energia desde el boton y rofi drun
clic $X_POWER; sleep 4
capas | grep -qx rofi && ok "clic en custom/power abre el menu en capa rofi" || fallo "clic en custom/power no abre rofi"
grim "$XDG_RUNTIME_DIR/s4-menu.png"
pkill -x rofi; sleep 1
rofi -show drun > "$XDG_RUNTIME_DIR/rofi.log" 2>&1 &
sleep 5
capas | grep -qx rofi && ok "rofi -show drun en Wayland, capa rofi" || fallo "rofi -show drun no aparece"
grim "$XDG_RUNTIME_DIR/s4-rofi.png"
pkill -x rofi; sleep 1
printf 'uno\ndos\n' | timeout 3 rofi -dmenu > /dev/null 2>"$XDG_RUNTIME_DIR/dmenu.log"
[ $? -eq 124 ] && ok "rofi -dmenu abre en Wayland" || fallo "rofi -dmenu fallo"
if grep -qiE 'error|failed' "$XDG_RUNTIME_DIR/rofi.log" "$XDG_RUNTIME_DIR/dmenu.log"; then fallo "rofi informa de errores"; else ok "rofi y tema sin errores"; fi

grim "$XDG_RUNTIME_DIR/s4-final.png"
clic $X_AUDIO; sleep 5
clientes | grep -qE '^(org\.pulseaudio\.)?pavucontrol$' && ok "clic en pulseaudio abre pavucontrol" || fallo "clic en pulseaudio no abre pavucontrol"
hyprctl clients | grep -B8 -E 'class: (org\.pulseaudio\.)?pavucontrol' | grep -q 'floating: 1' && ok "pavucontrol flotante" || fallo "pavucontrol no flotante"
pkill -x pavucontrol; sleep 1

# Conexion: clic en red y bandeja desplegable al pasar el raton
clic $X_RED; sleep 5
clientes | grep -qx nmtui-flotante && ok "clic en network abre nmtui flotante" || fallo "clic en network no abre nmtui: $(clientes | tr '
' ' ')"
hyprctl clients | grep -B8 'class: nmtui-flotante' | grep -q 'floating: 1' && ok "nmtui flotante" || fallo "nmtui no flotante"
pkill -f vs4-falso/nmtui; sleep 2
pgrep -x waybar >/dev/null && ok "waybar sigue vivo tras los clics" || fallo "waybar cayo"

# Cerrar sesion con el mismo comando que usa menu-energia
R=$(hyprctl dispatch 'hl.dsp.exit()')
sleep 4
[ "$R" = "ok" ] && ! pgrep -x Hyprland >/dev/null && ok "cerrar sesion con hl.dsp.exit() termina Hyprland" || fallo "cerrar sesion: respuesta '$R'"
pkill -x pipewire-pulse; pkill -x wireplumber; pkill -x pipewire; pkill -u "$(id -u)" -x dbus-daemon
