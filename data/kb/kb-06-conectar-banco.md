---
id: kb-06
title: Conectar tu banco
category: bank
---
haddock se conecta a tu banco a través de un agregador bancario regulado por la directiva europea PSD2. haddock solo tiene acceso de lectura. No puede hacer pagos ni transferencias.

## Bancos compatibles

Puedes conectar los principales bancos de España, entre ellos BBVA, CaixaBank, Santander, Sabadell, ING, Kutxabank, Ibercaja y Bankinter.

## Conectar una cuenta

1. Abre **Ajustes > Integraciones**.
2. En la sección **Banco**, haz clic en **Conectar banco**.
3. Elige tu banco en la lista.
4. Inicia sesión con las credenciales de tu banca online. Lo haces en la página del banco, no en haddock.
5. Autoriza el acceso y elige las cuentas que quieres conectar.
6. Vuelve a haddock. La integración aparece con el estado **OK**.

haddock importa los movimientos de los últimos 90 días. Después, sincroniza la cuenta una vez al día.

## El consentimiento caduca cada 180 días

La normativa PSD2 obliga a renovar el consentimiento cada 180 días. Es una regla bancaria, no de haddock.

Cuando el consentimiento caduca, la integración pasa a **Error** con el mensaje "PSD2 consent expired (180 days)". Los movimientos dejan de llegar.

Para renovarlo:

1. Abre **Ajustes > Integraciones**.
2. Haz clic en **Renovar consentimiento** junto a tu banco.
3. Inicia sesión en tu banco y autoriza el acceso otra vez.

haddock recupera los movimientos que faltan después de la renovación.

**Si el problema continúa:** contacta con soporte. Indica el nombre del banco, el estado de la integración y una captura de pantalla del mensaje de error.
