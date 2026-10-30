"""Instalador por usuário: executáveis versionados e dados preservados."""
import os, sys, json, zipfile, threading, queue, subprocess, base64
from pathlib import Path
from datetime import datetime
from desktop.common import padrao_dados, validar_dados

def extrair_seguro(arquivo, destino):
    destino=Path(destino).resolve()
    with zipfile.ZipFile(arquivo) as pacote:
        if sum(i.file_size for i in pacote.infolist()) > 2*1024**3: raise ValueError('Pacote excede o limite de tamanho.')
        for item in pacote.infolist():
            alvo=(destino/item.filename).resolve()
            if not alvo.is_relative_to(destino) or ':' in item.filename or item.filename.startswith(('/', '\\')): raise ValueError('Caminho inválido no pacote.')
        pacote.extractall(destino)

def instalar(programa, dados, payload, autostart=False):
    programa=Path(programa).resolve(); dados=validar_dados(dados)
    if programa==dados or programa.is_relative_to(dados) or dados.is_relative_to(programa):
        raise ValueError('Mantenha as pastas do programa e dos dados separadas.')
    if str(programa).replace('\\','/').startswith('//'): raise ValueError('Instale em disco local.')
    if (dados/'bot.py').exists() or (dados/'.venv').exists():
        raise ValueError('Esta é a pasta do código antigo. Selecione a pasta de dados que contém dados_bot.json.')
    dados.mkdir(parents=True,exist_ok=True)
    versao=programa/'versoes'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    versao.mkdir(parents=True)
    extrair_seguro(payload,versao)
    exe=versao/'myBotWinthor.exe'
    if not exe.is_file(): raise ValueError('Executável ausente no pacote.')
    from desktop.windows import PRODUCT, registrar
    config={'product':PRODUCT,'install_root':str(programa),'data_dir':str(dados),'executable':str(exe),'autostart':autostart}
    (versao/'desktop.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    desinstalador=versao/'Desinstalar-myBotWinthor.exe'
    if desinstalador.is_file():
        import shutil
        shutil.copy2(desinstalador,programa/desinstalador.name)
        config['owner_sid']=registrar(programa,exe,dados,autostart)
    anteriores=programa/'instalacao.json'
    owned=set()
    if anteriores.is_file():
        anterior=json.loads(anteriores.read_text(encoding='utf-8'))
        owned.update(anterior.get('owned_files',[]))
    for antiga in (programa/'versoes').iterdir():
        marca=antiga/'desktop.json'
        if not antiga.is_dir() or antiga.is_symlink() or not marca.is_file():continue
        try:reconhecida=json.loads(marca.read_text(encoding='utf-8'))
        except (ValueError,OSError):continue
        if Path(reconhecida.get('executable','')).resolve()!=antiga/'myBotWinthor.exe':continue
        owned.update(p.relative_to(programa).as_posix() for p in antiga.rglob('*') if p.is_file() and not p.is_symlink())
    owned.update(p.relative_to(programa).as_posix() for p in versao.rglob('*') if p.is_file())
    owned.update(('Desinstalar-myBotWinthor.exe','instalacao.json'))
    config['owned_files']=sorted(owned)
    temporario=programa/'instalacao.tmp'; temporario.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    temporario.replace(programa/'instalacao.json')
    # Só constantes e caminhos escapados são usados no comando do atalho.
    def ps(valor): return "'"+str(valor).replace("'","''")+"'"
    comando="$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'myBotWinthor.lnk')); $s.TargetPath="+ps(exe)+"; $s.WorkingDirectory="+ps(versao)+"; $s.Save()"
    resultado=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(comando.encode('utf-16le')).decode()],creationflags=subprocess.CREATE_NO_WINDOW,capture_output=True,timeout=20)
    if resultado.returncode==0:
        import ctypes
        desktop=ctypes.create_unicode_buffer(32768)
        result=ctypes.windll.shell32.SHGetFolderPathW(None,0x10,None,0,desktop)
        config['shortcut']=str(Path(desktop.value)/'myBotWinthor.lnk') if result==0 else ''
        temporario.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8');temporario.replace(programa/'instalacao.json')
    return exe, resultado.returncode==0

def main():
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    raiz=tk.Tk(); raiz.title('Instalar myBotWinthor'); raiz.geometry('820x740')
    corpo=ttk.Frame(raiz,padding=24); corpo.pack(fill='both',expand=True)
    from desktop.theme import aplicar,cabecalho
    aplicar(raiz);cabecalho(corpo,'Instalar ou atualizar')
    ttk.Label(corpo,text='Antes de atualizar: pare o bot antigo e desative serviços Windows antigos.\nFaça uma cópia da pasta de dados. Não mantenha dois bots com o mesmo token.',wraplength=690).pack(anchor='w',pady=8)
    programa=tk.StringVar(value=str(Path(os.environ['LOCALAPPDATA'])/'Programs'/'myBotWinthor'))
    dados=tk.StringVar(value=str(padrao_dados()))
    autostart=tk.BooleanVar(value=False)
    def recuperar(*args):
        arquivo=Path(programa.get())/'instalacao.json'
        try:
            if arquivo.is_file():
                info=json.loads(arquivo.read_text(encoding='utf-8'));dados.set(info['data_dir']);autostart.set(info.get('autostart',False))
        except (ValueError,KeyError,OSError): pass
    programa.trace_add('write',recuperar); recuperar()
    for rotulo,variavel in [('Pasta do programa',programa),('Pasta de dados — nova ou existente',dados)]:
        ttk.Label(corpo,text=rotulo).pack(anchor='w',pady=(8,0)); linha=ttk.Frame(corpo);linha.pack(fill='x')
        ttk.Entry(linha,textvariable=variavel).pack(side='left',fill='x',expand=True)
        def escolher(v=variavel):
            pasta=filedialog.askdirectory(title='Escolha a pasta')
            if pasta:v.set(pasta)
        ttk.Button(linha,text='Escolher…',command=escolher).pack(side='right')
    ttk.Label(corpo,text='Já usava outra versão? Selecione a pasta myBotWinthor-dados antiga (ou o BOT_DATA_DIR anterior), que contém dados_bot.json. Ela continuará sendo usada, sem mover nem substituir seus cadastros. Guarde também seu .env antigo; confira as conexões em Configurações.',wraplength=690).pack(anchor='w',pady=14)
    ttk.Checkbutton(corpo,text='Iniciar com o Windows, minimizado na bandeja (opcional)',variable=autostart).pack(anchor='w',pady=10)
    ttk.Label(corpo,text='Executa após entrar na conta do Windows. Pode desativar depois no gerenciador.').pack(anchor='w')
    aceito=tk.BooleanVar(); ttk.Checkbutton(corpo,text='Confirmei a pasta de dados e parei a versão anterior.',variable=aceito).pack(anchor='w')
    estado=tk.StringVar();ttk.Label(corpo,textvariable=estado).pack(anchor='w',pady=10)
    fila=queue.Queue(); instalado=None; ocupado=False
    def executar():
        nonlocal ocupado
        if not aceito.get(): messagebox.showwarning('Confira os dados','Confirme a pasta de dados e pare a versão anterior.');return
        ocupado=True; botao.configure(state='disabled');estado.set('Instalando… Aguarde a conclusão.');p,d,auto=programa.get(),dados.get(),autostart.get()
        payload=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'payload.zip'
        def tarefa():
            try:fila.put(('ok',instalar(p,d,payload,auto)))
            except Exception as erro:fila.put(('erro',str(erro)))
        threading.Thread(target=tarefa,daemon=True).start()
    botao=ttk.Button(corpo,text='Instalar / atualizar',command=executar);botao.pack(anchor='e')
    def checar():
        nonlocal ocupado,instalado
        try:
            tipo,valor=fila.get_nowait();ocupado=False;botao.configure(state='normal')
            if tipo=='ok':
                instalado,atalho=valor;estado.set('Instalação concluída. Dados: '+dados.get())
                messagebox.showinfo('Pronto','Abra myBotWinthor pelo atalho na Área de Trabalho.' if atalho else 'Programa instalado em '+str(instalado)+' (não foi possível criar o atalho).')
                if messagebox.askyesno('Configurar agora','Abrir o gerenciador para conferir as configurações?'):
                    subprocess.Popen([str(instalado)],cwd=instalado.parent,creationflags=subprocess.CREATE_NO_WINDOW)
            else:estado.set('Instalação não concluída.');messagebox.showerror('Não foi possível instalar',valor)
        except queue.Empty:pass
        raiz.after(200,checar)
    def fechar():
        if ocupado:messagebox.showinfo('Aguarde','Aguarde a instalação terminar.');return
        raiz.destroy()
    raiz.protocol('WM_DELETE_WINDOW',fechar);checar();raiz.mainloop()

if __name__=='__main__':main()
