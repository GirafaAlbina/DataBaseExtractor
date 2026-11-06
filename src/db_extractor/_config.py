import json
import os
import sys
import keyring

from ._exceptions import (
    ConfigNaoEncontrado,
    BancoNaoEncontrado,
    SenhaNaoEncontrada,
    CredencialInvalidaError,
)
from .utils import ler_senha_com_mascara
from .connection import testar_conexao


def localizar_config():
    env_path = os.environ.get("DB_EXPORT_CONFIG")
    if env_path and os.path.exists(env_path):
        return env_path

    if sys.argv and sys.argv[0]:
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        config_path = os.path.join(script_dir, "config.json")
        if os.path.exists(config_path):
            return config_path

    cwd_config = os.path.join(os.getcwd(), "config.json")
    if os.path.exists(cwd_config):
        return cwd_config

    raise ConfigNaoEncontrado("config.json não encontrado.")


def carregar_config():
    caminho = localizar_config()
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def _pedir_senha_terminal(nome_banco: str, usuario: str, motivo: str = "") -> str:
    if not (sys.stdin and sys.stdin.isatty()):
        raise SenhaNaoEncontrada(
            f"Não foi possível obter a senha para '{usuario}' no banco '{nome_banco}'. "
            f"O processo não está rodando em um terminal interativo."
        )

    if motivo:
        print(f"\n[ATENÇÃO] {motivo}")
    else:
        print(f"\n[db_extractor] Nenhuma credencial encontrada no cofre para '{usuario}' ({nome_banco}).")

    prompt = f"Digite a senha para '{usuario}' ({nome_banco}): "
    senha = ler_senha_com_mascara(prompt)

    if not senha.strip():
        raise SenhaNaoEncontrada("A senha fornecida não pode ser vazia.")

    return senha


def _validar_e_proteger_credencial(nome_banco: str, cfg: dict) -> dict:
    cfg_final = cfg.copy()
    usuario = cfg_final.get("user")
    senha = cfg_final.get("password")
    service_name = f"db_extractor_{nome_banco.upper()}"

    if not usuario:
        raise SenhaNaoEncontrada(
            f"Campo 'user' não informado para '{nome_banco}' no config.json."
        )

    origem_config = bool(senha)

    if not senha:
        senha = keyring.get_password(service_name, usuario)
        if not senha:
            senha = keyring.get_password("db_extractor", usuario)

        if not senha:
            senha = _pedir_senha_terminal(nome_banco, usuario)
            keyring.set_password(service_name, usuario, senha)

    cfg_final["password"] = senha

    sucesso, erro_credencial, detalhe_erro = testar_conexao(nome_banco, cfg_final)

    if sucesso:
        return cfg_final

    if erro_credencial:
        try:
            keyring.delete_password(service_name, usuario)
        except Exception:
            pass

        if origem_config:
            raise CredencialInvalidaError(
                f"A senha fornecida no config.json para '{usuario}' ({nome_banco}) é INVÁLIDA.\n"
                f"Detalhe: {detalhe_erro}\n"
                f"Operação cancelada para evitar bloqueio da conta no banco."
            )

        nova_senha = _pedir_senha_terminal(
            nome_banco,
            usuario,
            motivo=f"A senha utilizada para '{usuario}' no banco '{nome_banco}' falhou na validação!\n"
                   f"Detalhe: {detalhe_erro}\n"
                   f"Para proteger sua conta contra bloqueio, digite a senha correta (ÚLTIMA TENTATIVA):"
        )

        cfg_final["password"] = nova_senha
        sucesso_retry, _, detalhe_retry = testar_conexao(nome_banco, cfg_final)

        if sucesso_retry:
            keyring.set_password(service_name, usuario, nova_senha)
            print(f"[db_extractor] Senha validada com sucesso e salva no cofre do sistema!\n")
            return cfg_final
        else:
            raise CredencialInvalidaError(
                f"Segunda tentativa de autenticação falhou para '{usuario}' em '{nome_banco}'.\n"
                f"Detalhe: {detalhe_retry}\n"
                f"EXECUÇÃO INTERROMPIDA para evitar o bloqueio do seu usuário no banco de dados."
            )

    raise ConnectionError(
        f"Falha de conexão com o banco '{nome_banco}': {detalhe_erro}"
    )


def obter_config_banco(nome_banco):
    config = carregar_config()
    banco_procurado = nome_banco.strip().upper()

    for nome_config, cfg in config.items():
        if nome_config.upper() == banco_procurado:
            return _validar_e_proteger_credencial(nome_config, cfg)

    raise BancoNaoEncontrado(f"Banco '{nome_banco}' não encontrado.")