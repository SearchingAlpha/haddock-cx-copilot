---
id: kb-07
title: El banco no se sincroniza
category: bank
---
Si no ves movimientos bancarios recientes en haddock, revisa el estado de la integración.

## Comprobar el estado

1. Abre **Ajustes > Integraciones**.
2. Busca tu banco en la sección **Banco**.
3. Mira el estado y la fecha de la **Última sincronización**.

haddock sincroniza el banco una vez al día, normalmente de madrugada. Los movimientos de hoy pueden aparecer mañana.

## Error: "PSD2 consent expired (180 days)"

Es la causa más frecuente. La normativa PSD2 obliga a renovar el consentimiento bancario cada 180 días. Cuando caduca, la sincronización se para.

Para renovarlo:

1. Abre **Ajustes > Integraciones**.
2. Haz clic en **Renovar consentimiento** junto a tu banco.
3. Inicia sesión en tu banca online.
4. Autoriza el acceso otra vez.
5. Vuelve a haddock. El estado pasa a **OK**.

Después de la renovación, haddock recupera los movimientos pendientes. Esto puede tardar unas horas.

Soporte no puede renovar el consentimiento por ti. Solo el titular de la cuenta puede autorizar el acceso en su banco.

## Otras causas

- **Cambiaste las credenciales del banco.** Renueva el consentimiento con las credenciales nuevas.
- **El banco tiene una incidencia.** Espera unas horas. La sincronización se reanuda sola.
- **Cerraste o cambiaste de cuenta.** Conecta la cuenta nueva desde **Conectar banco**.

## Qué pasa con la conciliación

Mientras el banco no sincroniza, la conciliación no avanza. Tus facturas siguen sin conciliar hasta que llegan los movimientos.

**Si el problema continúa:** contacta con soporte. Indica el nombre del banco, el mensaje de error, la fecha de la última sincronización y si ya renovaste el consentimiento.
