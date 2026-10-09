# Pendientes por validar con los analistas

## Kits distintos en un mismo pallet
Hoy cada pallet lleva **un solo tipo de kit** (decisión de partida). Los restos de kits distintos, es decir los
pallets que quedan incompletos, no se juntan.

Ya está desarrollada la alternativa, **apagada por defecto**:
Configuración → Kits → «Permitir kits distintos en un mismo pallet» (ajuste `kits_mezclar`).
Si se enciende, los pallets incompletos de kits distintos del mismo destino se juntan cuando caben todos
(`app/cubicaje/kits.py`, `_mezclar_restos`). El pallet queda marcado como «Kit mixto».

**Qué revisar con los analistas**
- ¿En la operación real se acepta mezclar kits distintos en un pallet?
- Si sí: ¿solo con los restos, o también al armar pallets completos?
- ¿Aplica igual a todos los clientes (SODIMAC y otros) o solo a algunos?
- Con el ajuste encendido, ¿el resultado del cubicaje coincide con cómo arma el equipo de bodega?

## Kits a piso (MDA)
Los kits van en camiones completos de kits y el resto de los kits sale primero en el camión siguiente. Si un kit
queda partido entre dos camiones, el cubicaje lo avisa. Falta confirmar si es aceptable que los camiones de kits
completos no compartan espacio con otros productos.

## Kits en los modos por sucursal (predistribuido)
- **SDA predistribuido:** el kit va en pallets propios por sucursal (como en SDA).
- **MDA predistribuido y SDA predistribuido a piso:** el kit se abre en sus componentes y queda en la misma
  sucursal. No se garantiza que viajen en el mismo punto del camión.
