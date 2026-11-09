#!/bin/bash
# Parte en vivo de verificar-aspecto.sh. Se ejecuta DENTRO del chroot como usuario nuevo:
# arranca Hyprland de verdad en la pantalla de la VM y abre los clientes reales.
X=/tmp/vs5x
export XDG_RUNTIME_DIR=$X HOME="$HOME_PRUEBA" LANG=C.UTF-8
export LIBSEAT_BACKEND=seatd SEATD_SOCK=/run/seatd.sock
export HYPRLAND_NO_CRASHREPORTER=1 HYPRLAND_NO_SD_NOTIFY=1
export PATH=/usr/local/bin:/usr/bin:/bin
# Lo que haria el inicio de sesion real: SHELL viene de /etc/passwd, no de sudo.
export SHELL="$(getent passwd "$(id -un)" | cut -d: -f7)"
unset LIBGL_ALWAYS_SOFTWARE GSK_RENDERER

ok()   { echo "[OK]    $1"; }
fallo() { echo "[FALLO] $1"; }

chmod 700 "$X"; cd "$HOME"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$X/bus"
dbus-daemon --session --address="$DBUS_SESSION_BUS_ADDRESS" --fork --nopidfile
(pipewire >/dev/null 2>&1 &)
(wireplumber >/dev/null 2>&1 &)
(pipewire-pulse >/dev/null 2>&1 &)
sleep 2

# Config real de /etc/skel, sin --config.
timeout 330 Hyprland > "$X/hypr.log" 2>&1 &
sleep 15
export HYPRLAND_INSTANCE_SIGNATURE=$(ls "$X/hypr" | head -1)
export WAYLAND_DISPLAY=$(ls "$X" | grep -E '^wayland-[0-9]+$' | head -1)
# wlrctl escribe con un teclado virtual cuyos codigos de tecla coinciden con los de las teclas
# multimedia de la distribucion real: Hyprland ejecutaria esos atajos en vez de escribir letras.
# Se desactivan solo durante la prueba (en un teclado fisico no pasa).
hyprctl eval 'for _, b in ipairs(atajosMultimedia or {}) do b:set_enabled(false) end' >/dev/null 2>&1


[ -n "$HYPRLAND_INSTANCE_SIGNATURE" ] && hyprctl monitors | grep -q '^Monitor' && ok "Hyprland arranca en la VM" || fallo "Hyprland no arranca"
E=$(hyprctl configerrors | grep -v '^$' | grep -vi 'no errors' | head -3)
[ -z "$E" ] && ok "Hyprland sin errores de configuracion" || fallo "configerrors: $E"
hyprctl eval 'hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })' >/dev/null
sleep 2

clientes() { hyprctl clients | grep -E '^[[:space:]]+class:' | awk '{print $2}'; }
capas()    { hyprctl layers | grep -oE 'namespace: [a-z-]+' | cut -d' ' -f2; }
foto()     { grim -c "$X/$1.png"; }
muestra()  { python3 -c "import sys;from PIL import Image;i=Image.open('$X/'+sys.argv[1]+'.png').convert('RGB');print('%02x%02x%02x'%i.getpixel((int(sys.argv[2]),int(sys.argv[3]))))" "$@"; }
cerrar()   { hyprctl dispatch 'hl.dsp.window.close()' >/dev/null; sleep 2; }

echo "-- Escritorio vacio --"
# Sin sesion de logind (solo en el chroot de pruebas) lxpolkit no puede registrarse y abre un
# aviso; en una sesion real no abre nada (comprobado en VM). Solo aqui se descuenta.
if [ -z "$XDG_SESSION_ID" ]; then
    C=$(clientes | grep -vx lxpolkit | tr '\n' ' ')
else
    C=$(clientes | tr '\n' ' ')
fi
[ -z "${C// /}" ] && ok "al entrar no se abre ninguna ventana" || fallo "ventanas al entrar: $C"
foto s5-escritorio-vacio

echo "-- Fondo --"
pgrep -a swaybg | grep -q jaime0/aurora.jpg && ok "swaybg corre con el fondo" || fallo "swaybg sin el fondo: $(pgrep -a swaybg)"
capas | grep -qx wallpaper && ok "capa wallpaper presente" || fallo "falta la capa wallpaper"
foto s5-escritorio
python3 -c "
import sys
from PIL import Image
i = Image.open(sys.argv[1]).convert('RGB')
p = [i.getpixel((x, y)) for x in range(100, 1000, 200) for y in range(100, 700, 150)]
print('Tonos distintos del fondo:', len(set(p)))
sys.exit(0 if len(set(p)) >= 8 and all(b > r for r, g, b in p) else 1)
" "$X/s5-escritorio.png" && ok "el fondo tiene variedad de tonos azules" || fallo "el fondo parece un color solido o no es azul"

echo "-- Kitty --"
hyprctl dispatch 'hl.dsp.focus({ workspace = 2 })' >/dev/null; sleep 1
ACC=no; [ -r /dev/dri/renderD128 ] && [ -w /dev/dri/renderD128 ] && ACC=si
echo "Acceso a renderD128: $ACC"
[ "$ACC" = si ] && ok "el usuario tiene acceso a renderD128, como con logind" || fallo "sin acceso a renderD128: la prueba no reproduce el fallo"
# Reproduccion del fallo: sin el arreglo de sesion, con acceso a la GPU virtual.
# Se lanza por hyprctl para heredar el entorno de la sesion, quitando las dos variables.
hyprctl dispatch 'hl.dsp.exec_cmd("env -u LIBGL_ALWAYS_SOFTWARE -u GSK_RENDERER kitty --class repro-sin-arreglo > /tmp/vs5x/kitty-directo.log 2>&1")' >/dev/null
sleep 8
if clientes | grep -qx repro-sin-arreglo; then
    echo "Reproduccion kitty: SIGUE vivo sin el arreglo"; pkill -f repro-sin-arreglo
else
    echo "Reproduccion kitty: CAYO sin el arreglo: $(grep -m1 -E 'wl_surface|invalid arguments' "$X/kitty-directo.log" | cut -c1-120)"
fi
sleep 1
hyprctl dispatch 'hl.dsp.exec_cmd("env -u LIBGL_ALWAYS_SOFTWARE -u GSK_RENDERER pavucontrol > /tmp/vs5x/pavu-directo.log 2>&1")' >/dev/null
sleep 6
if clientes | grep -qE '^(org\.pulseaudio\.)?pavucontrol$'; then
    echo "Reproduccion pavucontrol: SIGUE vivo sin el arreglo"; pkill -x pavucontrol
else
    echo "Reproduccion pavucontrol: CAYO sin el arreglo: $(grep -m1 -E 'Wayland|Invalid' "$X/pavu-directo.log" | cut -c1-120)"
fi
sleep 2
pgrep -x Hyprland >/dev/null && ok "Hyprland sigue vivo tras las reproducciones" || fallo "Hyprland cayo en las reproducciones"

# SUPER+Enter real: el mismo camino que usa el usuario, con el entorno de la sesion.
hyprctl dispatch 'hl.dsp.exec_cmd("kitty > /tmp/vs5x/kitty-sesion.log 2>&1")' >/dev/null
sleep 8
clientes | grep -qx kitty && ok "kitty abre en la sesion" || fallo "kitty no abre: $(tail -2 "$X/kitty-sesion.log" | cut -c1-140)"
KP=$(pgrep -nx kitty); KE=$(tr '\0' '\n' < /proc/$KP/environ)
echo "$KE" | grep -q '^LIBGL_ALWAYS_SOFTWARE=1$' && ok "en VM, kitty hereda LIBGL_ALWAYS_SOFTWARE=1" || fallo "kitty sin LIBGL_ALWAYS_SOFTWARE"
echo "$KE" | grep -q '^GSK_RENDERER=cairo$' && ok "en VM, se hereda GSK_RENDERER=cairo" || fallo "sin GSK_RENDERER=cairo"
pgrep -x zsh >/dev/null && ok "zsh corre dentro de kitty" || fallo "kitty no abrio zsh"
sleep 2; foto s5-kitty

# Escribe de verdad en la terminal: lo que responde es la sesion interactiva real.
wlrctl keyboard type 'echo "$ZSH_VERSION|${ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE}|${+functions[_zsh_autosuggest_start]}|${ZSH_HIGHLIGHT_VERSION}|${STARSHIP_SHELL}|${KITTY_WINDOW_ID}" > /tmp/vs5x/zsh.txt'
sleep 1; wlrctl keyboard type $'\n'; sleep 3
Z=$(cat "$X/zsh.txt" 2>/dev/null); echo "Sesion zsh: $Z"
IFS='|' read -r ZV ZS ZF ZH ZST ZK <<< "$Z"
[ -n "$ZV" ] && ok "zsh interactivo responde: $ZV" || fallo "zsh no respondio"
[ "$ZS" = "fg=#565c78" ] && [ "$ZF" = 1 ] && ok "autosugerencias cargadas" || fallo "autosugerencias: '$ZS' '$ZF'"
[ -n "$ZH" ] && ok "resaltado de sintaxis cargado: $ZH" || fallo "resaltado de sintaxis no cargado"
[ "$ZST" = zsh ] && ok "starship activo" || fallo "starship: '$ZST'"
[ -n "$ZK" ] && ok "variable de kitty presente" || fallo "sin KITTY_WINDOW_ID"
# Autosugerencia y resaltado a la vista: empieza a escribir el comando anterior.
wlrctl keyboard type 'echo "$ZSH'; sleep 2; foto s5-zsh-autosugerencia
hyprctl dispatch 'hl.dsp.window.close()' >/dev/null; sleep 2

P=$(STARSHIP_SHELL= starship prompt 2>&1); echo "$P" | grep -q '❯' && ok "starship genera prompt con la config propia" || fallo "starship prompt: $P"
SAL=$(KITTY_WINDOW_ID=1 TERM=xterm-kitty zsh -ic 'exit' 2>&1 </dev/null)
echo "$SAL" | grep -q 'Hyprland' && ok "fastfetch se ejecuta con kitty interactivo" || fallo "fastfetch no salio en kitty: $(echo "$SAL" | head -3 | cut -c1-120)"
SAL=$(env -u KITTY_WINDOW_ID zsh -ic 'exit' 2>&1 </dev/null)
echo "$SAL" | grep -q 'Hyprland' && fallo "fastfetch sale fuera de kitty" || ok "fastfetch no sale fuera de kitty"
SAL=$(KITTY_WINDOW_ID=1 zsh -c 'exit' 2>&1 </dev/null)
echo "$SAL" | grep -q 'Hyprland' && fallo "fastfetch sale sin modo interactivo" || ok "fastfetch no sale sin modo interactivo"
fastfetch --config "$HOME/.config/fastfetch/config.jsonc" 2>&1 | grep -qiE 'error|invalid' && fallo "fastfetch informa de errores" || ok "fastfetch sin errores de config"

echo "-- Fastfetch y Starship --"
# Desde zsh, como en una terminal real: el modulo shell informa del proceso padre.
SAL=$(zsh -c "fastfetch --pipe; true" 2>&1)
echo "$SAL" | grep -iE "zsh|bash|sh " | head -2 | sed "s/^/Linea de shell: /"
for K in "OS" "WM" "PC" "Hyprland" "zsh" "Jaime0"; do echo "$SAL" | grep -q "$K" && ok "fastfetch muestra $K" || fallo "fastfetch sin $K"; done
N=$(echo "$SAL" | grep -c "│ ├"); [ "$N" -ge 7 ] && ok "fastfetch en arbol: $N ramas" || fallo "fastfetch sin arbol ($N)"
echo "$SAL" | grep -q "$(id -un)@" && ok "fastfetch muestra usuario@host" || fallo "fastfetch sin usuario@host"
SAL2=$(fastfetch 2>&1 | sed 's/\x1b\[[0-9;]*m//g')
echo "$SAL2" | grep -q ":ooooo:" && ok "fastfetch dibuja el logo J0" || fallo "fastfetch sin el logo J0"
D=$(STARSHIP_SHELL= starship prompt --right --status=0 2>&1); echo "$D" | sed 's/\x1b\[[0-9;]*m//g' | grep -qE '[0-9]{2}:[0-9]{2}:[0-9]{2}' && ok "starship: hora a la derecha" || fallo "starship derecha: $D"
D=$(STARSHIP_SHELL= starship prompt --right --status=1 2>&1); echo "$D" | sed 's/\x1b\[[0-9;]*m//g' | grep -q ' 1 ' && ok "starship: codigo de error a la derecha" || fallo "starship derecha con error: $D"

echo "-- Neovim --"
NV=$(nvim --headless "$X/prueba.py" -c 'lua io.stdout:write(tostring(vim.o.relativenumber).."|"..tostring(vim.o.termguicolors).."|"..vim.g.colors_name.."|"..vim.fn.synIDattr(vim.fn.hlID("Normal"),"bg").."|"..LineaEstado():sub(1,12))' -c 'qa!' 2>&1)
echo "Neovim: $(echo "$NV" | cut -c1-90)"
echo "$NV" | grep -q '^true|true|jaime0-transparente||' && ok "nvim: numeros relativos, colores y fondo transparente" || fallo "nvim: $NV"
echo "$NV" | grep -qiE 'error|E[0-9]+:' && fallo "nvim informa de errores" || ok "nvim abre sin errores"

echo "-- btop --"
hyprctl dispatch 'hl.dsp.focus({ workspace = 3 })' >/dev/null; sleep 1
hyprctl dispatch 'hl.dsp.exec_cmd("abrir-btop")' >/dev/null
sleep 7
clientes | grep -qx btop && ok "btop abre en kitty (ventana del mosaico)" || fallo "btop no abre"
foto s5-btop
pkill -x btop; sleep 2
grep -q 'jaime0' "$HOME/.config/btop/btop.conf" && ok "btop conserva el tema tras salir" || fallo "btop perdio el tema"

echo "-- GTK --"
[ "$(gsettings get org.gnome.desktop.interface gtk-theme)" = "'Adwaita-dark'" ] && ok "GSettings: Adwaita-dark" || fallo "GSettings gtk-theme"
hyprctl dispatch 'hl.dsp.focus({ workspace = 4 })' >/dev/null; sleep 1
thunar > "$X/thunar.log" 2>&1 &
sleep 7
clientes | grep -qiE '^thunar$' && ok "Thunar abre" || fallo "Thunar no abre"
foto s5-thunar
grep -iE 'gtk-warning|css|theme' "$X/thunar.log" | cut -c1-140 | head -5
grep -qiE 'gtk.css|Theme parsing error' "$X/thunar.log" && fallo "GTK3 informa de errores en gtk.css" || ok "GTK3 sin errores en gtk.css"
pkill -x thunar; pkill -x Thunar; sleep 2
hyprctl dispatch 'hl.dsp.focus({ workspace = 5 })' >/dev/null; sleep 1
hyprctl dispatch 'hl.dsp.focus({ workspace = 6 })' >/dev/null; sleep 1
hyprctl dispatch 'hl.dsp.exec_cmd("pavucontrol > /tmp/vs5x/pavu.log 2>&1")' >/dev/null
sleep 6
clientes | grep -qE '^(org\.pulseaudio\.)?pavucontrol$' && ok "pavucontrol (GTK4) abre" || fallo "pavucontrol no abre"
foto s5-pavucontrol
grep -iE 'gtk-warning|css|theme' "$X/pavu.log" | cut -c1-140 | head -5
grep -qiE 'gtk.css|Theme parsing error' "$X/pavu.log" && fallo "GTK4 informa de errores en gtk.css" || ok "GTK4 sin errores en gtk.css"
pkill -x pavucontrol; sleep 2

echo "-- Qt --"
tr '\0' '\n' < /proc/$(pgrep -x waybar | head -1)/environ | grep -E '^QT_QPA_PLATFORMTHEME|^XCURSOR_THEME|^HYPRCURSOR_THEME' | sed 's/^/Entorno de sesion: /'
hyprctl dispatch 'hl.dsp.focus({ workspace = 7 })' >/dev/null; sleep 1
for V in 6; do
    env QT_QPA_PLATFORMTHEME=qt6ct QT_QPA_PLATFORM='wayland;xcb' QT_DEBUG_PLUGINS=1 qt${V}ct > "$X/qt$V.log" 2>&1 &
    sleep 7
    clientes | grep -qiE "qt${V}ct" && ok "qt${V}ct abre como cliente Qt$V" || fallo "qt${V}ct no abre"
    grep -qE "libqt${V}ct\.so|qt${V}ct.*(loaded|Loaded)|platformthemes/libqt${V}ct" "$X/qt$V.log" && ok "Qt$V carga la plataforma qt${V}ct" || fallo "Qt$V no carga qt${V}ct"
    foto s5-qt$V
    pkill -x qt${V}ct; sleep 2
done

echo "-- Sesion --"
hyprctl dispatch 'hl.dsp.focus({ workspace = 1 })' >/dev/null; sleep 1
hyprctl dispatch 'hl.dsp.exec_cmd("kitty")' >/dev/null
sleep 6
hyprctl dispatch 'hl.dsp.exec_cmd("thunar")' >/dev/null
sleep 5
foto s5-escritorio-final
pkill -x thunar; pkill -x Thunar; pkill -x kitty; sleep 2

R=$(hyprctl dispatch 'hl.dsp.exit()'); sleep 4
[ "$R" = "ok" ] && ! pgrep -x Hyprland >/dev/null && ok "la sesion termina limpia" || fallo "cerrar sesion: '$R'"

echo "-- Camino de hardware real (detector falso: none) --"
PATH=/tmp/falso:$PATH timeout 40 Hyprland > "$X/hypr-real.log" 2>&1 &
sleep 14
SW=$(pgrep -x swaybg | head -1)
if [ -n "$SW" ]; then
    E=$(tr '\0' '\n' < /proc/$SW/environ)
    echo "$E" | grep -q '^LIBGL_ALWAYS_SOFTWARE=' && fallo "con detect-virt=none se fuerza software" || ok "con detect-virt=none no se fuerza software"
    echo "$E" | grep -q '^GSK_RENDERER=' && fallo "con detect-virt=none se fija GSK_RENDERER" || ok "con detect-virt=none no se fija GSK_RENDERER"
else
    fallo "no arranco la sesion con el detector falso"
fi
pkill -x Hyprland; sleep 4
pkill -x pipewire-pulse; pkill -x wireplumber; pkill -x pipewire; pkill -u "$(id -u)" -x dbus-daemon
exit 0
