"""Persistência local de perfis e configurações em JSON."""
import hashlib
import json
import os
import re
import secrets
import sqlite3
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from contextlib import closing

from dotenv import load_dotenv
from modulos.escopo import CHAVES_ESCOPO, validar_escopo

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
_diretorio_dados_configurado = os.getenv("BOT_DATA_DIR", "").strip()
if _diretorio_dados_configurado:
    DIRETORIO_DADOS = Path(_diretorio_dados_configurado).expanduser()
    if not DIRETORIO_DADOS.is_absolute():
        DIRETORIO_DADOS = (BASE_DIR / DIRETORIO_DADOS).resolve()
else:
    DIRETORIO_DADOS = BASE_DIR.parent / f"{BASE_DIR.name}-dados"
ARQUIVO_DADOS = DIRETORIO_DADOS / "dados_bot.json"
ARQUIVO_LEGADO = BASE_DIR / "permissoes.db"

_LOCK = threading.RLock()
_ITERACOES_SENHA_ADMIN = 310_000

OPCOES_CONSULTA = {'perguntar_filial', 'perguntar_regiao'}

PERMISSOES = (
    "consulta_preco",
    "ver_preco_programado",
    "buscar_por_foto",
    "buscar_codprod",
    "buscar_codauxiliar",
    "buscar_codauxiliar2",
    "ver_margem_produto",
    "ver_margem_departamento",
    "ver_custos",
)

CHAVES_CONFIGURACAO = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_ADMIN_ID",
    "ORACLE_HOST",
    "ORACLE_PORT",
    "ORACLE_SERVICE",
    "ORACLE_USER",
    "ORACLE_PASSWORD",
    "ORACLE_CLIENT_DIR",
    "WEB_ADMIN_USER",
    "WEB_ADMIN_HOST",
    "WEB_ADMIN_PORT",
    "WEB_ADMIN_URL",
    "WEB_HTTPS_ONLY",
    "WEB_SESSION_SECRET",
)

CHAVES_SECRETAS = frozenset({
    "TELEGRAM_BOT_TOKEN",
    "ORACLE_PASSWORD",
    "WEB_SESSION_SECRET",
})

VALORES_CONFIGURACAO_PADRAO = {
    "TELEGRAM_BOT_TOKEN": "",
    "TELEGRAM_ADMIN_ID": "",
    "ORACLE_HOST": "",
    "ORACLE_PORT": "1521",
    "ORACLE_SERVICE": "",
    "ORACLE_USER": "",
    "ORACLE_PASSWORD": "",
    "ORACLE_CLIENT_DIR": "",
    "WEB_ADMIN_USER": "admin",
    "WEB_ADMIN_HOST": "0.0.0.0",
    "WEB_ADMIN_PORT": "8765",
    "WEB_ADMIN_URL": "",
    "WEB_HTTPS_ONLY": "false",
    "WEB_SESSION_SECRET": "",
}

_VALORES_PERMISSAO_INICIAIS = {
    "aprovado": False,
    "consulta_preco": False,
    "ver_preco_programado": False,
    "buscar_por_foto": False,
    "buscar_codprod": False,
    "buscar_codauxiliar": False,
    "buscar_codauxiliar2": False,
    "ver_margem_produto": False,
    "ver_margem_departamento": False,
    "ver_custos": False,
}


def _novo_arquivo():
    return {
        "versao": 1,
        "usuarios": {},
        "configuracoes": {},
        "admin": {"senha_hash": None, "versao_sessao": 1},
    }


def _migrar_sqlite_legado():
    dados = _novo_arquivo()
    if not ARQUIVO_LEGADO.is_file():
        return dados

    try:
        with closing(sqlite3.connect(ARQUIVO_LEGADO)) as conexao:
            conexao.row_factory = sqlite3.Row
            tabelas = {
                linha["name"]
                for linha in conexao.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            if "usuarios" in tabelas:
                for linha in conexao.execute("SELECT * FROM usuarios"):
                    usuario = dict(linha)
                    telegram_id = int(usuario["telegram_id"])
                    perfil = dict(_VALORES_PERMISSAO_INICIAIS)
                    perfil.update(usuario)
                    if "ver_margem" in usuario:
                        perfil["ver_margem_produto"] = bool(usuario["ver_margem"])
                        perfil["ver_margem_departamento"] = bool(usuario["ver_margem"])
                        perfil.pop("ver_margem", None)
                    if "aprovado" not in usuario:
                        perfil.update({
                            "aprovado": True,
                            "consulta_preco": True,
                            "buscar_por_foto": True,
                            "buscar_codprod": True,
                            "buscar_codauxiliar": True,
                            "buscar_codauxiliar2": True,
                            "ver_margem_produto": True, "ver_margem_departamento": True,
                            "ver_custos": True,
                        })
                    perfil["telegram_id"] = telegram_id
                    dados["usuarios"][str(telegram_id)] = perfil

            if "usuarios_impressao" in tabelas:
                for linha in conexao.execute("SELECT * FROM usuarios_impressao"):
                    impressao = dict(linha)
                    telegram_id = int(impressao["telegram_id"])
                    chave = str(telegram_id)
                    perfil = dados["usuarios"].setdefault(chave, {
                        **_VALORES_PERMISSAO_INICIAIS,
                        "aprovado": True,
                        "consulta_preco": True,
                        "buscar_por_foto": True,
                        "buscar_codprod": True,
                        "buscar_codauxiliar": True,
                        "buscar_codauxiliar2": True,
                        "telegram_id": telegram_id,
                        "autorizado_em": impressao.get(
                            "autorizado_em", datetime.now().isoformat(timespec="seconds")
                        ),
                        "apelido": impressao.get("apelido"),
                        "nome": None,
                        "username": None,
                        "ultimo_acesso": None,
                    })

            if "configuracoes" in tabelas:
                for linha in conexao.execute("SELECT chave, valor FROM configuracoes"):
                    if linha["chave"] in CHAVES_CONFIGURACAO:
                        dados["configuracoes"][linha["chave"]] = str(linha["valor"])

            if "configuracao_admin" in tabelas:
                configuracoes_admin = {
                    linha["chave"]: linha["valor"]
                    for linha in conexao.execute(
                        "SELECT chave, valor FROM configuracao_admin"
                    )
                }
                dados["admin"]["senha_hash"] = configuracoes_admin.get("senha_hash")
                dados["admin"]["versao_sessao"] = int(
                    configuracoes_admin.get("versao_sessao", 1)
                )
    except (OSError, sqlite3.Error, TypeError, ValueError, KeyError) as erro:
        raise RuntimeError(
            f"Não foi possível migrar os dados de {ARQUIVO_LEGADO.name}."
        ) from erro
    return dados


def _validar_arquivo(dados):
    if (
        not isinstance(dados, dict)
        or dados.get("versao") != 1
        or not isinstance(dados.get("usuarios"), dict)
        or not isinstance(dados.get("configuracoes"), dict)
        or not isinstance(dados.get("admin"), dict)
    ):
        raise RuntimeError(
            f"O arquivo {ARQUIVO_DADOS.name} está inválido. "
            "Corrija ou restaure um backup antes de iniciar."
        )


def _gravar_json(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=caminho.parent,
            prefix=f".{caminho.name}.",
            suffix=".tmp",
            delete=False,
        ) as arquivo:
            temporario = Path(arquivo.name)
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    except OSError:
        if temporario is not None:
            try:
                temporario.unlink()
            except FileNotFoundError:
                pass
        raise


def _arquivos_configuracao():
    return {
        "config_bot.json": tuple(chave for chave in CHAVES_CONFIGURACAO if not chave.startswith("ORACLE_")),
        "config_oracle.json": tuple(chave for chave in CHAVES_CONFIGURACAO if chave.startswith("ORACLE_")),
    }


def _ler_configuracao_json(caminho):
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if not isinstance(dados, dict) or any(not isinstance(valor, str) for valor in dados.values()):
            raise ValueError("Formato de configuração inválido.")
        return dados
    except (OSError, ValueError) as erro:
        raise RuntimeError(f"Não foi possível ler {caminho.name}. Corrija o JSON ou restaure um backup.") from erro


def _migrar_permissoes_margem(dados):
    alterado = False
    for perfil in [*dados["usuarios"].values(), *dados.get("perfis_teste", {}).values()]:
        if "ver_margem" in perfil:
            valor = bool(perfil.pop("ver_margem"))
            perfil.setdefault("ver_margem_produto", valor)
            perfil.setdefault("ver_margem_departamento", valor)
            alterado = True
    return alterado


def _gravar_arquivo(dados):
    _validar_arquivo(dados)
    _migrar_permissoes_margem(dados)
    for nome, chaves in _arquivos_configuracao().items():
        caminho = ARQUIVO_DADOS.with_name(nome)
        configuracoes = {chave: valor for chave, valor in dados["configuracoes"].items() if chave in chaves}
        if not caminho.exists() or _ler_configuracao_json(caminho) != configuracoes:
            _gravar_json(caminho, configuracoes)
    # O arquivo principal conserva apenas cadastros, perfis e autenticação.
    _gravar_json(ARQUIVO_DADOS, {**dados, "configuracoes": {}})


def _carregar_arquivo():
    if not ARQUIVO_DADOS.is_file():
        _gravar_arquivo(_migrar_sqlite_legado())
    try:
        with ARQUIVO_DADOS.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, json.JSONDecodeError) as erro:
        raise RuntimeError(
            f"Não foi possível ler {ARQUIVO_DADOS.name}. "
            "Corrija o JSON ou restaure um backup."
        ) from erro
    _validar_arquivo(dados)
    migrar = _migrar_permissoes_margem(dados) or bool(dados["configuracoes"])
    for nome, chaves in _arquivos_configuracao().items():
        caminho = ARQUIVO_DADOS.with_name(nome)
        if caminho.exists():
            configuracoes = _ler_configuracao_json(caminho)
            if not set(configuracoes).issubset(chaves):
                raise RuntimeError(f"Campos desconhecidos em {nome}.")
            dados["configuracoes"].update(configuracoes)
        else:
            migrar = True
    if migrar:
        _gravar_arquivo(dados)
    return dados


def _normalizar_apelido(apelido):
    if apelido is None:
        return None
    apelido = apelido.strip().lower()
    if not re.fullmatch(r"[a-z0-9_]{2,32}", apelido):
        raise ValueError(
            "O apelido deve ter de 2 a 32 caracteres: letras sem acento, números ou _."
        )
    return apelido


def inicializar():
    """Cria o arquivo JSON ou migra perfis e configurações do SQLite antigo."""
    with _LOCK:
        if ARQUIVO_DADOS.is_file():
            _carregar_arquivo()
        else:
            _gravar_arquivo(_migrar_sqlite_legado())

        garantir_administrador()


def garantir_administrador():
    """Pré-cadastra o administrador real com acesso total."""
    admin_id = obter_configuracao()['TELEGRAM_ADMIN_ID'].strip()
    if admin_id.isascii() and admin_id.isdecimal() and int(admin_id) > 0:
        existente = obter_perfil(int(admin_id))
        if existente and existente.get('aprovado') and all(existente.get(chave) for chave in PERMISSOES):
            return existente
        return registrar_usuario(int(admin_id))
    return None


def obter_ou_criar_configuracao(chave, valor_padrao):
    if chave not in CHAVES_CONFIGURACAO:
        raise ValueError(f"Configuração desconhecida: {chave}")
    with _LOCK:
        dados = _carregar_arquivo()
        configuracoes = dados["configuracoes"]
        if chave not in configuracoes:
            configuracoes[chave] = str(valor_padrao)
            _gravar_arquivo(dados)
        return configuracoes[chave]


def obter_configuracao():
    with _LOCK:
        dados = _carregar_arquivo()
        configuracoes = dados["configuracoes"]
        alterado = False
        for chave in CHAVES_CONFIGURACAO:
            if chave not in configuracoes:
                valor_ambiente = (
                    ""
                    if chave == "TELEGRAM_BOT_TOKEN"
                    else os.getenv(chave, VALORES_CONFIGURACAO_PADRAO[chave])
                )
                configuracoes[chave] = valor_ambiente
                alterado = True
        if alterado:
            _gravar_arquivo(dados)
        return dict(configuracoes)


def salvar_configuracoes(configuracoes):
    if not configuracoes or not set(configuracoes).issubset(CHAVES_CONFIGURACAO):
        raise ValueError("Configuração contém campos inválidos.")
    if any(not isinstance(valor, str) for valor in configuracoes.values()):
        raise ValueError("Os valores da configuração devem ser textos.")
    with _LOCK:
        dados = _carregar_arquivo()
        atual = dados["configuracoes"]
        usuario_anterior = atual.get(
            "WEB_ADMIN_USER", os.getenv("WEB_ADMIN_USER", "admin")
        )
        for chave, valor in configuracoes.items():
            if chave == "WEB_SESSION_SECRET" and not valor:
                continue
            atual[chave] = valor
        if (
            "WEB_ADMIN_USER" in configuracoes
            and configuracoes["WEB_ADMIN_USER"] != usuario_anterior
        ):
            admin = dados["admin"]
            admin["versao_sessao"] = int(admin.get("versao_sessao", 1)) + 1
        _gravar_arquivo(dados)
        if 'TELEGRAM_ADMIN_ID' in configuracoes:
            garantir_administrador()


def _gerar_hash_senha(senha):
    sal = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", senha.encode("utf-8"), sal, _ITERACOES_SENHA_ADMIN
    )
    return f"{_ITERACOES_SENHA_ADMIN}${sal.hex()}${digest.hex()}"


def _senha_confere(senha, hash_armazenado):
    if not isinstance(senha, str) or len(senha) > 128:
        return False
    try:
        iteracoes_txt, sal_txt, digest_txt = hash_armazenado.split("$")
        iteracoes = int(iteracoes_txt)
        if not 100_000 <= iteracoes <= 2_000_000:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", senha.encode("utf-8"), bytes.fromhex(sal_txt), iteracoes
        )
        return secrets.compare_digest(digest.hex(), digest_txt)
    except (AttributeError, TypeError, ValueError):
        return False


def obter_versao_sessao_admin(senha_inicial="admin"):
    with _LOCK:
        dados = _carregar_arquivo()
        admin = dados["admin"]
        if not admin.get("senha_hash"):
            admin["senha_hash"] = _gerar_hash_senha(senha_inicial)
        admin.setdefault("versao_sessao", 1)
        _gravar_arquivo(dados)
        return int(admin["versao_sessao"])


def verificar_senha_admin(senha, senha_inicial="admin"):
    obter_versao_sessao_admin(senha_inicial)
    with _LOCK:
        dados = _carregar_arquivo()
        senha_hash = dados["admin"].get("senha_hash")
    return _senha_confere(senha, senha_hash)


def alterar_senha_admin(senha_atual, senha_nova, senha_inicial="admin"):
    if not isinstance(senha_nova, str) or not 12 <= len(senha_nova) <= 128:
        raise ValueError("A nova senha deve ter entre 12 e 128 caracteres.")
    with _LOCK:
        dados = _carregar_arquivo()
        admin = dados["admin"]
        if not admin.get("senha_hash"):
            admin["senha_hash"] = _gerar_hash_senha(senha_inicial)
        if not _senha_confere(senha_atual, admin["senha_hash"]):
            raise ValueError("Senha atual incorreta.")
        admin["senha_hash"] = _gerar_hash_senha(senha_nova)
        admin["versao_sessao"] = int(admin.get("versao_sessao", 1)) + 1
        _gravar_arquivo(dados)
        return int(admin["versao_sessao"])


def eh_admin(user_id):
    admin = obter_ou_criar_configuracao(
        "TELEGRAM_ADMIN_ID",
        os.getenv(
            "TELEGRAM_ADMIN_ID",
            VALORES_CONFIGURACAO_PADRAO["TELEGRAM_ADMIN_ID"],
        ),
    ).strip()
    return bool(admin.isascii() and admin.isdecimal()) and int(admin) == int(user_id)


def registrar_usuario(user_id, nome=None, username=None):
    """Registra usuários ainda pendentes e atualiza seus dados do Telegram."""
    user_id = int(user_id)
    if user_id <= 0:
        raise ValueError("ID inválido.")
    agora = datetime.now().isoformat(timespec="seconds")
    with _LOCK:
        dados = _carregar_arquivo()
        chave = str(user_id)
        perfil = dados["usuarios"].get(chave)
        if perfil is None:
            perfil = {
                **_VALORES_PERMISSAO_INICIAIS,
                "telegram_id": user_id,
                "autorizado_em": agora,
                "apelido": None,
                "nome": nome,
                "username": username,
                "ultimo_acesso": agora,
            }
            dados["usuarios"][chave] = perfil
        else:
            perfil["nome"] = nome or perfil.get("nome")
            perfil["username"] = username or perfil.get("username")
            perfil["ultimo_acesso"] = agora
        if eh_admin(user_id):
            perfil.update({
                "aprovado": True,
                "ver_preco_programado": True,
                "consulta_preco": True,
                "buscar_por_foto": True,
                "buscar_codprod": True,
                "buscar_codauxiliar": True,
                "buscar_codauxiliar2": True,
                "ver_margem_produto": True, "ver_margem_departamento": True,
                "ver_custos": True,
            })
        _gravar_arquivo(dados)
        return dict(perfil)


def obter_perfil(user_id):
    with _LOCK:
        perfil = _carregar_arquivo()["usuarios"].get(str(int(user_id)))
        return dict(perfil) if perfil else None


def perfil_teste_ativo(user_id):
    if not eh_admin(user_id):
        return None
    with _LOCK:
        dados = _carregar_arquivo()
        perfil = dados.get("perfis_teste", {}).get(dados.get("perfil_teste_ativo", ""))
        return dict(perfil) if perfil and perfil["telegram_id"] == int(user_id) else None


def eh_admin_bot(user_id):
    return eh_admin(user_id) and perfil_teste_ativo(user_id) is None


def _resolver_vinculo_modelo(dados, alteracoes):
    alteracoes = validar_escopo(dict(alteracoes))
    if 'modelo_perfil_id' not in alteracoes:
        return alteracoes
    modelo_id = alteracoes['modelo_perfil_id']
    if modelo_id is None:
        return alteracoes
    if not isinstance(modelo_id, str) or modelo_id not in dados.get('modelos_perfil', {}):
        raise ValueError('Modelo de perfil não encontrado.')
    modelo = dados['modelos_perfil'][modelo_id]
    alteracoes.update(modelo['permissoes'])
    alteracoes.update({chave: modelo.get(chave) for chave in CHAVES_ESCOPO})
    return alteracoes


def gerenciar_perfil_teste(acao, perfil_id=None, nome=None, permissoes=None):
    with _LOCK:
        dados = _carregar_arquivo()
        perfis = dados.setdefault("perfis_teste", {})
        if acao == "criar":
            perfil_id = secrets.token_hex(12)
            admin_id = obter_configuracao()["TELEGRAM_ADMIN_ID"].strip()
            if not admin_id.isdecimal() or int(admin_id) <= 0:
                raise ValueError("Configure o ID do administrador primeiro.")
            perfis[perfil_id] = {**_VALORES_PERMISSAO_INICIAIS, "id": perfil_id,
                                 "nome": nome, "telegram_id": int(admin_id)}
        elif acao == "salvar":
            if perfil_id not in perfis:
                raise ValueError("Perfil não encontrado.")
            if not isinstance(permissoes, dict) or not permissoes or not set(permissoes).issubset({"aprovado", "modelo_perfil_id", *CHAVES_ESCOPO, *OPCOES_CONSULTA, *PERMISSOES}) or any(type(v) is not bool for k, v in permissoes.items() if k not in CHAVES_ESCOPO | {'modelo_perfil_id'}):
                raise ValueError("Permissões inválidas.")
            permissoes = _resolver_vinculo_modelo(dados, permissoes)
            perfis[perfil_id].update(permissoes)
            if not perfis[perfil_id].get('aprovado'):
                perfis[perfil_id].update({chave: False for chave in PERMISSOES})
        elif acao == "remover":
            if perfil_id not in perfis:
                raise ValueError("Perfil não encontrado.")
            del perfis[perfil_id]
            if dados.get("perfil_teste_ativo") == perfil_id:
                dados["perfil_teste_ativo"] = None
        elif acao == "ativar":
            if perfil_id is not None and perfil_id not in perfis:
                raise ValueError("Perfil não encontrado.")
            dados["perfil_teste_ativo"] = perfil_id
        else:
            raise ValueError("Ação inválida.")
        _gravar_arquivo(dados)
        return {"profiles": list(perfis.values()), "active": dados.get("perfil_teste_ativo")}


def gerenciar_modelo_perfil(acao='listar', modelo_id=None, nome=None, permissoes=None, escopo=None):
    with _LOCK:
        dados = _carregar_arquivo()
        if 'modelos_perfil' not in dados:
            dados['modelos_perfil'] = {
                'funcionario': {'id': 'funcionario', 'nome': 'Funcionário', 'permissoes': {
                    chave: chave in ('consulta_preco', 'buscar_por_foto', 'buscar_codprod', 'buscar_codauxiliar', 'buscar_codauxiliar2') for chave in (*PERMISSOES, *OPCOES_CONSULTA)}},
                'cliente': {'id': 'cliente', 'nome': 'Cliente', 'permissoes': {
                    chave: chave in ('consulta_preco', 'buscar_codauxiliar', 'buscar_codauxiliar2') for chave in (*PERMISSOES, *OPCOES_CONSULTA)}},
            }
            _gravar_arquivo(dados)
        modelos = dados['modelos_perfil']
        if acao in ('criar', 'salvar'):
            if not isinstance(nome, str) or not nome.strip() or len(nome) > 128:
                raise ValueError('Informe um nome de perfil com até 128 caracteres.')
            if not isinstance(permissoes, dict) or not set(permissoes).issubset(set(PERMISSOES) | OPCOES_CONSULTA) or any(type(v) is not bool for v in permissoes.values()):
                raise ValueError('Permissões do modelo inválidas.')
            if acao == 'salvar' and modelo_id not in modelos:
                raise ValueError('Modelo não encontrado.')
            if any(m['nome'].casefold() == nome.strip().casefold() and m['id'] != modelo_id for m in modelos.values()):
                raise ValueError('Já existe um modelo com esse nome.')
            modelo_id = secrets.token_hex(12) if acao == 'criar' else modelo_id
            limites = validar_escopo({**{chave: modelos.get(modelo_id, {}).get(chave) for chave in CHAVES_ESCOPO}, **(escopo or {})})
            modelos[modelo_id] = {**{chave: limites.get(chave) for chave in CHAVES_ESCOPO}, 'id': modelo_id, 'nome': nome.strip(),
                                  'permissoes': {chave: permissoes.get(chave, False) for chave in (*PERMISSOES, *OPCOES_CONSULTA)}}
            for perfil in [*dados['usuarios'].values(), *dados.get('perfis_teste', {}).values()]:
                if perfil.get('modelo_perfil_id') == modelo_id:
                    if perfil in dados['usuarios'].values() and eh_admin(perfil['telegram_id']):
                        continue
                    perfil.update(modelos[modelo_id]['permissoes'])
                    perfil.update({chave: modelos[modelo_id].get(chave) for chave in CHAVES_ESCOPO})
                    if not perfil.get('aprovado'):
                        perfil.update({chave: False for chave in PERMISSOES})
        elif acao == 'remover':
            if modelo_id not in modelos:
                raise ValueError('Modelo não encontrado.')
            del modelos[modelo_id]
            for perfil in [*dados['usuarios'].values(), *dados.get('perfis_teste', {}).values()]:
                if perfil.get('modelo_perfil_id') == modelo_id:
                    perfil['modelo_perfil_id'] = None
        elif acao != 'listar':
            raise ValueError('Ação inválida.')
        if acao != 'listar':
            _gravar_arquivo(dados)
        return sorted(modelos.values(), key=lambda m: m['nome'].casefold())


def listar_perfis_teste():
    with _LOCK:
        dados = _carregar_arquivo()
        return {"profiles": list(dados.get("perfis_teste", {}).values()), "active": dados.get("perfil_teste_ativo")}


def tem_permissao(user_id, permissao):
    if permissao not in PERMISSOES:
        raise ValueError(f"Permissão desconhecida: {permissao}")
    teste = perfil_teste_ativo(user_id)
    if teste is not None:
        return bool(teste.get("aprovado") and teste.get(permissao))
    if eh_admin(user_id):
        return True
    perfil = obter_perfil(user_id)
    return bool(perfil and perfil.get("aprovado") and perfil.get(permissao))


def pode_ver_custo(user_id):
    return tem_permissao(user_id, "ver_custos")


def pode_ver_margem_produto(user_id):
    return tem_permissao(user_id, "ver_margem_produto")


def pode_ver_margem_departamento(user_id):
    return tem_permissao(user_id, "ver_margem_departamento")


def atualizar_perfil(user_id, perfil):
    user_id = int(user_id)
    if user_id <= 0:
        raise ValueError("ID inválido.")
    permitidas = {"aprovado", "modelo_perfil_id", *CHAVES_ESCOPO, *OPCOES_CONSULTA, *PERMISSOES}
    if not perfil or not set(perfil).issubset(permitidas):
        raise ValueError("Perfil contém campos inválidos.")
    if any(not isinstance(valor, bool) for chave, valor in perfil.items() if chave not in CHAVES_ESCOPO | {'modelo_perfil_id'}):
        raise ValueError("As permissões devem ser booleanas.")
    if eh_admin(user_id):
        if perfil.get("aprovado") is False:
            raise ValueError("Não é possível bloquear o administrador principal.")
        if set(perfil) & (set(PERMISSOES) | CHAVES_ESCOPO | {'modelo_perfil_id'}):
            raise ValueError("As permissões do administrador principal não podem ser alteradas.")
    with _LOCK:
        dados = _carregar_arquivo()
        existente = dados["usuarios"].get(str(user_id))
        if not existente:
            raise ValueError("Usuário não encontrado.")
        perfil = _resolver_vinculo_modelo(dados, perfil)
        existente.update(perfil)
        if not existente.get('aprovado'):
            existente.update({chave: False for chave in PERMISSOES})
        _gravar_arquivo(dados)
        return dict(existente)


def listar_perfis():
    with _LOCK:
        perfis = [
            dict(perfil) for perfil in _carregar_arquivo()["usuarios"].values()
        ]
    perfis.sort(key=lambda usuario: (
        bool(usuario.get("aprovado")),
        str(usuario.get("nome") or usuario.get("apelido") or usuario["telegram_id"]).casefold(),
    ))
    return perfis


def autorizar(user_id, apelido=None):
    """Compatibilidade com a antiga autorização por comando."""
    user_id = int(user_id)
    if user_id <= 0:
        raise ValueError("ID inválido.")
    apelido = _normalizar_apelido(apelido)
    perfil = obter_perfil(user_id)
    if perfil is None:
        perfil = registrar_usuario(user_id)
    alteracoes = {
        "aprovado": True,
        "consulta_preco": True,
        "buscar_por_foto": True,
        "buscar_codprod": True,
        "buscar_codauxiliar": True,
        "buscar_codauxiliar2": True,
        "ver_margem_produto": True, "ver_margem_departamento": True,
        "ver_custos": True,
    }
    if apelido is not None:
        alteracoes["apelido"] = apelido
    with _LOCK:
        dados = _carregar_arquivo()
        dados["usuarios"][str(user_id)].update(alteracoes)
        _gravar_arquivo(dados)
    return user_id


def identificar_usuario(identificador):
    valor = str(identificador).strip()
    with _LOCK:
        usuarios = _carregar_arquivo()["usuarios"]
        if valor.isascii() and valor.isdecimal():
            return int(valor) if valor in usuarios else None
        encontrados = [
            int(user_id)
            for user_id, perfil in usuarios.items()
            if (perfil.get("apelido") or "").casefold() == valor.casefold()
        ]
    if len(encontrados) > 1:
        raise ValueError("Apelido ambíguo. Informe o ID do Telegram.")
    return encontrados[0] if encontrados else None


def revogar(identificador):
    user_id = identificar_usuario(identificador)
    if user_id is None:
        return None
    if eh_admin(user_id):
        raise ValueError("Não é possível revogar o administrador principal.")
    with _LOCK:
        dados = _carregar_arquivo()
        dados["usuarios"].pop(str(user_id), None)
        _gravar_arquivo(dados)
    return user_id


def definir_apelido(identificador, apelido):
    user_id = identificar_usuario(identificador)
    if user_id is None:
        raise ValueError("Usuário não encontrado na lista de autorizados.")
    apelido = _normalizar_apelido(apelido)
    with _LOCK:
        dados = _carregar_arquivo()
        for outro_id, perfil in dados["usuarios"].items():
            if (
                outro_id != str(user_id)
                and (perfil.get("apelido") or "").casefold() == apelido.casefold()
            ):
                raise ValueError("Esse apelido já pertence a outro usuário.")
        dados["usuarios"][str(user_id)]["apelido"] = apelido
        _gravar_arquivo(dados)
    return user_id


def listar_usuarios():
    return [
        (perfil["telegram_id"], perfil.get("autorizado_em"), perfil.get("apelido"))
        for perfil in listar_perfis()
        if perfil.get("aprovado")
    ]


def obter_escopo_acesso(user_id):
    teste = perfil_teste_ativo(user_id)
    if teste is None and eh_admin(user_id):
        return {}
    perfil = teste if teste is not None else obter_perfil(user_id) or {}
    return {chave: perfil.get(chave) for chave in CHAVES_ESCOPO}


def obter_opcoes_consulta(user_id):
    perfil = perfil_teste_ativo(user_id)
    if perfil is None:
        perfil = obter_perfil(user_id) or {}
    return {chave: bool(perfil.get(chave, False)) for chave in OPCOES_CONSULTA}
