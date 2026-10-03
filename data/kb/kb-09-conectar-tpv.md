---
id: kb-09
title: Conectar tu TPV
category: pos
---
Conecta tu TPV para importar las ventas en haddock. Con las ventas, haddock calcula tus ingresos, tu food cost y tu P&L.

## TPV compatibles

- Last.app
- Revo
- Ágora

Si tienes varios locales, conecta el TPV de cada local por separado.

## Conectar Last.app o Ágora

1. Abre **Ajustes > Integraciones**.
2. En la sección **TPV**, haz clic en **Conectar TPV**.
3. Elige tu proveedor.
4. Inicia sesión con tu usuario de administrador del TPV.
5. Autoriza el acceso.
6. Elige el local que corresponde.

## Conectar Revo

Revo usa un token de API.

1. Entra en el back-office de Revo con un usuario administrador.
2. Abre la sección de integraciones y genera un token de API nuevo.
3. Copia el token.
4. En haddock, abre **Ajustes > Integraciones**.
5. Haz clic en **Conectar TPV** y elige **Revo**.
6. Pega el token y haz clic en **Guardar**.

## Qué pasa después

haddock importa las ventas de los últimos 30 días. Después, sincroniza el TPV varias veces al día. El estado de la integración pasa a **OK**.

## Error "Invalid API token (401)" en Revo

Este error indica que el token ya no es válido. Pasa si alguien regeneró o borró el token en Revo. Para solucionarlo:

1. Genera un token nuevo en el back-office de Revo.
2. Abre **Ajustes > Integraciones** en haddock.
3. Haz clic en **Editar** junto a Revo.
4. Pega el token nuevo y haz clic en **Guardar**.

**Si el problema continúa:** contacta con soporte. Indica el proveedor del TPV, el local afectado y una captura de pantalla del estado de la integración.
