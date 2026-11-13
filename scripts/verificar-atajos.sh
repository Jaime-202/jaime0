#!/bin/bash
# Verificacion: btop en mosaico desde la barra, cursor discreto y movimiento plano,
# atajos nuevos, bloqueo e inactividad, sin navegador en la ISO.
# Ejecutar con sudo desde ~/isolab despues de lb build (o lb chroot).
export LC_ALL=C
FALLOS=0; OKS=0
ok()        { echo "[OK]    $1"; OKS=$((OKS + 1)); }
fallo()     { echo "[FALLO] $1"; FALLOS=$((FALLOS + 1)); }
instalado() { chroot chroot dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -qE " ok installed"; }

[ "$(id -u)" -eq 0 ] || { echo "Ejecuta con sudo."; exit 1; }
[ -d chroot/etc/apt ] || { echo "No existe ./chroot."; exit 1; }
SKEL=chroot/etc/skel/.config
LUA=$SKEL/hypr/hyprland.lua
BIN=chroot/usr/local/bin

echo "== Paquetes =="
for P in hyprlock hypridle swaylock wob hyprsunset hyprpicker brightnessctl playerctl adwaita-icon-theme; do
    instalado "$P" && ok "$P instalado" || fallo "$P no instalado"
done
# 0.2: hyprlock e hypridle son el bloqueo y la inactividad (ver arriba); lo que no debe
# estar es swayidle, al que sustituye hypridle (inactividad solo lo usa si falta hypridle).
for P in swayidle brave-browser firefox-esr firefox chromium bibata-cursor-theme; do
    instalado "$P" && fallo "$P no deberia estar" || ok "$P ausente"
done

echo "== btop desde la barra =="
python3 - "$SKEL/waybar/config.jsonc" <<'PY' && ok "CPU y RAM abren abrir-btop" || fallo "on-click de CPU o RAM"
import json, re, sys
t = re.sub(r'^\s*//.*$', '', open(sys.argv[1], encoding='utf-8').read(), flags=re.M)
d = json.loads(t)
assert d['cpu']['on-click'] == 'abrir-btop' and d['memory']['on-click'] == 'abrir-btop'
PY
grep -rIq 'btop-flotante' chroot/etc/skel chroot/usr/local/bin && fallo "queda btop-flotante" || ok "sin regla ni clase btop-flotante"
[ -x $BIN/abrir-btop ] && sh -n $BIN/abrir-btop && ok "abrir-btop ejecutable y sin errores de sintaxis" || fallo "abrir-btop"
grep -q 'kitty --class btop' $BIN/abrir-btop && grep -q 'address:' $BIN/abrir-btop && ok "abrir-btop enfoca el abierto o abre uno en kitty" || fallo "abrir-btop sin enfoque"
# 0.2: ya no hay regla de opacidad por clase; la de todas las ventanas sale de jaime0-ajustes
# (opacidad_inactiva). btop tiene la misma que kitty si ninguna regla de opacidad nombra a
# kitty o btop (las que quedan solo fuerzan opacas pantalla completa, video y reproductores).
python3 - "$LUA" <<'PY' && ok "btop con la opacidad de las terminales (opacidad_inactiva, sin regla por clase)" || fallo "regla de opacidad de btop"
import re, sys
t = open(sys.argv[1], encoding='utf-8').read()
assert re.search(r'^\s*active_opacity\s*=\s*1\.0,', t, re.M)
assert re.search(r'^\s*inactive_opacity\s*=\s*ajuste\("opacidad_inactiva", decimal, 1\.0\),', t, re.M)
reglas = re.findall(r'hl\.window_rule\(\{(.*?)^\}\)', t, re.S | re.M)
assert reglas
for r in reglas:
    if re.search(r'^\s*opacity\s*=', r, re.M):
        assert not re.search(r'kitty|btop', r), r
        assert '1.0 override 1.0 override' in r, r
PY
grep -q 'match  = { class = "^(nmtui-flotante|atajos-flotante)$" }' "$LUA" && ok "btop ya no es flotante" || fallo "regla flotante-utilidades"
grep -q 'org\\\\.pulseaudio\\\\.pavucontrol|pavucontrol|blueman-manager' "$LUA" && ok "pavucontrol y blueman siguen flotantes" || fallo "regla de pavucontrol"

echo "== Cursor y raton =="
grep -q 'hl.env("XCURSOR_THEME", "Adwaita")' "$LUA" && grep -q 'hl.env("XCURSOR_SIZE", "24")' "$LUA" && ok "Hyprland: cursor Adwaita 24" || fallo "cursor en hyprland.lua"
grep -q 'HYPRCURSOR_THEME' "$LUA" && fallo "sigue HYPRCURSOR_THEME" || ok "sin tema hyprcursor (Adwaita es XCursor)"
grep -q 'accel_profile = "flat"' "$LUA" && ok "perfil de raton plano" || fallo "accel_profile"
grep -q 'no_hardware_cursors = esVirtual' "$LUA" && ok "cursor por software solo en VM" || fallo "no_hardware_cursors"
for F in gtk-3.0/settings.ini gtk-4.0/settings.ini; do grep -q 'gtk-cursor-theme-name=Adwaita' "$SKEL/$F" && ok "$F: Adwaita" || fallo "$F"; done
chroot chroot gsettings get org.gnome.desktop.interface cursor-theme 2>/dev/null | grep -q Adwaita && ok "gsettings cursor-theme Adwaita" || fallo "gsettings cursor-theme"

echo "== Atajos en la configuracion =="
for T in '" + B",              navegador' '" + Tab",            "rofi -show window"' '" + R",              "rofi -show run"' \
         '"CTRL + SHIFT + Escape",        monitorSis' '" + L",              "bloquear"' '"SHIFT + Print",                "captura pantalla"' \
         '" + Print",          "captura ventana"' '" + N",              "notificaciones panel"' '" + SHIFT + N",      "notificaciones cerrar"' '" + F2",             "modo-noche"' '" + SHIFT + C",      "hyprpicker --autocopy' \
         '" + J",            hl.dsp.layout("togglesplit")' '" + P",            hl.dsp.window.pseudo()' '" + C",            hl.dsp.window.center()' \
         '" + BackSpace",    hl.dsp.focus({ workspace = "previous" })' '" + mouse_down", hl.dsp.focus({ workspace = "e+1" })' \
         '"XF86AudioRaiseVolume",  "jaime0-osd volumen subir"' '"XF86MonBrightnessUp",   "jaime0-osd brillo subir"' '"XF86AudioNext",         "playerctl next"'; do
    grep -qF "$T" "$LUA" && ok "atajo: $T" || fallo "falta atajo: $T"
done
for S in abrir-navegador captura captura-area bloquear inactividad jaime0-osd modo-noche cancion-actual notificaciones; do
    [ -x $BIN/$S ] && sh -n $BIN/$S && ok "$S ejecutable y sin errores de sintaxis" || fallo "$S"
done
grep -q '^atajosMultimedia = {}' "$LUA" && [ "$(grep -c '^multimedia("XF86' "$LUA")" -eq 10 ] && ok "10 teclas multimedia, agrupadas en atajosMultimedia" || fallo "atajosMultimedia"
grep -q 'exec_cmd("inactividad")' "$LUA" && ok "inactividad en el autostart" || fallo "inactividad sin arrancar"
grep -q '\[ -d /run/live/medium \] && exit 0' $BIN/inactividad && ok "inactividad no bloquea la sesion en vivo" || fallo "inactividad en vivo"
grep -q 'ring-ver-color=54e58aff' $SKEL/swaylock/config && grep -q 'image=/usr/share/backgrounds/jaime0/jaime0.png' $SKEL/swaylock/config && ok "swaylock (respaldo) con tema y fondo de Jaime0" || fallo "tema de swaylock"
# Bloqueo: hyprlock sin captura de pantalla (falla con algunas graficas) y relevo a swaylock.
grep -q '^    disable_screencopy = true' $SKEL/hypr/hyprlock.conf && grep -q '^source = ~/.config/jaime0/generado/hyprlock.conf' $SKEL/hypr/hyprlock.conf && ok "hyprlock.conf sin screencopy y con acento generado" || fallo "hyprlock.conf"
grep -q 'exec swaylock' $BIN/bloquear && grep -q 'allow_session_lock_restore = true' "$LUA" && ok "bloquear pasa a swaylock si hyprlock falla" || fallo "relevo de bloqueo"
grep -q 'timeout = 600' $SKEL/hypr/hypridle.conf && grep -q 'before_sleep_cmd = loginctl lock-session || bloquear' $SKEL/hypr/hypridle.conf && grep -q 'exec hypridle' $BIN/inactividad && ok "hypridle: bloqueo a los 10 min y antes de suspender" || fallo "hypridle.conf"
[ -f chroot/etc/systemd/user/wob.service.d/10-jaime0.conf ] && ok "wob.service usa jaime0-osd" || fallo "falta el drop-in de wob"
chroot chroot python3 -m py_compile /usr/local/bin/atajos && ok "atajos: sintaxis Python" || fallo "atajos: sintaxis"
grep -q '"XF86AudioRaiseVolume": "Tecla Subir volumen"' $BIN/atajos && ok "atajos muestra nombres legibles" || fallo "atajos sin nombres legibles"
grep -q 'atajos añadir "SUPER+O"' $BIN/atajos && ok "la ayuda de atajos usa SUPER+O (SUPER+B es del sistema)" || fallo "ayuda de atajos"

echo "== Configuracion valida con el Hyprland real =="
# useradd necesita /proc para copiar /etc/skel dentro del chroot.
mountpoint -q chroot/proc || { mount -t proc proc chroot/proc; DESMONTAR=1; }
chroot chroot sh -c 'userdel -r verif12 2>/dev/null; useradd -m -k /etc/skel verif12'
[ -f chroot/home/verif12/.config/hypr/hyprland.lua ] && ok "un usuario nuevo recibe la configuracion de /etc/skel" || fallo "useradd no copio /etc/skel"
mkdir -p chroot/tmp/verif12-xdg; chown "$(chroot chroot id -u verif12)" chroot/tmp/verif12-xdg; chmod 700 chroot/tmp/verif12-xdg
S=$(chroot --userspec=verif12:verif12 chroot env HOME=/home/verif12 XDG_RUNTIME_DIR=/tmp/verif12-xdg Hyprland --verify-config --config /home/verif12/.config/hypr/hyprland.lua 2>&1)
echo "$S" | grep -q '^config ok' && ok "Hyprland --verify-config: config ok" || fallo "verify-config: $(echo "$S" | tail -3)"
chroot chroot userdel -r verif12 2>/dev/null; rm -rf chroot/tmp/verif12-xdg
[ -n "$DESMONTAR" ] && umount chroot/proc

echo
echo "RESULTADO: ${FALLOS} fallo(s), ${OKS} correctos"
[ "${FALLOS}" -eq 0 ]
