from ._config import carregar_config
from ._exceptions import SenhaNaoEncontrada
from .utils import ler_senha_com_mascara
from .credentials import (
    confirmar_acao,
    resolver_usuario,
    listar_cofre_windows,
    obter_senha_cofre,
    remover_senha_cofre,
    salvar_senha_cofre,
    servico_composto,
    servico_legado,
)


def cadastrar_credencial(banco: str, usuario: str | None = None, senha: str | None = None) -> None:
    banco_upper = banco.strip().upper()
    usuario = resolver_usuario(banco_upper, usuario, operacao="cadastro")
    senha_existente, servico_anterior = obter_senha_cofre(banco_upper, usuario)

    if senha_existente is not None:
        print(f"\n[db_extractor] O usuário '{usuario}' já possui credencial cadastrada para '{banco_upper}'.")
        confirmado = confirmar_acao(
            "Deseja sobrescrever a credencial existente? (s/N): ",
            f"A credencial para '{usuario}' em '{banco_upper}' já existe. Remova-a antes ou execute em modo interativo.",
        )
        if not confirmado:
            print("[db_extractor] Operação cancelada. A credencial existente foi mantida.")
            return

    if not senha:
        senha = ler_senha_com_mascara(f"Digite a senha para '{usuario}' ({banco_upper}): ")

    if not senha.strip():
        raise SenhaNaoEncontrada("A senha não pode ser vazia.")

    servico_novo = salvar_senha_cofre(banco_upper, usuario, senha, servico_anterior)
    print(f"[db_extractor] Credencial cadastrada com sucesso para '{usuario}' em '{banco_upper}' ({servico_novo}).")


def alterar_senha(banco: str, usuario: str | None = None, nova_senha: str | None = None) -> None:
    banco_upper = banco.strip().upper()
    usuario = resolver_usuario(banco_upper, usuario, operacao="alteração de senha")
    senha_atual, servico_anterior = obter_senha_cofre(banco_upper, usuario)

    if senha_atual is None:
        print(f"[db_extractor] Nenhuma senha anterior encontrada para '{usuario}' em '{banco_upper}'. Criando novo registro...")
    else:
        print(f"[db_extractor] Alterando senha de '{usuario}' em '{banco_upper}'.")

    if not nova_senha:
        nova_senha = ler_senha_com_mascara(f"Digite a NOVA senha para '{usuario}' ({banco_upper}): ")
        confirmacao = ler_senha_com_mascara("Confirme a nova senha: ")
        if nova_senha != confirmacao:
            raise SenhaNaoEncontrada("As senhas digitadas não coincidem. Nenhuma alteração foi feita.")

    if not nova_senha.strip():
        raise SenhaNaoEncontrada("A nova senha não pode ser vazia.")

    salvar_senha_cofre(banco_upper, usuario, nova_senha, servico_anterior)
    print(f"[db_extractor] Senha de '{usuario}' em '{banco_upper}' alterada com sucesso!")


def remover_credencial(banco: str, usuario: str | None = None, confirmar: bool = True) -> None:
    banco_upper = banco.strip().upper()
    usuario = resolver_usuario(banco_upper, usuario, operacao="remoção")
    senha_existente, servico_encontrado = obter_senha_cofre(banco_upper, usuario)

    if senha_existente is None:
        print(f"[db_extractor] Nenhuma credencial encontrada no cofre para '{usuario}' em '{banco_upper}'.")
        return

    if confirmar:
        confirmado = confirmar_acao(
            f"[db_extractor] Tem certeza que deseja remover a credencial de '{usuario}' em '{banco_upper}'? (s/N): ",
            f"Confirmação necessária para remover '{usuario}' em '{banco_upper}'. Passe confirmar=False em automações.",
        )
        if not confirmado:
            print(f"[db_extractor] Remoção cancelada. A credencial de '{usuario}' foi mantida.")
            return

    try:
        remover_senha_cofre(servico_encontrado, usuario)
        print(f"[db_extractor] Credencial de '{usuario}' em '{banco_upper}' removida do cofre.")
    except Exception as erro:
        print(f"[db_extractor] Não foi possível remover a credencial de '{usuario}' em '{banco_upper}': {erro}")


def listar_credenciais() -> None:
    config = None
    try:
        config = carregar_config()
    except Exception:
        config = None

    credenciais_cofre = listar_cofre_windows("db_extractor*")
    pares_listados: set[tuple[str, str]] = set()
    mapa_cofre: dict[tuple[str, str], dict] = {}

    for item in credenciais_cofre:
        chave = (item["banco"].upper(), item["usuario"].upper())
        if chave not in mapa_cofre or item["servico"].endswith(f"_{item['usuario'].upper()}"):
            mapa_cofre[chave] = item

    print("\n" + "=" * 98)
    print(f"{'BANCO':<15} {'USUÁRIO':<18} {'ORIGEM / STATUS':<20} {'ATUALIZADO EM':<18} {'SERVIÇO KEYRING'}")
    print("=" * 98)

    if config:
        for banco, cfg in config.items():
            banco_upper = banco.strip().upper()
            usuario = (cfg.get("user") or "").strip()

            if usuario:
                chave = (banco_upper, usuario.upper())
                pares_listados.add(chave)
                reg = mapa_cofre.get(chave)

                if reg:
                    status, atualizado_em, service_name = "Config [OK]", reg["atualizado_em"], reg["servico"]
                else:
                    status, atualizado_em, service_name = "Config [Pendente]", "-", servico_composto(banco_upper, usuario)

                print(f"{banco:<15} {usuario:<18} {status:<20} {atualizado_em:<18} {service_name}")
            else:
                print(f"{banco:<15} {'(não definido)':<18} {'Config [Sem User]':<20} {'-':<18} {servico_legado(banco_upper)}")

    extras_encontrados = False
    for item in sorted(credenciais_cofre, key=lambda x: (x["banco"], x["usuario"])):
        chave = (item["banco"].upper(), item["usuario"].upper())
        if chave not in pares_listados:
            pares_listados.add(chave)
            extras_encontrados = True
            usuario = item["usuario"] or "(sem usuário)"
            print(
                f"{item['banco']:<15} {usuario:<18} {'Cofre [Extra]':<20} "
                f"{item['atualizado_em']:<18} {item['servico']}"
            )

    if not config and not extras_encontrados:
        print("Nenhuma credencial do 'db_extractor' encontrada no cofre do sistema.")

    print("=" * 98 + "\n")
    