import sys
import ctypes
from ctypes import wintypes
import keyring
from ._config import carregar_config
from ._exceptions import SenhaNaoEncontrada
from .utils import ler_senha_com_mascara


def _listar_credenciais_windows_por_filtro(filtro: str = "db_extractor*") -> list:
    """Busca diretamente no Windows Credential Manager todas as credenciais com o prefixo."""
    if sys.platform != "win32":
        return []

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.c_void_p),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    PCREDENTIAL = ctypes.POINTER(CREDENTIAL)
    advapi32 = ctypes.WinDLL("advapi32.dll")

    cred_enumerate = advapi32.CredEnumerateW
    cred_enumerate.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(ctypes.POINTER(PCREDENTIAL)),
    ]
    cred_enumerate.restype = wintypes.BOOL

    cred_free = advapi32.CredFree
    cred_free.argtypes = [ctypes.c_void_p]

    count = wintypes.DWORD(0)
    creds_ptr = ctypes.POINTER(PCREDENTIAL)()

    registros = []
    if cred_enumerate(filtro, 0, ctypes.byref(count), ctypes.byref(creds_ptr)):
        try:
            for i in range(count.value):
                c = creds_ptr[i].contents
                target = c.TargetName or ""
                user = c.UserName or ""
                banco = target.replace("db_extractor_", "") if target.startswith("db_extractor_") else target
                registros.append({
                    "banco": banco,
                    "usuario": user,
                    "servico": target,
                })
        finally:
            cred_free(creds_ptr)

    return registros


def _descobrir_usuario(banco: str, usuario_informado: str | None = None) -> list[str]:
    """
    Retorna a lista de usuários associados ao banco sem exigir config.json.
    Verifica:
    1. Parâmetro informado.
    2. config.json (se existir e contiver o banco).
    3. Cofre do Windows (entradas existentes para db_extractor_<BANCO>).
    """
    if usuario_informado:
        return [usuario_informado.strip()]

    banco_upper = banco.strip().upper()
    servico_alvo = f"db_extractor_{banco_upper}"

    # 1. Tenta obter do config.json sem quebrar se não existir
    try:
        config = carregar_config()
        for nome, cfg in config.items():
            if nome.strip().upper() == banco_upper:
                user_cfg = cfg.get("user")
                if user_cfg:
                    return [user_cfg.strip()]
    except Exception:
        pass

    # 2. Tenta descobrir diretamente pelo cofre do sistema
    salvos = _listar_credenciais_windows_por_filtro(f"{servico_alvo}*")
    usuarios_cofre = [
        reg["usuario"]
        for reg in salvos
        if reg["servico"].upper() == servico_alvo.upper() and reg["usuario"]
    ]
    if usuarios_cofre:
        return list(set(usuarios_cofre))

    return []


def cadastrar_credencial(banco: str, usuario: str | None = None, senha: str | None = None) -> None:
    banco_upper = banco.strip().upper()

    usuarios = _descobrir_usuario(banco_upper, usuario)
    if usuarios:
        usuario = usuarios[0]
    elif sys.stdin and sys.stdin.isatty():
        usuario = input(f"Digite o nome de usuário para '{banco_upper}': ").strip()
    else:
        raise SenhaNaoEncontrada(f"Não foi possível determinar o usuário para '{banco_upper}'.")

    if not usuario:
        raise SenhaNaoEncontrada("O nome de usuário não pode ser vazio.")

    servico = f"db_extractor_{banco_upper}"
    senha_existente = keyring.get_password(servico, usuario)

    if senha_existente is not None:
        print(f"\n[db_extractor] O usuário '{usuario}' já possui credencial cadastrada para '{banco_upper}'.")
        if senha is None:
            resposta = input("Deseja sobrescrever a senha existente? (s/N): ").strip().lower()
            if resposta not in ("s", "sim", "y", "yes"):
                print("[db_extractor] Operação cancelada. A credencial existente foi mantida.")
                return

    if not senha:
        senha = ler_senha_com_mascara(f"Digite a senha para '{usuario}' ({banco_upper}): ")

    if not senha.strip():
        raise SenhaNaoEncontrada("A senha não pode ser vazia.")

    keyring.set_password(servico, usuario, senha)
    print(f"[db_extractor] Credencial cadastrada com sucesso para '{usuario}' em '{banco_upper}'.")


def alterar_senha(banco: str, usuario: str | None = None, nova_senha: str | None = None) -> None:
    banco_upper = banco.strip().upper()

    usuarios = _descobrir_usuario(banco_upper, usuario)
    if len(usuarios) == 1:
        usuario = usuarios[0]
    elif len(usuarios) > 1 and not usuario:
        print(f"[db_extractor] Múltiplos usuários encontrados no cofre para '{banco_upper}': {', '.join(usuarios)}")
        if sys.stdin and sys.stdin.isatty():
            usuario = input(f"Digite qual usuário deseja alterar: ").strip()
        else:
            raise SenhaNaoEncontrada(f"Especifique o parâmetro 'usuario'. Usuários encontrados: {usuarios}")
    elif not usuarios:
        if sys.stdin and sys.stdin.isatty():
            usuario = input(f"Digite o nome de usuário para '{banco_upper}': ").strip()
        else:
            raise SenhaNaoEncontrada(f"Não foi possível determinar o usuário para '{banco_upper}'.")

    if not usuario:
        raise SenhaNaoEncontrada("O nome de usuário não pode ser vazio.")

    servico = f"db_extractor_{banco_upper}"
    senha_atual = keyring.get_password(servico, usuario)

    if not senha_atual:
        print(f"[db_extractor] Nenhuma senha anterior encontrada para '{usuario}' em '{banco_upper}'.")
        print("[db_extractor] Criando novo registro de senha...")
    else:
        print(f"[db_extractor] Alterando senha de '{usuario}' em '{banco_upper}'.")

    if not nova_senha:
        nova_senha = ler_senha_com_mascara(f"Digite a NOVA senha para '{usuario}' ({banco_upper}): ")
        confirmacao = ler_senha_com_mascara("Confirme a nova senha: ")
        if nova_senha != confirmacao:
            raise SenhaNaoEncontrada("As senhas digitadas não coincidem. Nenhuma alteração foi feita.")

    if not nova_senha.strip():
        raise SenhaNaoEncontrada("A nova senha não pode ser vazia.")

    keyring.set_password(servico, usuario, nova_senha)
    print(f"[db_extractor] Senha de '{usuario}' em '{banco_upper}' alterada com sucesso!")


def remover_credencial(banco: str, usuario: str | None = None) -> None:
    banco_upper = banco.strip().upper()
    servico = f"db_extractor_{banco_upper}"

    # Descobre os usuários sem disparar erro se o config não existir
    usuarios = _descobrir_usuario(banco_upper, usuario)

    if not usuarios:
        # Tenta remover diretamente caso o backend suporte apenas o serviço
        try:
            keyring.delete_password(servico, usuario or "")
            print(f"[db_extractor] Credencial de '{banco_upper}' removida do cofre.")
            return
        except Exception:
            print(f"[db_extractor] Nenhuma credencial encontrada no cofre para '{banco_upper}'.")
            return

    removidos = 0
    for u in usuarios:
        try:
            keyring.delete_password(servico, u)
            print(f"[db_extractor] Credencial de '{u}' em '{banco_upper}' removida do cofre.")
            removidos += 1
        except Exception:
            pass

    if removidos == 0:
        print(f"[db_extractor] Nenhuma credencial encontrada para remover em '{banco_upper}'.")


def listar_credenciais() -> None:
    """
    Exibe o status das credenciais cadastradas.
    - Se config.json existir: cruza as informações dos bancos com o cofre.
    - Se config.json NÃO existir: lista todas as credenciais salvas no cofre com prefixo 'db_extractor_'.
    """
    config = None
    try:
        config = carregar_config()
    except Exception:
        config = None

    print("\n" + "=" * 65)

    if config:
        print(f"{'BANCO':<15} {'USUÁRIO':<15} {'NO COFRE?':<12} {'SERVIÇO KEYRING'}")
        print("=" * 65)

        for banco, cfg in config.items():
            usuario = cfg.get("user", "(não definido)")
            service_name = f"db_extractor_{banco.upper()}"

            tem_senha = False
            if usuario and usuario != "(não definido)":
                senha = keyring.get_password(service_name, usuario)
                if not senha:
                    senha = keyring.get_password("db_extractor", usuario)
                tem_senha = bool(senha)

            status = "Sim [OK]" if tem_senha else "Não [Pendente]"
            print(f"{banco:<15} {usuario:<15} {status:<12} {service_name}")

    else:
        print("[Aviso] config.json não encontrado. Listando entradas salvas no cofre:")
        print("=" * 65)
        print(f"{'BANCO':<20} {'USUÁRIO':<20} {'SERVIÇO KEYRING'}")
        print("=" * 65)

        credenciais_salvas = _listar_credenciais_windows_por_filtro("db_extractor*")

        if not credenciais_salvas:
            print("Nenhuma credencial do 'db_extractor' encontrada no cofre do sistema.")
        else:
            for item in credenciais_salvas:
                print(f"{item['banco']:<20} {item['usuario']:<20} {item['servico']}")

    print("=" * 65 + "\n")