"""Diagnóstico local com resultado sanitizado; nunca retorna credenciais."""
import json,re
from pathlib import Path


def validar_criptografia():
    from cryptography.hazmat.primitives import hashes, hmac, padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    return len(PBKDF2HMAC(algorithm=hashes.SHA512(),length=32,salt=b'diagnostico',iterations=1).derive(b'exemplo'))==32


def diagnosticar_oracle(arquivo):
    import oracledb
    try:
        validar_criptografia()
        config=json.loads(Path(arquivo).read_text(encoding='utf-8'))
        cliente=config.get('ORACLE_CLIENT_DIR','').strip()
        if cliente:
            if cliente.replace('\\','/').startswith('//') or '://' in cliente:
                raise ValueError('Cliente remoto não permitido.')
            oracledb.init_oracle_client(lib_dir=str(Path(cliente).resolve()))
        with oracledb.connect(user=config['ORACLE_USER'],password=config['ORACLE_PASSWORD'],host=config['ORACLE_HOST'],port=int(config['ORACLE_PORT']),service_name=config['ORACLE_SERVICE'],tcp_connect_timeout=5) as conexao:
            conexao.call_timeout=5000
            with conexao.cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
                cursor.execute('SELECT 1 FROM DUAL')
                return {'ok':cursor.fetchone()==(1,),'modo':'Thin' if conexao.thin else 'Thick','criptografia':True}
    except Exception as erro:
        return {'ok':False,'tipo':type(erro).__name__,'codigos':sorted(set(re.findall(r'\b(?:DPY|DPI|ORA)-\d{3,6}\b',str(erro))))}
