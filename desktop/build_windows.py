"""Gera pacotes limpos para cliente e uso portátil, sem dados de instalação."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import zipfile

DADOS_PROIBIDOS = {'desktop.json', 'instalacao.json', 'dados_bot.json',
    'config_bot.json', 'config_oracle.json', 'mensagens.json',
    'campos_produto.json', 'formulas_margem.json', 'permissoes.db'}
PASTAS_PROIBIDAS = {'.git', '.venv', 'venv', 'oracle_client'}


def validar_arquivo(arquivo, relativo):
    nome = arquivo.name.lower()
    if arquivo.is_symlink() or nome.startswith('.env') or nome in DADOS_PROIBIDOS or nome.endswith(('.log', '.bak', '.tmp')) or any(p.lower() in PASTAS_PROIBIDAS for p in relativo.parts):
        raise ValueError('Arquivo privado ou inesperado no runtime: ' + str(relativo))


def compactar(origem, destino):
    origem = Path(origem).resolve()
    arquivos = sorted(p for p in origem.rglob('*') if p.is_file() or p.is_symlink())
    for arquivo in arquivos:
        validar_arquivo(arquivo, arquivo.relative_to(origem))
    with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as pacote:
        for arquivo in arquivos:
            pacote.write(arquivo, arquivo.relative_to(origem))


def gravar_hashes(pasta):
    pasta = Path(pasta)
    linhas = []
    for arquivo in sorted(p for p in pasta.rglob('*') if p.is_file() and p.name != 'SHA256.txt'):
        with arquivo.open('rb') as conteudo:
            digest = hashlib.file_digest(conteudo, 'sha256').hexdigest()
        linhas.append(digest + '  ' + arquivo.relative_to(pasta).as_posix())
    (pasta / 'SHA256.txt').write_text('\n'.join(linhas) + '\n', encoding='utf-8')


def organizar_distribuicao(saida, runtime, payload, instalador):
    saida, runtime = Path(saida).resolve(), Path(runtime).resolve()
    projeto = Path(__file__).resolve().parents[1]
    protegidas = ('modulos', 'desktop', 'assets', 'tests', 'docs', '.git', '.venv', 'oracle_client')
    if saida == projeto or saida == saida.parent or saida.name == '.build' or any(saida.is_relative_to(projeto / nome) for nome in protegidas) or runtime.is_relative_to(saida) or saida.is_relative_to(runtime):
        raise ValueError('Saída deve ser uma pasta exclusiva e separada do runtime/código.')
    if not (runtime / 'myBotWinthor.exe').is_file() or not (runtime / '_internal').is_dir():
        raise ValueError('Runtime incompleto: EXE e _internal são obrigatórios.')
    for arquivo in runtime.rglob('*'):
        if arquivo.is_file() or arquivo.is_symlink():
            validar_arquivo(arquivo, arquivo.relative_to(runtime))
    with zipfile.ZipFile(payload) as pacote:
        if pacote.testzip() is not None:
            raise ValueError('ZIP do runtime está corrompido.')
        esperado = {p.relative_to(runtime).as_posix() for p in runtime.rglob('*') if p.is_file()}
        if set(pacote.namelist()) != esperado:
            raise ValueError('ZIP e runtime não contêm os mesmos arquivos.')
        for nome in esperado:
            with pacote.open(nome) as a, (runtime / nome).open('rb') as b:
                if hashlib.file_digest(a, 'sha256').digest() != hashlib.file_digest(b, 'sha256').digest():
                    raise ValueError('ZIP e runtime pertencem a versões diferentes: ' + nome)
    identificador = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
    # Todo o pacote é preparado antes de substituir a distribuição anterior.
    area = (saida.parent / '.build' / 'distribuicao').resolve()
    if not area.is_relative_to(saida.parent):
        raise ValueError('Área de build fora da pasta autorizada.')
    stage = area / ('stage-' + identificador)
    stage.mkdir(parents=True)
    cliente, portatil = stage / 'cliente', stage / 'portatil'
    cliente.mkdir()
    shutil.copy2(instalador, cliente / 'Instalar-myBotWinthor.exe')
    shutil.copytree(runtime, portatil)
    guia = Path(__file__).parent / 'INSTALACAO.txt'
    for pasta in (cliente, portatil):
        shutil.copy2(guia, pasta / 'LEIA-ME.txt')
        (pasta / 'pacote.json').write_text(json.dumps({
            'produto': 'myBotWinthor', 'build': identificador, 'plataforma': 'Windows x64',
            'formato': pasta.name, 'dados_incluidos': False,
            'dados_padrao': '%LOCALAPPDATA%/myBotWinthor/dados'}, indent=2), encoding='utf-8')
        gravar_hashes(pasta)
    # Compactar estas pastas inclui seus guias e manifestos, sem exigir arquivos da raiz.
    for pasta, nome in ((cliente, 'myBotWinthor-cliente.zip'), (portatil, 'myBotWinthor-portatil.zip')):
        with zipfile.ZipFile(stage / nome, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as pacote:
            for arquivo in sorted(p for p in pasta.rglob('*') if p.is_file()):
                pacote.write(arquivo, arquivo.relative_to(pasta))
    (stage / 'LEIA-ME.txt').write_text('ENVIO AO CLIENTE: myBotWinthor-cliente.zip ou a pasta cliente inteira.\nALTERNATIVA SEM INSTALACAO: myBotWinthor-portatil.zip ou a pasta portatil inteira.\nNao misture arquivos de versoes diferentes. Nao coloque dados pessoais nesta pasta.\n', encoding='utf-8')
    gravar_hashes(stage)
    backup = area / ('anterior-' + identificador)
    if saida.exists():
        # Ambos são caminhos absolutos verificados dentro do destino solicitado.
        if not backup.is_relative_to(saida.parent) or saida == projeto:
            raise ValueError('Destino de backup inválido.')
        saida.rename(backup)
    try:
        stage.rename(saida)
    except OSError:
        if backup.exists() and not saida.exists():
            backup.rename(saida)
        raise
    return saida


def main():
    raiz = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(raiz / 'distribuicao'))
    parser.add_argument('--work', default=str(raiz / '.build' / 'windows'))
    args = parser.parse_args()
    saida, work = Path(args.output).resolve(), Path(args.work).resolve()
    if work.is_relative_to(saida) or saida.is_relative_to(work):
        parser.error('Pastas de build e distribuição devem ser separadas.')
    (work / 'tmp').mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'TEMP': str(work / 'tmp'), 'TMP': str(work / 'tmp')}
    def build(argumentos):
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', *argumentos], cwd=raiz, env=env, check=True)
    build(['--distpath', str(work / 'dist'), '--workpath', str(work / 'build'), str(raiz / 'desktop/myBotWinthor.spec')])
    payload = work / 'payload.zip'
    compactar(work / 'dist/myBotWinthor', payload)
    build(['--onefile', '--windowed', '--name', 'Instalar-myBotWinthor', '--icon', str(raiz / 'assets/rb_app_icon.ico'), '--add-data', str(payload) + ';.', '--distpath', str(work / 'installer-dist'), '--workpath', str(work / 'installer-build'), '--specpath', str(work), str(raiz / 'desktop/installer.py')])
    organizar_distribuicao(saida, work / 'dist/myBotWinthor', payload, work / 'installer-dist/Instalar-myBotWinthor.exe')
    print('Distribuição pronta:', saida)


if __name__ == '__main__':
    main()
