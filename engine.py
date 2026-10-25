import io
import math
from datetime import date
import pandas as pd

VOLUME_COLS=['Код работы','Наименование','Ед. изм.','Количество']
NORM_COLS=['Код работы','Ед. работы','Артикул','Материал','Производитель','Документ','Ссылка на техкарту','Расход на ед. работы','Ед. материала','Потери %','Размер упаковки']
PRICE_COLS=['Артикул','Товар','Цена упаковки','Регион','Дата цены','Ссылка']
LABOR_COLS=['Код работы','Ед. изм.','Цена работ за ед.']

def read_table(upload, default_path):
    if upload is None: return pd.read_csv(default_path, dtype=str).fillna('')
    if upload.name.lower().endswith('.csv'):
        return pd.read_csv(upload, dtype=str).fillna('')
    return pd.read_excel(upload, dtype=str).fillna('')

def check_columns(df, columns, label):
    missing=[c for c in columns if c not in df.columns]
    if missing: raise ValueError(f'{label}: отсутствуют столбцы: {", ".join(missing)}')

def num(value, label, min_value=None):
    try: n=float(str(value).strip().replace(' ', '').replace(',','.'))
    except (ValueError,TypeError): raise ValueError(f'{label}: не число')
    if not math.isfinite(n) or (min_value is not None and n<min_value): raise ValueError(f'{label}: некорректное значение')
    return n

def normkey(s): return str(s).strip().casefold().replace('ё','е')

def calculate(volumes,norms,prices,labor,approved,max_age=14,overhead=10,profit=15):
    for df,cols,label in [(volumes,VOLUME_COLS,'Ведомость'),(norms,NORM_COLS,'Нормы'),(prices,PRICE_COLS,'Цены'),(labor,LABOR_COLS,'Работы')]: check_columns(df,cols,label)
    price_map={str(r['Артикул']).strip():r for _,r in prices.iterrows() if str(r['Артикул']).strip()}
    labor_map={normkey(r['Код работы']):r for _,r in labor.iterrows()}
    norm_map={code:group for code,group in norms.groupby(norms['Код работы'].map(normkey))}
    mats=[];works=[];warnings=[]
    for _,v in volumes.iterrows():
        code=normkey(v['Код работы']);unit=normkey(v['Ед. изм.']);name=str(v['Наименование'])
        try: qty=num(v['Количество'],f'{code}: количество',0.0000001)
        except ValueError as e: warnings.append(str(e));continue
        rate=labor_map.get(code)
        if rate is None or normkey(rate['Ед. изм.'])!=unit:
            warnings.append(f'{code}: ставка работ не найдена или несовпадение единиц');labor_rate=0
        else:
            try: labor_rate=num(rate['Цена работ за ед.'],'Ставка работ',0)
            except ValueError as e: warnings.append(str(e));labor_rate=0
        works.append({'Код работы':code,'Работа':name,'Ед.':unit,'Объём':qty,'Ставка работ':labor_rate,'Стоимость работ':round(qty*labor_rate,2)})
        group=norm_map.get(code)
        if group is None: warnings.append(f'{code}: отсутствуют нормы');continue
        for _,n in group.iterrows():
            sku=str(n['Артикул']).strip()
            if normkey(n['Ед. работы'])!=unit: warnings.append(f'{code}/{sku}: не совпадают единицы работ');continue
            try:
                consumption=num(n['Расход на ед. работы'],'Норма',0.0000001)
                loss=num(n['Потери %'],'Потери',0)
                pack=num(n['Размер упаковки'],'Упаковка',0.0000001)
                if loss>100: raise ValueError('Потери более 100%')
            except ValueError as e: warnings.append(f'{code}/{sku}: {e}');continue
            needed=qty*consumption*(1+loss/100)
            packs=math.ceil(needed/pack-1e-10)
            p=price_map.get(sku)
            matched=(code,sku) in approved
            price=None;age=None;link='';date_str='';region=''
            if p is None: warnings.append(f'{code}/{sku}: нет цены')
            else:
                link=str(p['Ссылка']);region=str(p['Регион']);date_str=str(p['Дата цены'])
                if normkey(region)!='москва': warnings.append(f'{code}/{sku}: регион цены не Москва')
                try:
                    price=num(p['Цена упаковки'],'Цена',0.0000001)
                    age=(date.today()-date.fromisoformat(date_str[:10])).days
                    if age<0 or age>max_age: warnings.append(f'{code}/{sku}: цена неактуальна')
                except (ValueError,TypeError) as e: warnings.append(f'{code}/{sku}: неверная цена или дата ({e})');price=None
            if not matched: warnings.append(f'{code}/{sku}: соответствие товара не подтверждено')
            if not str(n['Документ']).strip() or not str(n['Ссылка на техкарту']).strip(): warnings.append(f'{code}/{sku}: не указан источник норматива')
            eligible=matched and price is not None and age is not None and 0<=age<=max_age and normkey(region)=='москва' and bool(str(n['Документ']).strip()) and bool(str(n['Ссылка на техкарту']).strip())
            mats.append({'Код работы':code,'Работа':name,'Артикул':sku,'Материал':n['Материал'],'Производитель':n['Производитель'],'Документ':n['Документ'],'Техкарта':n['Ссылка на техкарту'],'Норма':consumption,'Ед. материала':n['Ед. материала'],'Потребность с потерями':round(needed,3),'Размер упаковки':pack,'Упаковок':packs,'Цена упаковки':price,'Стоимость материалов':round(packs*price,2) if price is not None else None,'Дата цены':date_str,'Ссылка Петрович':link,'Подтверждено':matched,'Готово к расчёту':eligible})
    materials=pd.DataFrame(mats);labor_df=pd.DataFrame(works)
    mat_total=float(materials['Стоимость материалов'].sum()) if not materials.empty else 0
    work_total=float(labor_df['Стоимость работ'].sum()) if not labor_df.empty else 0
    base=mat_total+work_total;oh=base*overhead/100;pr=(base+oh)*profit/100
    complete=(not materials.empty and materials['Готово к расчёту'].all() and not warnings)
    return materials,labor_df,sorted(set(warnings)),{'Материалы':round(mat_total,2),'Работы':round(work_total,2),'Накладные':round(oh,2),'Прибыль':round(pr,2),'Итого (предварительно)':round(base+oh+pr,2),'Полнота данных':bool(complete)}

def excel_bytes(materials,works,warnings,summary):
    buffer=io.BytesIO()
    with pd.ExcelWriter(buffer,engine='xlsxwriter') as writer:
        pd.DataFrame([summary]).to_excel(writer,'Итоги',index=False)
        works.to_excel(writer,'Работы',index=False)
        materials.to_excel(writer,'Материалы',index=False)
        pd.DataFrame({'Замечания':warnings}).to_excel(writer,'Проверка',index=False)
        for sheet in writer.sheets.values(): sheet.set_column(0,25,22)
    return buffer.getvalue()
