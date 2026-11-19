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
from .credentials import (
    listar_cofre_windows,
    obter_senha_cofre,
    salvar_senha_cofre,
    remover_senha_cofre,
)

# Cache indexado por (BANCO_UPPER, USUARIO_UPPER)
_CONFIG_VALIDADAS_CACHE: dict[tuple[str, str], dict] = {}
# Circuit Breaker indexado por (BANCO_UPPER, USUARIO_UPPER)
_CREDENCIAIS_BLOQUEADAS_SESSAO: set[tuple[str, str]] = set()


def localizar_config() -> str | None:
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

    return None


def carregar_config(caminho_arquivo=None):
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


def _extrair_usuarios_config(cfg: dict) -> tuple[str | None, list[str]]:
    """Extrai o usuário padrão ('user') e a lista completa ('users') sem duplicatas."""
    user_padrao = str(cfg["user"]).strip() if cfg.get("user") else None
    lista_users: list[str] = []

    if user_padrao:
        lista_users.append(user_padrao)

    for u in cfg.get("users", []):
        u_str = str(u).strip()
        if u_str and u_str not in lista_users:
            lista_users.append(u_str)

    return user_padrao, lista_users


def _resolver_usuario_conexao(nome_banco: str, cfg: dict, usuario_informado: str | None) -> str:
    """Resolve qual usuário utilizar na conexão com suporte a 'user', 'users' e cofre."""
    if usuario_informado and usuario_informado.strip():
        return usuario_informado.strip()

    banco_upper = nome_banco.strip().upper()
    user_padrao, lista_users = _extrair_usuarios_config(cfg)

    # 1. Se existe 'user' padrão no config.json, usa direto
    if user_padrao:
        return user_padrao

    # 2. Se existe apenas 1 usuário na lista 'users', usa direto
    if len(lista_users) == 1:
        return lista_users[0]

    # 3. Se não há usuário no JSON, verifica o cofre do sistema
    candidatos = lista_users
    if not candidatos:
        candidatos = sorted({
            r["usuario"]
            for r in listar_cofre_windows(f"db_extractor_{banco_upper}*")
            if r["banco"] == banco_upper and r["usuario"]
        })
        if len(candidatos) == 1:
            return candidatos[0]

    # 4. Múltiplos candidatos ou nenhum: exige escolha em terminal interativo
    if not (sys.stdin and sys.stdin.isatty()):
        raise SenhaNaoEncontrada(
            f"Múltiplos ou nenhum usuário configurado para '{nome_banco}' ({candidatos}). "
            "Informe o parâmetro 'usuario' explicitamente na chamada."
        )

    if candidatos:
        print(f"\n[db_extractor] Múltiplos usuários disponíveis para '{nome_banco}': {', '.join(candidatos)}")
    usuario_digitado = input(f"Digite qual usuário deseja utilizar para '{nome_banco}': ").strip()
    if not usuario_digitado:
        raise SenhaNaoEncontrada("O nome de usuário não pode ser vazio.")
    return usuario_digitado


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

    senha = ler_senha_com_mascara(f"Digite a senha para '{usuario}' ({nome_banco}): ")
    if not senha.strip():
        raise SenhaNaoEncontrada("A senha fornecida não pode ser vazia.")

    return senha


def _validar_e_proteger_credencial(
    nome_banco: str,
    cfg: dict,
    usuario_informado: str | None = None,
) -> dict:
    banco_chave = nome_banco.strip().upper()
    usuario = _resolver_usuario_conexao(nome_banco, cfg, usuario_informado)
    chave_sessao = (banco_chave, usuario.upper())

    # DISJUNTOR DE SEGURANÇA (Circuit Breaker por Banco + Usuário)
    if chave_sessao in _CREDENCIAIS_BLOQUEADAS_SESSAO:
        raise CredencialInvalidaError(
            f"[SEGURANÇA] Chamada para '{usuario}' em '{nome_banco}' bloqueada nesta sessão.\n"
            f"A autenticação já falhou anteriormente neste script. Tentativa interrompida "
            f"preventivamente para evitar bloqueio da conta no banco."
        )

    # CACHE DE SUCESSO
    if chave_sessao in _CONFIG_VALIDADAS_CACHE:
        return _CONFIG_VALIDADAS_CACHE[chave_sessao]

    cfg_final = cfg.copy()
    cfg_final["user"] = usuario
    senha = cfg_final.get("password")
    origem_config = bool(senha)
    servico_encontrado = None

    if not senha:
        senha, servico_encontrado = obter_senha_cofre(banco_chave, usuario)
        if not senha:
            senha = _pedir_senha_terminal(nome_banco, usuario)
            salvar_senha_cofre(banco_chave, usuario, senha)

    cfg_final["password"] = senha

    # TESTE DE CONEXÃO
    sucesso, erro_credencial, detalhe_erro = testar_conexao(nome_banco, cfg_final)

    if sucesso:
        _CONFIG_VALIDADAS_CACHE[chave_sessao] = cfg_final
        return cfg_final

    # TRATAMENTO DE ERRO DE CREDENCIAL
    if erro_credencial:
        if servico_encontrado:
            try:
                remover_senha_cofre(servico_encontrado, usuario)
            except Exception:
                pass

        if origem_config:
            _CREDENCIAIS_BLOQUEADAS_SESSAO.add(chave_sessao)
            raise CredencialInvalidaError(
                f"A senha fornecida no config.json para '{usuario}' ({nome_banco}) é INVÁLIDA.\n"
                f"Detalhe: {detalhe_erro}\n"
                f"Execução bloqueada nesta sessão para evitar travamento da conta."
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
            salvar_senha_cofre(banco_chave, usuario, nova_senha)
            print("[db_extractor] Senha validada com sucesso e salva no cofre do sistema!\n")
            _CONFIG_VALIDADAS_CACHE[chave_sessao] = cfg_final
            return cfg_final
        else:
            _CREDENCIAIS_BLOQUEADAS_SESSAO.add(chave_sessao)
            raise CredencialInvalidaError(
                f"Segunda tentativa de autenticação falhou para '{usuario}' em '{nome_banco}'.\n"
                f"Detalhe: {detalhe_retry}\n"
                f"O par '{usuario}' @ '{nome_banco}' foi BLOQUEADO nesta execução."
            )

    raise ConnectionError(f"Falha de conexão com o banco '{nome_banco}': {detalhe_erro}")


def obter_config_banco(nome_banco, arquivo_config=None, usuario: str | None = None):
    config = carregar_config(caminho_arquivo=arquivo_config)
    banco_procurado = nome_banco.strip().upper()

    for nome_config, cfg in config.items():
        if nome_config.upper() == banco_procurado:
            return _validar_e_proteger_credencial(nome_config, cfg, usuario_informado=usuario)

    origem = f"arquivo '{arquivo_config}'" if arquivo_config else "config.json ausente ou banco não declarado"
    raise BancoNaoEncontrado(f"Banco '{nome_banco}' não localizado nas configurações ({origem}).")


def inferir_tipo_banco_por_porta(porta: int | str) -> str:
    porta_int = int(porta)
    if porta_int == 1521:
        return "ORACLE"
    elif porta_int == 9996:
        return "DENODO"
    else:
        raise ValueError(
            f"Não foi possível inferir a engine pela porta '{porta}'. "
            "Portas conhecidas: 1521 (Oracle) ou 9996 (Denodo)."
        )


def montar_e_validar_config_direta(
    host: str,
    porta: int | str,
    usuario: str,
    database_ou_service: str,
    banco_alias: str | None = None,
) -> tuple[str, dict]:
    tipo = inferir_tipo_banco_por_porta(porta)
    host_limpo = host.split(".")[0].replace("-", "_").upper()
    alias = (banco_alias or f"{tipo}_{host_limpo}_{database_ou_service.upper()}").strip().upper()

    cfg = {
        "user": usuario,
        "host": host,
        "port": int(porta),
    }

    if tipo == "ORACLE":
        cfg["service"] = database_ou_service
    else:
        cfg["database"] = database_ou_service

    cfg_validada = _validar_e_proteger_credencial(alias, cfg, usuario_informado=usuario)
    return alias, cfg_validada
