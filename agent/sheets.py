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
COLUMNAS = ["fecha", "nombre", "empresa", "flota", "carga", "servicio", "urgencia", "email", "notas", "telefono"]


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
    return client.open_by_key(GOOGLE_SHEETS_ID).sheet1


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


def limpiar_respuesta(respuesta: str) -> str:
    """Remueve el bloque [LEAD_COMPLETO]...[/LEAD_COMPLETO] de la respuesta antes de enviarla al cliente."""
    patron = r"\[LEAD_COMPLETO\].*?\[/LEAD_COMPLETO\]"
    limpia = re.sub(patron, "", respuesta, flags=re.DOTALL).strip()
    return limpia


def guardar_lead_en_sheets(lead: dict, telefono: str) -> bool:
    """
    Guarda un lead calificado en Google Sheets.
    Retorna True si fue exitoso.
    """
    try:
        hoja = _obtener_hoja()

        fila = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            lead.get("nombre", ""),
            lead.get("empresa", ""),
            lead.get("flota", ""),
            lead.get("carga", ""),
            lead.get("servicio", ""),
            lead.get("urgencia", ""),
            lead.get("email", ""),
            lead.get("notas", ""),
            telefono,
        ]

        hoja.append_row(fila, value_input_option="USER_ENTERED")
        logger.info(f"Lead guardado en Google Sheets: {lead.get('nombre', '')} — {lead.get('empresa', '')}")
        return True

    except Exception as e:
        logger.error(f"Error guardando lead en Google Sheets: {e}")
        return False


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
    """
    Lee todos los leads de Google Sheets y los devuelve en formato JSON
    para el dashboard de React.
    """
    try:
        hoja = _obtener_hoja()
        registros = hoja.get_all_records()

        leads = []
        for i, row in enumerate(registros, start=1):
            urgencia = row.get("urgencia", "")
            fecha = row.get("fecha", "")

            lead = {
                "id": i,
                "empresa": row.get("empresa", ""),
                "contacto": row.get("nombre", ""),
                "telefono": row.get("telefono", ""),
                "email": row.get("email", ""),
                "ciudad": "",
                "flota": row.get("flota", ""),
                "tipo_carga": row.get("carga", ""),
                "urgencia": urgencia,
                "servicio": row.get("servicio", ""),
                "stage": "nuevo_contacto",
                "fecha_entrada": fecha,
                "fecha_stage": fecha,
                "notas": row.get("notas", ""),
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
