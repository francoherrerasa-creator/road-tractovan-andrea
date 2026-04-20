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


def test_es_cita_agendada():
    """Valida que _es_cita_agendada detecte correctamente mensajes con link de Cal.com + palabras de agendamiento."""
    from agent.main import _es_cita_agendada

    print("\n" + "=" * 55)
    print("   Test: _es_cita_agendada")
    print("=" * 55)

    # Casos que DEBEN retornar True
    casos_true = [
        "Te comparto nuestro calendario para que elijas el horario: https://cal.com/road-tractovan",
        "Aquí puedes agendar: cal.com/road-tractovan",
        "Reserva tu visita en https://cal.com/road-tractovan",
        "Tu cita queda agendada, aquí el link: https://cal.com/road-tractovan",
        "Te comparto nuestro calendario para agendar tu visita: https://cal.com/road-tractovan",
        "Programa tu cita aquí: cal.com/road-tractovan",
    ]

    # Casos que DEBEN retornar False
    casos_false = [
        "Mi número es 5555555555",
        "Tenemos varios modelos disponibles",
        "Visita nuestras instalaciones en Tepotzotlán",
        "Puedes agendar una llamada conmigo mañana",
        "Revisa cal.com para más info",
    ]

    todas_ok = True

    print("\n  Casos TRUE (deben detectar cita):")
    for caso in casos_true:
        resultado = _es_cita_agendada(caso)
        estado = "PASS" if resultado else "FAIL"
        if not resultado:
            todas_ok = False
        print(f"    [{estado}] {caso[:70]}...")

    print("\n  Casos FALSE (no deben detectar cita):")
    for caso in casos_false:
        resultado = _es_cita_agendada(caso)
        estado = "PASS" if not resultado else "FAIL"
        if resultado:
            todas_ok = False
        print(f"    [{estado}] {caso[:70]}...")

    print()
    if todas_ok:
        print("  RESULTADO: PASS — Todos los casos correctos")
    else:
        print("  RESULTADO: FAIL — Hay casos incorrectos")
    print()
    return todas_ok


async def test_buffer():
    """Valida que el buffer acumule mensajes y dispare el callback con debounce."""
    import os
    os.environ["DEBOUNCE_SECONDS"] = "1"  # 1 segundo para test rápido

    # Reimportar con el nuevo valor
    from agent.buffer import MessageBuffer

    print("\n" + "=" * 55)
    print("   Test: MessageBuffer (debounce)")
    print("=" * 55)

    resultados = {}

    async def callback_test(telefono, mensajes):
        resultados[telefono] = mensajes

    buf = MessageBuffer(callback=callback_test)
    buf._buffers = {}  # Reset

    # Simular 3 mensajes rápidos del mismo teléfono
    await buf.agregar("5551234567", "Hola")
    await buf.agregar("5551234567", "Cómo estás?")
    await buf.agregar("5551234567", "Busco un tracto")

    # Esperar a que expire el timer (1s + margen)
    await asyncio.sleep(1.5)

    if "5551234567" in resultados:
        msgs = resultados["5551234567"]
        if msgs == ["Hola", "Cómo estás?", "Busco un tracto"]:
            print("  [PASS] 3 mensajes acumulados y procesados como un solo turno")
        else:
            print(f"  [FAIL] Mensajes inesperados: {msgs}")
    else:
        print("  [FAIL] Callback no fue llamado")

    # Simular mensaje de otro teléfono (no debe mezclar)
    resultados.clear()
    await buf.agregar("5559999999", "Otro cliente")
    await asyncio.sleep(1.5)

    if resultados.get("5559999999") == ["Otro cliente"]:
        print("  [PASS] Teléfonos distintos se procesan por separado")
    else:
        print(f"  [FAIL] Resultado inesperado: {resultados}")

    print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test-etapas":
        test_actualizar_etapa()
    elif len(sys.argv) > 1 and sys.argv[1] == "test-cita":
        test_es_cita_agendada()
    elif len(sys.argv) > 1 and sys.argv[1] == "test-buffer":
        asyncio.run(test_buffer())
    else:
        asyncio.run(main())
