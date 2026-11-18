"""Factory for instantiating model providers based on environment configuration."""

from typing import Optional
from app.config import AppSettings
from app.providers.base import BaseModelProvider
from app.providers.groq_provider import GroqProvider
from app.providers.simulator_provider import SimulatorProvider


def create_model_provider(settings: Optional[AppSettings] = None) -> BaseModelProvider:
    """Instantiate the configured model provider based on application settings.

    Args:
        settings: Application settings. If None, loaded from environment/.env.

    Returns:
        BaseModelProvider instance (GroqProvider or SimulatorProvider).

    Raises:
        ValueError: If model_provider configuration is unsupported.
    """
    cfg = settings or AppSettings()
    provider_type = cfg.model_provider.lower().strip()

    if provider_type == "groq":
        return GroqProvider(
            api_key=cfg.groq_api_key,
            default_model=cfg.groq_model,
        )
    elif provider_type == "simulator":
        try:
            from simulator.main import app as simulator_app
        except ImportError:
            simulator_app = None

        return SimulatorProvider(
            base_url=cfg.simulator_base_url,
            default_model=cfg.simulator_model,
            app=simulator_app,
            timeout=cfg.simulator_timeout,
        )
    else:
        raise ValueError(
            f"Unsupported model provider '{cfg.model_provider}'. "
            "Supported providers are 'groq' and 'simulator'."
        )
