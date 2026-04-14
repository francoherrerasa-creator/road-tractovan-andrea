# agent/sheets.py — Integración con Google Sheets para guardar leads
# Generado por AgentKit

"""
Guarda leads calificados en Google Sheets usando gspread.
Se activa cuando Andrea detecta LEAD_COMPLETO en la conversación.
"""

import os
import re
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

# Columnas esperadas en la hoja (en orden)
COLUMNAS = ["fecha", "nombre", "telefono", "empresa", "producto_buscado", "presupuesto", "nivel_interes", "urgencia", "email", "etapa", "siguiente_accion", "notas"]


def _obtener_hoja():
    """Conecta con Google Sheets usando la Service Account."""
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # En producción: leer credenciales desde variable de entorno
    # En local: leer desde archivo credentials.json
    google_creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if google_creds_json:
        import json
        info = json.loads(google_creds_json)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
    else:
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)

    client = gspread.authorize(creds)
    return client.open_by_key(GOOGLE_SHEETS_ID).worksheet("Inbound")


def extraer_lead(respuesta: str) -> dict | None:
    """
    Busca el bloque [LEAD_COMPLETO]{...}[/LEAD_COMPLETO] en la respuesta de Andrea.
    Retorna el dict con los datos del lead, o None si no hay bloque.
    """
    patron = r"\[LEAD_COMPLETO\](.*?)\[/LEAD_COMPLETO\]"
    match = re.search(patron, respuesta, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1).strip())
    except json.JSONDecodeError as e:
        logger.error(f"Error parseando JSON del lead: {e}")
        return None


def extraer_lead_update(respuesta: str) -> dict | None:
    """Busca [LEAD_UPDATE]{...}[/LEAD_UPDATE] en la respuesta."""
    patron = r"\[LEAD_UPDATE\](.*?)\[/LEAD_UPDATE\]"
    match = re.search(patron, respuesta, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1).strip())
    except json.JSONDecodeError as e:
        logger.error(f"Error parseando JSON de lead update: {e}")
        return None


def limpiar_respuesta(respuesta: str) -> str:
    """Remueve los bloques [LEAD_COMPLETO]...[/LEAD_COMPLETO] y [LEAD_UPDATE]...[/LEAD_UPDATE] de la respuesta antes de enviarla al cliente."""
    patron = r"\[LEAD_COMPLETO\].*?\[/LEAD_COMPLETO\]"
    limpia = re.sub(patron, "", respuesta, flags=re.DOTALL).strip()
    limpia = re.sub(r"\[LEAD_UPDATE\].*?\[/LEAD_UPDATE\]", "", limpia, flags=re.DOTALL).strip()
    return limpia


def buscar_lead_por_telefono(telefono: str) -> int | None:
    """
    Busca un lead por número de teléfono en la columna C de la pestaña Inbound.
    Retorna el número de fila (1-indexed) si lo encuentra, None si no.
    """
    try:
        hoja = _obtener_hoja()
        # Columna C = Teléfono (índice 3). Saltar fila 1 (headers).
        telefonos = hoja.col_values(3)
        for i, tel in enumerate(telefonos[1:], start=2):
            if tel == telefono:
                return i
        return None
    except Exception as e:
        logger.error(f"Error buscando lead por telefono: {e}")
        return None


def crear_lead_inicial(telefono: str, primer_mensaje: str) -> bool:
    """
    Crea una fila inicial cuando un número escribe por primera vez.
    Solo se llenan: Fecha, Teléfono, Etapa, Siguiente Acción y Notas (con el primer mensaje).
    """
    try:
        hoja = _obtener_hoja()
        fila = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),  # Fecha
            "",                       # Nombre
            telefono,                 # Teléfono
            "",                       # Empresa
            "",                       # Producto Buscado
            "",                       # Presupuesto
            "",                       # Nivel de Interés
            "",                       # Urgencia
            "",                       # Email
            "Nuevo Contacto",         # Etapa
            "Andrea conversando",     # Siguiente Acción
            primer_mensaje,           # Notas
        ]
        hoja.append_row(fila, value_input_option="USER_ENTERED")
        logger.info(f"Lead inicial creado para {telefono}")
        return True
    except Exception as e:
        logger.error(f"Error creando lead inicial: {e}")
        return False


def actualizar_lead(telefono: str, lead: dict) -> bool:
    """
    Actualiza la fila existente del lead identificado por teléfono.
    Solo sobrescribe campos que vengan no-vacíos en el dict, conservando lo previo.
    Cambia Etapa a "Calificado" y Siguiente Acción a "Revisar y contactar".
    Si no encuentra la fila, hace append como fallback.
    """
    try:
        fila_num = buscar_lead_por_telefono(telefono)
        hoja = _obtener_hoja()

        if fila_num is None:
            # Fallback: no existe la fila, crearla con todos los datos disponibles
            logger.warning(f"No existe fila para {telefono}, creando nueva como fallback")
            fila = [
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                lead.get("nombre", ""),
                telefono,
                lead.get("empresa", ""),
                lead.get("producto_buscado", ""),
                lead.get("presupuesto", ""),
                lead.get("nivel_interes", ""),
                lead.get("urgencia", ""),
                lead.get("email", ""),
                "Calificado",
                "Revisar y contactar",
                lead.get("notas", ""),
            ]
            hoja.append_row(fila, value_input_option="USER_ENTERED")
            return True

        # Leer fila actual y mergear: solo sobrescribir si el nuevo valor no está vacío
        fila_actual = hoja.row_values(fila_num)
        while len(fila_actual) < 12:
            fila_actual.append("")

        nuevos_valores = [
            fila_actual[0],  # Fecha (mantener original)
            lead.get("nombre", "") or fila_actual[1],
            telefono,
            lead.get("empresa", "") or fila_actual[3],
            lead.get("producto_buscado", "") or fila_actual[4],
            lead.get("presupuesto", "") or fila_actual[5],
            lead.get("nivel_interes", "") or fila_actual[6],
            lead.get("urgencia", "") or fila_actual[7],
            lead.get("email", "") or fila_actual[8],
            "Calificado",                  # Etapa siempre pasa a Calificado
            "Revisar y contactar",         # Siguiente Acción siempre actualizada
            lead.get("notas", "") or fila_actual[11],
        ]
        hoja.update(
            f"A{fila_num}:L{fila_num}",
            [nuevos_valores],
            value_input_option="USER_ENTERED",
        )
        logger.info(f"Lead actualizado en fila {fila_num}: {telefono}")
        return True
    except Exception as e:
        logger.error(f"Error actualizando lead: {e}")
        return False


def actualizar_lead_parcial(telefono: str, datos: dict) -> bool:
    """Actualiza solo los campos proporcionados en la fila del lead, sin cambiar la etapa."""
    try:
        hoja = _obtener_hoja()
        fila_num = buscar_lead_por_telefono(telefono)
        if not fila_num:
            return False

        # Mapeo de campo del JSON a columna en Sheets
        campo_a_columna = {
            "nombre": 2,            # B
            "empresa": 4,           # D
            "producto_buscado": 5,  # E
            "presupuesto": 6,       # F
            "nivel_interes": 7,     # G
            "urgencia": 8,          # H
            "email": 9,             # I
        }

        for campo, valor in datos.items():
            if campo in campo_a_columna and valor:
                hoja.update_cell(fila_num, campo_a_columna[campo], valor)

        logger.info(f"Lead actualizado parcialmente para {telefono}: {list(datos.keys())}")
        return True
    except Exception as e:
        logger.error(f"Error actualizando lead parcialmente: {e}")
        return False


def guardar_lead_en_sheets(lead: dict, telefono: str) -> bool:
    """
    Wrapper compatible con código antiguo. Ahora actualiza la fila existente
    en vez de hacer append. Si no existe, hace fallback a append.
    """
    return actualizar_lead(telefono, lead)


def _calcular_score(urgencia: str) -> int:
    """Calcula score del lead basado en urgencia."""
    urgencia_lower = urgencia.lower()
    # Urgencia alta: palabras que indican inmediatez
    if any(p in urgencia_lower for p in ["hoy", "inmediata", "urgente", "esta semana", "lo antes posible", "ya", "cuanto antes"]):
        return 95
    # Urgencia media: este mes o pronto
    if any(p in urgencia_lower for p in ["este mes", "pronto", "semanas", "quincena", "15 dias"]):
        return 70
    # Urgencia baja: sin prisa o a futuro
    if any(p in urgencia_lower for p in ["no hay prisa", "cotizar", "explorando", "siguiente trimestre", "futuro"]):
        return 40
    # Default: media
    return 65


def obtener_leads() -> list[dict]:
    """Lee todos los leads de la pestaña Inbound y los devuelve en formato JSON para el dashboard."""
    try:
        hoja = _obtener_hoja()
        registros = hoja.get_all_records()

        leads = []
        for i, row in enumerate(registros, start=1):
            urgencia = row.get("Urgencia", "")
            fecha = row.get("Fecha", "")
            nivel = row.get("Nivel de Interés", "")

            lead = {
                "id": i,
                "empresa": row.get("Empresa", ""),
                "contacto": row.get("Nombre", ""),
                "telefono": row.get("Teléfono", ""),
                "email": row.get("Email", ""),
                "producto_buscado": row.get("Producto Buscado", ""),
                "presupuesto": row.get("Presupuesto", ""),
                "nivel_interes": nivel,
                "urgencia": urgencia,
                "stage": row.get("Etapa", "Nuevo Contacto"),
                "siguiente_accion": row.get("Siguiente Acción", ""),
                "fecha_entrada": fecha,
                "fecha_stage": fecha,
                "notas": row.get("Notas", ""),
                "score": _calcular_score(urgencia),
                "historial": [
                    {"fecha": fecha, "evento": "Lead capturado por Andrea via WhatsApp"}
                ],
            }
            leads.append(lead)

        return leads

    except Exception as e:
        logger.error(f"Error leyendo leads de Google Sheets: {e}")
        return []
