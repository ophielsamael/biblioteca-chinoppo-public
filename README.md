# Biblioteca Chinoppo

Biblioteca de pelÃ­culas y series al estilo de los reproductores R_volution para el **Chinoppo M9201**, un clon del Oppo UDP-203 sin lector de discos. Al encenderlo aparece un muro de carÃ¡tulas con sus formatos (4K, Dolby Vision, HDR10+, Atmos, DTS:X, 3D), pÃ¡ginas de detalle, temporadas y episodios. Eliges con el control y la pelÃ­cula se reproduce desde tu NAS.

*An R_volution-style movie library for the Chinoppo M9201 (Oppo UDP-203 clone), built as a BD-J disc plus a small Docker service. Docs are in Spanish.*

> Proyecto de la comunidad, sin relaciÃ³n con Oppo, Dolby ni TMDb. Ãšsalo bajo tu propio riesgo.

## ðŸ‘‰ GuÃ­a paso a paso

**[Abre la guÃ­a para principiantes](docs/guia.html)** (en GitHub se ve como cÃ³digo: descarga el archivo y Ã¡brelo en el navegador).

Solo necesitas tu Chinoppo con el firmware liberado RU 65-0131, un NAS con NFS y una app para Docker (Container Manager, Container Station, Portainerâ€¦), una memoria USB y una cuenta gratis de TMDb. No hay que programar ni usar la terminal.

## En resumen

1. **Chinoppo:** ConfiguraciÃ³n â†’ Red â†’ **Acceso red BD-Live = Activado**. Anota su IP.
2. **TMDb:** saca tu clave de la API (gratis).
3. **NAS:** NFS activado y con permiso para la IP del Chinoppo. Anota la ruta de tu carpeta de pelÃ­culas.
4. **Docker en el NAS:** sube este proyecto (Code â†’ Download ZIP) al NAS y crea con Ã©l un proyecto/stack de docker-compose. En el `compose.yaml` cambia solo las lÃ­neas marcadas con `<--`.
5. Abre **`http://IP-DEL-NAS:8095`** y elige tus carpetas de pelÃ­culas y series.
6. En esa misma pÃ¡gina, **Descargar archivos para la USB**. Descomprime el ZIP en la raÃ­z de una USB FAT32.
7. Conecta la USB al Chinoppo y enciÃ©ndelo: a los ~40 s aparece la Biblioteca.

## CÃ³mo funciona

El Chinoppo reproduce discos Blu-ray con **BD-Live**: discos con un programa Java dentro y permiso para usar la red.

1. **Disco Biblioteca** (`static/usb/Biblioteca.iso`, BD-J, Java 1.3): muestra el muro y le pide todo al servicio. Lee la direcciÃ³n del servicio de `BIBLIO.TXT`, un archivo dentro de la ISO que el servicio rellena al generar el ZIP para la USB.
2. **Servicio** (Flask en Docker, puerto 8095): lee el NAS, consulta TMDb, detecta formatos con ffprobe y 7-Zip, y dibuja carÃ¡tulas y franjas.
3. **Chinoppo:** recibe la orden por su API (puerto 436), monta la carpeta del NAS por NFS y reproduce.
4. **AutoScript** (funciÃ³n del firmware liberado) en la USB: abre la Biblioteca al encender, al despertar y al elegir el Ã­cono **Disco**.

## Controles

| Tecla | AcciÃ³n |
|---|---|
| Flechas | Moverse |
| OK | Detalle / reproducir |
| Colores | Secciones (rojo = atrÃ¡s) |
| POP-UP | AtrÃ¡s / menÃº |

RETURN, TOP MENU e INFO no le llegan al disco. Detalle en [disc/KEYS.md](disc/KEYS.md).

## Extras

- **Dolby Vision en MKV:** [fandangos/oppo-dv-mkv](https://github.com/fandangos/oppo-dv-mkv), zip `mkv-subtitles` de la versiÃ³n mÃ¡s reciente (probado v1.7.1 en RU 65-0131). Se instala con **otra** USB. TV en modo Dolby Vision *TV-led*.
- **Servidor Linux en vez del Synology**, **compilar el disco**, **SSH** y **barra oscura del menÃº:** en la secciÃ³n *Avanzado* de la guÃ­a.
- **Estuches:** `static/cases` trae plantillas simples (`tools/cases/make_cases.py`). Puedes cambiarlas por fotos reales: un PNG con la ventana de la portada transparente.

## Limitaciones conocidas

- La primera pelÃ­cula de cada carpeta tarda unos 40 s: el reproductor monta la carpeta del NAS y solo puede tener una montada a la vez.
- El standby es un apagado real; la Biblioteca se vuelve a abrir sola al encender.
- Dos Ã³rdenes de reproducciÃ³n simultÃ¡neas traban la API del reproductor; el servicio descarta las repetidas.

## Desarrollo

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
python -m pytest tests -q
bash disc/build.sh      # recompila el disco (bdj-sdk en WSL); copia disc/out/Biblioteca.iso a static/usb/
```

`consola` (en `tools/autoscript/AutoScript/`) se compila con `zig cc -target arm-linux-musleabihf -mcpu=cortex_a7 -static -O2 -o consola tools/autoscript/consola/consola.c`.

## Aviso

Este producto usa la API de TMDb, pero TMDb no lo respalda ni lo certifica.
