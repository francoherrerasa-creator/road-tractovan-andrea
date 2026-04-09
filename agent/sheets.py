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
