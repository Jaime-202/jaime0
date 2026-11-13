#!/bin/bash
# Verificacion: marca Jaime0, sistema ligero, acceso greetd, agente polkit, fondo y
# comando atajos. Ejecutar con sudo desde ~/isolab despues de lb build (o lb chroot).
# Crea un usuario de prueba en el chroot: despues hay que ejecutar lb clean.
export LC_ALL=C
FALLOS=0; OKS=0
ok()        { echo "[OK]    $1"; OKS=$((OKS + 1)); }
fallo()     { echo "[FALLO] $1"; FALLOS=$((FALLOS + 1)); }
instalado() { chroot chroot dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -qE " ok installed"; }

[ "$(id -u)" -eq 0 ] || { echo "Ejecuta con sudo."; exit 1; }
[ -d chroot/etc/apt ] || { echo "No existe ./chroot."; exit 1; }

echo "== Marca =="
. config/includes.chroot_after_packages/usr/local/share/marca/marca.conf
[ "$PRODUCTO" = "Jaime0" ] && ok "producto Jaime0" || fallo "producto: $PRODUCTO"
grep -qx 'NAME="Jaime0"' chroot/usr/lib/os-release && grep -qx 'ID=jaime0' chroot/usr/lib/os-release && grep -qx 'ID_LIKE=debian' chroot/usr/lib/os-release && ok "os-release: Jaime0, ID_LIKE=debian" || fallo "os-release: $(tr '\n' ' ' < chroot/usr/lib/os-release)"
grep -q 'hostname=jaime0' config/binary && ok "equipo en vivo: jaime0" || fallo "hostname en vivo"
grep -q 'template: "jaime0"' chroot/etc/calamares/modules/users.conf && ok "equipo instalado por defecto: jaime0" || fallo "template del equipo"
grep -q -- '--iso-volume "Jaime0"' auto/config && ok "volumen de la ISO: Jaime0" || fallo "volumen de la ISO"
grep -q 'J0' chroot/etc/calamares/branding/hypr/logo.svg && ! grep -qi 'debian' chroot/etc/calamares/branding/hypr/logo.svg && ok "logo propio J0, sin el de Debian" || fallo "logo"

echo "== Ligereza: lo que ya no esta =="
for P in sddm weston xvfb polkit-kde-agent-1 network-manager-applet nm-connection-editor udiskie qt5ct libqt5svg5 qtwayland5 libqt5core5t64; do
    instalado "$P" && fallo "$P sigue instalado" || ok "$P ausente"
done
# KDE Frameworks solo puede estar como dependencia del instalador: al quitarlo debe irse entero.
KF=$(chroot chroot dpkg-query -W -f='${Package}\n' | grep -E '^libkf[56]' | sort)
QUITA=$(chroot chroot apt-get -s purge --autoremove calamares qt6ct qt6-wayland qt6-svg-plugins libqt6svg6 $(cat config/package-lists/instalador.list.chroot config/package-lists/grafico.list.chroot | grep '^qml6-' | sort -u) 2>/dev/null | sed -n 's/^Purg \([^ ]*\).*/\1/p' | sort)
RESTO=$(comm -23 <(echo "$KF") <(echo "$QUITA") | grep -v '^$' | tr '\n' ' ')
[ -z "$RESTO" ] && ok "KDE Frameworks ($(echo "$KF" | grep -c .) paquetes) solo como dependencia del instalador: se va al instalar" || fallo "KDE Frameworks que se quedaria instalado: $RESTO"
N=$(chroot chroot dpkg-query -W -f='${Package}\n' | grep -cE '^libqt5'); [ "$N" -eq 0 ] && ok "sin Qt 5" || fallo "$N paquetes de Qt 5"
for P in greetd tuigreet lxpolkit; do instalado "$P" && ok "$P" || fallo "$P no instalado"; done

echo "== Ligereza: inicio de sesion =="
LUA=chroot/etc/skel/.config/hypr/hyprland.lua
for B in nm-applet blueman-applet "udiskie --tray"; do
    grep -q "exec_cmd(\"$B" "$LUA" && fallo "autostart con $B" || ok "sin $B en el autostart"
done
grep -q 'exec_cmd(polkitAgent)' "$LUA" && grep -q '"/usr/bin/lxpolkit"' "$LUA" && ok "autostart con lxpolkit" || fallo "autostart sin agente polkit"
grep -q 'enabled = false' "$LUA" && ok "sombras desactivadas" || fallo "sombras"
# 0.2: blur y animaciones salen de jaime0-ajustes (desenfoque, animaciones), pero en VM se
# apagan siempre, digan lo que digan los ajustes.
grep -qE '^\s*enabled\s*= ajuste\("desenfoque", sino, (true|false)\) and not esVirtual,' "$LUA" && grep -qE '^\s*enabled\s*= ajuste\("animaciones", sino, (true|false)\) and not esVirtual,' "$LUA" && ok "blur y animaciones apagados en VM (aunque los ajustes digan si)" || fallo "blur o animaciones en VM"
grep -q 'no_hardware_cursors = esVirtual' "$LUA" && ok "cursor por software en VM" || fallo "cursor en VM"

echo "== Medidas del sistema =="
N=$(chroot chroot dpkg-query -W | wc -l)
T=$(chroot chroot dpkg-query -W -f='${Installed-Size}\n' | awk '{s+=$1} END {printf "%.0f", s/1024}')
echo "MEDIDA paquetes=$N instalado_MiB=$T"
chroot chroot dpkg-query -W -f='${Installed-Size} ${Package}\n' | sort -rn | head -15 | awk '{printf "  %6.1f MiB  %s\n", $1/1024, $2}'
ok "medidas tomadas"

echo "== Acceso: greetd =="
[ "$(chroot chroot systemctl is-enabled greetd.service 2>/dev/null)" = enabled ] && ok "greetd habilitado" || fallo "greetd sin habilitar"
grep -q 'vt = 1' chroot/etc/greetd/config.toml && ok "greetd en tty1" || fallo "vt de greetd"
grep -q 'greetd.service' chroot/etc/calamares/modules/services-systemd.conf && ok "el instalador habilita greetd" || fallo "el instalador no habilita greetd"
grep -q 'initial_session' chroot/usr/lib/live/config/0086-greetd-vivo && ok "autologin solo en vivo" || fallo "sin autologin en vivo"
grep -q 'pam_env.so readenv=1 envfile=/etc/default/locale' chroot/etc/pam.d/greetd && ok "la sesion de greetd carga el idioma del sistema" || fallo "PAM de greetd sin /etc/default/locale"
grep -q 'EnvironmentFile=-/etc/default/locale' chroot/etc/systemd/system/greetd.service.d/10-idioma.conf && ok "tuigreet recibe el idioma del sistema" || fallo "greetd.service sin idioma"

echo "== Fondo =="
[ -s chroot/usr/share/backgrounds/jaime0/jaime0.png ] && ok "jaime0.png ($(du -k chroot/usr/share/backgrounds/jaime0/jaime0.png | cut -f1) KiB)" || fallo "falta el fondo"
[ -e chroot/usr/share/backgrounds/jaime0/aurora.jpg ] && fallo "queda el fondo antiguo aurora.jpg" || ok "sin el fondo antiguo"

echo "== atajos (sin sesion) =="
mount -t proc proc chroot/proc 2>/dev/null
trap 'umount chroot/proc 2>/dev/null' EXIT
A=chroot/usr/local/bin/atajos
[ -x "$A" ] && ok "atajos ejecutable" || fallo "atajos sin permiso"
chroot chroot python3 -m py_compile /usr/local/bin/atajos && ok "atajos: sintaxis Python" || fallo "atajos: sintaxis"
chroot chroot sh -c 'userdel -r atajosp 2>/dev/null; useradd -m -k /etc/skel atajosp'
U="chroot --userspec=atajosp:atajosp chroot env HOME=/home/atajosp XDG_RUNTIME_DIR=/tmp/atajosp-xdg"
mkdir -p chroot/tmp/atajosp-xdg; chown "$(chroot chroot id -u atajosp)" chroot/tmp/atajosp-xdg; chmod 700 chroot/tmp/atajosp-xdg
S=$($U atajos --help 2>&1); echo "$S" | grep -q 'atajos añadir TECLAS ORDEN DESCRIPCIÓN' && ok "atajos --help en español" || fallo "atajos --help: $(echo "$S" | head -2)"
S=$($U atajos 2>&1); [ $? -ne 0 ] && echo "$S" | grep -q 'sesión de Hyprland' && ok "sin sesion avisa en español" || fallo "sin sesion: $S"
S=$($U atajos añadir "SUPER+SHIFT" "kitty" "x" 2>&1); [ $? -ne 0 ] && echo "$S" | grep -q 'solo modificadores' && ok "rechaza teclas sin tecla normal" || fallo "teclas invalidas: $S"
S=$($U atajos añadir "SUPER+O" "kitty -e btop" "Abrir btop" 2>&1); echo "$S" | grep -q 'Añadido SUPER + O' && ok "añade SUPER+O tras verify-config" || fallo "añadir: $S"
grep -q 'atajo("SUPER + O", "kitty -e btop", "Abrir btop") -- atajos: SUPER + O' chroot/home/atajosp/.config/hypr/atajos-usuario.lua && ok "linea escrita en atajos-usuario.lua" || fallo "linea no escrita"
S=$($U Hyprland --verify-config --config /home/atajosp/.config/hypr/hyprland.lua 2>&1); echo "$S" | grep -q '^config ok' && ok "la configuracion con el atajo propio es valida" || fallo "config con atajo: $(echo "$S" | tail -2)"
S=$($U atajos anadir "super+o" "kitty" "otra" 2>&1); [ $? -eq 3 ] && ok "detecta que SUPER+O ya es propio (sin tilde: anadir)" || fallo "duplicado propio: $S"
# Un atajo que rompe la configuracion no debe aplicarse.
cp chroot/home/atajosp/.config/hypr/atajos-usuario.lua chroot/tmp/antes.lua
printf '#!/bin/sh\necho "atajo(esto no es lua" >> "$1"\n' > chroot/tmp/editor-roto.sh; chmod 755 chroot/tmp/editor-roto.sh
S=$($U EDITOR=/tmp/editor-roto.sh atajos editar 2>&1); RC=$?
cmp -s chroot/tmp/antes.lua chroot/home/atajosp/.config/hypr/atajos-usuario.lua && [ $RC -ne 0 ] && ok "control negativo: una edicion que rompe la config se rechaza y no cambia nada" || fallo "control negativo: rc=$RC $S"
rm -f chroot/tmp/editor-roto.sh
S=$($U atajos quitar "SUPER + O" 2>&1); echo "$S" | grep -q 'Quitado SUPER + O' && ! grep -q 'SUPER + O' chroot/home/atajosp/.config/hypr/atajos-usuario.lua && ok "quita SUPER+O" || fallo "quitar: $S"
S=$($U atajos quitar "SUPER+Q" 2>&1); [ $? -ne 0 ] && ok "no quita un atajo que no es propio" || fallo "quitar ajeno: $S"
chroot chroot sh -c 'userdel -r atajosp 2>/dev/null'; rm -rf chroot/tmp/atajosp-xdg chroot/tmp/antes.lua

echo
echo "RESULTADO: ${FALLOS} fallo(s), ${OKS} correctos"
[ "${FALLOS}" -eq 0 ]
