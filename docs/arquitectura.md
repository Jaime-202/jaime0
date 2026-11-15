# Arquitectura de Jaime0

Jaime0 está pensado para un equipo concreto: un **Acer Nitro AN515-55** (Intel i7-10750H con UHD Graphics, NVIDIA GTX 1650 Ti, Wi-Fi y Bluetooth Intel AX201, sonido Intel SOF, SSD NVMe, pantalla de 15,6" a 1920x1080, Secure Boot activado). Arranca en otros equipos y en máquinas virtuales, pero solo lleva el firmware de ese portátil.

## Base

| Pieza | Elección |
|---|---|
| Distribución base | Debian Forky (testing), amd64 |
| Construcción | live-build (`auto/config`): `debootstrap --variant=minbase`, sin paquetes recomendados, firmware solo del portátil, ISO híbrida BIOS + UEFI con Secure Boot (shim firmado por Debian) |
| Paquetes | APT de Debian y el repositorio oficial de Brave. Preferencias en `config/archives/`: sin Xorg ni otros escritorios, Waybar parcheado fijado |
| Escritorio | Hyprland 0.56/0.57 con configuración **Lua** (`hyprland.lua`), Waybar, rofi, kitty, Quickshell (ajustes y widgets) |
| Gráficas | La Intel dibuja el escritorio (`iniciar-sesion` fija `AQ_DRM_DEVICES`); la NVIDIA, con el controlador propietario 550 (DKMS), en modo *offload* con `prime-run` y apagada cuando no se usa. Ver [nvidia.md](nvidia.md) |
| Notificaciones, bloqueo, OSD | swaync (`notificaciones`), hyprlock + hypridle (`bloquear`, `inactividad`; swaylock de respaldo), wob activado por socket (`jaime0-osd`) |
| Energía | power-profiles-daemon (indicador en la barra), thermald, suspensión al cerrar la tapa |
| Acceso | greetd + tuigreet en la consola (`iniciar-sesion` lanza Hyprland y explica el fallo si no abre) |
| Instalador | Calamares con marca propia; se retira al instalar (`hypr-limpiar-vivo`). Pasos propios: snapper si es Btrfs y la clave de firma de NVIDIA |
| Sonido, red | PipeWire + WirePlumber, NetworkManager (`nmtui` desde la barra), BlueZ + blueman |
| Actualizaciones | `apt` para todo lo que viene en paquetes; aviso de seguridad en la barra (`actualizaciones`). Lo propio de Jaime0, con una ISO nueva. Ver [actualizaciones.md](actualizaciones.md) |
| Ajustes | `jaime0-ajustes`: predeterminados en `/usr/share/jaime0/ajustes.predeterminados`, cambios del usuario en `~/.config/jaime0/ajustes`. Ver [ajustes.md](ajustes.md) |
| Seguridad | UFW (entrante denegado), avisos de seguridad con debsecan, cifrado LUKS opcional. Ver [recuperacion.md](recuperacion.md) |
| Widgets | `jaime0-widgets` arranca un único Quickshell solo si hay widgets activos. El tiempo, de `jaime0-tiempo` (Open-Meteo, con caché) |
| Aplicaciones ancladas | `jaime0-anclar`: ajuste `anclas`; `jaime0-anclar vigilar` escucha los eventos de Hyprland y escribe el estado que lee Waybar (señal 9) |

## Flujo de construcción

```
auto/config ──> lb config
auto/build  ──> lb build
                 ├─ config/package-lists/*.list.chroot         paquetes (portatil.list: firmware, NVIDIA, energía)
                 ├─ config/includes.chroot_after_packages/     archivos propios
                 ├─ config/hooks/normal/*.hook.chroot          ajustes en el chroot (Brave, NVIDIA, versión...)
                 └─ config/hooks/normal/*.hook.binary          menú de arranque del medio
scripts/verificar-*.sh                                         comprobaciones sobre chroot/
```

`usr/share/jaime0/version` es la versión, que acaba en `/etc/os-release`.

## Decisiones

| Decisión | Motivo |
|---|---|
| Sin actualizador propio | Con el repositorio privado y un solo equipo, una ISO nueva es más simple que mantener firmas, canales y fusiones. Los paquetes ya se actualizan con `apt` |
| NVIDIA sin el metapaquete `nvidia-driver` | El metapaquete arrastra el controlador de Xorg, que Jaime0 bloquea. Las bibliotecas EGL, Vulkan, CUDA y NVENC se instalan sueltas |
| Intel para el escritorio, NVIDIA bajo demanda | La NVIDIA apagada ahorra batería y calor; Hyprland en la Intel evita los problemas de Wayland con NVIDIA. `prime-run` la usa para lo que lo merece |
| Clave de firma de NVIDIA por instalación | La ISO no lleva ninguna clave privada: el instalador crea una propia y recompila el módulo. Con Secure Boot se registra una vez (MokManager) |
| Firmware solo del portátil | La ISO es para este equipo: sobra el firmware de Broadcom, AMD, Qualcomm, Marvell... |
| Python 3 sin dependencias externas | `python3` ya forma parte de la imagen |
| Paquetes solo con `apt` | Es el gestor oficial de Debian; sin Flatpak ni gestores paralelos |
| UFW y no nftables a mano | Trae probadas las reglas que necesita un cliente (DHCP, ICMPv6, mDNS) |
| Btrfs + snapper como opción | En ext4 (por defecto) revertir paquetes no es fiable. Btrfs se ofrece con snapper y subvolúmenes aparte para `/home`, registros y cachés; `/boot` sigue en ext4 por LUKS |
| Ajustes del usuario fuera de `/etc/skel` | `~/.config/jaime0/ajustes` no lo trae la ISO: se conserva al copiar una configuración nueva |
| Esquema de ajustes solo en `jaime0-ajustes` | Valida con límites y lo expone con `ver --json` a la interfaz. Hyprland solo comprueba el tipo y ante un valor roto usa el predeterminado |
| Configuración de Hyprland: `hyprland.lua` con `hl.window_rule` | Hyprland 0.56 y 0.57 usan Lua |
| Acceso: `greetd` con `tuigreet` | Mucho más ligero que SDDM con su compositor |
| Agente de permisos: `lxpolkit` | El de KDE arrastra KDE Frameworks |
| Waybar: `0.15.0-1+hypr1`, parcheado, fijado y retenido | El de Debian no cambia de escritorio con la configuración Lua |
| Red y Bluetooth: Se abren desde la barra | Sin applets residentes |
| Qt: Lo necesitan Quickshell (aplicación de ajustes) y el instalador; Calamares se retira al instalar | Quickshell no es imprescindible: sin él, `jaime0-ajustes` funciona desde la terminal y el escritorio arranca igual |
| Base: `debootstrap` con `minbase`, sin recomendados | Lleva solo lo necesario |

## Identidad visual

Negro profundo `#080b0d` y negro secundario `#101519` de base, bordes `#26343a`, gris claro `#d8e2e8` y gris secundario `#71818c` para el texto, y un único acento verde `#54e58a` para lo importante: ventana y escritorio activos, selección y botón principal. El cian `#55cde0` aparece solo como acento secundario. Tonos derivados: superficie `#151c21`, gris medio `#a7b4bc`, gris apagado `#45545c` y blanco de selección `#eef4f7`. El rojo `#d9625b` y el ámbar `#d9a54a` solo avisan de errores. La consola de texto (`vt.default_*`), el acceso y los 16 colores ANSI de Kitty usan la misma paleta, con los colores de `git` y `ls` apagados pero distinguibles.

El fondo de pantalla es propio: una malla digital oscura con líneas geométricas y pequeños puntos verdes, generada de forma determinista con `scripts/generar-fondo.py` (Python y Pillow) y guardada en el repositorio. La compilación no descarga nada para él.
