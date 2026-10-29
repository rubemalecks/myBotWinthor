
import cv2
import numpy as np
import zxingcpp


def codigo_valido(codigo):
    return (
        codigo
        and codigo.isascii()
        and codigo.isdecimal()
        and len(codigo) in (8, 12, 13, 14)
    )


def tentar_ler(imagem):
    resultados = zxingcpp.read_barcodes(
        imagem,
        try_rotate=True,
        try_downscale=True,
        try_invert=True
    )

    for resultado in resultados:
        codigo = resultado.text.strip()

        if codigo_valido(codigo):
            return codigo

    return None


def ler_codigo_barras(imagem_bytes):
    from io import BytesIO
    from PIL import Image
    if len(imagem_bytes) > 5 * 1024 * 1024:
        raise ValueError('Imagem excede 5 MiB.')
    with Image.open(BytesIO(imagem_bytes)) as cabecalho:
        if cabecalho.width * cabecalho.height > 16_000_000:
            raise ValueError('Imagem excede 16 megapixels.')
    dados = np.frombuffer(
        imagem_bytes,
        dtype=np.uint8
    )

    imagem = cv2.imdecode(
        dados,
        cv2.IMREAD_COLOR
    )

    if imagem is None:
        return None

    # Primeira tentativa: imagem original
    codigo = tentar_ler(imagem)

    if codigo:
        return codigo

    cinza = cv2.cvtColor(
        imagem,
        cv2.COLOR_BGR2GRAY
    )

    # Segunda tentativa: escala de cinza
    codigo = tentar_ler(cinza)

    if codigo:
        return codigo

    # Terceira tentativa: melhorar contraste
    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    )

    contraste = clahe.apply(cinza)

    codigo = tentar_ler(contraste)

    if codigo:
        return codigo

    # Quarta tentativa: ampliar imagem
    for escala in (1.5, 2.0):
        ampliada = cv2.resize(
            contraste,
            None,
            fx=escala,
            fy=escala,
            interpolation=cv2.INTER_CUBIC
        )

        codigo = tentar_ler(ampliada)

        if codigo:
            return codigo

    # Quinta tentativa: dividir em faixas
    altura, largura = imagem.shape[:2]

    for inicio in (0.0, 0.2, 0.4, 0.6):
        y1 = int(altura * inicio)
        y2 = min(
            altura,
            y1 + int(altura * 0.4)
        )

        recorte = imagem[y1:y2, :]

        codigo = tentar_ler(recorte)

        if codigo:
            return codigo

    return None
