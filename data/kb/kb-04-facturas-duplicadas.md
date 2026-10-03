---
id: kb-04
title: Facturas duplicadas
category: invoices
---
haddock detecta facturas duplicadas para que no cuentes el mismo gasto dos veces en tu P&L.

## Cómo detecta un duplicado

haddock marca una factura como **Duplicada** cuando coinciden tres datos con otra factura de tu cuenta:

1. El mismo proveedor.
2. La misma fecha de emisión.
3. El mismo importe total.

El mensaje de error indica la factura original. Por ejemplo: "Same supplier, date and total as F-0401".

Una factura duplicada no aparece en tus informes hasta que tú decides qué hacer con ella.

## Qué puedes hacer

Tú decides. haddock no borra ninguna factura de forma automática.

**Descartar la factura** si es una copia real:

1. Abre **Facturas** y filtra por el estado **Duplicada**.
2. Abre la factura y compárala con la original.
3. Haz clic en **Descartar**.

**Mantener la factura** si es un gasto distinto. Por ejemplo, dos entregas del mismo proveedor, el mismo día y por el mismo importe:

1. Abre la factura duplicada.
2. Comprueba que el número de factura del proveedor es distinto.
3. Haz clic en **Mantener**. La factura pasa a **Procesada** y entra en tus informes.

## Cómo evitar duplicados

- Sube cada factura una sola vez.
- No subas la foto y el PDF de la misma factura.
- Si reenvías facturas por correo, no las subas también desde la web.

**Si el problema continúa:** contacta con soporte. Indica los identificadores de las dos facturas (la original y la duplicada) y explica por qué crees que la detección es incorrecta.
