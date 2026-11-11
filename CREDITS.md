# Créditos y licencias

El trabajo original de este repositorio se publica bajo la licencia MIT (`LICENSE`). Jaime0 se apoya en mucho software y material ajeno, que conserva su propia licencia.

## Base

| Componente | Licencia | Enlace |
|---|---|---|
| Debian GNU/Linux (paquetes de Forky) | Varias, ver `/usr/share/doc/*/copyright` en el sistema | https://www.debian.org/ |
| live-build | GPL-3.0-or-later | https://salsa.debian.org/live-team/live-build |
| Hyprland | BSD-3-Clause | https://hypr.land/ |

## Archivos de este repositorio derivados de otros proyectos

| Archivo | Origen | Licencia |
|---|---|---|
| `config/includes.chroot_after_packages/etc/calamares/branding/hypr/calamares-sidebar.qml` | Plantilla de Calamares | GPL-3.0-or-later |
| `config/includes.chroot_after_packages/etc/calamares/branding/hypr/welcomeq.qml` | Plantilla de Calamares | GPL-3.0-or-later |
| `config/includes.chroot_after_packages/etc/calamares/branding/hypr/show.qml` | Estructura de la presentación de Calamares | GPL-3.0-or-later |
| `config/includes.chroot_after_packages/usr/share/calamares/lang/*.qm`, `usr/share/locale/es/LC_MESSAGES/calamares-python.mo` | Traducciones de Calamares con correcciones (`scripts/construir-traduccion*.py`) | GPL-3.0-or-later |
| Parche aplicado por `scripts/construir-waybar.sh` | Waybar, a partir de su `src/modules/hyprland/workspace.cpp` | MIT |

## Instalador y escritorio

| Componente | Licencia | Enlace |
|---|---|---|
| Calamares | GPL-3.0-or-later | https://calamares.io/ |
| Waybar (parcheado, versión `0.15.0-1+hypr1`) | MIT | https://github.com/Alexays/Waybar |
| Kitty | GPL-3.0-only | https://sw.kovidgoyal.net/kitty/ |
| Rofi | MIT | https://github.com/davatorium/rofi |
| Dunst | BSD-3-Clause | https://dunst-project.org/ |
| btop | Apache-2.0 | https://github.com/aristocratos/btop |
| Thunar | GPL-2.0-or-later | https://docs.xfce.org/xfce/thunar/start |
| greetd y tuigreet | GPL-3.0 | https://sr.ht/~kennylevinsen/greetd/ |
| Starship | ISC | https://starship.rs/ |
| Fastfetch | MIT | https://github.com/fastfetch-cli/fastfetch |
| Neovim | Apache-2.0 y Vim | https://neovim.io/ |

## Fuentes, iconos e imágenes

| Elemento | Autor y licencia | Enlace |
|---|---|---|
| JetBrainsMono Nerd Font (se descarga al compilar, con SHA256) | JetBrains y Nerd Fonts, SIL OFL 1.1 | https://github.com/ryanoasis/nerd-fonts |
| Papirus | Papirus Development Team, GPL-3.0 | https://github.com/PapirusDevelopmentTeam/papirus-icon-theme |
| Adwaita (cursor) | Proyecto GNOME, LGPL-3.0 o CC-BY-SA-3.0 | https://gitlab.gnome.org/GNOME/adwaita-icon-theme |

El logotipo de Jaime0 y el fondo de escritorio `jaime0.png` (generado con `scripts/generar-fondo.py`) son originales y se publican bajo la licencia MIT. Jaime0 no está afiliado al proyecto Debian ni a ningún otro de los citados.
