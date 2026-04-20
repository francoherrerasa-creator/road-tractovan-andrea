# agent/buffer.py — Buffer de mensajes con debounce
"""
Acumula mensajes de un mismo teléfono y espera N segundos de silencio
antes de procesarlos como un solo turno. Evita respuestas fragmentadas
cuando el cliente manda varios mensajes seguidos.
"""

import os
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("agentkit")

DEBOUNCE_SECONDS = int(os.getenv("DEBOUNCE_SECONDS", "30"))


class MessageBuffer:
    """Buffer in-memory por teléfono con debounce via asyncio."""

    def __init__(self, callback):
        """
        Args:
            callback: async function(telefono, mensajes: list[str]) que se llama
                      cuando el timer expira. Recibe el teléfono y la lista de
                      mensajes acumulados.
        """
        self._callback = callback
        # {telefono: {"messages": list[str], "task": asyncio.Task | None, "lock": asyncio.Lock, "processing": bool}}
        self._buffers: dict = {}

    def _get_or_create(self, telefono: str) -> dict:
        """Obtiene o crea el buffer para un teléfono."""
        if telefono not in self._buffers:
            self._buffers[telefono] = {
                "messages": [],
                "task": None,
                "lock": asyncio.Lock(),
                "processing": False,
            }
        return self._buffers[telefono]

    async def agregar(self, telefono: str, mensaje: str):
        """
        Agrega un mensaje al buffer y reinicia el timer de debounce.
        Si ya se está procesando una respuesta, el mensaje se acumula
        y se procesará cuando termine la respuesta actual.
        """
        buf = self._get_or_create(telefono)

        async with buf["lock"]:
            buf["messages"].append(mensaje)
            logger.info(f"[BUFFER] Mensaje agregado para {telefono}, total: {len(buf['messages'])}. Esperando {DEBOUNCE_SECONDS}s")

            # Cancelar timer previo si existe
            if buf["task"] is not None and not buf["task"].done():
                buf["task"].cancel()
                logger.info(f"[BUFFER] Timer reseteado para {telefono}")

            # Iniciar nuevo timer
            buf["task"] = asyncio.create_task(self._esperar_y_procesar(telefono))

    async def _esperar_y_procesar(self, telefono: str):
        """Espera el debounce y luego procesa los mensajes acumulados."""
        try:
            await asyncio.sleep(DEBOUNCE_SECONDS)
        except asyncio.CancelledError:
            return

        buf = self._buffers.get(telefono)
        if not buf:
            return

        async with buf["lock"]:
            # Si está procesando, no hacer nada — cuando termine, revisará si hay nuevos
            if buf["processing"]:
                logger.info(f"[BUFFER] {telefono} ya está procesando, los mensajes esperan")
                return

            if not buf["messages"]:
                return

            # Tomar los mensajes y limpiar buffer
            mensajes = buf["messages"][:]
            buf["messages"] = []
            buf["processing"] = True

        logger.info(f"[BUFFER] Procesando {len(mensajes)} mensaje(s) acumulados para {telefono}")

        try:
            await self._callback(telefono, mensajes)
        except Exception as e:
            logger.error(f"[BUFFER] Error procesando mensajes de {telefono}: {e}")
        finally:
            async with buf["lock"]:
                buf["processing"] = False

                # Si llegaron mensajes mientras procesábamos, iniciar nuevo timer
                if buf["messages"]:
                    logger.info(f"[BUFFER] Nuevos mensajes llegaron durante procesamiento de {telefono}, reiniciando timer")
                    buf["task"] = asyncio.create_task(self._esperar_y_procesar(telefono))
