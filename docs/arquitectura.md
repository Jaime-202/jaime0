# Arquitectura de Jaime0

## Base

| Pieza | Elección |
|---|---|
| Distribución base | Debian Forky (testing), amd64 |
| Construcción | live-build (`auto/config`): `debootstrap --variant=minbase`, sin paquetes recomendados, ISO híbrida BIOS + UEFI con Secure Boot (shim firmado por Debian) |
| Paquetes | APT de Debian. Preferencias en `config/archives/`: sin Xorg ni otros escritorios, Waybar parcheado fijado |
| Escritorio | Hyprland 0.56/0.57 con configuración **Lua** (`hyprland.lua`), Waybar, rofi, dunst, kitty, swaylock/swayidle |
| Acceso | greetd + tuigreet en la consola (`iniciar-sesion` lanza Hyprland y explica el fallo si no abre) |
| Instalador | Calamares con marca propia; se retira al instalar (`hypr-limpiar-vivo`) |
| Sonido, red | PipeWire + WirePlumber, NetworkManager (`nmtui` desde la barra), BlueZ + blueman |
| Actualizaciones | `jaime0-update` (componentes propios, firmados) + `apt` (paquetes) |

## Flujo de construcción

```
auto/config ──> lb config
auto/build  ──> empaquetar-actualizacion.py --manifiesto-iso   (manifiesto de la versión)
            └─> lb build
                 ├─ config/package-lists/*.list.chroot         paquetes
                 ├─ config/includes.chroot_after_packages/     archivos propios (fuente única)
                 ├─ config/hooks/normal/*.hook.chroot          ajustes en el chroot
                 └─ config/hooks/normal/*.hook.binary          menú de arranque del medio
scripts/verificar-*.sh                                         comprobaciones sobre chroot/
```

## Fuente única de componentes y versiones

`config/includes.chroot_after_packages/` es la fuente de todo lo propio de Jaime0, tanto para la ISO como para las actualizaciones:

```
usr/share/jaime0/version ──┬─> ISO: /etc/os-release (VERSION, VERSION_ID), manifiesto de partida
                           └─> scripts/empaquetar-actualizacion.py ─> GitHub Release vVERSIÓN
                                    manifiesto.json (+ .sig Ed25519) + jaime0-VERSIÓN.tar.gz
                                                      │
                     sistema instalado: jaime0-update ┘  (verifica, compara y aplica)
```

Las reglas de qué rutas se gestionan, los componentes y el orden de versiones están solo en `jaime0-update`. El script de empaquetado carga ese mismo archivo como módulo, así que no hay dos listas que mantener.

Componentes del manifiesto:

| Componente | Rutas |
|---|---|
| `escritorio` | `etc/skel/**`, que se copia a cada usuario |
| `herramientas` | `usr/local/bin/**` |
| `temas` | `usr/share/backgrounds/jaime0`, `usr/share/grub/themes`, `usr/share/qt6ct` |
| `sistema` | `etc/default/grub.d`, `etc/fonts`, `etc/systemd`, `etc/jaime0`, `usr/lib/systemd/user`, `usr/share/jaime0`, `usr/share/glib-2.0/schemas`, `usr/local/share/marca` |

Fuera de las actualizaciones quedan los archivos que solo existen en el medio vivo (Calamares, live-config, `instalar-sistema`, `setxkbmap`) y `etc/greetd/config.toml`, que el instalador modifica.

Detalles del actualizador: [actualizaciones.md](actualizaciones.md).

## Decisiones

| Decisión | Motivo |
|---|---|
| Componentes propios en un tar firmado, no en un `.deb` | Un `.deb` necesitaría un repositorio APT propio firmado y su mantenimiento, y `dpkg` trataría cada archivo de `/etc/skel` como conffile sin poder fusionar con el `~/.config` de cada usuario. El tar + manifiesto permite la fusión a tres bandas por usuario con muy poco código |
| Firma Ed25519 verificada con `openssl` | `openssl` ya llega a la ISO (dependencia de `ca-certificates`); no añade dependencias. GPG sería más pesado de manejar para una sola clave |
| Python 3 sin dependencias externas | `python3` ya forma parte de la imagen; la fusión, los diarios y las pruebas son mucho más claros que en shell |
| Paquetes solo con `apt` | Es el gestor oficial de Debian; un gestor paralelo duplicaría trabajo y riesgos |
| Rollback solo de archivos propios | Sin Btrfs ni instantáneas, revertir paquetes de Debian no es fiable. Se documenta como límite en vez de prometerlo |
| Histórico de huellas en el manifiesto | Reconoce archivos sin tocar de cualquier versión anterior, también en instalaciones que no tenían manifiesto (0.1.x) |
