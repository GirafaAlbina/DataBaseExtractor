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

# Guarda as configurações já validadas com sucesso (evita retestar em loops)
_CONFIG_VALIDADAS_CACHE = {}
# Circuit Breaker: Guarda bancos que falharam na autenticação nesta sessão do Python
_BANCOS_BLOQUEADOS_SESSAO = set()


def carregar_config(caminho_arquivo=None):
    """
    Carrega o arquivo JSON de configuração.
    - Se caminho_arquivo for informado, carrega diretamente dele.
    - Se for None, tenta localizar automaticamente (env var, script_dir, cwd).
    """
    if caminho_arquivo:
        if not os.path.exists(caminho_arquivo):
            print(f"[db_extractor] Aviso: Arquivo indicado '{caminho_arquivo}' não encontrado. Seguindo execução...")
            return {}
        caminho = caminho_arquivo
    else:
        caminho = localizar_config()

    if not caminho:
        print("[db_extractor] Aviso: Arquivo config.json não encontrado. Seguindo execução...")
        return {}

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[db_extractor] Aviso: Falha ao ler arquivo de configuração '{caminho}' ({e}). Seguindo execução...")
        return {}


def obter_config_banco(nome_banco, arquivo_config=None):
    """
    Recupera a configuração do banco.
    Aceita arquivo_config opcional.
    """
    config = carregar_config(caminho_arquivo=arquivo_config)
    banco_procurado = nome_banco.strip().upper()

    for nome_config, cfg in config.items():
        if nome_config.upper() == banco_procurado:
            return _validar_e_proteger_credencial(nome_config, cfg)

    origem = f"arquivo '{arquivo_config}'" if arquivo_config else "config.json ausente ou banco não declarado"
    raise BancoNaoEncontrado(f"Banco '{nome_banco}' não localizado nas configurações ({origem}).")


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
    banco_chave = nome_banco.upper()

    # 1. DISJUNTOR DE SEGURANÇA (Circuit Breaker)
    # Se este banco já falhou a senha nesta execução, rejeita na hora sem bater no banco!
    if banco_chave in _BANCOS_BLOQUEADOS_SESSAO:
        raise CredencialInvalidaError(
            f"[SEGURANÇA] Chamada para o banco '{nome_banco}' bloqueada nesta sessão.\n"
            f"A autenticação já falhou anteriormente neste script. A tentativa foi interrompida "
            f"preventivamente para não bloquear o seu usuário no banco de dados."
        )

    # 2. CACHE DE SUCESSO
    # Se já validou neste mesmo script, retorna a configuração direto sem refazer SELECT 1
    if banco_chave in _CONFIG_VALIDADAS_CACHE:
        return _CONFIG_VALIDADAS_CACHE[banco_chave]

    cfg_final = cfg.copy()
    usuario = cfg_final.get("user")
    senha = cfg_final.get("password")
    service_name = f"db_extractor_{banco_chave}"

    if not usuario:
        raise SenhaNaoEncontrada(f"Campo 'user' não informado para '{nome_banco}' no config.json.")

    origem_config = bool(senha)

    if not senha:
        senha = keyring.get_password(service_name, usuario)
        if not senha:
            senha = keyring.get_password("db_extractor", usuario)

        if not senha:
            senha = _pedir_senha_terminal(nome_banco, usuario)
            keyring.set_password(service_name, usuario, senha)

    cfg_final["password"] = senha

    # 3. TESTE DE CONEXÃO
    sucesso, erro_credencial, detalhe_erro = testar_conexao(nome_banco, cfg_final)

    if sucesso:
        # Registra no cache de sucesso da sessão
        _CONFIG_VALIDADAS_CACHE[banco_chave] = cfg_final
        return cfg_final

    # 4. TRATAMENTO DE ERRO DE CREDENCIAL
    if erro_credencial:
        # Remove a senha errada do cofre imediatamente
        try:
            keyring.delete_password(service_name, usuario)
        except Exception:
            pass

        if origem_config:
            # Marca o banco como bloqueado nesta sessão
            _BANCOS_BLOQUEADOS_SESSAO.add(banco_chave)
            raise CredencialInvalidaError(
                f"A senha fornecida no config.json para '{usuario}' ({nome_banco}) é INVÁLIDA.\n"
                f"Detalhe: {detalhe_erro}\n"
                f"Execução bloqueada nesta sessão para evitar travamento da conta no banco."
            )

        # Concede apenas uma chance interativa de correção no terminal
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
            _CONFIG_VALIDADAS_CACHE[banco_chave] = cfg_final
            return cfg_final
        else:
            # Falhou pela segunda vez: arma o disjuntor para todas as próximas chamadas deste script
            _BANCOS_BLOQUEADOS_SESSAO.add(banco_chave)
            raise CredencialInvalidaError(
                f"Segunda tentativa de autenticação falhou para '{usuario}' em '{nome_banco}'.\n"
                f"Detalhe: {detalhe_retry}\n"
                f"O banco '{nome_banco}' foi BLOQUEADO para todas as próximas consultas desta execução "
                f"para proteger seu usuário contra bloqueio."
            )

    raise ConnectionError(f"Falha de conexão com o banco '{nome_banco}': {detalhe_erro}")


def obter_config_banco(nome_banco):
    config = carregar_config()
    banco_procurado = nome_banco.strip().upper()

    for nome_config, cfg in config.items():
        if nome_config.upper() == banco_procurado:
            return _validar_e_proteger_credencial(nome_config, cfg)

    raise BancoNaoEncontrado(f"Banco '{nome_banco}' não encontrado.")