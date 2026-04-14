# agent/main.py — Servidor FastAPI + Webhook de WhatsApp
# Generado por AgentKit

"""
Servidor principal del agente de WhatsApp.
Funciona con cualquier proveedor (Whapi, Meta, Twilio) gracias a la capa de providers.
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

from agent.brain import generar_respuesta
from agent.memory import inicializar_db, guardar_mensaje, obtener_historial
from agent.providers import obtener_proveedor
from agent.sheets import (
    extraer_lead,
    extraer_lead_update,
    limpiar_respuesta,
    obtener_leads,
    crear_lead_inicial,
    buscar_lead_por_telefono,
    actualizar_lead,
    actualizar_lead_parcial,
)

load_dotenv()

# Configuración de logging según entorno
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

# Proveedor de WhatsApp (se configura en .env con WHATSAPP_PROVIDER)
proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8000))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la base de datos al arrancar el servidor."""
    await inicializar_db()
    logger.info("Base de datos inicializada")
    logger.info(f"Servidor AgentKit corriendo en puerto {PORT}")
    logger.info(f"Proveedor de WhatsApp: {proveedor.__class__.__name__}")
    yield


app = FastAPI(
    title="AgentKit — WhatsApp AI Agent",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — en producción solo Vercel, en desarrollo cualquier origen
cors_origins = (
    ["https://leads-road-tractovan.vercel.app"]
    if ENVIRONMENT == "production"
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/")
async def health_check():
    """Endpoint de salud para Railway/monitoreo."""
    return {"status": "ok", "service": "agentkit"}


@app.get("/leads")
async def listar_leads():
    """Devuelve todos los leads de Google Sheets en formato JSON para el dashboard."""
    leads = obtener_leads()
    return {"total": len(leads), "leads": leads}


@app.api_route("/webhook", methods=["GET", "HEAD"])
@app.api_route("/webhook/messages", methods=["GET", "HEAD"])
async def webhook_verificacion(request: Request):
    """
    Verificación del webhook.
    Whapi hace GET/HEAD para confirmar que el endpoint existe antes de mandar mensajes.
    Meta Cloud API hace GET con hub.challenge para validar la suscripción.
    """
    # Meta Cloud API: responder con hub.challenge si aplica
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    # Whapi y otros: 200 OK basta para confirmar que el webhook existe
    return {"status": "ok"}


@app.post("/webhook")
@app.post("/webhook/messages")
async def webhook_handler(request: Request):
    """
    Recibe mensajes de WhatsApp via el proveedor configurado.
    Procesa el mensaje, genera respuesta con Claude y la envía de vuelta.
    """
    try:
        # Parsear webhook — el proveedor normaliza el formato
        mensajes = await proveedor.parsear_webhook(request)

        for msg in mensajes:
            # Ignorar mensajes propios o vacíos
            if msg.es_propio or not msg.texto:
                continue

            logger.info(f"Mensaje de {msg.telefono}: {msg.texto}")

            # Si es un número nuevo, crear fila inicial en Sheets.
            # Envuelto en try/except: si Sheets falla, el chat sigue funcionando.
            try:
                if buscar_lead_por_telefono(msg.telefono) is None:
                    crear_lead_inicial(msg.telefono, msg.texto)
            except Exception as e:
                logger.error(f"Error verificando/creando lead inicial: {e}")

            # Obtener historial ANTES de guardar el mensaje actual
            # (brain.py agrega el mensaje actual, evitando duplicados)
            historial = await obtener_historial(msg.telefono)

            # Generar respuesta con Claude
            respuesta = await generar_respuesta(msg.texto, historial)

            # Si Sofía emitió LEAD_COMPLETO, actualizar la fila con los datos finales.
            # También envuelto en try/except por seguridad.
            lead = extraer_lead(respuesta)
            if lead:
                try:
                    actualizar_lead(msg.telefono, lead)
                except Exception as e:
                    logger.error(f"Error actualizando lead: {e}")
                respuesta = limpiar_respuesta(respuesta)

            # Detectar actualizaciones parciales de datos
            if not lead:  # Solo si no hubo LEAD_COMPLETO
                lead_update = extraer_lead_update(respuesta)
                if lead_update:
                    try:
                        actualizar_lead_parcial(msg.telefono, lead_update)
                    except Exception as e:
                        logger.error(f"Error actualizando lead parcialmente: {e}")
                    respuesta = limpiar_respuesta(respuesta)

            # Guardar mensaje del usuario Y respuesta del agente en memoria
            await guardar_mensaje(msg.telefono, "user", msg.texto)
            await guardar_mensaje(msg.telefono, "assistant", respuesta)

            # Enviar respuesta por WhatsApp via el proveedor
            await proveedor.enviar_mensaje(msg.telefono, respuesta)

            logger.info(f"Respuesta a {msg.telefono}: {respuesta}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))
