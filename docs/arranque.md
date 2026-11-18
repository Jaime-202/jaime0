# Arranque

ZYRON arranca con una animación propia de Plymouth: la **activación del núcleo**.

## Qué se ve

Sobre negro profundo aparece un marco de esquinas, como un visor. Una línea de escaneo verde recorre la zona central, se enciende un halo y se construye el hexágono del símbolo. La Z se materializa y el núcleo cian se enciende con una onda. Después, un anillo de segmentos gira despacio, la marca ZYRON aparece debajo y el núcleo late mientras una línea fina indica el progreso real del arranque.

- **Duración:** la entrada dura unos 2 segundos y **nunca retrasa el arranque**; Plymouth se cierra en cuanto el sistema está listo, haya terminado la animación o no.
- **Resolución:** se escala a cualquier pantalla (diseño a 1920 × 1080).
- **Consumo:** son capas PNG renderizadas desde SVG. El anillo se gira cada tres cuadros y la onda se escala cada dos, para gastar poca CPU.
- **Apagar y reiniciar:** se muestra el símbolo ya activado, sin entrada.
- **Clave del disco cifrado y preguntas:** se piden en un recuadro bajo la marca. Los mensajes del sistema salen abajo, en gris.
- **Mensajes de arranque:** `Esc` muestra el texto de siempre, como con cualquier tema.

El tema está en `/usr/share/plymouth/themes/zyron/` (`zyron.script`, las capas PNG y sus originales en `capas/*.svg`); el hook `0310-plymouth` comprueba las capas y lo deja por defecto. Las actualizaciones (`jaime0-update`) también lo reparten y rehacen el initramfs.

Si se cambia un SVG, hay que volver a renderizar su PNG (en Linux, con `librsvg2-bin`):

```sh
cd config/includes.chroot_after_packages/usr/share/plymouth/themes/zyron
for s in capas/*.svg; do rsvg-convert "$s" -o "$(basename "$s" .svg).png"; done
```

## Arrancar sin la animación

| Cómo | Para qué |
|---|---|
| En GRUB, **Opciones avanzadas › modo seguro** | Arranque sin `splash` y con `nomodeset`: texto, sin Plymouth, para cuando falla la gráfica |
| En GRUB, `e` sobre la entrada y quitar `splash` (o añadir `plymouth.enable=0`) | Solo esa vez, sin animación |
| `sudo plymouth-set-default-theme -R jaime0` | Volver al tema sencillo anterior (negro con una rueda), que sigue instalado. `-R zyron` vuelve a la animación |

La consola de emergencia y el modo de rescate de systemd no dependen de Plymouth y siguen igual.

## Lo que no cambia

El menú está en español: la cuenta atrás se muestra en texto («Arranca en 2 s»), las entradas dicen «con Linux» y «modo seguro», y los otros sistemas, «(en /dev/…)». Con el disco cifrado, la clave se pide dentro de la animación y, si no es correcta, lo dice en español y sin el identificador interno del disco. La pantalla de acceso (tuigreet) también sale en español; solo «Password:» sigue en inglés, porque ese texto lo pone PAM.

GRUB conserva sus opciones: tiempo de espera, otros sistemas (Windows) con os-prober, núcleos anteriores en «Opciones avanzadas», modo seguro y el tema del menú. Snapper y Btrfs, NVIDIA (PRIME offload) y el cifrado funcionan igual: el tema solo dibuja.

## Entrada EFI en equipos instalados como Jaime0

El nombre de la entrada del firmware sale del nombre del sistema. En las instalaciones nuevas es `zyron`. En un equipo que ya tenía Jaime0 instalado, la próxima actualización del paquete de GRUB creará una entrada `zyron` y la antigua `jaime0` quedará sin usar. El equipo arranca igual (también con Windows y Secure Boot). Para borrar la vieja:

```bash
sudo efibootmgr                      # busca el número de la entrada "jaime0" (BootXXXX)
sudo efibootmgr -b XXXX -B           # bórrala (sustituye XXXX)
sudo rm -r /boot/efi/EFI/jaime0      # y su carpeta en la partición EFI
```

Antes de borrar, comprueba que la entrada `zyron` existe y arranca.

La animación nueva llega con una instalación nueva desde la ISO. `jaime0-update` no actualiza los temas de Plymouth de un sistema ya instalado.
