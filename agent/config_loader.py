# agent/config_loader.py — Renderiza el prompt desde template + variables
"""
Carga config/business.yaml + config/prompts.yaml y renderiza el prompt final
con las variables del negocio sustituidas. Permite cambiar de industria
modificando solo business.yaml.
"""

import yaml
import logging
from pathlib import Path
from jinja2 import Template

logger = logging.getLogger("agentkit")

CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_business_config() -> dict:
    """Carga config/business.yaml y retorna el dict bajo la clave 'business'."""
    path = CONFIG_DIR / "business.yaml"
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("business", {})
    except FileNotFoundError:
        logger.error(f"{path} no encontrado")
        return {}


def load_prompts_template() -> dict:
    """Carga config/prompts.yaml como template crudo (sin renderizar)."""
    path = CONFIG_DIR / "prompts.yaml"
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error(f"{path} no encontrado")
        return {}


def render_template(template_str: str, variables: dict) -> str:
    """Renderiza un string con Jinja2 usando las variables del negocio."""
    template = Template(template_str)
    return template.render(**variables)


def get_system_prompt() -> str:
    """
    Carga business.yaml + prompts.yaml, renderiza el template y devuelve
    el system prompt completo listo para mandar a Claude.
    """
    business = load_business_config()
    prompts = load_prompts_template()

    raw_prompt = prompts.get("system_prompt", "Eres un asistente útil. Responde en español.")
    return render_template(raw_prompt, business)


def get_fallback_message() -> str:
    """Retorna el mensaje de fallback renderizado."""
    business = load_business_config()
    prompts = load_prompts_template()
    raw = prompts.get("fallback_message", "Disculpa, no entendí tu mensaje.")
    return render_template(raw, business)


def get_error_message() -> str:
    """Retorna el mensaje de error renderizado."""
    business = load_business_config()
    prompts = load_prompts_template()
    raw = prompts.get("error_message", "Lo siento, estoy teniendo problemas técnicos.")
    return render_template(raw, business)
