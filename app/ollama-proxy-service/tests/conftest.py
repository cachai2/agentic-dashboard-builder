import os

os.environ["OLLAMA_MODE"] = "mock"

from ollama_proxy_service.app import config as config_module

config_module.get_settings.cache_clear()
