import json
import os
import sys
# db_extractor
from ._exceptions import ConfigNaoEncontrado, BancoNaoEncontrado


def localizar_config():
    env_path = os.environ.get("DB_EXPORT_CONFIG")
    if env_path and os.path.exists(env_path):
        return env_path

    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    config_path = os.path.join(script_dir,"config.json")
    if os.path.exists(config_path):
        return config_path

    raise ConfigNaoEncontrado("config.json não encontrado.")


def carregar_config():
    caminho = localizar_config()
    with open(caminho,"r",encoding="utf-8") as f:
        return json.load(f)


def obter_config_banco(nome_banco):
    config = carregar_config()
    banco_procurado = nome_banco.strip().upper()
    for nome_config, cfg in config.items():
        if nome_config.upper() == banco_procurado:
            return cfg

    raise BancoNaoEncontrado(f"Banco '{nome_banco}' não encontrado.")