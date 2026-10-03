---
id: kb-10
title: Las ventas del TPV no aparecen
category: pos
---
Si faltan ventas en haddock, revisa primero el estado de la integración del TPV.

## Comprobar el estado

1. Abre **Ajustes > Integraciones**.
2. Busca tu TPV en la sección **TPV**.
3. Mira el estado y la fecha de la **Última sincronización**.

## Estado "Error": "Invalid API token (401)"

Este error aparece en Revo. El token de API que guardaste en haddock ya no es válido. Pasa si alguien regeneró o borró el token en Revo.

1. Entra en el back-office de Revo con un usuario administrador.
2. Genera un token de API nuevo y cópialo.
3. En haddock, abre **Ajustes > Integraciones**.
4. Haz clic en **Editar** junto a Revo.
5. Pega el token nuevo y haz clic en **Guardar**.

Soporte no puede generar el token por ti. Solo un administrador de Revo puede hacerlo.

## Estado "Desconectado": "Integration disabled by user"

Un usuario de tu cuenta desactivó la integración. haddock no importa ventas mientras está desactivada.

1. Abre **Ajustes > Integraciones**.
2. Haz clic en **Activar** junto a tu TPV.
3. Si el sistema lo pide, inicia sesión en el TPV otra vez.

## Recuperar las ventas que faltan

Cuando el estado vuelve a **OK**, haddock recupera las ventas del periodo sin sincronizar. Esto puede tardar unas horas. Después, tu P&L se actualiza.

## Otras causas

- **Ventas de hoy:** pueden tardar unas horas en aparecer.
- **Local equivocado:** comprueba que el TPV está asociado al local correcto.
- **Caja sin cerrar:** algunos TPV envían las ventas al cerrar la caja.

**Si el problema continúa:** contacta con soporte. Indica el proveedor del TPV, el local, las fechas sin ventas y una captura de pantalla del estado de la integración.
