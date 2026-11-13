import QtQuick
import Quickshell.Services.Mpris

// Cancion actual por MPRIS (Spotify, mpv, navegadores...): caratula, titulo, artista,
// progreso y controles. Sin reproductor, el widget no se muestra.
Tarjeta {
    id: musica

    // El que esta sonando; si ninguno, el ultimo. playerctld es solo un intermediario.
    readonly property var reproductor: {
        const lista = Mpris.players.values.filter(p => !String(p.dbusName || "").endsWith("playerctld"));
        return lista.find(p => p.isPlaying) || (lista.length ? lista[lista.length - 1] : null);
    }
    readonly property var r: reproductor

    mostrar: r !== null
    ancho: 300

    // MPRIS no avisa del avance: se pide una vez por segundo, solo mientras suena.
    Timer {
        interval: 1000
        repeat: true
        running: musica.r !== null && musica.r.isPlaying
        onTriggered: musica.r.positionChanged()
    }

    Row {
        spacing: 12
        width: parent.width

        Rectangle {
            width: 64
            height: 64
            radius: 6
            color: Estado.superficie2
            clip: true

            Image {
                anchors.fill: parent
                source: musica.r ? musica.r.trackArtUrl : ""
                fillMode: Image.PreserveAspectCrop
                sourceSize.width: 128
                sourceSize.height: 128
                asynchronous: true
                visible: status === Image.Ready
            }

            Texto {
                anchors.centerIn: parent
                visible: !musica.r || musica.r.trackArtUrl === ""
                text: "\u{f075a}"
                font.pixelSize: 26
                tenue: true
            }
        }

        Column {
            width: parent.width - 76
            spacing: 4

            Texto {
                width: parent.width
                elide: Text.ElideRight
                text: musica.r ? (musica.r.trackTitle || musica.r.identity || "") : ""
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }

            Texto {
                width: parent.width
                elide: Text.ElideRight
                tenue: true
                text: musica.r ? (musica.r.trackArtist || "") : ""
            }

            Row {
                spacing: 2
                Boton {
                    glifo: "\u{f04ae}"
                    activo: musica.r !== null && musica.r.canGoPrevious
                    onPulsado: musica.r.previous()
                }
                Boton {
                    glifo: musica.r && musica.r.isPlaying ? "\u{f03e4}" : "\u{f040a}"
                    tamano: 18
                    activo: musica.r !== null && musica.r.canTogglePlaying
                    resaltado: true
                    onPulsado: musica.r.togglePlaying()
                }
                Boton {
                    glifo: "\u{f04ad}"
                    activo: musica.r !== null && musica.r.canGoNext
                    onPulsado: musica.r.next()
                }
            }
        }
    }

    Barra {
        width: parent.width
        visible: musica.r !== null && musica.r.lengthSupported && musica.r.length > 0
        valor: musica.r && musica.r.length > 0 ? musica.r.position / musica.r.length : 0
    }
}
