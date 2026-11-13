#!/bin/bash
# Verifica una sesion de Jaime0 en marcha (VM o equipo real), desde una terminal de la
# propia sesion:   bash verificar-sesion.sh
# Comprueba procesos, configuracion, ajustes, ancladas, widgets y notificaciones. Cambia
# un ajuste para probarlo y deja los tuyos exactamente como estaban. No bloquea la
# pantalla ni suspende el equipo.
set -u

FALLOS=0 OKS=0
ok()     { printf '[OK]    %s\n' "$*"; OKS=$((OKS + 1)); }
fallo()  { printf '[FALLO] %s\n' "$*"; FALLOS=$((FALLOS + 1)); }
info()   { printf '[INFO]  %s\n' "$*"; }
seccion() { printf '\n== %s ==\n' "$*"; }
corre()  { pgrep -x -u "$(id -u)" "$1" >/dev/null 2>&1; }

if [ -z "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]; then
    echo "Ejecútalo desde una terminal de la sesión de Hyprland." >&2
    exit 2
fi
EN_VIVO=no; [ -d /run/live/medium ] && EN_VIVO=si
CONF="${XDG_CONFIG_HOME:-$HOME/.config}"
AJUSTES="$CONF/jaime0/ajustes"
GEN="$CONF/jaime0/generado"

# Copia de los ajustes del usuario: se restauran al salir pase lo que pase.
COPIA=$(mktemp)
TENIA=no; [ -f "$AJUSTES" ] && { cp -p "$AJUSTES" "$COPIA"; TENIA=si; }
restaurar() {
    if [ "$TENIA" = si ]; then cp -p "$COPIA" "$AJUSTES"; else rm -f "$AJUSTES"; fi
    jaime0-ajustes aplicar >/dev/null 2>&1
}
trap 'restaurar; rm -f "$COPIA"' EXIT

seccion "Sistema"
info "Jaime0 $(cat /usr/share/jaime0/version 2>/dev/null || echo '?'), en vivo: $EN_VIVO, $(hyprctl version 2>/dev/null | head -n 1)"

seccion "Hyprland"
V=$(Hyprland --verify-config -c "$CONF/hypr/hyprland.lua" 2>&1 | tail -n 1)
[ "$V" = "config ok" ] && ok "hyprland.lua valido" || fallo "hyprland.lua: $V"
E=$(hyprctl configerrors 2>/dev/null | grep -v '^$')
[ -z "$E" ] && ok "sin errores de configuracion cargada" || fallo "errores de configuracion: $E"
[ "$(hyprctl getoption general:resize_on_border 2>/dev/null | head -n 1)" = "bool: true" ] && ok "redimensionar arrastrando el borde" || fallo "resize_on_border"
[ "$(hyprctl getoption misc:allow_session_lock_restore 2>/dev/null | head -n 1)" = "bool: true" ] && ok "relevo del bloqueo permitido" || fallo "allow_session_lock_restore"

seccion "Procesos de la sesion"
for P in waybar swaybg lxpolkit; do corre "$P" && ok "$P en marcha" || fallo "$P no esta en marcha"; done
if command -v swaync >/dev/null 2>&1; then
    corre swaync && ok "swaync en marcha" || fallo "swaync no esta en marcha"
    corre dunst && fallo "dunst en marcha junto a swaync" || ok "un solo sistema de notificaciones"
else
    corre dunst && ok "dunst en marcha (respaldo: swaync no esta instalado)" || fallo "sin sistema de notificaciones"
fi
pgrep -u "$(id -u)" -f '^/usr/bin/python3 -I /usr/local/bin/jaime0-anclar vigilar$' >/dev/null && ok "jaime0-anclar vigilar en marcha" || fallo "jaime0-anclar vigilar no esta en marcha"
if [ "$EN_VIVO" = si ]; then
    corre hypridle && fallo "hypridle en la sesion en vivo (no debe bloquear)" || ok "sin hypridle en vivo"
else
    corre hypridle && ok "hypridle en marcha" || fallo "hypridle no esta en marcha"
fi
systemctl --user is-active --quiet wob.socket && ok "wob.socket activo" || fallo "wob.socket inactivo"
hyprctl layers 2>/dev/null | grep -q 'namespace: waybar' && ok "capa de Waybar" || fallo "falta la capa de Waybar"

seccion "Ajustes"
for F in waybar.json waybar.css rofi.rasi swaync.css hyprlock.conf wob.ini widgets.json anclas fondo; do
    [ -s "$GEN/$F" ] || fallo "falta $GEN/$F"
done
ok "archivos generados revisados"
AV=$(jaime0-ajustes ver --json 2>/dev/null | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["avisos"]))' 2>/dev/null)
[ "$AV" = 0 ] && ok "ajustes sin avisos" || fallo "ajustes con avisos ($AV): jaime0-ajustes ver"
# Ida y vuelta: un ajuste llega a Hyprland y se restablece.
ORIGINAL=$(hyprctl getoption decoration:rounding | head -n 1 | awk '{print $2}')
PRUEBA=3; [ "$ORIGINAL" = 3 ] && PRUEBA=5
jaime0-ajustes poner esquinas "$PRUEBA" >/dev/null 2>&1; sleep 1
[ "$(hyprctl getoption decoration:rounding | head -n 1 | awk '{print $2}')" = "$PRUEBA" ] && ok "jaime0-ajustes poner llega a Hyprland" || fallo "el ajuste no llego a Hyprland"
restaurar; sleep 1
[ "$(hyprctl getoption decoration:rounding | head -n 1 | awk '{print $2}')" = "$ORIGINAL" ] && ok "ajustes restaurados" || fallo "no se restauraron las esquinas"

seccion "Aplicaciones ancladas"
N=0
for I in 1 2 3 4 5 6; do
    python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "${XDG_RUNTIME_DIR}/jaime0/anclas/$I.json" 2>/dev/null || N=$((N + 1))
done
[ "$N" -eq 0 ] && ok "estado de los 6 huecos" || fallo "$N huecos sin estado valido"
info "ancladas: $(jaime0-anclar lista 2>/dev/null | tr '\n' ' ')"

seccion "Widgets"
ACTIVOS=$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["widgets"]))' "$GEN/widgets.json" 2>/dev/null || echo 0)
QS=no; for P in $(pgrep -x -u "$(id -u)" quickshell); do tr '\0' ' ' < "/proc/$P/cmdline" | grep -q '/usr/share/jaime0/widgets/shell.qml' && QS=si; done
if [ "$ACTIVOS" -gt 0 ]; then
    [ "$QS" = si ] && ok "$ACTIVOS widget(s) activos y Quickshell en marcha" || fallo "hay widgets activos y Quickshell no esta en marcha"
else
    [ "$QS" = no ] && ok "sin widgets y sin proceso de widgets" || fallo "Quickshell de widgets en marcha sin widgets activos"
fi
if [ -n "$(jaime0-ajustes ver --json | python3 -c 'import json,sys; print([a["valor"] for a in json.load(sys.stdin)["ajustes"] if a["clave"]=="tiempo_ciudad"][0])')" ]; then
    jaime0-tiempo | python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if d["ok"] else 1)' && ok "jaime0-tiempo responde" || fallo "jaime0-tiempo sin datos (¿red?)"
else
    info "sin ciudad para el tiempo: no se prueba jaime0-tiempo"
fi

seccion "Notificaciones y sonido"
notify-send -a verificar-sesion "Prueba de Jaime0" "Notificación de verificar-sesion.sh" 2>/dev/null; sleep 1.5
hyprctl layers | grep -qE 'namespace: (swaync-notification-window|notifications)' && ok "la notificacion se muestra" || fallo "la notificacion no aparece"
command -v swaync-client >/dev/null && swaync-client --close-all --skip-wait >/dev/null 2>&1
wpctl inspect @DEFAULT_AUDIO_SINK@ >/dev/null 2>&1 && ok "salida de sonido por defecto" || fallo "sin salida de sonido"

printf '\nRESULTADO: %s fallo(s), %s correctos\n' "$FALLOS" "$OKS"
[ "$FALLOS" -eq 0 ]
