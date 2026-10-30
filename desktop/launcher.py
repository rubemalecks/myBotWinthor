"""Gerenciador gráfico e processo isolado do bot/API."""
import os, sys, json, subprocess, ctypes, time, webbrowser, queue, threading
from pathlib import Path
from desktop.common import pasta_dados, identificador

def main():
    if '--oracle-diagnostic' in sys.argv:
        from desktop.diagnostics import diagnosticar_oracle
        i=sys.argv.index('--oracle-diagnostic')
        resultado=diagnosticar_oracle(sys.argv[i+1])
        Path(sys.argv[i+2]).write_text(json.dumps(resultado),encoding='utf-8')
        raise SystemExit(0 if resultado['ok'] else 1)
    if '--self-test' in sys.argv:
        import tempfile, importlib, traceback
        destino=Path(sys.argv[sys.argv.index('--self-test')+1])
        try:
            with tempfile.TemporaryDirectory(dir=destino.parent) as pasta:
                os.environ['BOT_DATA_DIR']=pasta
                for nome in ('modulos.bot','modulos.painel_admin','cv2','numpy','zxingcpp','oracledb'):
                    importlib.import_module(nome)
                from desktop.diagnostics import validar_criptografia
                assert validar_criptografia()
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
    (dados/'logs').mkdir(exist_ok=True)
    gui_log=dados/'logs'/'gerenciador.log'
    if gui_log.exists() and gui_log.stat().st_size>2*1024*1024:gui_log.replace(dados/'logs'/'gerenciador-anterior.log')
    sys.stderr=gui_log.open('a',encoding='utf-8',buffering=1)
    from desktop.windows import kernel as windows_kernel
    controle=windows_kernel()
    controle.CreateMutexW.restype=ctypes.c_void_p;controle.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
    controle.CreateEventW.restype=ctypes.c_void_p;controle.CreateEventW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_bool,ctypes.c_wchar_p]
    controle.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];controle.ResetEvent.argtypes=[ctypes.c_void_p]
    guard=controle.CreateMutexW(None,True,identificador(dados)+'-gui')
    if not guard:raise OSError('Falha no controle de instância.')
    if ctypes.get_last_error()==183:
        from desktop.windows import sinalizar
        sinalizar(dados,'-show');controle.CloseHandle(guard);return
    mostrar_evento=controle.CreateEventW(None,True,False,identificador(dados)+'-show')
    sair_evento=controle.CreateEventW(None,True,False,identificador(dados)+'-quit')
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    from tkinter.scrolledtext import ScrolledText
    from modulos.permissoes import obter_configuracao, salvar_configuracoes
    raiz = tk.Tk(); raiz.title('myBotWinthor — Controle da aplicação'); raiz.geometry('1120x800'); raiz.minsize(980,720)
    from desktop.theme import aplicar, assets
    aplicar(raiz)
    style=ttk.Style(raiz)
    style.configure('Card.TFrame',background='#ffffff')
    style.configure('Card.TLabel',background='#ffffff',foreground='#263746')
    style.configure('Muted.TLabel',foreground='#607586',font=('Segoe UI',9))
    style.configure('Secondary.TButton',background='#e3edf3',foreground='#24475c',padding=(12,9))
    style.map('Secondary.TButton',background=[('active','#d0e2ed'),('disabled','#edf2f5')],foreground=[('disabled','#8c9da8')])
    style.configure('Danger.TButton',background='#f6e9e9',foreground='#9c3434',padding=(12,9))
    frame = ttk.Frame(raiz, padding=20); frame.pack(fill='both', expand=True)
    header=ttk.Frame(frame,style='Card.TFrame',padding=16);header.pack(fill='x',pady=(0,12));header.columnconfigure(1,weight=1)
    from PIL import Image,ImageTk
    image=Image.open(assets()/'Logo geométrico myBotWinthor com monograma RB.png');image.thumbnail((290,96))
    foto=ImageTk.PhotoImage(image);marca=ttk.Label(header,image=foto,style='Card.TLabel');marca.image=foto;marca.grid(row=0,column=0,rowspan=2,padx=(0,24))
    ttk.Label(header,text='Gerenciador Windows',style='Card.TLabel',font=('Segoe UI',19,'bold')).grid(row=0,column=1,sticky='sw')
    ttk.Label(header,text='Controle a aplicação e acompanhe sua atividade em um só lugar.',style='Card.TLabel').grid(row=1,column=1,sticky='nw',pady=(5,0))
    operacao=ttk.Frame(frame,style='Card.TFrame',padding=16);operacao.pack(fill='x',pady=(0,12))
    ttk.Label(operacao,text='PROCESSO LOCAL',style='Card.TLabel',font=('Segoe UI',9,'bold')).pack(anchor='w')
    status = tk.StringVar(value='Parada')
    badge=ttk.Label(operacao,textvariable=status,style='Card.TLabel',font=('Segoe UI',18,'bold'));badge.pack(anchor='w',pady=(4,3))
    status_ajuda=tk.StringVar(value='Clique em Iniciar para disponibilizar o painel e o bot.')
    ttk.Label(operacao,textvariable=status_ajuda,style='Card.TLabel').pack(anchor='w')
    botoes = ttk.Frame(operacao,style='Card.TFrame'); botoes.pack(fill='x', pady=(14,0))
    ferramentas=ttk.Frame(frame);ferramentas.pack(fill='x',pady=(0,10))
    ttk.Label(ferramentas,text='Atividade em tempo real',font=('Segoe UI',12,'bold')).pack(side='left')
    seguir=tk.BooleanVar(value=True)
    ttk.Checkbutton(ferramentas,text='Acompanhar últimas linhas',variable=seguir).pack(side='right')
    logs = ScrolledText(frame,state='disabled',font=('Consolas',10),height=12,background='#122534',foreground='#e1eef5',insertbackground='white',borderwidth=0,padx=12,pady=12,wrap='none')
    logs.pack(fill='both',expand=True)
    rodape=ttk.Frame(frame,padding=(0,12,0,0));rodape.pack(fill='x')
    ttk.Label(rodape,text='ARMAZENAMENTO',font=('Segoe UI',8,'bold')).pack(anchor='w')
    ttk.Label(rodape,text=str(dados),style='Muted.TLabel',wraplength=1020).pack(anchor='w',pady=(3,8))
    controles={}
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
        config = obter_configuracao(); janela = tk.Toplevel(raiz); janela.title('Configurar instalação'); aplicar(janela); janela.transient(raiz); janela.grab_set()
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
    for texto,acao in [('Iniciar',iniciar),('Parar',parar),('Reiniciar',lambda:parar(True))]:
        botao=ttk.Button(botoes,text=texto,command=acao);botao.pack(side='left',padx=(0,8));controles[texto]=botao
    for texto,acao in [('Abrir painel',painel),('Configurações',configurar),('Pasta de dados',lambda:os.startfile(dados))]:
        botao=ttk.Button(botoes,text=texto,command=acao,style='Secondary.TButton');botao.pack(side='left',padx=(0,8));controles[texto]=botao
    acoes=queue.Queue(); encerrar=False; tray=None; tray_ready=threading.Event(); tray_falhou=False
    def mostrar():
        raiz.deiconify();raiz.state('normal');raiz.lift()
    def minimizar():
        if tray is not None and tray_ready.is_set():raiz.withdraw()
        else:raiz.iconify()
    def sair():
        nonlocal encerrar
        if ativo() and not messagebox.askyesno('Encerrar aplicação','Parar o bot/API e sair?'):return
        encerrar=True
        if ativo():parar()
    def atualizar():
        nonlocal posicao, parando, reiniciar, encerrar
        if controle.WaitForSingleObject(mostrar_evento,0)==0:
            controle.ResetEvent(mostrar_evento);mostrar()
        if controle.WaitForSingleObject(sair_evento,0)==0:
            controle.ResetEvent(sair_evento);encerrar=True
            print('Parada do gerenciador solicitada.',file=sys.stderr)
            if ativo() and not parando:parar()
        while not acoes.empty():acoes.get_nowait()()
        if encerrar and not ativo() and not (processo and processo.poll() is None):
            print('Processo encerrado. Fechando interface e ícone.',file=sys.stderr)
            if tray:tray.stop()
            raiz.destroy();return
        arquivo = dados / 'logs' / 'aplicacao.log'
        if arquivo.exists():
            if arquivo.stat().st_size < posicao: posicao=0
            with arquivo.open('rb') as f:
                f.seek(posicao); trecho=f.read(65536); posicao=f.tell()
            if trecho:
                logs.configure(state='normal'); logs.insert('end',trecho.decode('utf-8',errors='replace'))
                if int(logs.index('end-1c').split('.')[0]) > 2500: logs.delete('1.0','500.0')

                if seguir.get():logs.see('end')
                logs.configure(state='disabled')
        rodando = ativo()
        if parando and not rodando:
            parando=False
            if reiniciar: reiniciar=False; iniciar()
        elif parando and time.monotonic()>prazo:
            parando=False; reiniciar=False
            messagebox.showwarning('Parada demorada','A parada ainda não terminou. Confira os logs; nenhuma segunda instância foi iniciada.')
        iniciando=bool(processo and processo.poll() is None and not rodando)
        if not parando:status.set('Em execução' if rodando else 'Iniciando…' if iniciando else 'Parada')
        badge.configure(foreground='#147c58' if rodando and not parando else '#087caf' if iniciando or parando else '#667987')
        status_ajuda.set('Bandeja indisponível neste ambiente. Use a janela e o botão Sair.' if tray_falhou else 'Aguarde a conclusão das operações em andamento.' if parando else 'Processo ativo. Confira Oracle e Telegram no painel.' if rodando else 'Clique em Iniciar para disponibilizar o painel e o bot.')
        for nome in ('Iniciar','Parar','Reiniciar','Configurações','Abrir painel'):
            habilitado={'Iniciar':not rodando and not iniciando,'Parar':rodando,'Reiniciar':rodando,'Configurações':not rodando and not iniciando,'Abrir painel':rodando}[nome] and not parando
            controles[nome].configure(state='normal' if habilitado else 'disabled')
        raiz.after(600,atualizar)
    try:
        import pystray
        from PIL import Image
        from desktop.theme import assets
        def agendar(acao):return lambda icon,item:acoes.put(acao)
        tray=pystray.Icon('myBotWinthor',Image.open(assets()/'rb_app_icon.ico'),'myBotWinthor',pystray.Menu(
            pystray.MenuItem('Abrir gerenciador',agendar(mostrar),default=True),
            pystray.MenuItem('Abrir painel',agendar(painel)),
            pystray.MenuItem('Iniciar',agendar(iniciar)),
            pystray.MenuItem('Reiniciar',agendar(lambda:parar(True))),
            pystray.MenuItem('Parar',agendar(parar)),
            pystray.MenuItem('Sair e parar a aplicação',agendar(sair))))
        candidato=tray
        def falha_tray():
            nonlocal tray,tray_falhou
            tray=None;tray_falhou=True;mostrar()
        def loop_tray():
            try:
                def pronto(icon):
                    icon.visible=True;tray_ready.set()
                candidato.run(setup=pronto)
            except Exception:
                import traceback;traceback.print_exc(file=sys.stderr);acoes.put(falha_tray)
        threading.Thread(target=loop_tray,daemon=True,name='icone-bandeja').start()
    except Exception as erro:
        tray=None;messagebox.showwarning('Bandeja indisponível','A janela será mantida visível: '+str(erro))
    def minimizar_evento(event):
        if event.widget is raiz and raiz.state()=='iconic' and tray:raiz.after(50,minimizar)
    ttk.Button(rodape,text='Minimizar para a bandeja',command=minimizar,style='Secondary.TButton').pack(side='right',padx=(8,0))
    ttk.Button(rodape,text='Sair',command=sair,style='Danger.TButton').pack(side='right')
    def mudar_inicio():
        from desktop.windows import inicializacao
        try:inicializacao(sys.executable,inicio.get())
        except OSError as erro:inicio.set(not inicio.get());messagebox.showerror('Inicialização',str(erro))
    base=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
    info=json.loads((base/'desktop.json').read_text(encoding='utf-8')) if (base/'desktop.json').exists() else {}
    inicio=tk.BooleanVar(value=info.get('autostart',False))
    if getattr(sys,'frozen',False) and info.get('install_root'):
        ttk.Checkbutton(rodape,text='Iniciar com o Windows na bandeja',variable=inicio,command=mudar_inicio).pack(side='left')
    raiz.bind('<Unmap>',minimizar_evento);raiz.protocol('WM_DELETE_WINDOW',minimizar)
    if '--autostart' in sys.argv:raiz.after(100,iniciar);raiz.after(200,minimizar)
    atualizar()
    try:raiz.mainloop()
    finally:
        if tray:tray.stop()
        for handle in (mostrar_evento,sair_evento,guard):controle.CloseHandle(handle)


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
