"""Gerenciador gráfico e processo isolado do bot/API."""
import os, sys, json, subprocess, ctypes, time, webbrowser
from pathlib import Path
from desktop.common import pasta_dados, identificador

def main():
    if '--self-test' in sys.argv:
        import tempfile, importlib, traceback
        destino=Path(sys.argv[sys.argv.index('--self-test')+1])
        try:
            with tempfile.TemporaryDirectory(dir=destino.parent) as pasta:
                os.environ['BOT_DATA_DIR']=pasta
                for nome in ('modulos.bot','modulos.painel_admin','cv2','numpy','zxingcpp','oracledb'):
                    importlib.import_module(nome)
                import tkinter as tk
                janela=tk.Tk(); janela.withdraw(); janela.update(); janela.destroy()
                from modulos.painel_admin import BASE_DIR
                assert (BASE_DIR/'assets'/'rb_app_icon.png').is_file()
                destino.write_text(json.dumps({'ok':True,'imports':True,'tkinter':True,'assets':True}),encoding='utf-8')
        except Exception:
            destino.write_text(json.dumps({'ok':False,'error':traceback.format_exc()}),encoding='utf-8')
            raise SystemExit(1)
        return
    dados = pasta_dados()
    dados.mkdir(parents=True, exist_ok=True)
    os.environ['BOT_DATA_DIR'] = str(dados)
    if '--worker' in sys.argv:
        worker(dados)
        return
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    from tkinter.scrolledtext import ScrolledText
    from modulos.permissoes import obter_configuracao, salvar_configuracoes
    raiz = tk.Tk(); raiz.title('myBotWinthor — Controle da aplicação'); raiz.geometry('1000x680')
    frame = ttk.Frame(raiz, padding=16); frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='myBotWinthor', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='Dados e configurações: ' + str(dados), wraplength=940).pack(anchor='w', pady=8)
    status = tk.StringVar(value='Parado'); ttk.Label(frame, textvariable=status).pack(anchor='w')
    botoes = ttk.Frame(frame); botoes.pack(fill='x', pady=12)
    logs = ScrolledText(frame, state='disabled', font=('Consolas', 10)); logs.pack(fill='both', expand=True)
    processo = None; reiniciar = False; posicao = 0; parando = False; prazo = 0
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenMutexW.restype = ctypes.c_void_p; kernel.OpenEventW.restype = ctypes.c_void_p
    kernel.OpenMutexW.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.OpenEventW.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]; kernel.SetEvent.argtypes = [ctypes.c_void_p]
    def ativo():
        handle = kernel.OpenMutexW(0x100000, False, identificador(dados))
        if handle: kernel.CloseHandle(handle)
        return bool(handle)
    def iniciar():
        nonlocal processo
        if ativo() or (processo and processo.poll() is None):
            messagebox.showinfo('Já está rodando', 'A aplicação já está ativa nesta pasta de dados.'); return
        comando = [sys.executable, '--worker'] if getattr(sys, 'frozen', False) else [sys.executable, '-m', 'desktop.launcher', '--worker']
        processo = subprocess.Popen(comando, cwd=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1], env={**os.environ, 'PYTHONUTF8':'1'}, creationflags=subprocess.CREATE_NO_WINDOW)
        status.set('Iniciando…')
    def parar(reinicia=False):
        nonlocal reiniciar, parando, prazo
        if not ativo():
            if reinicia: iniciar()
            return
        handle = kernel.OpenEventW(2, False, identificador(dados) + '-stop')
        if not handle:
            messagebox.showerror('Não foi possível parar', 'O processo não disponibilizou o controle de parada. Confira o log.'); return
        kernel.SetEvent(handle); kernel.CloseHandle(handle)
        reiniciar = reinicia; parando = True; prazo = time.monotonic() + 35; status.set('Encerrando consultas e painel…')
    def painel():
        config = obter_configuracao()
        webbrowser.open('http://127.0.0.1:' + config['WEB_ADMIN_PORT'])
    def configurar():
        if ativo():
            messagebox.showinfo('Pare antes de configurar', 'Pare a aplicação antes de alterar as conexões.'); return
        config = obter_configuracao(); janela = tk.Toplevel(raiz); janela.title('Configurar instalação'); janela.transient(raiz); janela.grab_set()
        campos = {}; corpo = ttk.Frame(janela, padding=18); corpo.pack(fill='both', expand=True)
        itens = [('ORACLE_HOST','Servidor Oracle'),('ORACLE_PORT','Porta Oracle'),('ORACLE_SERVICE','Serviço Oracle'),('ORACLE_USER','Usuário Oracle'),('ORACLE_PASSWORD','Senha Oracle (vazio mantém a atual)'),('ORACLE_CLIENT_DIR','Pasta local do Oracle Client (opcional)'),('TELEGRAM_BOT_TOKEN','Token Telegram (vazio mantém o atual)'),('TELEGRAM_ADMIN_ID','ID do administrador Telegram'),('WEB_ADMIN_PORT','Porta do painel')]
        for i,(chave,rotulo) in enumerate(itens):
            ttk.Label(corpo,text=rotulo).grid(row=i,column=0,sticky='w',padx=6,pady=6)
            secreto = chave in ('ORACLE_PASSWORD','TELEGRAM_BOT_TOKEN')
            entrada = ttk.Entry(corpo,width=52,show='*' if secreto else ''); entrada.grid(row=i,column=1,pady=6)
            entrada.insert(0,'' if secreto else config[chave]); campos[chave]=entrada
        ttk.Label(corpo,text='Os cadastros são preservados. A senha do painel é alterada no próprio painel.').grid(row=10,column=0,columnspan=2,pady=10)
        def salvar():
            try:
                valores={k:e.get().strip() for k,e in campos.items()}
                for k in ('ORACLE_PORT','WEB_ADMIN_PORT'):
                    if not valores[k].isascii() or not valores[k].isdecimal() or not 1 <= int(valores[k]) <= 65535: raise ValueError('Porta inválida.')
                if valores['TELEGRAM_ADMIN_ID'] and (not valores['TELEGRAM_ADMIN_ID'].isascii() or not valores['TELEGRAM_ADMIN_ID'].isdecimal()): raise ValueError('ID Telegram inválido.')
                from modulos.database import validar_diretorio_cliente
                validar_diretorio_cliente(valores['ORACLE_CLIENT_DIR'])
                for k in ('ORACLE_PASSWORD','TELEGRAM_BOT_TOKEN'):
                    if not valores[k]: valores.pop(k)
                salvar_configuracoes(valores); janela.destroy(); messagebox.showinfo('Configuração salva','Clique em Iniciar; depois abra o painel para configurar usuários e trocar a senha inicial.')
            except (ValueError,OSError) as erro: messagebox.showerror('Não foi possível salvar',str(erro))
        ttk.Button(corpo,text='Salvar configuração',command=salvar).grid(row=11,column=1,sticky='e')
    for texto,acao in [('Iniciar',iniciar),('Parar',parar),('Reiniciar',lambda:parar(True)),('Configurações',configurar),('Abrir painel',painel),('Abrir pasta de dados',lambda:os.startfile(dados))]:
        ttk.Button(botoes,text=texto,command=acao).pack(side='left',padx=4)
    def atualizar():
        nonlocal posicao, parando, reiniciar
        arquivo = dados / 'logs' / 'aplicacao.log'
        if arquivo.exists():
            if arquivo.stat().st_size < posicao: posicao=0
            with arquivo.open('rb') as f:
                f.seek(posicao); trecho=f.read(65536); posicao=f.tell()
            if trecho:
                logs.configure(state='normal'); logs.insert('end',trecho.decode('utf-8',errors='replace'))
                if int(logs.index('end-1c').split('.')[0]) > 2500: logs.delete('1.0','500.0')
                logs.see('end'); logs.configure(state='disabled')
        rodando = ativo()
        if parando and not rodando:
            parando=False
            if reiniciar: reiniciar=False; iniciar()
        elif parando and time.monotonic()>prazo:
            parando=False; reiniciar=False
            messagebox.showwarning('Parada demorada','A parada ainda não terminou. Confira os logs; nenhuma segunda instância foi iniciada.')
        if not parando: status.set('Em execução' if rodando else 'Parado')
        raiz.after(600,atualizar)
    def fechar():
        if ativo():
            messagebox.showinfo('Aplicação ativa','Use Parar e aguarde o encerramento antes de fechar o gerenciador.'); return
        raiz.destroy()
    raiz.protocol('WM_DELETE_WINDOW',fechar); atualizar(); raiz.mainloop()

def worker(dados):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.restype=ctypes.c_void_p; kernel.CreateEventW.restype=ctypes.c_void_p
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
    kernel.CreateEventW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_bool,ctypes.c_wchar_p]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]; kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
    mutex=kernel.CreateMutexW(None,True,identificador(dados))
    if not mutex: raise OSError('Não foi possível criar o controle de instância.')
    if ctypes.get_last_error()==183: kernel.CloseHandle(mutex); return
    evento=kernel.CreateEventW(None,True,False,identificador(dados)+'-stop')
    if not evento: kernel.CloseHandle(mutex); raise OSError('Não foi possível criar o controle de parada.')
    pasta=dados/'logs'; pasta.mkdir(exist_ok=True)
    log=pasta/'aplicacao.log'
    if log.exists() and log.stat().st_size > 10*1024*1024: log.replace(pasta/'aplicacao-anterior.log')
    sys.stdout=log.open('a',encoding='utf-8',buffering=1); sys.stderr=sys.stdout
    try:
        if not (dados/'config_bot.json').exists():
            from modulos.permissoes import salvar_configuracoes
            salvar_configuracoes({'WEB_ADMIN_HOST':'127.0.0.1'})
        from modulos.bot import main as iniciar_bot
        iniciar_bot(parar=lambda:kernel.WaitForSingleObject(evento,0)==0)
    except Exception:
        import traceback; traceback.print_exc()
    finally:
        kernel.CloseHandle(evento); kernel.CloseHandle(mutex); sys.stdout.flush()

if __name__=='__main__':
    try: main()
    except Exception as erro:
        import tkinter.messagebox as mb
        mb.showerror('myBotWinthor', 'Não foi possível abrir: '+str(erro))
