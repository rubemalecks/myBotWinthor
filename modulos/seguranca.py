"""Limites por processo e proteção comum das rotas administrativas."""
from collections import OrderedDict, deque
from threading import Lock, BoundedSemaphore
import time
import asyncio
import ipaddress
from urllib.parse import urlsplit
from fastapi import Request, HTTPException
from starlette.responses import JSONResponse
from starlette.datastructures import MutableHeaders


class LimiteTaxa:
    def __init__(self, max_chaves=4096):
        self.registros = OrderedDict()
        self.lock = Lock()
        self.max_chaves = max_chaves

    def permitir(self, chave, limite, janela=60):
        agora = time.monotonic()
        with self.lock:
            fila = self.registros.pop(chave, deque())
            while fila and fila[0] <= agora - janela:
                fila.popleft()
            permitido = len(fila) < limite
            if permitido:
                fila.append(agora)
            self.registros[chave] = fila
            while len(self.registros) > self.max_chaves:
                self.registros.popitem(last=False)
            return permitido


class ProtecaoHTTP:
    MAX_CORPO = 65536

    def __init__(self, app, autenticar, csrf, hostname):
        self.hostname = hostname
        self.app, self.autenticar, self.csrf = app, autenticar, csrf
        self.taxa = LimiteTaxa()
        self.operacoes = BoundedSemaphore(8)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request = Request(scope, receive=receive)
        path, method = scope['path'], scope['method']
        async def protegido(message):
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(scope=message)
                headers['X-Content-Type-Options'] = 'nosniff'
                headers['X-Frame-Options'] = 'DENY'
                headers['Referrer-Policy'] = 'no-referrer'
                headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
                if path.startswith('/api/'):
                    headers['Cache-Control'] = 'no-store'
            await send(message)
        async def negar(status, detalhe):
            resposta = JSONResponse({'detail': detalhe}, status_code=status,
                                    headers={'Retry-After': '60'} if status == 429 else None)
            await resposta(scope, receive, protegido)
        try:
            host = urlsplit('//' + request.headers.get('host', '')).hostname
            try:
                ipaddress.ip_address(host)
                host_valido = True
            except ValueError:
                host_valido = host in ('localhost', self.hostname())
            if not host or not host_valido:
                return await negar(400, 'Host não autorizado. Use o IP do painel ou configure WEB_ADMIN_URL.')
        except ValueError:
            return await negar(400, 'Host inválido.')
        if path.startswith('/api/'):
            if path != '/api/login':
                try:
                    self.autenticar(request)
                    if method not in ('GET', 'HEAD', 'OPTIONS'):
                        self.csrf(request)
                except HTTPException as erro:
                    return await negar(erro.status_code, erro.detail)
            ip = request.client.host if request.client else 'unknown'
            if not self.taxa.permitir(('http', ip), 600):
                return await negar(429, 'Muitas requisições. Aguarde um minuto.')
            if path == '/api/login' and not self.taxa.permitir(('login', ip), 10):
                return await negar(429, 'Muitas tentativas de login. Aguarde um minuto.')
            if method not in ('GET', 'HEAD', 'OPTIONS'):
                origem = request.headers.get('origin')
                if origem:
                    try:
                        origem_valida = urlsplit(origem).netloc.lower() == request.headers.get('host', '').lower()
                    except ValueError:
                        origem_valida = False
                    if not origem_valida:
                        return await negar(403, 'Origem da requisição inválida.')
        consulta = path.startswith(('/api/formulas', '/api/message-templates', '/api/product-fields')) or path in ('/api/connections', '/api/access-options', '/api/settings')
        adquirido = False
        if consulta:
            chave = scope.get('session', {}).get('csrf', '')
            if not self.taxa.permitir(('consulta', chave), 60):
                return await negar(429, 'Limite de consultas do painel atingido. Aguarde um minuto.')
            adquirido = self.operacoes.acquire(blocking=False)
            if not adquirido:
                return await negar(503, 'Painel ocupado. Aguarde as consultas atuais terminarem.')
        try:
            if method not in ('GET', 'HEAD', 'OPTIONS'):
                try:
                    tamanho = int(request.headers.get('content-length', '0'))
                except ValueError:
                    return await negar(400, 'Tamanho da requisição inválido.')
                if tamanho < 0:
                    return await negar(400, 'Tamanho da requisição inválido.')
                if tamanho > self.MAX_CORPO:
                    return await negar(413, 'Requisição muito grande (máximo 64 KiB).')
                corpo = bytearray()
                prazo = time.monotonic() + 10
                while True:
                    try:
                        mensagem = await asyncio.wait_for(receive(), timeout=max(0.001, prazo - time.monotonic()))
                    except asyncio.TimeoutError:
                        return await negar(408, 'Tempo para envio da requisição excedido.')
                    if mensagem['type'] == 'http.disconnect':
                        return
                    corpo.extend(mensagem.get('body', b''))
                    if len(corpo) > self.MAX_CORPO:
                        return await negar(413, 'Requisição muito grande (máximo 64 KiB).')
                    if not mensagem.get('more_body'):
                        break
                entregue = False
                async def receber():
                    nonlocal entregue
                    if not entregue:
                        entregue = True
                        return {'type': 'http.request', 'body': bytes(corpo), 'more_body': False}
                    return await receive()
                await self.app(scope, receber, protegido)
            else:
                await self.app(scope, receive, protegido)
        finally:
            if adquirido:
                self.operacoes.release()
