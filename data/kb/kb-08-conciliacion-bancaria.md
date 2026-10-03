---
id: kb-08
title: Cómo funciona la conciliación bancaria
category: bank
---
La conciliación bancaria relaciona cada movimiento de tu banco con su factura o su venta. Así sabes qué está pagado y qué está pendiente.

## Qué necesitas

- Un banco conectado con el estado **OK**. Consulta el artículo "Conectar tu banco".
- Facturas con el estado **Procesada**.

## Conciliación automática

Cada día, después de sincronizar el banco, haddock busca coincidencias. Compara estos datos:

1. El importe del movimiento y el total de la factura.
2. El nombre del proveedor en el concepto bancario.
3. La fecha del movimiento y la fecha de vencimiento de la factura.

Si la coincidencia es clara, haddock concilia el movimiento de forma automática. Si hay dudas, lo marca como **Sugerencia** para que tú lo revises.

## Revisar sugerencias

1. Abre **Banco > Conciliación**.
2. Filtra por **Sugerencias**.
3. Revisa cada pareja de movimiento y factura.
4. Haz clic en **Confirmar** o en **Rechazar**.

## Conciliar a mano

1. Abre **Banco > Conciliación**.
2. Filtra por **Sin conciliar**.
3. Selecciona el movimiento.
4. Busca la factura o las facturas que corresponden.
5. Haz clic en **Conciliar**.

Un solo movimiento puede pagar varias facturas. Una factura también puede pagarse en varios movimientos.

## Movimientos sin factura

Algunos movimientos no tienen factura: comisiones bancarias, nóminas o impuestos. Asígnales una categoría de gasto con **Categorizar**. Así aparecen bien en tu P&L.

Si el banco no sincroniza, la conciliación se para. Consulta el artículo "El banco no se sincroniza".

**Si el problema continúa:** contacta con soporte. Indica la fecha y el importe del movimiento, y el identificador de la factura que esperabas conciliar.
