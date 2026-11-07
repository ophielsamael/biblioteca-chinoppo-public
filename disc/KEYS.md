# Teclas y memoria medidas en el Chinoppo M901 (2026-11-02, disco KeyProbe)

| Tecla del mando | keyCode en el xlet |
|---|---|
| ◀ ▶ ▲ ▼ | 37, 39, 38, 40 |
| OK | 10 |
| Rojo, verde, amarillo, azul | 403, 404, 405, 406 |
| POP-UP MENU | 461 |
| 1 (números) | 49 (0–9 = 48–57) |
| RETURN / BACK | **no llega al xlet** (el Chinoppo muestra el icono de prohibido) |
| TOP MENU | no llega: el Chinoppo **sale del disco** a la lista azul |
| INFO | no llega: el Chinoppo muestra su OSD de reproducción |

**"Atrás" en la Biblioteca** (no hay RETURN): POP-UP MENU (461) o ROJO (403). En la ficha también ◀ sobre el primer botón.

**Memoria Java**: `totalMemory` 2364–2688 KB, `freeMemory` 1086–1399 KB al arrancar. Es muy poco, así que la pared mantiene en memoria solo los pósters de la pantalla visible, y libera (`flush`) los demás.
