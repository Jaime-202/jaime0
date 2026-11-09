#!/bin/bash
# Comprueba sobre el chroot resultante la identidad Jaime0 y los archivos del instalador.
# Ejecutar con sudo desde ~/isolab, despues de lb build.
export LC_ALL=C
FALLOS=0; OKS=0
ok()    { echo "[OK]    $1"; OKS=$((OKS + 1)); }
fallo() { echo "[FALLO] $1"; FALLOS=$((FALLOS + 1)); }
hay()   { [ -e "chroot$1" ] && ok "$1" || fallo "falta $1"; }
tiene() { grep -q -- "$2" "chroot$1" && ok "$1 contiene: $2" || fallo "$1 sin: $2"; }

. config/includes.chroot_after_packages/usr/local/share/marca/marca.conf
[ "$PRODUCTO" = Jaime0 ] && ok "producto $PRODUCTO" || fallo "producto $PRODUCTO"

M=/etc/calamares/branding/hypr
for F in branding.desc calamares-sidebar.qml welcomeq.qml show.qml stylesheet.qss logo.svg img/check.svg img/radio.svg img/flecha.svg; do hay "$M/$F"; done
tiene "$M/branding.desc" "productName: \"$PRODUCTO\""
grep -q '@PRODUCTO@' "chroot$M/branding.desc" && fallo "branding sin sustituir" || ok "branding sustituido"
for Q in /usr/share/calamares/lang/calamares_es.qm /usr/share/calamares/lang/tz_es.qm /usr/share/locale/es/LC_MESSAGES/calamares-python.mo; do hay "$Q"; done
strings "chroot/usr/share/calamares/lang/calamares_es.qm" >/dev/null 2>&1

tiene /etc/calamares/settings.conf 'welcomeq'
tiene /etc/calamares/settings.conf 'luksbootkeyfile'
tiene /etc/calamares/modules/partition.conf 'enableLuksAutomatedPartitioning: true'
tiene /etc/calamares/modules/partition.conf 'noEncrypt: true'
tiene /etc/calamares/modules/users.conf 'doAutologin: false'
tiene /etc/calamares/modules/users.conf 'template: "jaime0"'

for P in calamares cryptsetup cryptsetup-initramfs os-prober ntfs-3g qml6-module-qtquick qml6-module-qtquick-controls; do
    chroot chroot dpkg-query -W -f='${Status}' "$P" 2>/dev/null | grep -qE " ok installed" && ok "$P" || fallo "$P no instalado"
done

tiene /usr/lib/os-release "^NAME=\"$PRODUCTO\""
tiene /usr/lib/os-release "^PRETTY_NAME=\"$PRODUCTO\""
tiene /usr/lib/os-release '^ID_LIKE=debian'
tiene /etc/issue "$PRODUCTO"
tiene /etc/default/grub.d/90-hypr.cfg "^GRUB_DISTRIBUTOR=\"$PRODUCTO\""
tiene /etc/default/grub.d/90-hypr.cfg '^GRUB_DISABLE_OS_PROBER=false'
tiene /usr/share/grub/themes/hypr/theme.txt "$PRODUCTO"
tiene /etc/greetd/config.toml "--greeting '$PRODUCTO'"
tiene /etc/calamares/modules/services-systemd.conf 'greetd.service'
grep -q 'displaymanager' chroot/etc/calamares/settings.conf && fallo "settings.conf aun usa displaymanager" || ok "settings.conf sin displaymanager (greetd se configura aparte)"
tiene /etc/calamares/modules/packages.conf 'qml6-module-qtquick'
tiene /usr/local/sbin/hypr-limpiar-vivo 'initial_session'
tiene /etc/skel/.config/hypr/hyprland.lua 'tecladoSistema'
hay /usr/share/plymouth/themes/jaime0/watermark.png
python3 -c "import sys; d=open(sys.argv[1],'rb').read(24); assert d[:8]==b'\x89PNG\r\n\x1a\n'" chroot/usr/share/plymouth/themes/jaime0/watermark.png && ok "marca de arranque PNG generada del SVG" || fallo "marca de arranque invalida"
tiene /etc/calamares/branding/hypr/logo.svg 'Jaime0'
hay /usr/local/bin/setxkbmap
[ -x chroot/usr/local/bin/setxkbmap ] && ok "setxkbmap ejecutable" || fallo "setxkbmap sin permisos"

# Identidad visible del producto
[ -f binary/boot/grub/grub.cfg ] && { grep -q "$PRODUCTO" binary/boot/grub/grub.cfg && ok "menu vivo con $PRODUCTO" || fallo "menu vivo sin $PRODUCTO"; }

echo
echo "RESULTADO: ${FALLOS} fallo(s), ${OKS} correctos"
[ "${FALLOS}" -eq 0 ]
