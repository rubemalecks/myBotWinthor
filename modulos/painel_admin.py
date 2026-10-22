import asyncio
import hmac
import ipaddress
import logging
import os
import re
import secrets
import socket
import time
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from telegram import Bot
from telegram.error import InvalidToken, NetworkError, TelegramError

from modulos.database import ErroAcessoWinthor, testar_conexao_oracle, listar_opcoes_acesso
from modulos.escopo import CHAVES_ESCOPO
from modulos.mensagens import listar_modelos, salvar_modelos, previa_modelo, LIMITE_MODELO
from modulos.permissoes import (
    CHAVES_CONFIGURACAO,
    CHAVES_SECRETAS,
    DIRETORIO_DADOS,
    PERMISSOES,
    alterar_senha_admin,
    atualizar_perfil,
    eh_admin,
    listar_perfis,
    registrar_usuario,
    gerenciar_perfil_teste,
    listar_perfis_teste,
    gerenciar_modelo_perfil,
    garantir_administrador, OPCOES_CONSULTA,
    revogar,
    obter_configuracao,
    obter_ou_criar_configuracao,
    obter_versao_sessao_admin,
    salvar_configuracoes,
    verificar_senha_admin,
)
from modulos.servico_windows import obter_status_servico, solicitar_acao_servico

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
logger = logging.getLogger(__name__)

ADMIN_PASSWORD = os.getenv("WEB_ADMIN_PASSWORD") or "admin"
SESSION_SECRET = obter_ou_criar_configuracao(
    "WEB_SESSION_SECRET",
    os.getenv("WEB_SESSION_SECRET", "").strip() or secrets.token_urlsafe(48),
)

app = FastAPI(title="Painel de permissões do bot", docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="strict",
    https_only=obter_configuracao()["WEB_HTTPS_ONLY"].strip().lower() == "true",
    max_age=8 * 60 * 60,
)

_tentativas_login = {}
PAGINA = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Permissões do bot</title>
  <link rel="icon" type="image/png" href="/assets/icone.png">
  <style>
    :root { font-family: system-ui, sans-serif; color: #17212b; background: #f3f6fa; }
    body { margin: 0 auto; max-width: 1050px; padding: 24px; }
    h1 { font-size: 1.7rem; }
    .card { background: white; border: 1px solid #dce3eb; border-radius: 10px;
      padding: 18px; margin: 14px 0; box-shadow: 0 2px 8px #17212b0a; }
    .row { display: flex; flex-wrap: wrap; gap: 12px 20px; margin: 12px 0; }
    label { display: flex; align-items: center; gap: 7px; }
    input[type=text], input[type=password] { box-sizing: border-box; width: 100%;
      padding: 10px; margin: 6px 0 14px; border: 1px solid #aab7c4; border-radius: 6px; }
    button { padding: 9px 14px; border: 0; border-radius: 6px; color: white;
      background: #1769aa; cursor: pointer; }
    button.secondary { background: #526273; }
    .muted { color: #526273; }
    .pending { color: #915d00; font-weight: 700; }
    .approved { color: #16733b; font-weight: 700; }
    #status { min-height: 1.5em; white-space: pre-line; }
    [hidden] { display: none !important; }
    :root { color-scheme: dark; --bg:#0c1422; --surface:#152033; --field:#0f192a; --text:#e6edf7; --muted:#a5b4ca; --border:#30405a; --accent:#75baff; color:var(--text); background:var(--bg); }
    :root[data-theme="light"] { color-scheme:light; --bg:#f1f5f9; --surface:#fff; --field:#f8fafc; --text:#17283f; --muted:#52647b; --border:#c8d3e0; --accent:#1765ad; }
    * { box-sizing:border-box; }
    body { max-width:1120px; padding:32px 24px; line-height:1.55; }
    header { display:flex; align-items:center; gap:12px; justify-content:space-between; }
    h1 { margin:0; letter-spacing:-.03em; } h2 { font-size:1.2rem; margin-top:0; }
    h3 { color:var(--accent); margin-top:28px; padding-top:18px; border-top:1px solid var(--border); }
    .card,dialog { background:var(--surface); color:var(--text); border:1px solid var(--border); border-radius:16px; padding:26px; box-shadow:0 8px 30px #0002; }
    #login { max-width:460px; margin:48px auto; }
    input:not([type=checkbox]) { width:100%; padding:12px; margin:7px 0 18px; border:1px solid var(--border); border-radius:8px; background:var(--field); color:var(--text); font:inherit; }
    input[type=checkbox] { accent-color:#2479cb; width:18px; height:18px; }
    button { font:inherit; font-weight:600; padding:11px 18px; border-radius:8px; }
    button.secondary { background:var(--field); color:var(--text); border:1px solid var(--border); }
    button:hover { filter:brightness(1.15); } button:disabled { opacity:.6; cursor:wait; }
    :focus-visible { outline:3px solid var(--accent); outline-offset:3px; }
    .muted { color:var(--muted); } .approved { color:#48b985; } .pending { color:#dcaa45; }
    :root[data-theme="light"] .approved { color:#16733b; }
    :root[data-theme="light"] .pending { color:#855400; }
    .row { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:16px; margin:20px 0; }
    .form-actions { margin-top:24px; }
    #status { position:sticky; top:12px; z-index:2; }
    #status:empty { display:none; }
    #status:not(:empty) { background:var(--surface); padding:16px; border:1px solid var(--border); border-left:4px solid var(--accent); border-radius:10px; box-shadow:0 5px 20px #0002; }
    @media(max-width:600px) { body { padding:20px 14px; } .card { padding:18px; } header { align-items:flex-start; } h1 { font-size:1.3rem; } }
    body { padding:18px 22px; }
    h1 { font-size:1.45rem; } h2 { font-size:1.05rem; margin-bottom:10px; }
    p { margin:8px 0; }
    .card { padding:16px 18px; margin:12px 0; border-radius:12px; }
    button { padding:8px 12px; font-size:.88rem; }
    label { font-size:.85rem; }
    input:not([type=checkbox]),input[type=text],input[type=password] { padding:8px 10px; margin:4px 0 0; font-size:.9rem; }
    .fields-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px 16px; align-items:start; }
    .field { min-width:0; }
    .fields-grid > label { align-self:end; min-height:38px; }
    fieldset { min-width:0; padding:10px 0 14px; margin:10px 0 0; border:0; border-top:1px solid var(--border); }
    legend { color:var(--accent); font-weight:600; font-size:.95rem; padding-right:12px; }
    .form-actions { margin-top:4px; }
    .compact-help,.storage-details { font-size:.82rem; color:var(--muted); }
    summary { cursor:pointer; } .storage-details code { overflow-wrap:anywhere; }
    .security-details > summary { font-weight:600; }
    .security-details form { margin-top:14px; }
    #password-form button { justify-self:start; }
    .row { grid-template-columns:repeat(auto-fit,minmax(175px,1fr)); gap:9px 14px; margin:12px 0; }
    #users .card h2 { margin-bottom:2px; } #users .card p { font-size:.82rem; margin:4px 0; }
    #logout { display:block; margin:0 0 0 auto; }
    .users-title { margin:18px 0 8px; }
    .brand-header { gap:16px; flex-wrap:wrap; }
    .brand-logos { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
    .brand-logo { display:block; object-fit:contain; background:transparent; border:0;
      filter:invert(1) hue-rotate(180deg); mix-blend-mode:screen; }
    :root[data-theme="light"] .brand-logo { filter:none; mix-blend-mode:multiply; }
    .brand-header { padding:6px 0 14px; border-bottom:1px solid var(--border); }
    .brand-product { width:270px; height:90px; }
    .brand-company { width:240px; height:76px; object-fit:cover; object-position:center; }
    .brand-footer { display:flex; flex-direction:column; align-items:center; gap:0;
      margin-top:28px; padding:18px 0 12px; border-top:1px solid var(--border); }
    .brand-footer small { font-size:.72rem; letter-spacing:.06em; color:var(--muted); }
    .panel-heading { font-size:1rem; margin:10px 0 0; color:var(--muted); }
    @media(max-width:600px) { .brand-logos { flex:1; gap:8px; } .brand-product { width:210px; height:70px; } .brand-company { width:210px; height:66px; } }
    @media(max-width:420px) { .brand-product { width:180px; height:60px; } }
    .profile-item > summary { font-weight:600; padding:3px 0; }
    .profile-item[open] > summary { border-bottom:1px solid var(--border); padding-bottom:10px; margin-bottom:12px; }
    .permissions-toolbar { padding:10px 0; border-bottom:1px solid var(--border); font-weight:600; }
    button.danger { background:#a52b35; color:#fff; }
    .dashboard-nav { display:flex; gap:8px; align-items:center; margin:12px 0; border-bottom:1px solid var(--border); padding-bottom:10px; }
    .dashboard-nav [role=tab] { background:var(--field); color:var(--muted); border:1px solid var(--border); }
    .dashboard-nav [aria-selected=true] { background:#1769aa; color:white; border-color:#1769aa; }
    .dashboard-nav #logout { margin-left:auto; }
    .connection-status { display:flex; flex-wrap:wrap; gap:8px; margin:12px 0; }
    .connection-status button { border:1px solid transparent; padding:7px 12px; font-size:.8rem; }
    .connection-status .offline { background:#a52b35; color:#fff; border-color:#d85a65; }
    .connection-status .online { background:#167447; color:#fff; border-color:#38a973; }
    .connection-status button[aria-busy="true"] { opacity:.7; }
    @media(max-width:480px) { .dashboard-nav { flex-wrap:wrap; } .dashboard-nav button { padding:8px; } }
    @media(max-width:760px) { .fields-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
    @media(max-width:480px) { body { padding:14px 10px; } .card { padding:14px; } .fields-grid { grid-template-columns:1fr; } }
  </style>
  <style>
    body { min-height:100dvh; display:flex; flex-direction:column; }
    .brand-footer { margin-top:auto; }
    #dashboard { padding-bottom:28px; }
    body:has(#dashboard[hidden]) .panel-heading,
    body:has(#dashboard[hidden]) #panel-description { display:none; }
    body:has(#dashboard[hidden]) { background:radial-gradient(ellipse at 50% 35%, #2376c011, transparent 65%); }
    #login { width:100%; max-width:440px; margin:44px auto; padding:30px; border-radius:18px;
      box-shadow:0 16px 48px #0002; border-top:3px solid var(--accent); }
    #login h2 { font-size:1.45rem; margin:14px 0 6px; letter-spacing:-.025em; }
    .login-badge { width:42px; height:42px; display:grid; place-items:center;
      color:var(--accent); background:var(--field); border:1px solid var(--border); border-radius:12px; }
    .login-intro { font-size:.9rem; color:var(--muted); margin:0 0 24px; }
    #login-form { display:grid; gap:18px; }
    #login input { min-height:44px; margin:7px 0 0; }
    .password-control { position:relative; }
    #login .password-control input { padding-right:82px; }
    .password-toggle { position:absolute; right:7px; top:13px; background:transparent;
      color:var(--accent); font-size:.78rem; padding:6px 8px; }
    .oracle-private-control input:not([type=checkbox]) { padding-right:82px; }
    .oracle-private-control .password-toggle { top:10px; }
    #login-submit { width:100%; min-height:44px; margin-top:2px; font-size:.95rem; }
    #login-error { color:#ffb4b9; background:#a52b351a; border:1px solid #b8445055;
      padding:10px 12px; border-radius:8px; margin:0; font-size:.85rem; }
    :root[data-theme="light"] #login-error { color:#a52b35; }
    #login-error:empty { display:none; }
    .message-layout { display:grid; grid-template-columns:minmax(0, 1fr) minmax(0, 1fr); gap:18px; }
    .message-editor select,.message-editor textarea { width:100%; box-sizing:border-box; background:var(--field); color:var(--text); border:1px solid var(--border); border-radius:8px; padding:10px; font:inherit; margin:6px 0 12px; }
    .message-editor textarea { min-height:220px; resize:vertical; font-family:Consolas,monospace; line-height:1.5; }
    .message-variables { display:flex; flex-wrap:wrap; gap:6px; margin:8px 0 12px; }
    .message-variables button { font-size:.8rem; padding:5px 8px; }
    #message-preview { white-space:pre-wrap; overflow-wrap:anywhere; background:var(--field); border:1px solid var(--border); border-radius:10px; padding:16px; min-height:180px; line-height:1.6; }
    #message-error { color:var(--accent); }
    #message-error:empty { display:none; }
    @media(max-width:720px) { .message-layout { grid-template-columns:1fr; } }
    #caps-warning { display:block; font-size:.78rem; color:var(--muted); margin-top:6px; }
    body:has(#dashboard[hidden]) .brand-footer { padding-top:14px; }
    @media(max-width:480px) { #login { padding:24px 20px; margin:28px auto; } }
  </style>
</head>
<body>
  <header class="brand-header"><div class="brand-logos">
    <img class="brand-logo brand-product" src="/assets/logo-produto.png" alt="myBotWinthor" width="270" height="90" fetchpriority="high">
    </div>
    <button id="theme-toggle" type="button" class="secondary">Tema claro</button></header>
  <h1 class="panel-heading">Painel de administração</h1>
  <p id="panel-description" class="muted">A aprovação e cada permissão são configuradas individualmente.</p>
  <p id="status" role="status"></p>
  <section id="login" class="card">
    <div class="login-badge" aria-hidden="true"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/></svg></div>
    <h2>Acesse seu painel</h2>
    <p class="login-intro">Gerencie seu bot, a conexão Oracle e as permissões de acesso em um só lugar.</p>
    <form id="login-form" method="post" action="/api/login" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other">
      <div class="field"><label for="username">Usuário administrativo</label>
      <input id="username" name="username" type="text" required autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other"></div>
      <div class="field"><label for="password">Senha</label>
      <div class="password-control"><input id="password" name="password" type="password" required autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other">
        <button id="toggle-login-password" class="password-toggle" type="button" aria-controls="password" aria-pressed="false">Mostrar</button></div>
        <small id="caps-warning" hidden>Caps Lock está ativado.</small></div>
      <p id="login-error" role="alert"></p>
      <button id="login-submit" type="submit">Entrar no painel</button>
    </form>
  </section>
  <main id="dashboard" hidden>
    <div class="connection-status" role="group" aria-label="Estado das conexões" aria-live="polite">
      <button id="oracle-connection" type="button" class="offline" title="Clique para verificar a conexão">ORACLE: OFF</button>
      <button id="telegram-connection" type="button" class="offline" title="Clique para verificar a conexão">TELEGRAM: OFF</button>
    </div>
    <nav class="dashboard-nav" aria-label="Navegação do painel">
      <div role="tablist" aria-label="Áreas do painel">
        <button id="tab-settings" type="button" role="tab" aria-selected="true" aria-controls="panel-settings">Bot</button>
        <button id="tab-oracle" type="button" role="tab" aria-selected="false" aria-controls="panel-oracle" tabindex="-1">Servidor Oracle</button>
        <button id="tab-profiles" type="button" role="tab" aria-selected="false" aria-controls="panel-profiles" tabindex="-1">Perfis e permissões</button>
        <button id="tab-templates" type="button" role="tab" aria-selected="false" aria-controls="panel-templates" tabindex="-1">Modelos de perfil</button>
        <button id="tab-personalization" type="button" role="tab" aria-selected="false" aria-controls="panel-personalization" tabindex="-1">Personalização</button>
      </div>
    <button id="logout" class="secondary" type="button">Sair</button>
    </nav>
    <div id="panel-settings" role="tabpanel" aria-labelledby="tab-settings" tabindex="0">
    <section class="card">
      <h2>Configurações do bot</h2>
      <p class="muted compact-help">Deixe o token vazio para manter o valor salvo. Reinicie o bot após alterar o token.</p>
      <details class="storage-details"><summary>Armazenamento</summary><code id="data-directory"></code></details>
      <form id="settings-form" method="post" action="/api/settings" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other">
        <fieldset><legend>Telegram</legend><div class="fields-grid">
        <div class="field"><label for="telegram-admin-id">ID do administrador no Telegram</label>
        <input id="telegram-admin-id" type="password" inputmode="numeric" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other"></div>
        <div class="field"><label for="telegram-bot-token">Token do bot (opcional para substituir)</label>
        <input id="telegram-bot-token" type="password" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other"></div>
        <label><input id="clear-telegram-token" type="checkbox" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other"> Remover token salvo</label>

        </div></fieldset><div class="form-actions"><button type="submit">SALVAR E TESTAR BOT</button></div>
      </form>
    </section>
    <details class="card security-details">
      <summary>Alterar senha do painel</summary>
      <form id="password-form" class="fields-grid" method="post" action="/api/change-password" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other">
        <div class="field"><label for="current-password">Senha atual</label>
        <input id="current-password" name="current_password" type="password" required autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other"></div>
        <div class="field"><label for="new-password">Nova senha (12 a 128 caracteres)</label>
        <input id="new-password" name="new_password" type="password"
          minlength="12" maxlength="128" required autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other"></div>
        <div class="field"><label for="confirm-password">Confirme a nova senha</label>
        <input id="confirm-password" name="confirm_password" type="password"
          minlength="12" maxlength="128" required autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other"></div>
        <button type="submit">Alterar senha</button>
      </form>
    </details>
    <section id="windows-service" class="card" hidden>
      <h2>Inicialização automática do Windows</h2>
      <p id="windows-service-status" class="muted"></p>
      <p class="muted">
        O serviço roda como LocalSystem. Confirme o aviso administrativo na máquina
        que hospeda a API. A ativação inicia o bot no próximo boot; não inicie o
        serviço enquanto uma instância manual de bot.py estiver rodando.
      </p>
      <button id="enable-windows-service" type="button">Ativar inicialização automática</button>
      <button id="disable-windows-service" class="secondary" type="button" hidden>
        Desativar serviço
      </button>
      <button id="remove-windows-service" class="secondary" type="button" hidden>
        Remover serviço
      </button>
    </section>
    </div>
    <div id="panel-oracle" role="tabpanel" aria-labelledby="tab-oracle" tabindex="0" hidden>
      <section class="card"><h2>Servidor Oracle / WinThor</h2>
        <p class="muted compact-help">Deixe a senha vazia para manter o valor salvo. O teste valida a conexão e o acesso à consulta de produtos.</p>
      <form id="oracle-settings-form" method="post" action="/api/settings" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other">
<fieldset><legend>Oracle / WinThor</legend><div class="fields-grid">
        <div class="field"><label for="oracle-host">Host do Oracle</label>
        <div class="password-control oracle-private-control">
        <input id="oracle-host" type="text" placeholder="192.168.0.10" aria-describedby="oracle-host-help" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other">
        <button id="toggle-oracle-host" type="button" class="password-toggle" aria-controls="oracle-host" aria-label="Ocultar host do Oracle" aria-pressed="true">Ocultar</button></div>
        <small id="oracle-host-help" class="muted">IPv4 com pontos ou nome do servidor. Use ponto para avançar em grupos menores que 3 dígitos.</small></div>
        <div class="field"><label for="oracle-port">Porta do Oracle</label>
        <input id="oracle-port" type="number" min="1" max="65535" required autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other"></div>
        <div class="field"><label for="oracle-service">Service name</label>
        <input id="oracle-service" type="text" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other"></div>
        <div class="field"><label for="oracle-user">Usuário do Oracle</label>
        <div class="password-control oracle-private-control">
        <input id="oracle-user" type="text" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other">
        <button id="toggle-oracle-user" type="button" class="password-toggle" aria-controls="oracle-user" aria-label="Ocultar usuário do Oracle" aria-pressed="true">Ocultar</button></div></div>
        <div class="field"><label for="oracle-password">Senha do Oracle (opcional para substituir)</label>
        <input id="oracle-password" type="password" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other"></div>
        </div></fieldset><div class="form-actions"><button type="submit">SALVAR E TESTAR ORACLE</button></div>
      </form></section>
    </div>
    <div id="panel-profiles" role="tabpanel" aria-labelledby="tab-profiles" tabindex="0" hidden>
      <h2 class="users-title">Perfis e permissões de acesso</h2>
      <p class="muted compact-help">Os usuários aparecem após iniciar o bot no Telegram. Aprove cada perfil e selecione as permissões de acesso.</p>
      <section class="card">
        <h2>Cadastrar usuário</h2>
        <form id="create-user-form" class="fields-grid" autocomplete="off" data-1p-ignore="true" data-lpignore="true">
          <div class="field"><label for="new-user-id">ID do Telegram</label>
            <input id="new-user-id" type="text" inputmode="numeric" required aria-describedby="new-user-id-help" autocomplete="off" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other">
            <small id="new-user-id-help" class="muted">Use o ID numérico informado pelo comando /meuid.</small></div>
          <div class="field"><label for="new-user-name">Nome (opcional)</label>
            <input id="new-user-name" type="text" maxlength="128" autocomplete="off" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other"></div>
          <div class="form-actions"><button type="submit">Cadastrar perfil</button></div>
        </form>
        <p class="muted compact-help">Peça ao usuário que envie /meuid ao bot. Após cadastrar, permita o acesso e escolha as permissões abaixo.</p>
      </section>
      <button id="refresh-users" type="button" class="secondary">Atualizar usuários</button>
      <section class="card">
        <h2>Acesso do administrador</h2>
        <p class="muted compact-help">O administrador é pré-cadastrado e pode ter suas permissões do bot editadas como qualquer usuário. Seu acesso ao painel é independente. Perfis de teste antigos são independentes desse cadastro.</p>
        <button id="restore-admin" type="button" class="secondary">Encerrar perfil de teste</button>
        <p id="test-profile-status" role="status"></p>
      </section>
      <p id="users-status" class="muted" role="status"></p>
      <h2 class="users-title">Perfis cadastrados</h2>
      <p class="muted compact-help">Clique em um perfil para editar. Marque todas as permissões ou selecione cada uma e salve.</p>
      <div class="profiles-list"><div id="test-profiles"></div><div id="users"></div></div>
    </div>
    <div id="panel-templates" role="tabpanel" aria-labelledby="tab-templates" tabindex="0" hidden>
      <section class="card"><h2>Modelos de perfil</h2>
        <p class="muted">Salve predefinições e vincule aos usuários. Alterações no modelo atualizam automaticamente as permissões dos usuários vinculados, mantendo bloqueados os usuários sem acesso ao bot.</p>
        <form id="template-create-form" autocomplete="off">
          <label for="template-name">Nome do novo perfil</label>
          <input id="template-name" type="text" maxlength="128" required autocomplete="off" data-1p-ignore="true" data-lpignore="true" data-bwignore="true" data-form-type="other">
          <button type="submit">Cadastrar modelo</button>
        </form>
      </section><div id="profile-templates"></div>
    </div>
    <div id="panel-personalization" role="tabpanel" aria-labelledby="tab-personalization" tabindex="0" hidden>
      <section class="card">
        <h2>Mensagens do bot</h2>
        <p class="muted compact-help">Personalize o padrão de retorno para seus clientes. Consultas por código, foto e nome usam os mesmos blocos de produto. Custos, lucro e preço programado continuam dependendo das permissões do usuário.</p>
        <div class="message-layout">
          <form id="message-form" class="message-editor" autocomplete="off">
            <label for="message-template">Tipo de mensagem</label>
            <select id="message-template" required></select>
            <label for="message-content">Texto da mensagem</label>
            <textarea id="message-content" rows="9" maxlength="2500" required spellcheck="false" aria-describedby="message-hint message-counter"></textarea>
            <small id="message-counter" class="muted"></small>
            <p id="message-hint" class="muted compact-help">Clique em uma variável para inseri-la no texto. Mantenha as chaves, como {descricao}. Quebras de linha e emojis são permitidos.</p>
            <div id="message-variables" class="message-variables" role="group" aria-label="Variáveis disponíveis"></div>
            <p id="message-error" role="alert"></p>
            <div class="form-actions"><button id="message-save" type="submit">Salvar mensagem</button>
              <button id="message-reset" type="button" class="secondary">Restaurar padrão</button></div>
            <small class="muted">O padrão restaurado só será aplicado depois de salvar. Alterações valem nas próximas consultas, sem reiniciar.</small>
          </form>
          <div><h3>Prévia deste bloco</h3>
            <p class="muted compact-help">Dados fictícios para ilustrar o texto. O resultado completo combina os blocos autorizados para cada usuário.</p>
            <div id="message-preview" role="status" aria-live="polite"></div>
          </div>
        </div>
      </section>
    </div>
  </main>
  <footer class="brand-footer">
    <small>Desenvolvido por</small>
    <img class="brand-logo brand-company" src="/assets/logo-empresa.png" alt="RBTech Soluções" width="240" height="76" loading="lazy">
  </footer>
  <script>
    const removeSpaces = value => value.replace(/\\s/g, "");
    for (const id of ["new-user-id", "telegram-admin-id", "oracle-host", "oracle-port", "oracle-service", "oracle-user"]) {
      const field = document.getElementById(id);
      field.addEventListener("input", () => {
        const position = field.selectionStart;
        const before = field.value;
        field.value = removeSpaces(before);
        if (position !== null && ["text", "password"].includes(field.type)) {
          const removed = before.slice(0, position).length - removeSpaces(before.slice(0, position)).length;
          field.setSelectionRange(position - removed, position - removed);
        }
      });
    }
    const hostField = document.getElementById("oracle-host");
    function definirVisibilidadeOracle(id, visible) {
      const field = document.getElementById(id);
      const button = document.getElementById(`toggle-${id}`);
      field.type = visible ? "text" : "password";
      button.textContent = visible ? "Ocultar" : "Mostrar";
      button.setAttribute("aria-pressed", String(visible));
      button.setAttribute("aria-label", `${visible ? "Ocultar" : "Mostrar"} ${id === "oracle-host" ? "host" : "usuário"} do Oracle`);
    }
    function ocultarDadosOracle() {
      for (const id of ["oracle-host", "oracle-user"]) definirVisibilidadeOracle(id, false);
    }
    for (const id of ["oracle-host", "oracle-user"]) {
      document.getElementById(`toggle-${id}`).addEventListener("click", () => {
        definirVisibilidadeOracle(id, document.getElementById(id).type === "password");
      });
    }
    hostField.addEventListener("input", event => {
      const value = hostField.value;
      if (event.inputType !== "insertText" || !/^[0-9]$/.test(event.data || "") ||
          hostField.selectionStart !== value.length || !/^[0-9.]+$/.test(value)) return;
      const parts = value.split(".");
      if (parts.length < 4 && parts[parts.length - 1].length === 3 &&
          parts.every(part => Number(part) <= 255)) hostField.value += ".";
    });
    const tabs = [...document.querySelectorAll('[role="tab"]')];
    function selectTab(tab) {
      for (const item of tabs) {
        const selected = item === tab;
        item.setAttribute("aria-selected", String(selected));
        item.tabIndex = selected ? 0 : -1;
        document.getElementById(item.getAttribute("aria-controls")).hidden = !selected;
      }
      if (tab.id === "tab-personalization") {
        carregarPersonalizacao().catch(error => { notificarTemporariamente(error.message, 10000); });
      }
    }
    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => selectTab(tab));
      tab.addEventListener("keydown", event => {
        let next;
        if (event.key === "ArrowRight") next = tabs[(index + 1) % tabs.length];
        if (event.key === "ArrowLeft") next = tabs[(index + tabs.length - 1) % tabs.length];
        if (event.key === "Home") next = tabs[0];
        if (event.key === "End") next = tabs[tabs.length - 1];
        if (next) { event.preventDefault(); selectTab(next); next.focus(); }
      });
    });
    const themeToggle = document.querySelector("#theme-toggle");
    function setTheme(theme) {
      document.documentElement.dataset.theme = theme;
      themeToggle.textContent = theme === "dark" ? "Tema claro" : "Tema escuro";
      themeToggle.setAttribute("aria-pressed", String(theme === "light"));
      try { localStorage.setItem("panel-theme", theme); } catch (_) {}
    }
    let savedTheme; try { savedTheme = localStorage.getItem("panel-theme"); } catch (_) {}
    setTheme(savedTheme === "light" ? "light" : "dark");
    themeToggle.addEventListener("click", () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));
    const status = document.querySelector("#status");
    const notificationTimers = new WeakMap();
    function notificarTemporariamente(message, duration = 2500, target = status) {
      window.clearTimeout(notificationTimers.get(target));
      notificationTimers.delete(target);
      target.textContent = message;
      // Uma operação em andamento usa duração zero, até chegar seu resultado.
      if (!message || duration <= 0) return;
      const timer = window.setTimeout(() => {
        if (notificationTimers.get(target) !== timer) return;
        target.textContent = "";
        notificationTimers.delete(target);
      }, duration);
      notificationTimers.set(target, timer);
    }
    const login = document.querySelector("#login");
    const dashboard = document.querySelector("#dashboard");
    const usersContainer = document.querySelector("#users");
    let csrf = "";
    let configuracaoAtual = {};
    const permissions = [
      ["consulta_preco", "Consultar preços"],
      ["ver_preco_programado", "Ver preço programado"],
      ["perguntar_filial", "Perguntar filial na consulta"],
      ["perguntar_regiao", "Perguntar região/tabela de preço"],
      ["buscar_por_foto", "Buscar por foto"],
      ["buscar_codprod", "Buscar por CODPROD"],
      ["buscar_codauxiliar", "Buscar por CODAUXILIAR"],
      ["buscar_codauxiliar2", "Buscar por CODAUXILIAR2"],
      ["ver_margem_produto", "Ver margem por produto"],
      ["ver_margem_departamento", "Ver margem por departamento"],
      ["ver_custos", "Ver custos detalhados"]
    ];
    let modelosPerfil = [];
    let opcoesEscopo = {};
    let erroOpcoesEscopo = "";

    async function request(url, options = {}) {
      const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
      if (options.method && options.method !== "GET") headers["X-CSRF-Token"] = csrf;
      const response = await fetch(url, { ...options, headers, credentials: "same-origin" });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || "Falha na solicitação.");
      }
      return response.status === 204 ? null : response.json();
    }

    const messageSelect = document.getElementById("message-template");
    const messageContent = document.getElementById("message-content");
    const messagePreview = document.getElementById("message-preview");
    const messageError = document.getElementById("message-error");
    let messageTemplates = [];
    const messageDrafts = new Map();
    let previewTimer;
    let previewVersion = 0;
    function atualizarPreviaMensagem() {
      window.clearTimeout(previewTimer);
      const version = ++previewVersion;
      const id = messageSelect.value;
      const texto = messageContent.value;
      messageError.textContent = "";
      document.getElementById("message-counter").textContent = `${texto.length} / ${messageContent.maxLength} caracteres`;
      messagePreview.textContent = "Atualizando prévia…";
      previewTimer = window.setTimeout(async () => {
        try {
          const result = await request("/api/message-templates/preview", {method:"POST", body:JSON.stringify({id, texto})});
          if (version !== previewVersion) return;
          messagePreview.textContent = result.texto;
        } catch (error) {
          if (version !== previewVersion) return;
          messagePreview.textContent = "Corrija o texto para visualizar a mensagem.";
          messageError.textContent = error.message;
        }
      }, 250);
    }
    function mostrarEditorMensagem() {
      const model = messageTemplates.find(item => item.id === messageSelect.value);
      if (!model) return;
      messageContent.value = messageDrafts.has(model.id) ? messageDrafts.get(model.id) : model.texto;
      const variables = document.getElementById("message-variables"); variables.replaceChildren();
      for (const [name, example] of Object.entries(model.exemplo)) {
        const button = document.createElement("button"); button.type = "button"; button.className = "secondary";
        button.textContent = `{${name}}`; button.title = `Exemplo: ${example}`;
        button.addEventListener("click", () => {
          const variable = `{${name}}`;
          if (messageContent.value.length - (messageContent.selectionEnd - messageContent.selectionStart) + variable.length > messageContent.maxLength) return;
          messageContent.setRangeText(variable, messageContent.selectionStart, messageContent.selectionEnd, "end");
          messageContent.focus(); messageContent.dispatchEvent(new Event("input"));
        });
        variables.append(button);
      }
      if (!Object.keys(model.exemplo).length) variables.textContent = "Este aviso aceita somente texto livre.";
      atualizarPreviaMensagem();
    }
    async function carregarPersonalizacao() {
      const result = await request("/api/message-templates");
      const selected = messageSelect.value;
      messageTemplates = result.templates;
      messageContent.maxLength = result.limite;
      messageSelect.replaceChildren();
      const groups = new Map();
      for (const model of messageTemplates) {
        if (!groups.has(model.grupo)) {
          const group = document.createElement("optgroup"); group.label = model.grupo;
          groups.set(model.grupo, group); messageSelect.append(group);
        }
        const option = document.createElement("option"); option.value = model.id;
        option.textContent = model.titulo + (model.personalizado ? " · Personalizado" : "");
        groups.get(model.grupo).append(option);
      }
      if (messageTemplates.some(item => item.id === selected)) messageSelect.value = selected;
      mostrarEditorMensagem();
    }
    messageSelect.addEventListener("change", mostrarEditorMensagem);
    messageContent.addEventListener("input", () => {
      messageDrafts.set(messageSelect.value, messageContent.value); atualizarPreviaMensagem();
    });
    document.getElementById("message-reset").addEventListener("click", () => {
      const model = messageTemplates.find(item => item.id === messageSelect.value);
      if (!model) return;
      messageContent.value = model.padrao;
      messageContent.dispatchEvent(new Event("input"));
    });
    document.getElementById("message-form").addEventListener("submit", async event => {
      event.preventDefault();
      const model = messageTemplates.find(item => item.id === messageSelect.value);
      if (!model) return;
      const fields = [...event.currentTarget.querySelectorAll("input,select,textarea,button")];
      fields.forEach(field => { field.disabled = true; });
      try {
        const texto = messageContent.value === model.padrao ? null : messageContent.value;
        await request("/api/message-templates", {method:"PUT", body:JSON.stringify({templates:{[model.id]:texto}})});
        messageDrafts.delete(model.id);
        await carregarPersonalizacao();
        notificarTemporariamente("Mensagem salva. O bot já usará o novo padrão.");
      } catch (error) { notificarTemporariamente(error.message, 10000); }
      finally { fields.forEach(field => { field.disabled = false; }); }
    });

    let checkingConnections = false;
    function renderConnections(checks) {
      for (const [key, check] of Object.entries(checks)) {
        const button = document.getElementById(`${key}-connection`);
        if (!button) continue;
        const online = check.status === "connected";
        button.textContent = `${key.toUpperCase()}: ${online ? "OK" : "OFF"}`;
        button.className = online ? "online" : "offline";
        button.title = check.message || "Sem resposta";
      }
    }
    async function checkConnections() {
      if (checkingConnections || dashboard.hidden) return;
      checkingConnections = true;
      const buttons = document.querySelectorAll('.connection-status button');
      buttons.forEach(button => { button.disabled = true; button.setAttribute("aria-busy", "true"); });
      try {
        const result = await request("/api/connections");
        renderConnections(result.checks);
      } catch (_) {
        renderConnections({oracle: {status: "error", message: "Não foi possível verificar a conexão"},
                           telegram: {status: "error", message: "Não foi possível verificar a conexão"}});
      } finally {
        checkingConnections = false;
        buttons.forEach(button => { button.disabled = false; button.setAttribute("aria-busy", "false"); });
      }
    }
    document.querySelectorAll('.connection-status button').forEach(button => button.addEventListener("click", checkConnections));
    window.setInterval(() => { if (!document.hidden) checkConnections(); }, 60000);

    function criarCampo(container, texto, checked, disabled = false) {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = Boolean(checked);
      input.disabled = disabled;
      label.append(input, document.createTextNode(texto));
      container.append(label);
      return input;
    }

    function vincularAcessoPermissoes(approved, checks) {
      approved.addEventListener("change", () => {
        if (!approved.checked) {
          for (const input of Object.values(checks)) input.checked = false;
          approved.dispatchEvent(new Event("accesschange"));
        }
      });
      for (const input of Object.values(checks)) {
        input.addEventListener("change", () => {
          if (input.checked) approved.checked = true;
        });
      }
    }

    function adicionarSeletorModelo(container, approved, checks, vinculoAtual = null) {
      let vinculo = vinculoAtual;
      let aplicando = false;
      const group = document.createElement("div"); group.className = "row";
      const label = document.createElement("label"); label.textContent = "Predefinição: ";
      const select = document.createElement("select"); select.setAttribute("aria-label", "Modelo de permissões");
      select.style.cssText = "background:var(--field);color:var(--text);border:1px solid var(--border);padding:8px;border-radius:8px;max-width:100%";
      const empty = document.createElement("option"); empty.value = ""; empty.textContent = "Sem vínculo (personalizado)"; select.append(empty);
      for (const modelo of modelosPerfil) {
        const option = document.createElement("option"); option.value = modelo.id; option.textContent = modelo.nome; select.append(option);
      }
      select.value = vinculo || "";
      for (const input of Object.values(checks)) input.addEventListener("change", () => {
        if (!aplicando) {
          if (vinculo) notificarTemporariamente("Permissões personalizadas: o vínculo será removido ao salvar. Reaplique o modelo para manter o vínculo.");
          vinculo = null; select.value = "";
        }
      });
      const apply = document.createElement("button"); apply.type = "button"; apply.className = "secondary"; apply.textContent = "Aplicar modelo"; apply.disabled = true;
      select.addEventListener("change", () => { apply.disabled = false; });
      apply.addEventListener("click", () => {
        const modelo = modelosPerfil.find(item => item.id === select.value);
        if (!modelo) {
          vinculo = null;
          notificarTemporariamente("Vínculo removido do formulário. Salve o perfil para manter permissões personalizadas.");
          return;
        }
        aplicando = true;
        for (const [key, input] of Object.entries(checks)) {
          input.checked = Boolean(modelo.permissoes[key]);
          input.dispatchEvent(new Event("change", {bubbles:true}));
        }
        if (Object.values(checks).some(input => input.checked)) approved.checked = true;
        aplicando = false; vinculo = modelo.id;
        notificarTemporariamente(`Modelo ${modelo.nome} vinculado ao formulário. Salve para confirmar e receber atualizações futuras do modelo.`);
      });
      label.append(select); group.append(label, apply); container.append(group);
      const obter = () => vinculo;
      obter.desvincular = () => { vinculo = null; select.value = ""; };
      obter.escopoAplicado = null;
      apply.addEventListener("click", () => {
        const modelo = modelosPerfil.find(item => item.id === select.value);
        if (modelo && obter.escopoAplicado) obter.escopoAplicado(modelo);
      });
      return obter;
    }

    function editarEscopo(container, perfil, aoAlterar = () => {}) {
      const group = document.createElement("fieldset");
      const legend = document.createElement("legend"); legend.textContent = "Filiais e tabelas autorizadas"; group.append(legend);
      const fields = {};
      for (const [key, title] of [["filiais_permitidas", "filiais"], ["tabelas_permitidas", "tabelas de preço"]]) {
        const all = criarCampo(group, `Todas as ${title}`, perfil[key] == null);
        const list = document.createElement("div"); list.className = "row";
        list.style.cssText = "max-height:220px;overflow:auto;padding:4px";
        group.append(list);
        const checks = new Map();
        function desenhar(valores) {
          const itens = new Map((opcoesEscopo[key] || []).map(item => [String(item.codigo), item]));
          for (const codigo of valores || []) {
            const normalizado = String(codigo);
            if (!itens.has(normalizado)) itens.set(normalizado, {codigo:normalizado, nome:"Código salvo, ausente na lista atual"});
          }
          list.replaceChildren(); checks.clear();
          for (const [codigo, item] of itens) {
            const texto = key === "filiais_permitidas" ? `${codigo} — ${item.nome}` : `${codigo} — ${item.nome}${item.ativa === false ? " (inativa)" : ""}`;
            const input = criarCampo(list, texto, all.checked || (valores || []).map(String).includes(codigo));
            checks.set(codigo, input);
            input.addEventListener("change", () => { all.checked = false; aoAlterar(); });
          }
          if (!itens.size) {
            const vazio = document.createElement("small"); vazio.className = "muted";
            vazio.textContent = erroOpcoesEscopo || "Nenhuma opção cadastrada no Oracle."; list.append(vazio);
          }
        }
        desenhar(perfil[key]);
        fields[key] = {all, checks, desenhar};
        all.addEventListener("change", () => { for (const input of checks.values()) input.checked = all.checked; aoAlterar(); });
      }
      const note = document.createElement("small"); note.className = "muted";
      note.textContent = "Marque as filiais e regiões permitidas. Nenhuma marcada bloqueia a categoria; 'Todas' inclui também opções futuras. " + (erroOpcoesEscopo ? "Não foi possível atualizar a lista do Oracle; seleções salvas foram preservadas. Use Atualizar usuários para tentar novamente." : "");
      group.append(note); container.append(group);
      const ler = () => Object.fromEntries(Object.entries(fields).map(([key, {all, checks}]) => [key, all.checked ? null : [...checks].filter(([, input]) => input.checked).map(([codigo]) => codigo)]));
      ler.aplicar = modelo => { for (const [key, field] of Object.entries(fields)) { field.all.checked = modelo[key] == null; field.desenhar(modelo[key]); } };
      return ler;
    }

    async function carregarModelosPerfil() {
      try { opcoesEscopo = await request("/api/access-options"); erroOpcoesEscopo = ""; }
      catch (_) { opcoesEscopo = {}; erroOpcoesEscopo = "Lista Oracle indisponível."; }
      modelosPerfil = await request("/api/profile-templates");
      const container = document.querySelector("#profile-templates"); container.replaceChildren();
      for (const modelo of modelosPerfil) {
        const card = document.createElement("details"); card.className = "card profile-item";
        const heading = document.createElement("summary"); heading.textContent = modelo.nome;
        const label = document.createElement("label"); label.textContent = "Nome do modelo";
        const name = document.createElement("input"); name.type = "text"; name.value = modelo.nome; name.maxLength = 128; name.autocomplete = "off"; label.append(name);
        const fields = document.createElement("div"); fields.className = "row";
        const checks = {};
        for (const [key, text] of permissions) checks[key] = criarCampo(fields, text, modelo.permissoes[key]);
        card.append(heading, label); adicionarMarcarTodos(card, checks); card.append(fields);
        const lerEscopo = editarEscopo(card, modelo);
        const save = document.createElement("button"); save.type = "button"; save.textContent = "Salvar modelo";
        save.addEventListener("click", async () => {
          save.disabled = true;
          try {
            await request(`/api/profile-templates/${modelo.id}`, {method:"PUT", body:JSON.stringify({...lerEscopo(), nome:name.value, permissoes:Object.fromEntries(Object.entries(checks).map(([key, input]) => [key, input.checked]))})});
            await carregarModelosPerfil(); notificarTemporariamente("Modelo salvo. Permissões dos usuários vinculados atualizadas automaticamente.");
          } catch (error) { notificarTemporariamente(error.message, 10000); } finally { save.disabled = false; }
        });
        const remove = document.createElement("button"); remove.type = "button"; remove.className = "danger"; remove.textContent = "Remover modelo";
        remove.addEventListener("click", async () => {
          if (!window.confirm(`Remover o modelo ${modelo.nome}? Usuários existentes serão preservados.`)) return;
          try { await request(`/api/profile-templates/${modelo.id}`, {method:"DELETE"}); await carregarModelosPerfil(); }
          catch (error) { notificarTemporariamente(error.message, 10000); }
        });
        const actions = document.createElement("div"); actions.className = "row"; actions.append(save, remove); card.append(actions); container.append(card);
      }
    }
    document.querySelector("#tab-templates").addEventListener("click", () => carregarModelosPerfil().catch(error => { notificarTemporariamente(error.message, 10000); }));
    document.querySelector("#template-create-form").addEventListener("submit", async event => {
      event.preventDefault(); const form = event.currentTarget; const button = form.querySelector("button"); button.disabled = true;
      try {
        await request("/api/profile-templates", {method:"POST", body:JSON.stringify({nome:document.querySelector("#template-name").value, permissoes:{}})});
        form.reset(); await carregarModelosPerfil(); notificarTemporariamente("Modelo criado. Abra-o, selecione as permissões e salve.");
      } catch (error) { notificarTemporariamente(error.message, 10000); } finally { button.disabled = false; }
    });

    function adicionarMarcarTodos(container, checks, approved = null) {
      const toolbar = document.createElement("div");
      toolbar.className = "permissions-toolbar";
      const all = criarCampo(toolbar, "Marcar todas as permissões", false);
      const inputs = Object.values(checks);
      function sync() {
        const count = inputs.filter(input => input.checked).length;
        all.checked = count === inputs.length;
        all.indeterminate = count > 0 && count < inputs.length;
      }
      all.addEventListener("change", () => {
        const checked = all.checked;
        inputs.forEach(input => {
          input.checked = checked;
          input.dispatchEvent(new Event("change", {bubbles: true}));
        });
        sync();
      });
      inputs.forEach(input => input.addEventListener("change", sync));
      if (approved) approved.addEventListener("accesschange", sync);
      sync(); container.append(toolbar);
    }

    async function carregarUsuarios() {
      await carregarModelosPerfil();
      await carregarPerfisTeste();
      const users = await request("/api/users");
      usersContainer.replaceChildren();
      for (const user of users) {
        const card = document.createElement("details");
        card.className = "card profile-item";
        card.setAttribute("name", "profile-list");
        const heading = document.createElement("summary");
        heading.textContent = user.nome || user.apelido || `Telegram ${user.telegram_id}`;
        const details = document.createElement("p");
        details.className = "muted";
        details.textContent = `ID ${user.telegram_id}` +
          (user.username ? ` · @${user.username}` : "") +
          (user.ultimo_acesso ? ` · Último acesso: ${user.ultimo_acesso}` : "");
        if (user.administrador) heading.textContent += " \u00b7 Administrador";
        const statusLine = document.createElement("p");
        statusLine.textContent = user.aprovado ? "Aprovado" : "Pendente";
        statusLine.className = user.aprovado ? "approved" : "pending";
        const fields = document.createElement("div");
        fields.className = "row";
        const access = document.createElement("div");
        access.className = "permissions-toolbar";
        const approved = criarCampo(access, "Permitir acesso ao bot", user.aprovado);
        const checks = {};
        for (const [key, label] of permissions) {
          checks[key] = criarCampo(fields, label, user[key]);
        }
        const editor = document.createElement("div");
        const obterVinculo = adicionarSeletorModelo(editor, approved, checks, user.modelo_perfil_id);
        const lerEscopo = editarEscopo(editor, user, obterVinculo.desvincular);
        obterVinculo.escopoAplicado = lerEscopo.aplicar;
        vincularAcessoPermissoes(approved, checks);
        editor.append(access);
        adicionarMarcarTodos(editor, checks, approved);
        const save = document.createElement("button");
        save.type = "button";
        save.textContent = "Salvar perfil";
        save.addEventListener("click", async () => {
          const profile = {...lerEscopo(), modelo_perfil_id: obterVinculo()};
          if (approved.checked !== Boolean(user.aprovado)) profile.aprovado = approved.checked;
          for (const [key] of permissions) profile[key] = checks[key].checked;
          try {
            await request(`/api/users/${user.telegram_id}`, {
              method: "PUT", body: JSON.stringify(profile)
            });
            notificarTemporariamente("Perfil atualizado.");
            await carregarUsuarios();
          } catch (error) { notificarTemporariamente(error.message, 10000); }
        });
        const remove = document.createElement("button");
        remove.type = "button"; remove.className = "danger"; remove.textContent = "Remover usuário";
        remove.disabled = Boolean(user.administrador);
        if (user.administrador) remove.title = "O administrador principal não pode ser excluído.";
        remove.addEventListener("click", async () => {
          if (!window.confirm(`Remover ${heading.textContent} (ID ${user.telegram_id})? Se iniciar o bot novamente, voltará como pendente.`)) return;
          remove.disabled = true;
          try {
            await request(`/api/users/${user.telegram_id}`, {method: "DELETE"});
            await carregarUsuarios(); notificarTemporariamente("Usuário removido.");
          } catch (error) { notificarTemporariamente(error.message, 10000); }
          finally { remove.disabled = false; }
        });
        const actions = document.createElement("div"); actions.className = "row";
        actions.append(save, remove);
        editor.append(fields, actions);
        card.append(heading, details, statusLine, editor);
        usersContainer.append(card);
      }
      document.querySelector("#users-status").textContent = users.some(user => !user.administrador)
        ? "Marque Permitir acesso ao bot, escolha as permissões e clique em Salvar perfil. Desmarque para bloquear o acesso."
        : "Nenhum usuário comum cadastrado. Cadastre pelo ID acima ou peça para outro usuário iniciar o bot.";
    }

    document.querySelector("#refresh-users").addEventListener("click", async () => {
      try { await carregarUsuarios(); } catch (error) { notificarTemporariamente(error.message, 10000); }
    });
    document.querySelector("#tab-profiles").addEventListener("click", () => {
      carregarUsuarios().catch(error => { notificarTemporariamente(error.message, 10000); });
    });
    document.querySelector("#create-user-form").addEventListener("submit", async event => {
      event.preventDefault();
      const form = event.currentTarget;
      const idField = document.querySelector("#new-user-id");
      const telegramId = removeSpaces(idField.value);
      idField.value = telegramId;
      if (!/^[0-9]+$/.test(telegramId) || BigInt(telegramId) <= 0n || BigInt(telegramId) > 4503599627370496n) {
        notificarTemporariamente("Informe um ID válido do Telegram, somente com números. Peça ao usuário que envie /meuid ao bot.", 10000);
        idField.focus();
        return;
      }
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true;
      try {
        const result = await request("/api/users", { method: "POST", body: JSON.stringify({
          telegram_id: telegramId,
          nome: document.querySelector("#new-user-name").value.trim()
        }) });
        form.reset();
        await carregarUsuarios();
        notificarTemporariamente(result.administrador
          ? "Administrador cadastrado. As permissões personalizadas existentes foram preservadas."
          : "Perfil cadastrado. Configure o acesso e salve o perfil.");
      } catch (error) { notificarTemporariamente(error.message, 10000); }
      finally { button.disabled = false; }
    });

    async function acaoPerfilTeste(action, id = null, permissions = null) {
      await request("/api/test-profiles", { method: "POST", body: JSON.stringify({action, id, permissions}) });
      await carregarPerfisTeste();
    }
    document.querySelector("#restore-admin").addEventListener("click", () => {
      acaoPerfilTeste("ativar").catch(error => { notificarTemporariamente(error.message, 10000); });
    });
    async function carregarPerfisTeste() {
      const data = await request("/api/test-profiles");
      const container = document.querySelector("#test-profiles");
      container.replaceChildren();
      const active = data.profiles.find(profile => profile.id === data.active);
      document.querySelector("#test-profile-status").textContent = active
        ? `Teste ativo: ${active.nome}. O bot usa as permissões deste perfil.`
        : "Perfil principal do administrador ativo.";
      for (const profile of data.profiles) {
        const card = document.createElement("details"); card.className = "card profile-item";
        card.setAttribute("name", "profile-list");
        const heading = document.createElement("summary");
        heading.textContent = profile.nome + " · Perfil de teste" + (profile.id === data.active ? " · Ativo" : "");
        const fields = document.createElement("div"); fields.className = "row";
        const access = document.createElement("div"); access.className = "permissions-toolbar";
        const approved = criarCampo(access, "Permitir acesso ao bot", profile.aprovado);
        const checks = {};
        for (const [key, label] of permissions) checks[key] = criarCampo(fields, label, profile[key]);
        const editor = document.createElement("div");
        const obterVinculo = adicionarSeletorModelo(editor, approved, checks, profile.modelo_perfil_id);
        const lerEscopo = editarEscopo(editor, profile, obterVinculo.desvincular);
        obterVinculo.escopoAplicado = lerEscopo.aplicar;
        vincularAcessoPermissoes(approved, checks);
        editor.append(access);
        adicionarMarcarTodos(editor, checks, approved);
        const save = document.createElement("button"); save.type = "button"; save.textContent = "Salvar permissões";
        save.addEventListener("click", async () => {
          save.disabled = true;
          try {
            const values = Object.fromEntries(Object.entries(checks).map(([key, input]) => [key, input.checked]));
            values.modelo_perfil_id = obterVinculo();
            Object.assign(values, lerEscopo());
            if (approved.checked !== Boolean(profile.aprovado)) values.aprovado = approved.checked;
            await acaoPerfilTeste("salvar", profile.id, values);
            notificarTemporariamente("Permissões do perfil salvas.");
          } catch (error) { notificarTemporariamente(error.message, 10000); }
          finally { save.disabled = false; }
        });
        const actions = document.createElement("div"); actions.className = "row";
        const remove = document.createElement("button"); remove.type = "button";
        remove.className = "danger"; remove.textContent = "Remover perfil";
        remove.addEventListener("click", async () => {
          if (!window.confirm(`Remover o perfil ${profile.nome}?`)) return;
          remove.disabled = true;
          try { await acaoPerfilTeste("remover", profile.id); notificarTemporariamente("Perfil removido."); }
          catch (error) { notificarTemporariamente(error.message, 10000); }
          finally { remove.disabled = false; }
        });
        actions.append(save, remove); editor.append(fields, actions);
        card.append(heading, editor); container.append(card);
      }
    }

    async function carregarConfiguracoes() {
      configuracaoAtual = await request("/api/settings");
      document.querySelector("#data-directory").textContent =
        configuracaoAtual.BOT_DATA_DIR;
      const campos = {
        "telegram-admin-id": "TELEGRAM_ADMIN_ID",
        "oracle-host": "ORACLE_HOST",
        "oracle-port": "ORACLE_PORT",
        "oracle-service": "ORACLE_SERVICE",
        "oracle-user": "ORACLE_USER",
      };
      for (const [id, key] of Object.entries(campos)) {
        document.querySelector(`#${id}`).value = configuracaoAtual[key] || "";
        if (id === "oracle-host" || id === "oracle-user") {
          definirVisibilidadeOracle(id, !configuracaoAtual[key]);
        }
      }
      document.querySelector("#telegram-bot-token").placeholder =
        configuracaoAtual.TELEGRAM_BOT_TOKEN_configured ? "Token salvo" : "Ainda não configurado";
      document.querySelector("#oracle-password").placeholder =
        configuracaoAtual.ORACLE_PASSWORD_configured ? "Senha salva" : "Ainda não configurada";
      await carregarServicoWindows();
    }

    async function carregarServicoWindows() {
      const response = await request("/api/windows-service");
      const section = document.querySelector("#windows-service");
      section.hidden = !response.available;
      if (!response.available) return;

      const status = document.querySelector("#windows-service-status");
      const enable = document.querySelector("#enable-windows-service");
      const disable = document.querySelector("#disable-windows-service");
      const remove = document.querySelector("#remove-windows-service");
      if (response.installed && response.binary_exists === false) {
        status.textContent = "O executável registrado no serviço não existe. Clique em Reparar e confirme a solicitação administrativa.";
        enable.hidden = false;
        enable.textContent = "Reparar inicialização automática";
        disable.hidden = true;
        remove.hidden = false;
      } else if (!response.installed) {
        status.textContent = "Serviço ainda não instalado.";
        enable.hidden = false;
        enable.textContent = "Ativar inicialização automática";
        disable.hidden = true;
        remove.hidden = true;
      } else if (response.automatic) {
        status.textContent = `Serviço instalado · ${response.state} · inicialização automática ativa.`;
        enable.hidden = true;
        disable.hidden = false;
        remove.hidden = false;
      } else {
        status.textContent = `Serviço instalado · ${response.state} · inicialização automática desativada.`;
        enable.hidden = false;
        enable.textContent = "Ativar inicialização automática";
        disable.hidden = true;
        remove.hidden = false;
      }
    }

    async function executarAcaoServicoWindows(action) {
      if (action === "remove" &&
          !window.confirm("Confirma parar e remover o serviço do Windows?")) return;
      try {
        const result = await request(`/api/windows-service/${action}`, {
          method: "POST", body: "{}"
        });
        notificarTemporariamente(result.message);
        window.setTimeout(() => {
          carregarServicoWindows().catch(error => { notificarTemporariamente(error.message, 10000); });
        }, 1500);
      } catch (error) { notificarTemporariamente(error.message, 10000); }
    }

    async function abrirPainel() {
      try {
        const session = await request("/api/session");
        csrf = session.csrf;
        login.hidden = true;
        dashboard.hidden = false;
        checkConnections();
        await carregarConfiguracoes();
        await carregarUsuarios();
      } catch (_) {
        csrf = "";
        login.hidden = false;
        dashboard.hidden = true;
      }
    }

    const loginPassword = document.querySelector("#password");
    const loginError = document.querySelector("#login-error");
    document.querySelector("#toggle-login-password").addEventListener("click", event => {
      const visible = loginPassword.type === "password";
      loginPassword.type = visible ? "text" : "password";
      event.currentTarget.textContent = visible ? "Ocultar" : "Mostrar";
      event.currentTarget.setAttribute("aria-pressed", String(visible));
    });
    for (const name of ["keydown", "keyup"]) loginPassword.addEventListener(name, event => {
      document.querySelector("#caps-warning").hidden = !event.getModifierState("CapsLock");
    });
    loginPassword.addEventListener("blur", () => { document.querySelector("#caps-warning").hidden = true; });
    document.querySelector("#login-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = document.querySelector("#login-submit");
      if (button.disabled) return;
      button.disabled = true; button.textContent = "Entrando…";
      button.setAttribute("aria-busy", "true"); notificarTemporariamente("", 0, loginError);
      const form = new FormData(event.currentTarget);
      try {
        const result = await request("/api/login", {
          method: "POST",
          body: JSON.stringify({
            username: form.get("username"),
            password: form.get("password")
          })
        });
        csrf = result.csrf;
        loginPassword.value = "";
        loginPassword.type = "password";
        document.querySelector("#toggle-login-password").textContent = "Mostrar";
        document.querySelector("#toggle-login-password").setAttribute("aria-pressed", "false");
        notificarTemporariamente("");
        await abrirPainel();
      } catch (error) {
        notificarTemporariamente(error.message, 10000, loginError);
        loginPassword.focus();
      } finally {
        button.disabled = false; button.textContent = "Entrar no painel";
        button.setAttribute("aria-busy", "false");
      }
    });

    document.querySelector("#logout").addEventListener("click", async () => {
      try {
        await request("/api/logout", { method: "POST", body: "{}" });
        csrf = "";
        await abrirPainel();
      } catch (error) { notificarTemporariamente(error.message, 10000); }
    });

    document.querySelector("#password-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const newPassword = form.get("new_password");
      if (newPassword !== form.get("confirm_password")) {
        notificarTemporariamente("A confirmação não corresponde à nova senha.", 10000);
        return;
      }
      try {
        const result = await request("/api/change-password", {
          method: "POST",
          body: JSON.stringify({
            current_password: form.get("current_password"),
            new_password: newPassword
          })
        });
        csrf = result.csrf;
        event.currentTarget.reset();
        notificarTemporariamente("Senha alterada. As outras sessões foram encerradas.");
      } catch (error) { notificarTemporariamente(error.message, 10000); }
    });

    for (const formId of ["settings-form", "oracle-settings-form"]) {
    document.getElementById(formId).addEventListener("submit", async (event) => {
      event.preventDefault();
      const settingsForm = event.currentTarget;
      const section = formId === "settings-form" ? "bot" : "oracle";
      const buttonText = section === "bot" ? "SALVAR E TESTAR BOT" : "SALVAR E TESTAR ORACLE";
      const saveButton = event.currentTarget.querySelector('button[type="submit"]');
      saveButton.disabled = true;
      saveButton.textContent = "SALVANDO E TESTANDO…";
      notificarTemporariamente(section === "bot" ? "Verificando Telegram…" : "Verificando Oracle…", 0);
      const fields = {
        TELEGRAM_ADMIN_ID: "telegram-admin-id",
        TELEGRAM_BOT_TOKEN: "telegram-bot-token",
        ORACLE_HOST: "oracle-host",
        ORACLE_PORT: "oracle-port",
        ORACLE_SERVICE: "oracle-service",
        ORACLE_USER: "oracle-user",
        ORACLE_PASSWORD: "oracle-password",
      };
      const settings = {};
      for (const [key, id] of Object.entries(fields)) {
        const field = settingsForm.querySelector(`#${id}`);
        if (!field) continue;
        const value = field.value;
        settings[key] = ["TELEGRAM_BOT_TOKEN", "ORACLE_PASSWORD"].includes(key)
          ? value : value.trim();
      }
      try {
        const result = await request("/api/settings", {
          method: "PUT",
          body: JSON.stringify({
            settings, section,
            clear_telegram_token: section === "bot" && document.querySelector("#clear-telegram-token").checked,
            clear_oracle_password: false
          })
        });
        for (const field of settingsForm.querySelectorAll('#telegram-bot-token, #oracle-password')) field.value = "";
        for (const field of settingsForm.querySelectorAll('input[type="checkbox"]')) field.checked = false;
        if (section === "oracle") ocultarDadosOracle();
        renderConnections(result.checks);
        const verificacoes = Object.entries(result.checks)
          .map(([servico, check]) => `${servico}: ${check.message}`)
          .join("\\n");
        notificarTemporariamente(`${result.message}\\n${verificacoes}`, 10000);
      } catch (error) { notificarTemporariamente(error.message, 10000); }
      finally {
        saveButton.disabled = false;
        saveButton.textContent = buttonText;
      }
    });

    }

    document.querySelector("#enable-windows-service").addEventListener("click", () => {
      executarAcaoServicoWindows("install");
    });
    document.querySelector("#disable-windows-service").addEventListener("click", () => {
      executarAcaoServicoWindows("disable");
    });
    document.querySelector("#remove-windows-service").addEventListener("click", () => {
      executarAcaoServicoWindows("remove");
    });

    abrirPainel();
  </script>
</body>
</html>
"""


def _exigir_admin(request):
    if request.session.get("admin") is not True:
        raise HTTPException(status_code=401, detail="Autenticação necessária.")
    versao = obter_versao_sessao_admin(ADMIN_PASSWORD)
    if request.session.get("versao_sessao") != versao:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Sessão encerrada. Entre novamente.")


def _exigir_csrf(request):
    token = request.headers.get("x-csrf-token", "")
    esperado = request.session.get("csrf", "")
    if not esperado or not hmac.compare_digest(token, esperado):
        raise HTTPException(status_code=403, detail="Token de segurança inválido.")


@app.get("/", response_class=HTMLResponse)
def pagina_inicial():
    return HTMLResponse(PAGINA, headers={"Cache-Control": "no-store"})


@app.get("/assets/{nome}")
def imagem_painel(nome: str):
    imagens = {
        "logo-produto.png": "Logo geométrico myBotWinthor com monograma RB.png",
        "logo-empresa.png": "Logo tecnológico RBTech Soluções.png",
        "icone.png": "rb_app_icon.png",
    }
    arquivo = imagens.get(nome)
    if arquivo is None or not (BASE_DIR / "assets" / arquivo).is_file():
        raise HTTPException(status_code=404, detail="Imagem não encontrada.")
    return FileResponse(BASE_DIR / "assets" / arquivo, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=3600"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/directories")
def listar_diretorios(request: Request, path: str = ""):
    _exigir_admin(request)
    if not path and os.name == "nt":
        unidades = [Path(f"{letra}:/") for letra in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
        return {"path": "", "parent": None, "directories": [
            {"name": str(p), "path": str(p)} for p in unidades if p.is_dir()
        ]}
    try:
        pasta = Path(path).expanduser() if path else Path.home()
        if not pasta.is_absolute():
            raise ValueError("Caminho relativo inválido.")
        pasta = pasta.resolve(strict=True)
        if not pasta.is_dir():
            raise ValueError("Pasta inválida.")
        diretorios = []
        for item in pasta.iterdir():
            try:
                if item.is_dir():
                    diretorios.append({"name": item.name, "path": str(item)})
            except OSError:
                continue
        return {
            "path": str(pasta),
            "parent": str(pasta.parent) if pasta.parent != pasta else ("" if os.name == "nt" else None),
            "directories": sorted(diretorios, key=lambda item: item["name"].casefold()),
        }
    except (OSError, ValueError, RuntimeError) as erro:
        raise HTTPException(status_code=400, detail="Não foi possível abrir esta pasta. Verifique o caminho e as permissões.") from erro


@app.get("/api/session")
def sessao(request: Request):
    _exigir_admin(request)
    return {"csrf": request.session["csrf"]}


@app.post("/api/login")
async def login(request: Request):
    ip = request.client.host if request.client else "unknown"
    agora = time.monotonic()
    tentativas, bloqueado_ate = _tentativas_login.get(ip, (0, 0.0))
    if bloqueado_ate > agora:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde alguns minutos.")
    try:
        dados = await request.json()
    except ValueError as erro:
        raise HTTPException(status_code=400, detail="Requisição inválida.") from erro
    usuario = dados.get("username", "") if isinstance(dados, dict) else ""
    senha = dados.get("password", "") if isinstance(dados, dict) else ""
    admin_user = obter_ou_criar_configuracao(
        "WEB_ADMIN_USER", os.getenv("WEB_ADMIN_USER", "admin")
    ).strip()
    usuario_ok = isinstance(usuario, str) and hmac.compare_digest(
        usuario.encode("utf-8"), admin_user.encode("utf-8")
    )
    senha_ok = (
        usuario_ok
        and isinstance(senha, str)
        and verificar_senha_admin(senha, ADMIN_PASSWORD)
    )
    if not usuario_ok or not senha_ok:
        tentativas += 1
        bloqueado_ate = agora + 300 if tentativas >= 5 else 0.0
        _tentativas_login[ip] = (0 if bloqueado_ate else tentativas, bloqueado_ate)
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")
    _tentativas_login.pop(ip, None)
    request.session.clear()
    request.session["admin"] = True
    request.session["versao_sessao"] = obter_versao_sessao_admin(ADMIN_PASSWORD)
    request.session["csrf"] = os.urandom(32).hex()
    return {"csrf": request.session["csrf"]}


@app.post("/api/logout", status_code=204)
def logout(request: Request):
    _exigir_admin(request)
    _exigir_csrf(request)
    request.session.clear()


@app.get("/api/settings")
def obter_configuracoes_painel(request: Request):
    _exigir_admin(request)
    configuracoes = obter_configuracao()
    resposta = {
        chave: (
            bool(configuracoes[chave])
            if chave in CHAVES_SECRETAS
            else configuracoes[chave]
        )
        for chave in CHAVES_CONFIGURACAO
        if chave != "WEB_SESSION_SECRET"
    }
    resposta["BOT_DATA_DIR"] = str(DIRETORIO_DADOS)
    resposta.update({
        f"{chave}_configured": bool(configuracoes[chave])
        for chave in CHAVES_SECRETAS
        if chave != "WEB_SESSION_SECRET"
    })
    return resposta


@app.get("/api/message-templates")
def modelos_mensagem(request: Request):
    _exigir_admin(request)
    try:
        return {'templates': listar_modelos(), 'limite': LIMITE_MODELO}
    except (RuntimeError, OSError) as erro:
        raise HTTPException(status_code=503, detail='Não foi possível carregar mensagens.json. Verifique o arquivo ou restaure um backup.') from erro


@app.put("/api/message-templates")
async def atualizar_modelos_mensagem(request: Request):
    _exigir_admin(request)
    _exigir_csrf(request)
    try:
        dados = await request.json()
        if not isinstance(dados, dict) or set(dados) != {'templates'}:
            raise ValueError('Informe os modelos de mensagem.')
        return {'templates': salvar_modelos(dados['templates']), 'limite': LIMITE_MODELO}
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    except (RuntimeError, OSError) as erro:
        raise HTTPException(status_code=503, detail='Não foi possível salvar mensagens.json. Verifique a pasta de dados.') from erro


@app.post("/api/message-templates/preview")
async def previa_mensagem(request: Request):
    _exigir_admin(request)
    _exigir_csrf(request)
    try:
        dados = await request.json()
        if not isinstance(dados, dict) or set(dados) != {'id', 'texto'} or not isinstance(dados['id'], str):
            raise ValueError('Informe o tipo e o texto da mensagem.')
        return {'texto': previa_modelo(dados['id'], dados['texto'])}
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro


@app.get("/api/windows-service")
def status_servico_windows(request: Request):
    _exigir_admin(request)
    try:
        return obter_status_servico()
    except (OSError, RuntimeError) as erro:
        raise HTTPException(
            status_code=503, detail=f"Não foi possível consultar o serviço do Windows: {erro}"
        ) from erro


@app.post("/api/windows-service/{acao}")
def gerenciar_servico_windows(acao: str, request: Request):
    _exigir_admin(request)
    _exigir_csrf(request)
    if acao not in {"install", "disable", "remove"}:
        raise HTTPException(status_code=400, detail="Ação de serviço inválida.")
    try:
        return solicitar_acao_servico(acao)
    except (OSError, RuntimeError, ValueError) as erro:
        raise HTTPException(status_code=503, detail=str(erro)) from erro


async def _verificar_telegram(configuracoes):
    token = configuracoes["TELEGRAM_BOT_TOKEN"].strip()
    if not token:
        return {"status": "not_configured", "message": "não configurado"}

    try:
        async with Bot(token=token) as bot:
            await asyncio.wait_for(bot.get_me(), timeout=12)
    except InvalidToken:
        return {"status": "invalid_token", "message": "token recusado pelo Telegram"}
    except (NetworkError, asyncio.TimeoutError):
        return {"status": "unavailable", "message": "Telegram sem resposta ou sem rede"}
    except TelegramError as erro:
        logger.warning("Falha ao testar o Telegram (%s)", type(erro).__name__)
        return {"status": "error", "message": "Telegram respondeu com erro"}
    except Exception as erro:
        logger.warning("Falha inesperada ao testar o Telegram (%s)", type(erro).__name__)
        return {"status": "error", "message": "não foi possível testar o Telegram"}
    return {"status": "connected", "message": "conectado"}


async def _verificar_oracle(configuracoes):
    obrigatorias = (
        "ORACLE_HOST",
        "ORACLE_SERVICE",
        "ORACLE_USER",
        "ORACLE_PASSWORD",
    )
    if any(not configuracoes[chave].strip() for chave in obrigatorias):
        return {"status": "not_configured", "message": "não configurado"}

    try:
        conectado = await asyncio.wait_for(
            asyncio.to_thread(testar_conexao_oracle),
            timeout=12,
        )
    except ErroAcessoWinthor as erro:
        return {"status": "insufficient_access", "message": str(erro)}
    except (asyncio.TimeoutError, OSError, RuntimeError) as erro:
        logger.warning("Falha ao testar o Oracle (%s)", type(erro).__name__)
        return {
            "status": "unavailable",
            "message": "sem acesso; confira host, porta, serviço e credenciais",
        }
    except Exception as erro:
        logger.warning("Falha ao testar o Oracle (%s)", type(erro).__name__)
        return {
            "status": "error",
            "message": "conexão ou consulta de teste falhou",
        }
    if not conectado:
        return {"status": "error", "message": "consulta de teste não retornou resultado"}
    return {"status": "connected", "message": "conectado; consulta de produtos do WinThor validada"}


@app.get("/api/connections")
async def verificar_conexoes(request: Request):
    _exigir_admin(request)
    configuracoes = obter_configuracao()
    telegram, oracle = await asyncio.gather(
        _verificar_telegram(configuracoes), _verificar_oracle(configuracoes)
    )
    from fastapi.responses import JSONResponse
    return JSONResponse({"checks": {"telegram": telegram, "oracle": oracle}},
                        headers={"Cache-Control": "no-store"})


@app.put("/api/settings")
async def atualizar_configuracoes_painel(request: Request):
    _exigir_admin(request)
    _exigir_csrf(request)
    try:
        dados = await request.json()
    except ValueError as erro:
        raise HTTPException(status_code=400, detail="Requisição inválida.") from erro
    if not isinstance(dados, dict) or not isinstance(dados.get("settings"), dict):
        raise HTTPException(status_code=400, detail="Configurações inválidas.")
    configuracoes = dados["settings"]
    secao = dados.get("section")
    if secao not in (None, "bot", "oracle"):
        raise HTTPException(status_code=400, detail="Seção de configuração inválida.")
    if secao and any(chave.startswith("ORACLE_") != (secao == "oracle") for chave in configuracoes):
        raise HTTPException(status_code=400, detail="Os campos não pertencem à seção selecionada.")
    permitidas = set(CHAVES_CONFIGURACAO) - {"WEB_SESSION_SECRET"}
    if not configuracoes or not set(configuracoes).issubset(permitidas):
        raise HTTPException(status_code=400, detail="Campos de configuração inválidos.")
    if any(not isinstance(valor, str) for valor in configuracoes.values()):
        raise HTTPException(status_code=400, detail="As configurações devem ser textos.")
    if any(len(valor) > 2048 for valor in configuracoes.values()):
        raise HTTPException(status_code=400, detail="Um dos valores excede o limite permitido.")

    atualizar = {chave: valor for chave, valor in configuracoes.items()}
    for chave in ("TELEGRAM_ADMIN_ID", "ORACLE_HOST", "ORACLE_PORT", "ORACLE_SERVICE", "ORACLE_USER"):
        if chave in atualizar:
            atualizar[chave] = re.sub(r"\s+", "", atualizar[chave])
    host_oracle = atualizar.get("ORACLE_HOST", "")
    if host_oracle and "." in host_oracle and re.fullmatch(r"[0-9.]+", host_oracle):
        try:
            ipaddress.IPv4Address(host_oracle)
        except ValueError as erro:
            raise HTTPException(status_code=400, detail="Informe o IP do Oracle com quatro grupos de 0 a 255, por exemplo 192.168.0.10.") from erro
    for chave, campo_limpar in (
        ("TELEGRAM_BOT_TOKEN", "clear_telegram_token"),
        ("ORACLE_PASSWORD", "clear_oracle_password"),
    ):
        limpar = dados.get(campo_limpar, False)
        if not isinstance(limpar, bool):
            raise HTTPException(status_code=400, detail="Opção para limpar segredo inválida.")
        if secao and (chave.startswith("ORACLE_") != (secao == "oracle")):
            if limpar:
                raise HTTPException(status_code=400, detail="O segredo não pertence à seção selecionada.")
            continue
        if limpar:
            atualizar[chave] = ""
        elif not atualizar.get(chave):
            atualizar.pop(chave, None)

    for chave in ("ORACLE_PORT", "WEB_ADMIN_PORT"):
        if chave in atualizar:
            try:
                porta = int(atualizar[chave])
            except ValueError as erro:
                raise HTTPException(
                    status_code=400, detail=f"{chave} precisa ser numérica."
                ) from erro
            if not 1 <= porta <= 65535:
                raise HTTPException(
                    status_code=400, detail=f"{chave} precisa estar entre 1 e 65535."
                )
            atualizar[chave] = str(porta)

    if "TELEGRAM_ADMIN_ID" in atualizar:
        admin_id = atualizar["TELEGRAM_ADMIN_ID"]
        if admin_id and (not admin_id.isascii() or not admin_id.isdecimal() or int(admin_id) <= 0):
            raise HTTPException(status_code=400, detail="O ID do administrador deve ser numérico.")

    if "WEB_ADMIN_USER" in atualizar and not atualizar["WEB_ADMIN_USER"].strip():
        raise HTTPException(status_code=400, detail="O usuário do painel não pode ficar vazio.")
    if "WEB_ADMIN_HOST" in atualizar:
        host = atualizar["WEB_ADMIN_HOST"].strip()
        if host not in ("0.0.0.0", "::", "localhost"):
            try:
                ipaddress.ip_address(host)
            except ValueError as erro:
                raise HTTPException(
                    status_code=400,
                    detail="Informe um IP válido, localhost, 0.0.0.0 ou :: para o painel.",
                ) from erro
        atualizar["WEB_ADMIN_HOST"] = host
    if "WEB_ADMIN_URL" in atualizar and atualizar["WEB_ADMIN_URL"]:
        url = urlparse(atualizar["WEB_ADMIN_URL"])
        if url.scheme not in ("http", "https") or not url.netloc:
            raise HTTPException(status_code=400, detail="Informe uma URL HTTP ou HTTPS válida.")
    if "WEB_HTTPS_ONLY" in atualizar:
        if atualizar["WEB_HTTPS_ONLY"].lower() not in ("true", "false"):
            raise HTTPException(status_code=400, detail="A opção HTTPS deve ser true ou false.")
        atualizar["WEB_HTTPS_ONLY"] = atualizar["WEB_HTTPS_ONLY"].lower()

    try:
        salvar_configuracoes(atualizar)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    configuracoes_salvas = obter_configuracao()
    if secao == "bot":
        checks = {"telegram": await _verificar_telegram(configuracoes_salvas)}
    elif secao == "oracle":
        checks = {"oracle": await _verificar_oracle(configuracoes_salvas)}
    else:
        telegram, oracle = await asyncio.gather(
            _verificar_telegram(configuracoes_salvas),
            _verificar_oracle(configuracoes_salvas),
        )
        checks = {"telegram": telegram, "oracle": oracle}
    return {
        "message": (
            "Configurações salvas. A API continua ativa mesmo se um teste falhar. "
            "Reinicie bot.py para iniciar ou atualizar o polling do Telegram."
        ),
        "checks": checks,
    }


@app.post("/api/change-password")
async def mudar_senha(request: Request):
    _exigir_admin(request)
    _exigir_csrf(request)
    try:
        dados = await request.json()
    except ValueError as erro:
        raise HTTPException(status_code=400, detail="Requisição inválida.") from erro
    if not isinstance(dados, dict):
        raise HTTPException(status_code=400, detail="Requisição inválida.")
    try:
        versao = alterar_senha_admin(
            dados.get("current_password"),
            dados.get("new_password"),
            ADMIN_PASSWORD,
        )
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    request.session["versao_sessao"] = versao
    request.session["csrf"] = os.urandom(32).hex()
    return {"csrf": request.session["csrf"]}


@app.get("/api/users")
def usuarios(request: Request):
    _exigir_admin(request)
    garantir_administrador()
    return [
        {**perfil, "administrador": eh_admin(perfil["telegram_id"])}
        for perfil in listar_perfis()
    ]


@app.post("/api/users", status_code=201)
async def criar_usuario(request: Request):
    _exigir_admin(request)
    _exigir_csrf(request)
    try:
        dados = await request.json()
    except ValueError as erro:
        raise HTTPException(status_code=400, detail="Requisição inválida.") from erro
    if not isinstance(dados, dict):
        raise HTTPException(status_code=400, detail="Requisição inválida.")
    identificador = dados.get("telegram_id")
    nome = dados.get("nome", "")
    texto = re.sub(r"\s+", "", str(identificador))
    if not texto.isascii() or not texto.isdecimal() or not 0 < int(texto) <= 2**52:
        raise HTTPException(status_code=400, detail="Informe um ID válido do Telegram.")
    if not isinstance(nome, str) or len(nome) > 128:
        raise HTTPException(status_code=400, detail="Nome inválido (máximo 128 caracteres).")
    if not eh_admin(int(texto)) and any(p["telegram_id"] == int(texto) for p in listar_perfis()):
        raise HTTPException(status_code=409, detail="Este usuário já está cadastrado. Edite o perfil na lista.")
    if eh_admin(int(texto)):
        return {**registrar_usuario(int(texto), nome.strip() or None), 'administrador': True}
    return registrar_usuario(int(texto), nome.strip() or None)


@app.get("/api/access-options")
def opcoes_acesso(request: Request):
    _exigir_admin(request)
    try:
        return listar_opcoes_acesso()
    except Exception as erro:
        logger.warning('Falha ao listar filiais e regiões (%s)', type(erro).__name__)
        raise HTTPException(status_code=503, detail='Não foi possível carregar filiais e regiões do Oracle.') from erro


@app.get("/api/profile-templates")
def modelos_perfil(request: Request):
    _exigir_admin(request)
    return gerenciar_modelo_perfil()


async def _salvar_modelo(request, acao, modelo_id=None):
    _exigir_admin(request)
    _exigir_csrf(request)
    try:
        dados = await request.json()
        if not isinstance(dados, dict):
            raise ValueError('Requisição inválida.')
        return gerenciar_modelo_perfil(acao, modelo_id, dados.get('nome'), dados.get('permissoes'),
                                      {chave: dados[chave] for chave in CHAVES_ESCOPO if chave in dados})
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro


@app.post("/api/profile-templates", status_code=201)
async def criar_modelo_perfil(request: Request):
    return await _salvar_modelo(request, 'criar')


@app.put("/api/profile-templates/{modelo_id}")
async def salvar_modelo_perfil(modelo_id: str, request: Request):
    return await _salvar_modelo(request, 'salvar', modelo_id)


@app.delete("/api/profile-templates/{modelo_id}")
def remover_modelo_perfil(modelo_id: str, request: Request):
    _exigir_admin(request)
    _exigir_csrf(request)
    try:
        return gerenciar_modelo_perfil('remover', modelo_id)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro


@app.get("/api/test-profiles")
def perfis_teste(request: Request):
    _exigir_admin(request)
    return listar_perfis_teste()


@app.post("/api/test-profiles")
async def alterar_perfil_teste(request: Request):
    _exigir_admin(request)
    _exigir_csrf(request)
    try:
        dados = await request.json()
        if not isinstance(dados, dict) or dados.get("action") not in ("criar", "salvar", "ativar", "remover"):
            raise ValueError("Ação inválida.")
        if dados['action'] == 'criar':
            nome = dados.get('nome')
            if not isinstance(nome, str) or not nome.strip() or len(nome) > 128:
                raise ValueError('Informe o nome do perfil de teste.')
            return gerenciar_perfil_teste('criar', nome=nome.strip())
        if dados.get("id") is not None and not isinstance(dados["id"], str):
            raise ValueError("Perfil inválido.")
        return gerenciar_perfil_teste(dados["action"], perfil_id=dados.get("id"), permissoes=dados.get("permissions"))
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro


@app.delete("/api/users/{telegram_id}", status_code=204)
def remover_usuario(telegram_id: int, request: Request):
    _exigir_admin(request)
    _exigir_csrf(request)
    try:
        removido = revogar(str(telegram_id))
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    if removido is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")


@app.put("/api/users/{telegram_id}")
async def atualizar_usuario(telegram_id: int, request: Request):
    _exigir_admin(request)
    _exigir_csrf(request)
    try:
        perfil = await request.json()
    except ValueError as erro:
        raise HTTPException(status_code=400, detail="Requisição inválida.") from erro
    campos = {"aprovado", "modelo_perfil_id", *CHAVES_ESCOPO, *OPCOES_CONSULTA, *PERMISSOES}
    if not isinstance(perfil, dict) or not perfil or not set(perfil).issubset(campos):
        raise HTTPException(status_code=400, detail="Campos de perfil inválidos.")
    if any(not isinstance(valor, bool) for chave, valor in perfil.items() if chave not in CHAVES_ESCOPO | {'modelo_perfil_id'}):
        raise HTTPException(status_code=400, detail="As permissões devem ser booleanas.")
    try:
        return atualizar_perfil(telegram_id, perfil)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro


def iniciar_painel():
    import threading
    import uvicorn

    configuracoes = obter_configuracao()
    host = configuracoes["WEB_ADMIN_HOST"].strip()
    try:
        port = int(configuracoes["WEB_ADMIN_PORT"])
    except ValueError as erro:
        raise RuntimeError("WEB_ADMIN_PORT precisa ser numérica.") from erro
    if not host or not 1 <= port <= 65535:
        raise RuntimeError("WEB_ADMIN_HOST e WEB_ADMIN_PORT precisam ser válidos.")
    server = uvicorn.Server(
        uvicorn.Config(app, host=host, port=port, log_level="info")
    )
    thread = threading.Thread(
        target=server.run, name="painel-admin", daemon=True
    )
    thread.start()
    limite = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < limite:
        time.sleep(0.1)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=2)
        raise RuntimeError("O painel administrativo não iniciou; confira host, porta e logs.")
    return server, thread


def obter_url_acesso():
    configuracoes = obter_configuracao()
    url_configurada = configuracoes["WEB_ADMIN_URL"].strip()
    if url_configurada:
        return url_configurada
    host = configuracoes["WEB_ADMIN_HOST"].strip()
    if host not in ("", "0.0.0.0", "::"):
        ip = host
    else:
        ip = "127.0.0.1"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as conexao:
                conexao.connect(("192.0.2.1", 9))
                ip = conexao.getsockname()[0]
        except OSError:
            try:
                enderecos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
                ip = next(
                    (item[4][0] for item in enderecos
                     if not item[4][0].startswith(("127.", "169.254."))),
                    ip,
                )
            except OSError:
                pass
    port = int(configuracoes["WEB_ADMIN_PORT"])
    return f"http://{ip}:{port}"
