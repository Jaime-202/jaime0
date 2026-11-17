# NVIDIA GTX 1650 Ti

El portátil tiene dos gráficas. ZYRON las reparte así:

| Gráfica | Para qué | Estado normal |
|---|---|---|
| Intel UHD | Todo el escritorio: Hyprland, la barra, las ventanas, el vídeo por hardware (VA-API) | Siempre en uso |
| NVIDIA GTX 1650 Ti | Lo que tú pidas con `prime-run`: juegos, renderizado, CUDA, codificar vídeo (NVENC) y el monitor por HDMI | Apagada (no gasta batería) |

Es el modo **offload** (PRIME render offload): la NVIDIA calcula y la Intel muestra el resultado. Así el portátil dura más y se calienta menos, y Hyprland evita los problemas que todavía tiene Wayland directamente sobre NVIDIA.

## Usarla

```bash
prime-run PROGRAMA
```

Por ejemplo `prime-run mpv video.mkv` o `prime-run brave-browser`. Para comprobar que funciona:

```bash
jaime0-nvidia
```

Dice si el módulo está cargado y si la gráfica está despierta (`active`) o apagada (`suspended`). `nvidia-smi` muestra el detalle, pero al ejecutarlo la despierta un momento.

## La primera vez: registrar la clave (Secure Boot)

Este portátil tiene **Secure Boot activado**, así que el firmware solo carga módulos firmados por una clave en la que confía. El módulo de NVIDIA se compila en tu equipo (DKMS) y el instalador lo firma con una clave nueva, propia de tu instalación (`/var/lib/dkms/mok.pub`; la privada, `mok.key`, solo la lee root). La ISO no lleva ninguna clave privada.

Hay que registrar esa clave **una vez**. Al entrar por primera vez aparece un aviso; entonces:

1. Abre una terminal y ejecuta:

   ```bash
   jaime0-nvidia registrar
   ```

   Pide la clave de `sudo` y después una clave de un solo uso, dos veces. Elige una sencilla: solo se usa en el paso 3 y allí el teclado es inglés (US).

2. Reinicia.
3. Aparece una pantalla azul (**MokManager**). Elige **Enroll MOK**, **Continue**, **Yes**, escribe la clave de un solo uso y elige **Reboot**.

Después, `jaime0-nvidia` debe decir que está lista. Las actualizaciones del núcleo no piden repetirlo: DKMS firma el módulo nuevo con la misma clave.

Si prefieres no registrar nada, desactivar Secure Boot en la BIOS (F2 al encender, pestaña **Boot**) también funciona, pero el equipo queda menos protegido.

## Monitor por HDMI

En este portátil el HDMI va conectado a la NVIDIA. Si al iniciar sesión hay un monitor enchufado, `iniciar-sesion` le pasa a Hyprland las dos gráficas (`AQ_DRM_DEVICES`) y el monitor funciona; mientras tanto la NVIDIA no se apaga. Si lo conectas con la sesión ya abierta, cierra sesión y vuelve a entrar.

## Si algo falla

- `jaime0-nvidia` explica el estado y lo siguiente que hay que hacer.
- El detalle del núcleo: `journalctl -b -k | grep -i nvidia`.
- Clave nueva y módulo recompilado y firmado: `sudo jaime0-nvidia recompilar` (después hay que registrar la clave nueva).
- El escritorio nunca depende de la NVIDIA: si su módulo falla, todo sigue en la Intel.

## Cómo está montado

| Pieza | Archivo |
|---|---|
| Paquetes (sin `nvidia-driver`, que arrastraría Xorg) | `config/package-lists/portatil.list.chroot` |
| Ahorro de energía (`NVreg_DynamicPowerManagement=0x02`) y `nvidia-drm.modeset=1` | `/etc/modprobe.d/jaime0-nvidia.conf` |
| Apagado automático de la gráfica y sus funciones (sonido HDMI, USB-C) | `/etc/udev/rules.d/80-jaime0-nvidia-pm.rules` |
| Elegir la Intel para el escritorio, y la NVIDIA solo con HDMI | `/usr/local/bin/iniciar-sesion` |
| Abrir con la NVIDIA | `/usr/local/bin/prime-run` |
| Estado, registro de la clave y aviso al entrar | `/usr/local/bin/jaime0-nvidia` |
| Comprobación al compilar y borrado de la clave de la ISO | `config/hooks/normal/0400-nvidia.hook.chroot` |
| Clave nueva y módulo firmado al instalar | `jaime0-nvidia recompilar` (paso `shellprocess@nvidia` de Calamares) |

**Sin probar todavía:** todo lo de este documento necesita el portátil real; en una máquina virtual no hay NVIDIA. En la VM solo se comprueba que el módulo se compila, que la ISO no lleva clave privada y que el escritorio funciona sin NVIDIA.
