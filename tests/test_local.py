# tests/test_local.py — Simulador de chat en terminal
# Generado por AgentKit

"""
Prueba tu agente sin necesitar WhatsApp.
Simula una conversación en la terminal.
"""

import asyncio
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.brain import generar_respuesta
from agent.memory import inicializar_db, guardar_mensaje, obtener_historial, limpiar_historial
from agent.sheets import extraer_lead, limpiar_respuesta, guardar_lead_en_sheets, actualizar_etapa, ETAPAS_VALIDAS

TELEFONO_TEST = "test-local-001"


async def main():
    """Loop principal del chat de prueba."""
    await inicializar_db()

    print()
    print("=" * 55)
    print("   AgentKit — Test Local")
    print("   Agente: Sofía | Road Tractovan")
    print("=" * 55)
    print()
    print("  Escribe mensajes como si fueras un cliente.")
    print("  Comandos especiales:")
    print("    'limpiar'  — borra el historial")
    print("    'salir'    — termina el test")
    print()
    print("-" * 55)
    print()

    while True:
        try:
            mensaje = input("Tu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nTest finalizado.")
            break

        if not mensaje:
            continue

        if mensaje.lower() == "salir":
            print("\nTest finalizado.")
            break

        if mensaje.lower() == "limpiar":
            await limpiar_historial(TELEFONO_TEST)
            print("[Historial borrado]\n")
            continue

        # Obtener historial ANTES de guardar (brain.py agrega el mensaje actual)
        historial = await obtener_historial(TELEFONO_TEST)

        # Generar respuesta
        respuesta = await generar_respuesta(mensaje, historial)

        # Detectar si Sofía completó la calificación de un lead
        lead = extraer_lead(respuesta)
        if lead:
            print("\n[LEAD DETECTADO — Guardando en Google Sheets...]")
            guardar_lead_en_sheets(lead, TELEFONO_TEST)
            respuesta = limpiar_respuesta(respuesta)

        print(f"\nSofía: {respuesta}")
        print()

        # Guardar mensaje del usuario y respuesta del agente
        await guardar_mensaje(TELEFONO_TEST, "user", mensaje)
        await guardar_mensaje(TELEFONO_TEST, "assistant", respuesta)


def test_actualizar_etapa():
    """Valida que actualizar_etapa funcione con etapas válidas e inválidas."""
    print("\n" + "=" * 55)
    print("   Test: actualizar_etapa")
    print("=" * 55)

    # Test etapas válidas — solo valida que no lanza excepción
    # (requiere un lead existente en Sheets para retornar True)
    telefono_test = "525543503382"
    for etapa in ETAPAS_VALIDAS:
        resultado = actualizar_etapa(telefono_test, etapa)
        estado = "OK" if resultado else "NO ENCONTRADO (esperado si no hay lead en Sheets)"
        print(f"  [{etapa}] -> {estado}")

    # Test etapa inválida — debe retornar False sin tocar Sheets
    etapas_invalidas = ["Rechazado", "En Proceso", "", "nuevo contacto"]
    todas_false = True
    for etapa in etapas_invalidas:
        resultado = actualizar_etapa(telefono_test, etapa)
        if resultado:
            todas_false = False
            print(f"  ERROR: '{etapa}' debería retornar False pero retornó True")
        else:
            print(f"  ['{etapa}'] -> False (correcto, etapa inválida rechazada)")

    if todas_false:
        print("\n  PASS: Todas las etapas inválidas fueron rechazadas correctamente")
    else:
        print("\n  FAIL: Alguna etapa inválida fue aceptada")

    print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test-etapas":
        test_actualizar_etapa()
    else:
        asyncio.run(main())
