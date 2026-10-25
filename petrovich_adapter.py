"""Safe, offline-first adapter: user-supplied product page text or HTML.
No HTTP requests, crawling, bypassing access controls, or undocumented API use.
"""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from html import unescape

ALLOWED_HOSTS={"moscow.petrovich.ru", "petrovich.ru", "www.petrovich.ru"}
PRICE_RE=re.compile(r"(?<!\d)([\d\s\u00a0\u202f]{1,12})\s*[₽р](?:уб\.?)?",re.I)
SKU_RE=re.compile(r"(?:Код\s*(?:товара)?\s*[:№]?\s*)(\d{5,9})",re.I)

def validate_url(url):
    p=urlparse(str(url).strip())
    if p.scheme!='https' or p.hostname not in ALLOWED_HOSTS or p.username or p.password or p.port:
        raise ValueError('Допустима только HTTPS-ссылка на официальный сайт Петровича')
    if not (p.path.startswith('/product/') or p.path.startswith('/catalog/')):
        raise ValueError('Укажите ссылку на карточку товара или каталог')
    return p.geturl()

def extract_candidates(text):
    """Extract candidate prices only; never claim authoritative/live price."""
    clean=unescape(re.sub(r'<[^>]+>', ' ',str(text)))
    clean=re.sub(r'[ \t]+',' ',clean)
    values=[]
    for m in PRICE_RE.finditer(clean):
        raw=re.sub(r'\D','',m.group(1))
        if raw and 1<=int(raw)<=10000000 and int(raw) not in values:
            values.append(int(raw))
    skus=list(dict.fromkeys(SKU_RE.findall(clean)))
    return {'prices':values[:30], 'skus':skus[:20]}

def history_row(sku, product, price, url, employee, region='Москва'):
    validate_url(url)
    if not str(sku).strip() or not str(product).strip(): raise ValueError('Укажите артикул и название')
    try: amount=float(str(price).replace(' ','').replace(',','.'))
    except (TypeError,ValueError): raise ValueError('Некорректная цена')
    if not 0<amount<10000000: raise ValueError('Некорректная цена')
    return {'Артикул':str(sku).strip(),'Товар':str(product).strip(),
            'Цена упаковки':amount,'Регион':region,'Дата цены':datetime.now(timezone.utc).date().isoformat(),
            'Ссылка':url,'Сотрудник':str(employee).strip() or 'не указан',
            'Источник':'ручная проверка карточки', 'Дата записи UTC':datetime.now(timezone.utc).isoformat()}
