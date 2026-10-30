"""Desinstalação explícita e limitada aos arquivos pertencentes à instalação."""
import ctypes, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
from desktop.common import ARQUIVOS_DADOS
from desktop.windows import PRODUCT


def plano(manifesto,apagar_dados):
    manifesto=Path(manifesto).absolute()
    if manifesto.is_symlink():raise ValueError('Manifesto não pode ser um link.')
    info=json.loads(manifesto.read_text(encoding='utf-8'))
    root=manifesto.parent.resolve();dados=Path(info['data_dir']).resolve()
    if info.get('product')!=PRODUCT or Path(info['install_root']).resolve()!=root:
        raise ValueError('Esta pasta não é uma instalação reconhecida.')
    if root==Path(root.anchor) or root==Path.home().resolve() or root==dados or root.is_relative_to(dados) or dados.is_relative_to(root):
        raise ValueError('Pastas de desinstalação inseguras.')
    arquivos=[]
    for nome in info.get('owned_files',[]):
        rel=Path(nome)
        if rel.is_absolute() or '..' in rel.parts or not rel.parts or (rel.parts[0]!='versoes' and rel.as_posix() not in ('Desinstalar-myBotWinthor.exe','instalacao.json')):
            raise ValueError('Arquivo fora do escopo de remoção.')
        alvo=root/rel
        if alvo.is_symlink() or not alvo.resolve().is_relative_to(root):raise ValueError('Link externo na instalação.')
        arquivos.append(alvo)
    if not arquivos:raise ValueError('Instalação sem inventário de arquivos.')
    if apagar_dados:
        nomes=list(ARQUIVOS_DADOS)+['logs/aplicacao.log','logs/aplicacao-anterior.log','logs/gerenciador.log','logs/gerenciador-anterior.log']
        for nome in ARQUIVOS_DADOS:
            nomes.extend(p.name for p in dados.glob('.'+nome+'.*.tmp') if p.is_file())
        for nome in nomes:
            alvo=dados/nome
            if alvo.is_symlink() or not alvo.resolve().is_relative_to(dados):raise ValueError('Link externo nos dados.')
            arquivos.append(alvo)
    return info,root,dados,arquivos


def limpar_arquivos(manifesto,apagar_dados):
    info,root,dados,arquivos=plano(manifesto,apagar_dados)
    diretorios=set()
    # O manifesto é removido por último para permitir repetir uma remoção incompleta.
    arquivos.sort(key=lambda p:p.name=='instalacao.json')
    for arquivo in arquivos:
        if arquivo.exists():arquivo.unlink()
        pai=arquivo.parent
        while pai.is_relative_to(root) and pai!=root:
            diretorios.add(pai);pai=pai.parent
    for pasta in sorted(diretorios,key=lambda p:len(p.parts),reverse=True):
        try:pasta.rmdir()
        except OSError:pass
    for pasta in ([dados/'logs',dados] if apagar_dados else [])+[root]:
        try:pasta.rmdir()
        except OSError:pass
    return info


def executar(manifesto,apagar_dados,remover_legado):
    from desktop.windows import sinalizar,ativo,remover_servico,RUN,UNINSTALL,chave_inicio
    info,root,dados,_=plano(manifesto,apagar_dados)
    sinalizar(dados,'-quit');sinalizar(dados)
    for _ in range(90):
        if not ativo(dados) and not ativo(dados,True):break
        time.sleep(.5)
    else:raise RuntimeError('O aplicativo ainda está ativo. Nenhum arquivo foi apagado.')
    if remover_legado:remover_servico()
    import winreg
    sid=info.get('owner_sid')
    base=winreg.HKEY_USERS if sid else winreg.HKEY_CURRENT_USER
    prefixo=(sid+'\\') if sid else ''
    try:
        with winreg.OpenKey(base,prefixo+RUN,0,winreg.KEY_SET_VALUE) as chave:
            try:winreg.DeleteValue(chave,chave_inicio(info['executable']))
            except FileNotFoundError:pass
    except FileNotFoundError:pass
    try:winreg.DeleteKey(base,prefixo+UNINSTALL)
    except FileNotFoundError:pass
    # Somente o atalho criado pelo instalador, do usuário proprietário.
    atalho=info.get('shortcut')
    if atalho:
        arquivo=Path(atalho)
        if arquivo.name=='myBotWinthor.lnk' and arquivo.is_file():arquivo.unlink()
    limpar_arquivos(manifesto,apagar_dados)


def agendar_limpeza_temp():
    import base64
    exe=Path(sys.executable).resolve();pasta=exe.parent
    if exe.name!='Desinstalar-myBotWinthor.exe' or not pasta.name.startswith('myBotWinthor-uninstall-') or not pasta.is_relative_to(Path(tempfile.gettempdir()).resolve()):return
    def ps(v):return "'"+str(v).replace("'","''")+"'"
    script='Wait-Process -Id '+str(os.getpid())+' -ErrorAction SilentlyContinue; Remove-Item -LiteralPath '+ps(exe)+' -Force -ErrorAction SilentlyContinue; Remove-Item -LiteralPath '+ps(pasta)+' -ErrorAction SilentlyContinue'
    subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()],creationflags=subprocess.CREATE_NO_WINDOW)


def main():
    import tkinter as tk
    from tkinter import ttk,messagebox
    from desktop.theme import aplicar,cabecalho
    if '--cleanup' in sys.argv:
        i=sys.argv.index('--cleanup');manifesto=Path(sys.argv[i+1]);pid=int(sys.argv[i+2])
        # Aguarda a janela original fechar/liberar o EXE antes de remover arquivos.
        import win32api,win32event,win32con,pywintypes
        try:
            h=win32api.OpenProcess(win32con.SYNCHRONIZE,False,pid)
            try:win32event.WaitForSingleObject(h,15000)
            finally:h.Close()
        except pywintypes.error:pass
        try:
            executar(manifesto,'--delete-data' in sys.argv,'--remove-service' in sys.argv)
            messagebox.showinfo('myBotWinthor removido','Desinstalação concluída. Arquivos não reconhecidos e backups externos foram preservados.')
        except Exception as erro:messagebox.showerror('Remoção incompleta',str(erro))
        finally:agendar_limpeza_temp()
        return
    manifesto=Path(sys.argv[sys.argv.index('--manifest')+1]) if '--manifest' in sys.argv else Path(sys.executable).parent/'instalacao.json'
    try:info,root,dados,_=plano(manifesto,False)
    except Exception as erro:messagebox.showerror('Instalação não reconhecida',str(erro));return
    raiz=tk.Tk();raiz.title('Desinstalar myBotWinthor');raiz.geometry('780x620');aplicar(raiz)
    corpo=ttk.Frame(raiz,padding=24);corpo.pack(fill='both',expand=True);cabecalho(corpo,'Desinstalar aplicação')
    ttk.Label(corpo,text='Programa: '+str(root)+'\nDados: '+str(dados),wraplength=720).pack(anchor='w',pady=12)
    apagar=tk.BooleanVar(value=False);legado=tk.BooleanVar(value=False)
    ttk.Checkbutton(corpo,text='Apagar também cadastros, login, senhas, tokens, fórmulas e logs',variable=apagar).pack(anchor='w',pady=10)
    ttk.Label(corpo,text='Esta opção é irreversível. Faça backup antes. Não apaga o Oracle nem arquivos desconhecidos, outras aplicações ou backups externos.',wraplength=700).pack(anchor='w')
    from desktop.windows import servico_existe
    try:existe=servico_existe()
    except Exception:existe=True
    if existe:
        legado.set(True);ttk.Checkbutton(corpo,text='Remover também o serviço legado MyBotWinthorBot (exige administrador)',variable=legado).pack(anchor='w',pady=12)
    def confirmar():
        if not messagebox.askyesno('Confirmar desinstalação','Parar a aplicação e remover os arquivos?'+('\nTODOS os dados reconhecidos desta instalação serão apagados.' if apagar.get() else '\nOs cadastros e configurações serão preservados.')):return
        destino=Path(tempfile.mkdtemp(prefix='myBotWinthor-uninstall-'))/'Desinstalar-myBotWinthor.exe'
        shutil.copy2(sys.executable,destino)
        argumentos=['--cleanup',str(manifesto),str(os.getpid())]
        if apagar.get():argumentos.append('--delete-data')
        if legado.get():argumentos.append('--remove-service')
        if legado.get() and not ctypes.windll.shell32.IsUserAnAdmin():
            resultado=ctypes.windll.shell32.ShellExecuteW(None,'runas',str(destino),subprocess.list2cmdline(argumentos),str(destino.parent),0)
            if resultado<=32:messagebox.showerror('Remoção cancelada','É necessário autorizar a remoção do serviço no Windows.');return
        else:subprocess.Popen([str(destino),*argumentos],env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'},creationflags=subprocess.CREATE_NO_WINDOW)
        raiz.destroy()
    ttk.Button(corpo,text='Desinstalar',command=confirmar).pack(anchor='e',pady=24)
    raiz.mainloop()

if __name__=='__main__':main()
