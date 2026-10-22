"""Endereços locais para acesso ao painel."""
import ipaddress
import socket


def detectar_ip_rede():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as conexao:
            conexao.connect(('192.0.2.1', 9))
            ip = conexao.getsockname()[0]
            if not ipaddress.ip_address(ip).is_loopback and not ip.startswith('169.254.'):
                return ip
    except OSError:
        pass
    try:
        enderecos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        return next((item[4][0] for item in enderecos
                     if not item[4][0].startswith(('127.', '169.254.', '0.'))), None)
    except OSError:
        return None


def enderecos_painel(porta, host='0.0.0.0'):
    host = host.strip()
    local = f'http://127.0.0.1:{porta}' if host in ('', '0.0.0.0', 'localhost', '127.0.0.1') else None
    if host in ('localhost', '127.0.0.1', '::1'):
        return local or f'http://[::1]:{porta}', None
    ip = detectar_ip_rede() if host in ('', '0.0.0.0', '::') else host
    if ip and ':' in ip:
        ip = f'[{ip}]'
    return local, f'http://{ip}:{porta}' if ip else None
