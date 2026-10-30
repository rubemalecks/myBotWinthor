"""Identidade visual compartilhada pelas janelas Windows."""
from pathlib import Path
from PIL import Image, ImageTk
BG='#f2f6fa'; INK='#263746'; BLUE='#087caf'; CARD='#ffffff'

def assets():
    return Path(__file__).resolve().parents[1]/'assets'

def aplicar(root):
    from tkinter import ttk
    root.configure(background=BG)
    root.iconbitmap(str(assets()/'rb_app_icon.ico'))
    style=ttk.Style(root);style.theme_use('clam')
    style.configure('.',font=('Segoe UI',10),background=BG,foreground=INK)
    style.configure('TFrame',background=BG);style.configure('TLabel',background=BG)
    style.configure('TButton',padding=(12,8),background=BLUE,foreground='white',borderwidth=0)
    style.map('TButton',background=[('active','#09688e'),('disabled','#ced9e0')])
    style.configure('TCheckbutton',background=BG,foreground=INK)
    style.configure('TEntry',fieldbackground=CARD,padding=6)
    return style

def cabecalho(parent,subtitulo):
    from tkinter import ttk
    image=Image.open(assets()/'Logo geométrico myBotWinthor com monograma RB.png')
    image.thumbnail((460,154))
    foto=ImageTk.PhotoImage(image)
    label=ttk.Label(parent,image=foto,background='white');label.image=foto;label.pack(anchor='w',pady=(0,12))
    ttk.Label(parent,text=subtitulo,font=('Segoe UI',16,'bold')).pack(anchor='w',pady=(0,12))
