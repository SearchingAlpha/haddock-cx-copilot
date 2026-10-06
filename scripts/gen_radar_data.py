"""Generate the radar dataset: ~250 tickets over 6 weeks with planted product problems. Spec: docs/specs/data.md.

    python -m uv run python -m scripts.gen_radar_data

Deterministic (seeded). Writes data/radar/tickets.jsonl and data/radar/truth.json, and appends
customers C-011..C-050 to data/customers.json (C-001..C-010 stay as they are). Labels come from the
plan below, so they are right by construction.
"""

import json
import random
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

from app.domain import Customer, RadarTicket

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SEED = 7
START, END = datetime(2026, 8, 24), datetime(2026, 10, 4, 22, 0)
TODAY = date(2026, 10, 4)
GARRIDO = "Distribuciones Garrido"
KUTXA_ERROR = "Kutxabank rechaza el consentimiento PSD2 después de reautorizar (401)"

# --- customers C-011..C-050 ------------------------------------------------------------------
# (name, city, plan, locations, bank, pos, suppliers, contact)
NEW_CUSTOMERS = [
    ("Casa Urrutia", "Bilbao", "pro", 1, "Kutxabank", "Last.app", ["Carnicería Goñi", "Makro"], "Iñaki Urrutia"),
    ("Gure Etxea", "Vitoria-Gasteiz", "starter", 1, "Kutxabank", None, ["Eroski Profesional"], "Ane Ibarra"),
    ("Sidrería Altxerri", "San Sebastián", "pro", 2, "Kutxabank", "Revo", ["Sidras Petritegi", "Makro"], "Jon Etxeberria"),
    ("Pintxos Zazpi", "San Sebastián", "starter", 1, "Kutxabank", "Last.app", ["Makro"], "Maite Zubiri"),
    ("Txoko Berria", "Bilbao", "enterprise", 3, "Kutxabank", "Ágora", ["Carnicería Goñi", "Pescados Getxo"], "Koldo Arrieta"),
    ("Erretegia Mendi", "Pamplona", "pro", 1, "Kutxabank", "Revo", ["Makro"], "Garazi Mendia"),
    ("La Bilbaína", "Bilbao", "pro", 1, "Kutxabank", "Square", ["Eroski Profesional"], "Begoña Larrea"),
    ("Mesón El Fogón", "Madrid", "pro", 1, "Santander", "Revo", [GARRIDO, "Makro"], "Luis Herranz"),
    ("Casa Lucía", "Madrid", "starter", 1, "BBVA", None, [GARRIDO], "Lucía Gómez"),
    ("La Tasquita de Chamberí", "Madrid", "pro", 2, "CaixaBank", "Last.app", [GARRIDO, "Mahou"], "Pedro Sanz"),
    ("Grupo Alcalá Food", "Madrid", "enterprise", 4, "Santander", "Revo", [GARRIDO, "Makro", "Pescados del Cantábrico"], "Elena Ruiz"),
    ("El Rincón de Getafe", "Getafe", "starter", 1, "BBVA", None, [GARRIDO], "Antonio Pardo"),
    ("Taberna Los Arcos", "Alcalá de Henares", "pro", 1, "Bankinter", "Ágora", [GARRIDO, "Mahou"], "Rosa Medina"),
    ("Brasería Sierra", "Collado Villalba", "pro", 1, "Santander", "Revo", [GARRIDO], "Jorge Alonso"),
    ("Arrocería La Barca", "Toledo", "starter", 1, "Unicaja", None, [GARRIDO, "Makro"], "Carmen Toledano"),
    ("Cervecería El Grifo", "Madrid", "pro", 1, "ING", "Last.app", [GARRIDO, "Mahou"], "Álvaro Gil"),
    ("Asador Castilla", "Segovia", "pro", 2, "CaixaBank", "Revo", [GARRIDO, "Carnes Selectas Guadarrama"], "Teresa Velasco"),
    ("Bar La Plaza", "Guadalajara", "starter", 1, "Ibercaja", None, [GARRIDO], "Manuel Ortega"),
    ("Gastrobar Lavapiés", "Madrid", "pro", 1, "BBVA", "Square", [GARRIDO, "Makro"], "Sara Benítez"),
    ("Can Pujol", "Barcelona", "pro", 2, "CaixaBank", "Last.app", ["Makro", "Estrella Damm"], "Jordi Pujol"),
    ("El Xiringuito", "Sitges", "starter", 1, "Sabadell", "Square", ["Estrella Damm"], "Núria Vidal"),
    ("Bistró Gràcia", "Barcelona", "pro", 1, "Sabadell", "Ágora", ["Mercabarna Fruites"], "Pau Ferrer"),
    ("Grup Mediterrani", "Barcelona", "enterprise", 5, "CaixaBank", "Revo", ["Makro", "Mercabarna Fruites", "Estrella Damm"], "Montse Soler"),
    ("La Huerta de Murcia", "Murcia", "pro", 1, "Cajamar", "Last.app", ["Frutas Hermanos Ruiz"], "Ginés Martínez"),
    ("Casa Pepa", "Valencia", "starter", 1, "Sabadell", None, ["Pescados Albufera"], "Pepa Ferrando"),
    ("Arrocería Malvarrosa", "Valencia", "pro", 2, "CaixaBank", "Revo", ["Pescados Albufera", "Makro"], "Vicent Llorens"),
    ("Mar de Cádiz", "Cádiz", "pro", 1, "Unicaja", "Last.app", ["Cruzcampo"], "Rocío Bernal"),
    ("Freiduría Triana", "Sevilla", "starter", 1, "CaixaBank", None, ["Cruzcampo"], "Curro Romero"),
    ("Grupo Sur Gastro", "Málaga", "enterprise", 3, "Unicaja", "Revo", ["Cruzcampo", "Distribuciones Andaluzas"], "Inma Castillo"),
    ("Pulpería O Porto", "A Coruña", "pro", 1, "Abanca", "Ágora", ["Mariscos Rías Baixas"], "Xosé Varela"),
    ("Casa Fermín", "Oviedo", "pro", 1, "Unicaja", "Last.app", ["Sidra El Gaitero"], "Fermín Álvarez"),
    ("La Bodeguilla", "Salamanca", "starter", 1, "Santander", None, ["Makro"], "Isabel Hernández"),
    ("Restaurante Marisma", "Huelva", "pro", 1, "CaixaBank", "Square", ["Mariscos Rías Baixas"], "Paco Domínguez"),
    ("El Patio Cordobés", "Córdoba", "pro", 2, "BBVA", "Ágora", ["Cruzcampo"], "Rafael Luque"),
    ("Burger Lab", "Zaragoza", "pro", 3, "Ibercaja", "Revo", ["Makro"], "Marcos Lahoz"),
    ("Grupo Tapa Norte", "Santander", "enterprise", 4, "Santander", "Last.app", ["Makro", "Pescados del Cantábrico"], "Cristina Ceballos"),
    ("Ramen Kaze", "Madrid", "pro", 1, "ING", "Square", ["Makro"], "Kenji Moreno"),
    ("Vegano Verde", "Valencia", "starter", 1, "ING", None, ["Huerta de Aranjuez"], "Laura Peris"),
    ("Pizzería Nápoles", "Alicante", "pro", 2, "Sabadell", "Last.app", ["Makro"], "Davide Russo"),
    ("Cafetería Aurora", "Valladolid", "starter", 1, "BBVA", None, ["Cafés Orús"], "Aurora Prieto"),
]
POS_DISCONNECTED = {"C-049"}  # decoy: sales missing because the POS is disconnected


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in text if ch.isalnum() and not unicodedata.combining(ch))


def _price(plan: str, locations: int) -> float:
    return {"starter": 59.0, "pro": 149.0}.get(plan, float(max(420, 140 * locations)))


def build_customers(rng: random.Random) -> list[dict]:
    out = []
    for n, (name, city, plan, locations, bank, pos, suppliers, contact) in enumerate(NEW_CUSTOMERS, start=11):
        cid = f"C-{n:03d}"
        kutxa = bank == "Kutxabank"
        integrations = [{
            "kind": "bank", "provider": bank, "status": "error" if kutxa else "ok",
            "last_sync": "2026-09-14T06:00:00" if kutxa else "2026-10-04T06:00:00",
            **({"error": KUTXA_ERROR} if kutxa else {}),
        }]
        if pos:
            off = cid in POS_DISCONNECTED
            integrations.append({"kind": "pos", "provider": pos, "status": "disconnected" if off else "ok",
                                 "last_sync": "2026-09-27T23:50:00" if off else "2026-10-04T06:10:00"})
        invoices, seq = [], 1
        for supplier in suppliers:
            for issue in ([date(2026, 8, 27), date(2026, 9, 12), date(2026, 9, 26)] if supplier == GARRIDO
                          else [date(2026, 9, 18 + rng.randint(0, 10))]):
                failed = supplier == GARRIDO and issue >= date(2026, 9, 1)
                invoices.append({
                    "id": f"F-{n:02d}{seq:02d}", "supplier": supplier, "issue_date": issue.isoformat(),
                    "uploaded_at": f"{issue + timedelta(days=1)}T09:{seq * 7 % 60:02d}:00",
                    "amount_eur": round(rng.uniform(90, 2400), 2),
                    "status": "failed" if failed else "processed",
                    **({"error": "No se pudo leer el total"} if failed else {}),
                })
                seq += 1
        first = contact.split()[0].lower()
        out.append({
            "id": cid, "name": name, "city": city, "plan": plan, "locations": locations,
            "contact_name": contact, "contact_email": f"{_slug(first)}@{_slug(name)}.es",
            "signup_date": (date(2025, 1, 15) + timedelta(days=rng.randint(0, 480))).isoformat(),
            "billing": {"monthly_price_eur": _price(plan, locations), "payment_status": "ok",
                        "next_billing_date": f"2026-10-{rng.randint(5, 28):02d}"},
            "integrations": integrations, "invoices": invoices,
        })
    return out


# --- planted problems -------------------------------------------------------------------------
# Each body is a template: {supplier} {bank} {pos} {day} {dish} {n} {locales}. Labels come from here.

PROBLEMS = [
    {
        "id": "P1", "title": "El OCR no lee el total de las facturas de Distribuciones Garrido desde el release del 1-sep",
        "component": "invoices.ocr", "kind": "bug", "entity": GARRIDO, "start": "2026-09-01",
        "shape": "spike", "count": 32, "customers": "supplier:" + GARRIDO,
        "category": "invoices", "priority": ["high", "high", "urgent", "normal"],
        "tools": ["get_invoices", "search_kb"], "articles": ["kb-03"],
        "key_point": "Las facturas de Distribuciones Garrido fallan con «No se pudo leer el total» desde el 1-sep",
        "subjects": ["Facturas de Garrido en rojo", "No se leen las facturas de Garrido", "Error en factura Distribuciones Garrido",
                     "Garrido: no se lee el total", "Otra factura de Garrido con error", "Facturas en error"],
        "bodies": [
            "Desde principios de mes todas las facturas de {supplier} me salen en rojo. Las de otros proveedores van bien. ¿Qué está pasando?",
            "Las facturas de {supplier} no se leen. Me sale «No se pudo leer el total». Las subo en PDF original, no es una foto.",
            "Otra vez {supplier}: la factura del {day} se queda en error. Ya tengo varias así y la gestoría me las pide.",
            "El total de las facturas de {supplier} sale vacío. Antes funcionaba perfecto. ¿Habéis cambiado algo?",
            "{supplier} nos manda ahora las facturas con dos tipos de IVA en columnas y haddock no saca el total. Las de antes de septiembre sí se leyeron.",
            "He subido 3 veces la misma factura de {supplier} y siempre da error de lectura. El PDF se ve perfecto.",
            "no me lee las facturas de garrido!! no puedo cerrar el mes asi",
            "Buenas, ¿hay algún problema con {supplier}? En el bar de al lado les pasa lo mismo, nos lo han comentado.",
            "Me aparece «No se pudo leer el total» en todas las facturas de {supplier} de septiembre. ¿Tengo que meterlas a mano?",
            "Las facturas de {supplier} se quedan en error desde hace semanas. Es nuestro proveedor principal, necesito una solución.",
        ],
        "bodies_ca": ["Les factures de {supplier} surten en vermell des de setembre. Diu «No se pudo leer el total». Les altres van bé."],
    },
    {
        "id": "P2", "title": "Kutxabank no sincroniza desde el 15-sep: rechaza el consentimiento PSD2 después de reautorizar",
        "component": "bank.sync", "kind": "bug", "entity": "Kutxabank", "start": "2026-09-15",
        "shape": "spike", "count": 22, "customers": "list:C-011,C-012,C-013,C-014,C-015,C-016,C-017",
        "category": "bank", "priority": ["high", "urgent", "high"],
        "tools": ["get_bank_sync_status", "search_kb"], "articles": ["kb-07"],
        "key_point": "La conexión con Kutxabank está en error: rechaza el consentimiento después de reautorizar",
        "subjects": ["Kutxabank no sincroniza", "Banco sin movimientos", "Error al reautorizar Kutxabank",
                     "La conexión con el banco falla", "Kutxabank otra vez"],
        "bodies": [
            "Los movimientos de {bank} no entran desde el día 15. He reautorizado la conexión dos veces y vuelve a fallar.",
            "Me pide reautorizar {bank} cada día. Lo hago, pone que todo bien, y al día siguiente otra vez error.",
            "La conciliación está parada porque el banco ({bank}) no sincroniza desde hace una semana. ¿Es cosa vuestra o del banco?",
            "Error de conexión con {bank}. He seguido los pasos del artículo de ayuda y no se arregla.",
            "kutxabank no va, ni reautorizando. llevamos dias sin ver movimientos",
            "Desde mediados de mes {bank} nos da error 401 al sincronizar. En la app del banco todo funciona.",
            "Necesito los movimientos del banco para el cierre y {bank} no actualiza nada desde el 14. Urgente por favor.",
            "Otro restaurante de la zona que también usa {bank} tiene el mismo problema. ¿Sabéis algo?",
        ],
        "bodies_ca": [],
    },
    {
        "id": "P3", "title": "Revo duplica las ventas cuando el cierre de caja pasa de medianoche",
        "component": "pos.sales", "kind": "bug", "entity": "Revo", "start": "2026-09-08",
        "shape": "steady", "count": 26, "customers": "pos:Revo",
        "category": "pos", "priority": ["high", "high", "normal", "urgent"],
        "tools": ["get_customer", "search_kb"], "articles": ["kb-10"],
        "key_point": "Las ventas de Revo aparecen duplicadas en los días con cierre de caja después de las 00:00",
        "subjects": ["Ventas duplicadas", "Las ventas del TPV salen dobles", "Revo: ventas repetidas",
                     "El P&L infla las ventas", "Ventas del sábado duplicadas"],
        "bodies": [
            "Las ventas del {day} salen dobles en haddock. En {pos} el total es la mitad.",
            "Cuando cerramos caja después de medianoche, las ventas de {pos} aparecen dos veces. Los días que cerramos antes, bien.",
            "El P&L me dice que vendimos el doble el fin de semana. He mirado y los tickets de {pos} están repetidos.",
            "Tengo ventas duplicadas del TPV ({pos}) en varios días de septiembre. Me descuadra todo el food cost.",
            "ventas repetidas otra vez, el viernes cerramos a la 1 y sale todo doble",
            "¿Por qué haddock suma dos veces las ventas de {pos} algunos días? Siempre son viernes y sábados.",
            "Nuestra encargada ha visto que las ventas del {day} están duplicadas. Usamos {pos}. ¿Podéis revisarlo?",
        ],
        "bodies_en": ["Sales from {pos} show up twice in haddock on days when we close the till after midnight. Can you check?"],
    },
    {
        "id": "P4", "title": "El coste del escandallo no se actualiza cuando cambia el precio del proveedor",
        "component": "inventory.recipes", "kind": "bug", "entity": None, "start": "2026-09-20",
        "shape": "steady", "count": 18, "customers": "list:C-001,C-004,C-030,C-032,C-035,C-040,C-044,C-047,C-049",
        "category": "inventory", "priority": ["normal", "high", "normal"],
        "tools": ["search_kb"], "articles": ["kb-12"],
        "key_point": "El escandallo sigue con el precio antiguo aunque la factura nueva trae otro precio",
        "subjects": ["El escandallo no se actualiza", "Food cost mal", "Precio antiguo en las recetas",
                     "Coste de receta incorrecto"],
        "bodies": [
            "He subido la factura nueva con el aceite más caro y el escandallo de la {dish} sigue con el precio antiguo.",
            "El food cost de la carta no cambia aunque los precios de los proveedores han subido este mes.",
            "El coste de la {dish} en el escandallo es el de agosto. La factura de septiembre trae otro precio y no se refleja.",
            "¿Cada cuánto se actualiza el coste de las recetas? Llevo una semana con precios viejos en los escandallos.",
            "Los escandallos no recogen los precios nuevos. He probado a editar la receta y nada.",
            "el coste de los platos no se actualiza, tengo la {dish} con el precio de hace un mes",
        ],
        "bodies_ca": ["L'escandall de la {dish} no s'actualitza amb el preu nou de la factura."],
    },
    {
        "id": "P5", "title": "El Excel exportado del P&L suma el IVA en las ventas",
        "component": "reports.export", "kind": "bug", "entity": None, "start": "2026-09-25",
        "shape": "rising", "count": 14, "customers": "list:C-002,C-006,C-031,C-034,C-037,C-041,C-046,C-050",
        "category": "reports", "priority": ["high", "normal", "high"],
        "tools": ["search_kb"], "articles": ["kb-13"],
        "key_point": "El P&L en pantalla está bien, pero el Excel exportado muestra las ventas con IVA",
        "subjects": ["El Excel del P&L no cuadra", "Export del P&L con IVA", "La gestoría dice que no cuadra",
                     "Error en el informe exportado"],
        "bodies": [
            "El Excel del P&L que exporto no cuadra con lo que veo en pantalla. Las ventas salen más altas.",
            "Mi gestoría dice que el P&L exportado suma el IVA en las ventas. En la web sale bien.",
            "He descargado el informe de septiembre en Excel y las ventas tienen el IVA incluido. Antes no pasaba.",
            "el export del pyg sale mal, las ventas con iva",
            "La diferencia entre el P&L en pantalla y el Excel es justo el 10% de IVA. ¿Es un error del export?",
        ],
        "bodies_ca": [],
    },
    {
        "id": "P6", "title": "Petición: un P&L consolidado de todos los locales",
        "component": "reports.pnl", "kind": "feature", "entity": None, "start": "2026-08-24",
        "shape": "steady", "count": 12, "customers": "list:C-001,C-020,C-030,C-036,C-045,C-046",
        "category": "reports", "priority": ["low", "normal", "low"],
        "tools": ["search_kb"], "articles": ["kb-13"],
        "key_point": "haddock no tiene un P&L consolidado de varios locales",
        "subjects": ["P&L de todos los locales", "Informe consolidado", "Sugerencia: vista multi-local",
                     "Ver los {locales} locales juntos"],
        "bodies": [
            "Tenemos {locales} locales y queremos ver un P&L conjunto. Ahora tengo que sumar los informes a mano.",
            "¿Podéis añadir un informe consolidado de todos los locales? Sería muy útil para el socio.",
            "Sugerencia: una vista del P&L con todos los locales y la comparación entre ellos.",
            "Cada mes exporto el P&L de los {locales} locales y los junto en un Excel. ¿Está previsto un consolidado?",
        ],
        "bodies_ca": [],
    },
    {
        "id": "P7", "title": "En Safari no se descarga el PDF original de la factura",
        "component": "invoices.suppliers", "kind": "bug", "entity": None, "start": "2026-09-28",
        "shape": "steady", "count": 2, "customers": "list:C-042,C-048",
        "category": "invoices", "priority": ["normal"],
        "tools": ["search_kb"], "articles": ["kb-01"],
        "key_point": "El botón de descarga del PDF original no funciona en Safari",
        "subjects": ["No puedo descargar la factura"],
        "bodies": ["Desde el Mac (Safari) el botón de descargar el PDF original de la factura no hace nada. En Chrome sí funciona."],
        "bodies_ca": [],
    },
]

# --- decoys: same words as a planted problem, another cause ----------------------------------
# (component, kind, entity rule, count, category, tools, subjects, bodies, key_point)
DECOYS = [
    ("invoices.ocr", "user_error", "supplier:other", 9, "invoices", ["get_invoices", "search_kb"],
     ["Factura con error de lectura", "No se lee la factura"],
     ["La factura de {supplier} que subí ayer sale en rojo. La foto la hice con el móvil en el coche, igual se ve mal.",
      "Me da error de lectura una factura de {supplier}. Está un poco arrugada, ¿la vuelvo a escanear?",
      "Subí la foto de un albarán de {supplier} y no lee el total. ¿Tiene que ser la factura?"],
     "La foto es borrosa o no es una factura: volver a subirla nítida (kb-03)"),
    ("invoices.duplicates", "user_error", "supplier:" + GARRIDO, 4, "invoices", ["get_invoices", "search_kb"],
     ["Factura de Garrido duplicada"],
     ["Me aparece dos veces la misma factura de {supplier}. Creo que la subí por email y también desde la app."],
     "La misma factura se subió dos veces: borrar el duplicado (kb-04)"),
    ("bank.sync", "how_to", "bank:Kutxabank", 4, "bank", ["get_bank_sync_status", "search_kb"],
     ["Segunda cuenta de Kutxabank", "Añadir otra cuenta"],
     ["¿Cómo conecto una segunda cuenta de {bank}? La de la tarjeta de empresa.",
      "Queremos añadir la cuenta de {bank} del segundo local. ¿Se puede?"],
     "Explicar cómo conectar otra cuenta (kb-06)"),
    ("bank.sync", "user_error", "bank:other", 6, "bank", ["get_bank_sync_status", "search_kb"],
     ["El banco no sincroniza", "Error de conexión con el banco"],
     ["He cambiado la contraseña de la banca online de {bank} y ahora haddock no sincroniza.",
      "Desde que el banco ({bank}) me cambió la tarjeta de coordenadas la conexión da error."],
     "Reautorizar la conexión después del cambio de credenciales (kb-07)"),
    ("pos.sync", "how_to", "pos:Revo", 4, "pos", ["get_customer", "search_kb"],
     ["Segundo terminal de Revo", "Conectar otra caja"],
     ["Hemos puesto un segundo terminal de {pos} en la terraza. ¿Cómo lo conecto?",
      "¿Las ventas del segundo terminal de {pos} entran solas o hay que configurar algo?"],
     "Explicar cómo conectar otro terminal (kb-09)"),
    ("pos.sync", "user_error", "list:C-049", 3, "pos", ["get_customer", "search_kb"],
     ["No aparecen las ventas", "Faltan ventas del TPV"],
     ["Desde el domingo no aparecen las ventas de {pos}. ¿Pasa algo?",
      "Faltan las ventas de esta semana. El TPV funciona normal."],
     "El TPV está desconectado desde el 27-sep: reconectarlo (kb-10)"),
    ("inventory.recipes", "how_to", "any", 4, "inventory", ["search_kb"],
     ["Cómo crear un escandallo", "Escandallos"],
     ["¿Cómo creo el escandallo de un plato nuevo? Quiero saber el food cost de la {dish}.",
      "¿Se pueden poner mermas en los escandallos?"],
     "Explicar los escandallos (kb-12)"),
    ("reports.export", "how_to", "any", 3, "reports", ["search_kb"],
     ["Exportar el P&L", "Excel del informe"],
     ["¿Cómo exporto el P&L a Excel para la gestoría?"],
     "Explicar el export del P&L (kb-13)"),
    ("pos.sales", "how_to", "pos:Revo", 3, "pos", ["get_customer", "search_kb"],
     ["Ventas por camarero"],
     ["¿Se pueden ver las ventas de {pos} por camarero en haddock?"],
     "haddock muestra las ventas por día y por familia; por camarero, en el TPV"),
]

NOISE = [
    ("account.users", "how_to", 22, "account", ["search_kb"],
     ["Dar acceso a mi gestor", "Nuevo usuario", "Permisos de un encargado", "Quitar acceso"],
     ["¿Cómo doy acceso a mi gestoría para que vea las facturas?",
      "Quiero que mi encargado vea las ventas pero no el banco. ¿Se puede?",
      "Un camarero se ha ido, ¿cómo le quito el acceso?",
      "¿Cuántos usuarios puedo tener en mi plan?"],
     "Explicar usuarios y permisos (kb-14)"),
    ("account.billing", "how_to", 18, "account", ["get_customer", "search_kb"],
     ["Cambio de plan", "Factura de haddock", "Dudas con la cuota"],
     ["Quiero pasar al plan pro. ¿Cambia el precio este mes?",
      "¿Dónde descargo las facturas de haddock para mi contabilidad?",
      "¿Puedo cambiar la tarjeta con la que pago haddock?"],
     "Explicar el plan y la facturación (kb-15)"),
    ("invoices.suppliers", "how_to", 14, "invoices", ["search_kb"],
     ["Proveedor duplicado", "Unificar proveedores", "Dar de alta un proveedor"],
     ["Me sale el mismo proveedor dos veces con nombres distintos. ¿Los puedo juntar?",
      "¿Cómo doy de alta un proveedor nuevo?",
      "¿Puedo reenviar las facturas por email en vez de subirlas?"],
     "Explicar proveedores (kb-05)"),
    ("bank.reconciliation", "how_to", 12, "bank", ["search_kb"],
     ["Conciliación", "Movimiento sin factura"],
     ["Tengo un movimiento del banco que no encuentra factura. ¿Cómo lo concilio a mano?",
      "¿Cómo funciona la conciliación automática?"],
     "Explicar la conciliación (kb-08)"),
    ("inventory.stock", "how_to", 10, "inventory", ["search_kb"],
     ["Recuento de inventario", "Inventario mensual"],
     ["¿Cómo hago el recuento de inventario de fin de mes?",
      "¿Puedo hacer el inventario desde el móvil?"],
     "Explicar el recuento (kb-11)"),
    ("other", "how_to", 8, "other", ["search_kb"],
     ["Gracias", "Sugerencia", "Duda general"],
     ["Solo quería daros las gracias, el cierre de mes ahora nos lleva la mitad.",
      "¿Tenéis app para Android?",
      "¿Hacéis formaciones para el equipo nuevo?"],
     "Responder con amabilidad; no hace falta acción"),
]

DISHES = ["tortilla", "paella", "hamburguesa clásica", "croqueta de jamón", "ensalada de la casa", "pizza margarita"]
OPENERS = ["Hola,\n\n", "Buenas,\n\n", "Hola equipo,\n\n", "", "Buenos días,\n\n"]
REPEAT = "Os escribí hace unos días por esto y sigue igual. "


def _customers_for(rule: str, customers: dict[str, Customer]) -> list[str]:
    kind, _, value = rule.partition(":")
    ids = sorted(customers)
    if kind == "list":
        return value.split(",")
    if kind == "supplier":
        if value == "other":
            return [c for c in ids if any(i.supplier != GARRIDO for i in customers[c].invoices)]
        return [c for c in ids if any(i.supplier == value for i in customers[c].invoices)]
    if kind in ("bank", "pos"):
        has = [c for c in ids if any(i.kind == kind and (value == "other" or i.provider == value)
                                     for i in customers[c].integrations)]
        if value == "other":
            has = [c for c in has if not any(i.kind == "bank" and i.provider == "Kutxabank"
                                             for i in customers[c].integrations)]
        return has
    return ids


def _when(rng: random.Random, start: datetime, shape: str) -> datetime:
    span = (END - start).total_seconds()
    if shape == "spike":
        offset = min(rng.expovariate(1 / (6 * 86400)), span)
    elif shape == "rising":
        offset = rng.triangular(0, span, span)
    else:
        offset = rng.uniform(0, span)
    t = start + timedelta(seconds=offset)
    return t.replace(hour=rng.randint(8, 22), minute=rng.choice([0, 5, 12, 20, 33, 41, 48, 55]), second=0, microsecond=0)


def _fill(text: str, rng: random.Random, customer: Customer, entity: str | None, when: datetime) -> str:
    supplier = entity if entity and entity in {i.supplier for i in customer.invoices} else (
        rng.choice([i.supplier for i in customer.invoices if i.supplier != GARRIDO] or ["Makro"]))
    bank = next((i.provider for i in customer.integrations if i.kind == "bank"), "el banco")
    pos = next((i.provider for i in customer.integrations if i.kind == "pos"), "el TPV")
    day = (when - timedelta(days=rng.randint(1, 4))).strftime("%d/%m")
    return text.format(supplier=supplier, bank=bank, pos=pos, day=day, dish=rng.choice(DISHES),
                       locales=customer.locations, n=rng.randint(2, 5))


def _body(rng, template: str, customer: Customer, entity, when, repeat: bool, lang: str) -> str:
    text = _fill(template, rng, customer, entity, when)
    if lang != "es":
        sign = customer.contact_name.split()[0]
        return f"{'Hola' if lang == 'ca' else 'Hi'},\n\n{text}\n\n{sign}"
    opener = rng.choice(OPENERS) if text[0].isupper() else ""
    sign = rng.choice([f"\n\n{customer.contact_name.split()[0]}", f"\n\nGracias,\n{customer.contact_name}",
                       f"\n\nUn saludo,\n{customer.contact_name}\n{customer.name}", ""])
    return f"{opener}{REPEAT if repeat else ''}{text}{sign}"


def _sentiment(rng, kind: str, repeat: bool) -> str:
    if kind in ("bug",):
        return "very_negative" if repeat and rng.random() < 0.5 else rng.choice(["negative", "negative", "neutral"])
    return rng.choice(["neutral", "neutral", "positive"])


def build_tickets(rng: random.Random, customers: dict[str, Customer]) -> tuple[list[dict], list[dict]]:
    raw, truth = [], []
    for p in PROBLEMS:
        pool = _customers_for(p["customers"], customers)
        start = datetime.fromisoformat(p["start"])
        order = pool + [rng.choice(pool) for _ in range(p["count"] - len(pool))]
        seen: set[str] = set()
        times = sorted(_when(rng, start, p["shape"]) for _ in order)
        rng.shuffle(order)
        for cid, when in zip(order, times):
            c = customers[cid]
            lang = "es"
            templates = p["bodies"]
            if p.get("bodies_ca") and rng.random() < 0.08:
                lang, templates = "ca", p["bodies_ca"]
            elif p.get("bodies_en") and rng.random() < 0.08:
                lang, templates = "en", p["bodies_en"]
            raw.append({
                "customer_id": cid, "channel": rng.choice(["email", "email", "chat"]), "created_at": when,
                "subject": _fill(rng.choice(p["subjects"]), rng, c, p["entity"], when),
                "body": _body(rng, rng.choice(templates), c, p["entity"], when, cid in seen, lang),
                "labels": {
                    "category": p["category"], "priority": rng.choice(p["priority"]),
                    "sentiment": _sentiment(rng, p["kind"], cid in seen), "language": lang,
                    "expected_tools": p["tools"], "relevant_articles": p["articles"],
                    "key_points": [p["key_point"]], "should_escalate": False,
                    "component": p["component"], "kind": p["kind"], "entity": p["entity"], "problem_id": p["id"],
                },
            })
            seen.add(cid)
        truth.append({k: p[k] for k in ("id", "title", "component", "kind", "entity", "start")}
                     | {"customers": sorted(set(order))})

    for component, kind, rule, count, category, tools, subjects, bodies, key_point in DECOYS:
        pool = _customers_for(rule, customers)
        for _ in range(count):
            cid = rng.choice(pool)
            c, when = customers[cid], _when(rng, START, "steady")
            entity = _decoy_entity(rule, c, rng)
            raw.append(_plain(rng, c, when, subjects, bodies, entity, category, tools, key_point,
                              component, kind, decoy=True))

    for component, kind, count, category, tools, subjects, bodies, key_point in NOISE:
        for _ in range(count):
            c, when = customers[rng.choice(sorted(customers))], _when(rng, START, "steady")
            raw.append(_plain(rng, c, when, subjects, bodies, None, category, tools, key_point, component, kind))

    raw.sort(key=lambda t: t["created_at"])
    tickets = []
    for n, t in enumerate(raw, start=1):
        t = {"id": f"R-{n:03d}", **t, "created_at": t["created_at"].isoformat()}
        tickets.append(RadarTicket.model_validate(t).model_dump(mode="json"))
    by_problem: dict[str, list[str]] = {}
    for t in tickets:
        if t["labels"]["problem_id"]:
            by_problem.setdefault(t["labels"]["problem_id"], []).append(t["id"])
    for p in truth:
        p["tickets"] = by_problem[p["id"]]
    return tickets, truth


def _decoy_entity(rule: str, c: Customer, rng: random.Random) -> str | None:
    kind, _, value = rule.partition(":")
    if kind == "supplier":
        if value == "other":
            return rng.choice(sorted({i.supplier for i in c.invoices if i.supplier != GARRIDO}))
        return value
    if kind in ("bank", "pos"):
        return next(i.provider for i in c.integrations if i.kind == kind)
    if kind == "list":
        return next((i.provider for i in c.integrations if i.kind == "pos"), None)
    return None


def _plain(rng, c, when, subjects, bodies, entity, category, tools, key_point, component, kind, decoy=False):
    return {
        "customer_id": c.id, "channel": rng.choice(["email", "chat"]), "created_at": when,
        "subject": rng.choice(subjects),
        "body": _body(rng, rng.choice(bodies), c, entity, when, False, "es"),
        "labels": {
            "category": category, "priority": "normal" if kind == "user_error" else rng.choice(["normal", "low"]),
            "sentiment": _sentiment(rng, kind, False), "language": "es", "expected_tools": tools,
            "relevant_articles": [], "key_points": [key_point], "should_escalate": False,
            "component": component, "kind": kind, "entity": entity, "problem_id": None, "decoy": decoy,
        },
    }


def main() -> None:
    rng = random.Random(SEED)
    path = DATA / "customers.json"
    text = path.read_text(encoding="utf-8")
    # C-001..C-010 are hand-formatted: keep their text as it is, replace only what comes after.
    marker = ',\n  {\n    "id": "C-011"'
    head = text[: text.index(marker)] if marker in text else text[: text.rindex("\n]")]
    new = build_customers(rng)
    entries = ["  " + json.dumps(c, ensure_ascii=False, indent=2).replace("\n", "\n  ") for c in new]
    path.write_text(head + ",\n" + ",\n".join(entries) + "\n]\n", encoding="utf-8")
    all_customers = json.loads(path.read_text(encoding="utf-8"))
    customers = {c["id"]: Customer.model_validate(c) for c in all_customers}

    tickets, truth = build_tickets(rng, customers)
    out = DATA / "radar"
    out.mkdir(exist_ok=True)
    (out / "tickets.jsonl").write_text(
        "".join(json.dumps(t, ensure_ascii=False) + "\n" for t in tickets), encoding="utf-8")
    (out / "truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    planted = sum(len(p["tickets"]) for p in truth)
    print(f"{len(customers)} customers, {len(tickets)} tickets: {planted} in {len(truth)} planted problems, "
          f"{sum(t['labels']['decoy'] for t in tickets)} decoys")
    for p in truth:
        print(f"  {p['id']} {len(p['tickets']):3} tickets {len(p['customers']):2} customers  {p['title']}")


if __name__ == "__main__":
    main()
