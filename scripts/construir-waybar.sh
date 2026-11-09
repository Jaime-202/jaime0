#!/bin/bash
# Recompila el waybar 0.15.0-1 de Debian con los comandos de escritorio en sintaxis
# Lua, necesaria con Hyprland 0.55 o superior. Motivo: waybar 0.15.0 envia
# "dispatch workspace N", que Hyprland con Lua rechaza; el arreglo oficial
# (Alexays/Waybar#5013) aun no esta en ninguna version publicada.
#
# Uso: sudo ./construir-waybar.sh RAIZ_CHROOT_FORKY DESTINO
# Hay que ejecutarlo en un chroot de Forky desechable, con /proc montado y red.
set -eu

RAIZ="$1"
DESTINO="$2"
VERSION_LOCAL="0.15.0-1+hypr1"
TRABAJO=/tmp/waybar-build

cat > "${RAIZ}/tmp/parchear.py" <<'PY'
import sys
ruta = sys.argv[1]
texto = open(ruta).read()
cambios = [
    ('"dispatch focusworkspaceoncurrentmonitor " + std::to_string(id())',
     '"dispatch hl.dsp.focus({ workspace = " + std::to_string(id()) + ", on_current_monitor = true })"'),
    ('"dispatch workspace " + std::to_string(id())',
     '"dispatch hl.dsp.focus({ workspace = " + std::to_string(id()) + " })"'),
    ('"dispatch focusworkspaceoncurrentmonitor name:" + name()',
     '"dispatch hl.dsp.focus({ workspace = \\"name:" + name() + "\\", on_current_monitor = true })"'),
    ('"dispatch workspace name:" + name()',
     '"dispatch hl.dsp.focus({ workspace = \\"name:" + name() + "\\" })"'),
    ('"dispatch togglespecialworkspace " + name()',
     '"dispatch hl.dsp.workspace.toggle_special(\\"" + name() + "\\")"'),
    ('"dispatch togglespecialworkspace"',
     '"dispatch hl.dsp.workspace.toggle_special()"'),
]
for viejo, nuevo in cambios:
    if texto.count(viejo) != 1:
        sys.exit("No se encontro exactamente una vez: " + viejo)
    texto = texto.replace(viejo, nuevo)
open(ruta, "w").write(texto)
PY

cat > "${RAIZ}/tmp/compilar.sh" <<EOF
#!/bin/bash
set -eu
export LC_ALL=C DEBIAN_FRONTEND=noninteractive DEB_BUILD_OPTIONS="nocheck nodoc"
echo 'deb-src https://deb.debian.org/debian/ forky main' > /etc/apt/sources.list.d/fuentes.list
apt-get -qq update
apt-get -y -qq --no-install-recommends install build-essential dpkg-dev python3
apt-get -y -qq --no-install-recommends build-dep waybar
rm -rf ${TRABAJO}; mkdir -p ${TRABAJO}; cd ${TRABAJO}
apt-get -qq source waybar
cd waybar-0.15.0
python3 /tmp/parchear.py src/modules/hyprland/workspace.cpp
grep -n 'dispatch' src/modules/hyprland/workspace.cpp
{
  echo "waybar (${VERSION_LOCAL}) forky; urgency=medium"
  echo
  echo "  * Comandos de escritorio en sintaxis Lua para Hyprland 0.55 o superior."
  echo
  echo " -- Constructor local <root@localhost>  \$(date -R)"
  echo
  cat debian/changelog
} > /tmp/changelog.nuevo
mv /tmp/changelog.nuevo debian/changelog
dpkg-buildpackage -b -uc -us -j\$(nproc)
ls -la ${TRABAJO}/*.deb
rm -f /etc/apt/sources.list.d/fuentes.list
EOF

chmod +x "${RAIZ}/tmp/compilar.sh"
chroot "${RAIZ}" /tmp/compilar.sh
mkdir -p "${DESTINO}"
cp "${RAIZ}${TRABAJO}/waybar_${VERSION_LOCAL}_amd64.deb" "${DESTINO}/"
sha256sum "${DESTINO}/waybar_${VERSION_LOCAL}_amd64.deb"
