---
id: kb-12
title: Escandallos y food cost
category: inventory
---
Un escandallo es la ficha de coste de un plato. Lista los ingredientes, las cantidades y el coste de cada uno. haddock calcula el coste del plato con los precios de tus facturas.

## Qué es el food cost

El food cost es el porcentaje del precio de venta que corresponde al coste de los ingredientes.

Food cost = coste del plato ÷ precio de venta sin IVA × 100

Por ejemplo, un plato con un coste de 3 € y un precio sin IVA de 12 € tiene un food cost del 25 %.

## Crear un escandallo

1. Abre **Inventario > Escandallos**.
2. Haz clic en **Nuevo escandallo**.
3. Escribe el nombre del plato y el número de raciones.
4. Añade cada ingrediente y su cantidad neta.
5. Indica el porcentaje de merma si el ingrediente lo tiene. Por ejemplo, la limpieza del pescado.
6. Asocia el plato con el producto de tu TPV.
7. Haz clic en **Guardar**.

## Cómo se actualizan los costes

haddock usa el último precio de compra de cada ingrediente. Cuando procesa una factura con un precio nuevo, recalcula todos los escandallos que usan ese ingrediente.

Si un ingrediente no tiene facturas, puedes escribir su precio a mano.

## Food cost teórico y real

- **Teórico:** coste de los escandallos × platos vendidos en el TPV.
- **Real:** consumo calculado con tus recuentos de inventario y tus compras.

La diferencia entre los dos indica mermas, raciones mayores de lo previsto o errores de registro. Para ver el food cost real, necesitas un TPV conectado y recuentos de inventario.

## Alertas de precio

haddock te avisa cuando el coste de un plato sube por encima del umbral que configuras en **Ajustes > Inventario**.

**Si el problema continúa:** contacta con soporte. Indica el nombre del escandallo, el ingrediente afectado y el identificador de la factura con el precio que no esperabas.
