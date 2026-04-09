# agent/tools.py — Herramientas del agente
# Generado por AgentKit

"""
Herramientas específicas de Road Tractovan.
Extienden las capacidades de Andrea más allá de responder texto.
"""

import os
import yaml
import logging
from datetime import datetime

logger = logging.getLogger("agentkit")


def cargar_info_negocio() -> dict:
    """Carga la información del negocio desde business.yaml."""
    try:
        with open("config/business.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config/business.yaml no encontrado")
        return {}


def obtener_horario() -> dict:
    """Retorna el horario de atención del negocio."""
    info = cargar_info_negocio()
    return {
        "horario": info.get("negocio", {}).get("horario", "No disponible"),
        "esta_abierto": True,  # TODO: calcular según hora actual y horario
    }


def buscar_en_knowledge(consulta: str) -> str:
    """
    Busca información relevante en los archivos de /knowledge.
    Retorna el contenido más relevante encontrado.
    """
    resultados = []
    knowledge_dir = "knowledge"

    if not os.path.exists(knowledge_dir):
        return "No hay archivos de conocimiento disponibles."

    for archivo in os.listdir(knowledge_dir):
        ruta = os.path.join(knowledge_dir, archivo)
        if archivo.startswith(".") or not os.path.isfile(ruta):
            continue
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
                if consulta.lower() in contenido.lower():
                    resultados.append(f"[{archivo}]: {contenido[:500]}")
        except (UnicodeDecodeError, IOError):
            continue

    if resultados:
        return "\n---\n".join(resultados)
    return "No encontré información específica sobre eso en mis archivos."


# ═══════════════════════════════════════════════════════════════
# Herramientas para AGENDAR CITAS
# ═══════════════════════════════════════════════════════════════

def registrar_cita(telefono: str, nombre: str, empresa: str, fecha: str, hora: str, unidad_interes: str) -> dict:
    """
    Registra una solicitud de cita para visitar el patio en Tepotzotlán.
    En producción esto se conectaría a un calendario o CRM.
    """
    cita = {
        "telefono": telefono,
        "nombre": nombre,
        "empresa": empresa,
        "fecha": fecha,
        "hora": hora,
        "unidad_interes": unidad_interes,
        "registrada": datetime.now().isoformat(),
        "estado": "pendiente_confirmacion"
    }
    logger.info(f"Cita registrada: {cita}")
    return cita


# ═══════════════════════════════════════════════════════════════
# Herramientas para CALIFICAR LEADS
# ═══════════════════════════════════════════════════════════════

def registrar_lead(telefono: str, nombre: str, empresa: str, interes: str, presupuesto: str, urgencia: str) -> dict:
    """
    Registra un lead calificado para seguimiento por el equipo de ventas.
    En producción esto se conectaría a un CRM.
    """
    lead = {
        "telefono": telefono,
        "nombre": nombre,
        "empresa": empresa,
        "interes": interes,
        "presupuesto": presupuesto,
        "urgencia": urgencia,
        "registrado": datetime.now().isoformat(),
        "estado": "nuevo"
    }
    logger.info(f"Lead registrado: {lead}")
    return lead


def calificar_lead(presupuesto: str, urgencia: str) -> str:
    """
    Califica un lead según presupuesto y urgencia.
    Retorna: 'caliente', 'tibio' o 'frio'.
    """
    urgencia_lower = urgencia.lower()
    if "inmediata" in urgencia_lower or "urgente" in urgencia_lower or "esta semana" in urgencia_lower:
        return "caliente"
    elif "mes" in urgencia_lower or "pronto" in urgencia_lower:
        return "tibio"
    return "frio"
