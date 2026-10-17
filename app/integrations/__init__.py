from flask import current_app

from .base import IdentityProvider, ProviderMisconfigured
from .pustik import PustikIdentityProvider
from .sample import SampleIdentityProvider

_PROVIDER_KEY = "identity_provider"


def provider_name(config):
    return (config.get("IDENTITY_PROVIDER") or "sample").strip().lower()


def identity_provider_is_sample(config):
    return provider_name(config) == "sample"


def build_identity_provider(config):
    name = provider_name(config)
    if name == "sample":
        return SampleIdentityProvider()
    if name == "pustik":
        return PustikIdentityProvider(
            base_url=config.get("PUSTIK_BASE_URL", ""),
            api_key=config.get("PUSTIK_API_KEY", ""),
            timeout=config.get("PUSTIK_TIMEOUT", 8),
        )
    raise ProviderMisconfigured(f"IDENTITY_PROVIDER tidak dikenal: {name}")


def get_identity_provider():
    cached = current_app.extensions.get(_PROVIDER_KEY)
    if cached is None:
        cached = build_identity_provider(current_app.config)
        current_app.extensions[_PROVIDER_KEY] = cached
    return cached
