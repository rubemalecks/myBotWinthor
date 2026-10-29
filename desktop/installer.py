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

def instalar(programa, dados, payload):
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
    config={'data_dir':str(dados),'executable':str(exe)}
    (versao/'desktop.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    temporario=programa/'instalacao.tmp'; temporario.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    temporario.replace(programa/'instalacao.json')
    # Só constantes e caminhos escapados são usados no comando do atalho.
    def ps(valor): return "'"+str(valor).replace("'","''")+"'"
    comando="$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'myBotWinthor.lnk')); $s.TargetPath="+ps(exe)+"; $s.WorkingDirectory="+ps(versao)+"; $s.Save()"
    resultado=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(comando.encode('utf-16le')).decode()],creationflags=subprocess.CREATE_NO_WINDOW,capture_output=True,timeout=20)
    return exe, resultado.returncode==0

def main():
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    raiz=tk.Tk(); raiz.title('Instalar myBotWinthor'); raiz.geometry('750x490')
    corpo=ttk.Frame(raiz,padding=24); corpo.pack(fill='both',expand=True)
    ttk.Label(corpo,text='Instalar ou atualizar myBotWinthor',font=('Segoe UI',18,'bold')).pack(anchor='w',pady=10)
    ttk.Label(corpo,text='Antes de atualizar: pare o bot antigo e desative serviços Windows antigos.\nFaça uma cópia da pasta de dados. Não mantenha dois bots com o mesmo token.',wraplength=690).pack(anchor='w',pady=8)
    programa=tk.StringVar(value=str(Path(os.environ['LOCALAPPDATA'])/'Programs'/'myBotWinthor'))
    dados=tk.StringVar(value=str(padrao_dados()))
    def recuperar(*args):
        arquivo=Path(programa.get())/'instalacao.json'
        try:
            if arquivo.is_file(): dados.set(json.loads(arquivo.read_text(encoding='utf-8'))['data_dir'])
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
    aceito=tk.BooleanVar(); ttk.Checkbutton(corpo,text='Confirmei a pasta de dados e parei a versão anterior.',variable=aceito).pack(anchor='w')
    estado=tk.StringVar();ttk.Label(corpo,textvariable=estado).pack(anchor='w',pady=10)
    fila=queue.Queue(); instalado=None; ocupado=False
    def executar():
        nonlocal ocupado
        if not aceito.get(): messagebox.showwarning('Confira os dados','Confirme a pasta de dados e pare a versão anterior.');return
        ocupado=True; botao.configure(state='disabled');estado.set('Instalando… Aguarde a conclusão.');p,d=programa.get(),dados.get()
        payload=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'payload.zip'
        def tarefa():
            try:fila.put(('ok',instalar(p,d,payload)))
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
                if messagebox.askyesno('Configurar agora','Abrir o gerenciador? Nenhum bot será iniciado automaticamente.'):
                    subprocess.Popen([str(instalado)],cwd=instalado.parent,creationflags=subprocess.CREATE_NO_WINDOW)
            else:estado.set('Instalação não concluída.');messagebox.showerror('Não foi possível instalar',valor)
        except queue.Empty:pass
        raiz.after(200,checar)
    def fechar():
        if ocupado:messagebox.showinfo('Aguarde','Aguarde a instalação terminar.');return
        raiz.destroy()
    raiz.protocol('WM_DELETE_WINDOW',fechar);checar();raiz.mainloop()

if __name__=='__main__':main()
