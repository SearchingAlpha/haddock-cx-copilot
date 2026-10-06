# Guion de la demo

Demo en vivo de la entrevista técnica: 8 min como máximo (PLAN.md, fase 5). Presenta solo Pablo: conduce y narra a la vez.

**Momento de la demo:** el entrevistador ve, en menos de 2 minutos, un ticket que llega, un borrador con la evidencia del cliente al lado y un ticket con riesgo que el copilot escala solo. Hoy un agente CX busca esos datos a mano en la cuenta, en el banco y en el centro de ayuda.

## Qué funciona hoy

Verificado el 2026-10-04 con `haddock.db` y la app en `localhost:8000`:

| Funciona de punta a punta | Estado en la demo |
|---|---|
| Webhook → classify (Jev) → agente (Sonnet) → guardrails → cola | En vivo, solo para un ticket (T-024). Tarda 10–30 s. |
| T-005 «Pago fallido»: `ready`, sin banners, borrador corto | Precalculado |
| T-002 «Factura Carnes Selectas con error»: cita F-0301, 3.480 €, error de OCR | Precalculado, con enlace «Ver la traza en Langfuse» |
| T-011 «me habeis cobrado 2 veces»: `escalated` a Finanzas, borrador sin promesa de reembolso | Precalculado |
| Aprobar con `A`: guarda la revisión, envía los scores y abre el siguiente ticket | En vivo |
| `/metrics` | En vivo, pero solo tiene cifras si hay revisiones (ver pre-warm) |
| Datasets → `cx-tickets` → Runs en Langfuse | Ya existe, se enseña sin ejecutar nada |

**Lo que no entra en el camino principal:**
- T-021 (urgente, pide una garantía de plazo) no escaló en la última ejecución. El agente no es determinista. No lo uses como trampa.
- T-020 (inyección de instrucciones) escala bien, pero está en modo manual: la pantalla dice «modo manual» y distrae. Úsalo solo si preguntan por *prompt injection*.
- Las cifras de tiempo de `/metrics` vienen de revisiones de ensayo. Dilo en voz alta. No las presentes como productividad real (PRODUCT.md).

## Camino principal

Punto de partida: la última escena de `/presentacion` («Ver la demo») y la cola abierta. Pestañas del navegador: 1 app, 2 traza de T-002 en Langfuse, 3 Datasets → `cx-tickets` → Runs, 4 vídeo de respaldo. Una terminal con el comando ya escrito.

| Segundo | Acción | Entrada fija | Qué aparece | Qué dices |
|---|---|---|---|---|
| 0–20 | Clic en «Ver la demo» | — | La cola: «Escalados 2» arriba, «Listos para revisar» debajo | «Esta es la cola del agente CX: lo que tiene riesgo arriba, lo rutinario abajo.» |
| 20–35 | En la terminal, pulsa Enter | `python -m uv run python -m scripts.seed_demo T-024` | `T-024 202 copilot`. En la cola aparece «En proceso» | «Entra un ticket por el webhook, como llegaría de Zendesk. Lo dejamos trabajar.» |
| 35–75 | Clic en T-005 «Pago fallido» | — | Mensaje de Laura, borrador «así lo verá Laura», a la derecha «Evidencia citada: Plan pro · pago fallido» | «El copilot ya miró la cuenta: el pago figura como fallido. El borrador dice solo lo que la evidencia confirma.» |
| 75–90 | Pulsa `A` | — | Se abre el siguiente ticket pendiente: T-011 | «Lo apruebo sin cambios. La decisión vuelve a Langfuse como score.» |
| 90–150 | Lee el banner de T-011 | — | «Escalado a Finanzas…» en rojo, y el borrador: «Yo no puedo prometer ni aprobar reembolsos» | «Aquí el cliente pide un reembolso. El copilot no lo promete: lo escala a Finanzas con el contexto ya escrito.» |
| 150–210 | Clic en T-002 en la cola | — | Borrador con F-0301, 3.480 €, «total not readable (blurry photo)» | «Este dato no está en el mensaje del cliente. Sale de sus facturas, con get_invoices.» |
| 210–270 | Clic en «Ver la traza en Langfuse» (o pestaña 2) | — | [missing: árbol de la traza de T-002: classify, iteraciones del agente, tools, guardrails, coste] | «Cada ticket es una traza: qué decidió Jev, qué tools llamó Sonnet, cuánto costó y con qué versión del prompt.» |
| 270–300 | Vuelve a la pestaña 1. Clic en T-024 | — | T-024 ya `ready` (si sigue «En proceso», pasa al siguiente paso y vuelve al final) | «El ticket que entró en directo ya tiene borrador, con el estado de la sincronización bancaria.» |
| 300–360 | Clic en «Impacto» en el rail | — | `/metrics`: tiempo con y sin copilot, aprobados sin editar, escalados, coste por ticket ($0.016) | «Uno de cada cinco tickets se responde sin copilot: es la línea base. Estas cifras son de mis ensayos, no de producción.» |
| 360–450 | Pestaña 3 | — | [missing: comparación de runs `prompt-v1-judge-v3` y `prompt-v2-judge-v3`] | «Cada cambio de prompt pasa por 40 tickets etiquetados. La v2 mejoró el formato y empeoró el escalado, así que production sigue en la v1.» |
| 450–480 | Vuelve a la cola | — | La cola | «Eso es todo: el copilot investiga, el agente CX decide y todo se mide.» |

El momento clave (T-011 escalado) llega antes del segundo 150. Total: 8 min. Si vas justo de tiempo, quita T-024 y su vuelta (ahorras 45 s).

## Pre-warm (2 h antes y 2 min antes)

**2 h antes** (el pipeline no es determinista: prepara el estado y no lo vuelvas a generar):
1. Copia el estado bueno: `copy haddock.db haddock.golden.db`. Si algo cambia, vuelve a copiarlo al revés.
2. Comprueba en la cola: T-011 y T-020 en «Escalados»; T-005, T-002 y T-024 no están revisados; T-024 no existe aún en la base de datos.
3. Revisa a mano 6–8 tickets para que `/metrics` tenga cifras, dos de ellos en modo manual (T-006, T-007). No toques T-005, T-002 ni T-011.
4. Haz las capturas del plan B: `python -m uv run python -m scripts.shoot --out docs/demo --pages / /tickets/T-005 /tickets/T-011 /tickets/T-002 /metrics`, y a mano la traza de T-002 y la página de Runs de Langfuse.
5. Graba el vídeo de respaldo (ver abajo).

**2 min antes:**
- `python -m uv run uvicorn app.main:app` en marcha. `/queue` responde 200.
- Langfuse con la sesión iniciada en las pestañas 2 y 3.
- Una llamada de calentamiento: `python -m uv run python -m scripts.hello_jev`.
- Navegador al 125 %. `localStorage` con la intro ya vista (abre `/` una vez).
- Notificaciones, bloqueo de pantalla y Slack apagados. Pestaña 4 con el vídeo.
- Wifi y hotspot del móvil preparados.

**Pre-flight (el día antes):** cargador, adaptador HDMI/USB-C probado (si es presencial), vídeo en el portátil y en el móvil, este guion impreso, agua. Si es online: comparte solo la ventana del navegador, no la pantalla completa (el `.env` y la terminal no se ven).

## Escalera de respaldo

| Escalón | Disparador | Qué haces | Qué dices mientras cambias |
|---|---|---|---|
| 1. En vivo | — | El camino principal | — |
| 2. Solo precalculado | El webhook no responde, o T-024 tarda más de 30 s, o un error | Ignora T-024. Sigue con T-005, T-011 y T-002, que ya están en la base de datos | «Este lo dejo trabajando; vamos con los que ya están procesados.» |
| 3. Vídeo sin voz | Cuentas tres y no pasa nada en pantalla, o Langfuse no carga | Pestaña 4. Narra encima con las mismas frases | «Os enseño la ejecución grabada.» |
| 4. Capturas | El portátil o la red caen del todo | Las capturas de `docs/demo/` | «Os lo enseño con las capturas de esta mañana.» |

Nunca depures en directo. Un error en pantalla es el disparador del escalón siguiente, no un problema para resolver.

**Vídeo:** grábalo el día antes, sin voz, 90–120 s: cola → T-005 → `A` → T-011 → T-002 → traza → `/metrics` → Runs.

## Un solo presentador

No hay conductor y narrador separados. Las reglas cambian así:
- No escribas nada en directo. El único comando ya está escrito en la terminal; solo pulsas Enter.
- Habla mientras algo carga, nunca en silencio. Cada cambio de pantalla tiene su frase en la tabla.
- Las tres transiciones que debes ensayar:
  1. Slides → demo: «Vamos a verlo funcionando.» (clic en «Ver la demo»).
  2. App → Langfuse: «Ahora miremos qué pasó por dentro.»
  3. Demo → revisión de código: «Ahora os enseño cómo está construido, empezando por el diagrama.» (icono `</>` del rail: `/codigo`).

## Checklist de ensayo

- [ ] Ensayo 1: camino principal completo, cronometrado (objetivo: menos de 8 min).
- [ ] Ensayo 2: igual, y anota qué frase se alarga.
- [ ] Ensayo 3: fuerza el escalón 2 (no arranques el webhook).
- [ ] Ensayo 4: fuerza el escalón 3 (Langfuse cerrado, cambia al vídeo).
- [ ] Ensayo 5: completo, con `haddock.golden.db` restaurado antes, como el día real.

## Radar de producto (2 min 30 s, después de `/metrics`)

**Momento de la demo:** el entrevistador ve que 250 tickets se convierten en 6 problemas de producto con su impacto, que una petición aprobada crea una issue real, y que al cerrarla cada cliente afectado recibe un aviso personal en la cola. Ticket → problema → issue → fix → cliente avisado.

| Segundo | Acción | Entrada fija | Qué aparece | Qué dices |
|---|---|---|---|---|
| 0–30 | Clic en el icono del radar | — | Cifras arriba; grafo área → problema → cliente; clientes con anillo rojo | «Los tickets también dicen qué arreglar. El copiloto los agrupa en problemas y mide a quién afectan y cuánto pagan esos clientes.» |
| 30–50 | Pasa el ratón por Kutxabank | — | Sus 7 clientes; el resto se apaga | «Siete clientes, 1.134 € al mes. Se detectó con 3 tickets, medio día después del inicio.» |
| 50–90 | Clic en el problema de Kutxabank | — | Aviso ámbar «Cruzó el umbral»; la petición redactada con citas literales | «Sonnet redacta la issue. Los números y los clientes los pone el código, y cada cita es texto literal de un ticket.» |
| 90–105 | «Crear la issue en GitHub» | — | «Issue #N en GitHub» | «Una persona aprueba. La issue ya está en el repo de producto.» |
| 105–125 | En la terminal, pulsa Enter | `python -m uv run python -m scripts.seed_demo R-LIVE-1` | `R-LIVE-1 202`. Unos 30 s después, la issue tiene el comentario «+1 cliente · C-051 · enterprise · 3 locales» | «Entra un ticket nuevo del mismo problema. Producto se entera solo.» |
| 125–140 | Pestaña de GitHub: cierra la issue como completada | — | La issue cerrada | «Hago de developer: el fix está hecho.» |
| 140–150 | En `/radar`, «Comprobar GitHub» | — | «1 problema resuelto: el copiloto está redactando un aviso para cada cliente» | «Sin webhook en local: la app pregunta a GitHub.» |
| 150–180 | Cola → «Avisos proactivos» → el primero | — | La tarjeta con los tickets del cliente y el borrador: «El 16 de septiembre nos escribiste…» | «Cada cliente recibe un aviso con su fecha y su caso. El agente CX lo revisa como cualquier borrador.» Pulsa `A`. |

**Pre-warm del radar** (en la misma base de datos que la cola):
1. `python -m uv run python -m scripts.radar_backfill --reset --draft` (≈1 min y ≈0,15 $): carga el histórico y redacta las 6 peticiones.
2. Comprueba `/radar`: 6 problemas «Para pedir a producto», P7 (Safari) abierto.
3. `.env` con `GITHUB_TOKEN` y `GITHUB_REPO`. Pulsa «Comprobar GitHub» una vez para confirmar el token.
4. Ten abierta la pestaña del repo de issues, con la sesión iniciada.
5. Plan B sin red: la URL pública tiene el mismo radar ya calculado, con un problema resuelto y sus avisos en la cola.

R-LIVE-1 es de C-051 (Asador Bidasoa), un cliente con Kutxabank en error que no está en el histórico. Su borrador en la cola también es coherente: el agente ve el error de consentimiento.
