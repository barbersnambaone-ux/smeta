from pathlib import Path
from datetime import date
import pandas as pd
import streamlit as st
from engine import read_table,calculate,excel_bytes,VOLUME_COLS,NORM_COLS,PRICE_COLS,LABOR_COLS
from petrovich_adapter import validate_url,extract_candidates,history_row

st.set_page_config(page_title='Смета AI 0.6 Cloud',page_icon='🏗️',layout='wide')
ROOT=Path(__file__).resolve().parent
st.title('🏗️ Смета AI 0.6 Cloud')
st.caption('Демонстрация · Москва · Нормы производителей · Каталог цен Петровича, вводимый пользователем')
st.warning('Нет автоматического подключения к Петровичу. Вкладка проверки цен работает с текстом или HTML, предоставленным пользователем. Демонстрационные цены и нормы НЕ являются подтверждёнными рыночными данными или техническими нормативами. Не используйте пример как реальную смету.')
st.info('Данные текущего расчёта обрабатываются в памяти приложения. Не загружайте конфиденциальные проекты в публичную демоверсию.')

with st.sidebar:
    st.header('Параметры расчёта')
    overhead=st.number_input('Накладные расходы, %',0.,100.,10.,step=0.5)
    profit=st.number_input('Прибыль, %',0.,100.,15.,step=0.5)
    max_age=st.number_input('Актуальность цены, дней',1,365,14)
    st.caption('НДС, доставка и разгрузка не включены. Итог предварительный до устранения замечаний.')

configs=[('Ведомость объёмов','volumes.csv',VOLUME_COLS),('Нормы производителей','manufacturer_norms.csv',NORM_COLS),('Каталог цен Петровича','petrovich_prices.csv',PRICE_COLS),('Расценки работ','labor.csv',LABOR_COLS)]
frames=[]
tabs=st.tabs(['📁 Исходные данные','🔎 Согласование','🧮 Расчёт и экспорт','🛒 Петрович: проверка цен','ℹ️ Методика'])
with tabs[0]:
    st.subheader('Загрузите свои Excel или CSV')
    st.caption('Если файл не загружен, используется учебный образец. Источники норм указываются в таблице — они должны быть проверены специалистом.')
    cols=st.columns(2)
    for i,(label,filename,required) in enumerate(configs):
        with cols[i%2]:
            file=st.file_uploader(label,type=['csv','xlsx'],key=filename)
            try:
                df=read_table(file,ROOT/'sample_data'/filename)
                missing=[c for c in required if c not in df.columns]
                if missing: st.error('Нет столбцов: '+', '.join(missing))
                else: st.caption(f'Загружено строк: {len(df)}')
                with st.expander('Просмотр таблицы: '+label): st.dataframe(df,hide_index=True)
                frames.append(df)
            except Exception as e:
                st.error(f'Ошибка чтения {label}: {e}');frames.append(pd.DataFrame())
    st.caption('Шаблоны CSV входят в репозиторий, в папке sample_data.')

volumes,norms,prices,labor=frames
with tabs[1]:
    st.subheader('Подтверждение соответствия норматива и товара')
    st.write('Проверьте марку материала, характеристики, единицы, техническую карту производителя и артикул Петровича. Галочка подтверждает только выбор товара, но не актуальность цены.')
    if all(set(cols).issubset(df.columns) for df,cols in zip(frames,[VOLUME_COLS,NORM_COLS,PRICE_COLS,LABOR_COLS])):
        candidates=norms[['Код работы','Артикул','Материал','Производитель','Документ','Ссылка на техкарту']].copy()
        candidates.insert(0,'Утвердить',False)
        candidates['Код работы']=candidates['Код работы'].astype(str).str.strip().str.casefold().str.replace('ё','е')
        candidates['Артикул']=candidates['Артикул'].astype(str).str.strip()
        edited=st.data_editor(candidates,hide_index=True,key='approvals',disabled=[c for c in candidates.columns if c!='Утвердить'],use_container_width=True)
        approved={(str(r['Код работы']),str(r['Артикул'])) for _,r in edited.iterrows() if r['Утвердить']}
    else: approved=set();st.error('Сначала исправьте исходные таблицы')
with tabs[2]:
    st.subheader('Расчёт коммерческой сметы')
    if all(set(cols).issubset(df.columns) for df,cols in zip(frames,[VOLUME_COLS,NORM_COLS,PRICE_COLS,LABOR_COLS])):
        try:
            mats,works,warnings,summary=calculate(volumes,norms,prices,labor,approved,max_age,overhead,profit)
            a,b,c=st.columns(3)
            a.metric('Материалы, ₽',f"{summary['Материалы']:,.2f}")
            b.metric('Работы, ₽',f"{summary['Работы']:,.2f}")
            c.metric('Предварительный итог, ₽',f"{summary['Итого (предварительно)']:,.2f}")
            if summary['Полнота данных']: st.success('Все обязательные проверки пройдены')
            else: st.error('Расчёт НЕ готов к утверждению. Отсутствующие цены и ставки не следует считать нулевой стоимостью.')
            st.subheader('Материалы');st.dataframe(mats,hide_index=True,use_container_width=True)
            st.subheader('Работы');st.dataframe(works,hide_index=True,use_container_width=True)
            st.subheader('Замечания')
            if warnings:
                for w in warnings: st.write('• '+w)
            else: st.success('Замечаний нет')
            st.download_button('⬇️ Скачать предварительную смету Excel',data=excel_bytes(mats,works,warnings,summary),file_name='smeta_ai_05.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except Exception as e: st.error(f'Ошибка расчёта: {e}')
    else: st.error('Неверный формат исходных таблиц')
with tabs[3]:
    st.subheader('Проверка цены по карточке Петровича — Москва')
    st.info('Приложение не скачивает страницы сайта автоматически. Откройте карточку товара в браузере, скопируйте текст страницы или загрузите сохранённый HTML. Выберите цену вручную: на странице могут быть скидки, цены по карте и цены других товаров.')
    url=st.text_input('Ссылка на карточку',placeholder='https://moscow.petrovich.ru/product/123456/')
    product=st.text_input('Название товара')
    sku=st.text_input('Код товара Петровича')
    employee=st.text_input('Кто проверил цену',value='Сметчик')
    page=st.text_area('Вставьте текст страницы с ценой',height=140)
    html_file=st.file_uploader('Или загрузите сохранённую страницу HTML',type=['html','htm'],key='product_html')
    if html_file:
        page=html_file.getvalue().decode('utf-8',errors='replace')
    if page:
        found=extract_candidates(page)
        st.write('Возможные цены (₽), требуют проверки:',found['prices'] or 'не обнаружены')
        st.write('Возможные коды:',found['skus'] or 'не обнаружены')
    price=st.number_input('Подтверждённая цена за упаковку, ₽',min_value=0.0,step=1.0)
    if 'price_history' not in st.session_state: st.session_state.price_history=[]
    if st.button('Сохранить подтверждённую цену'):
        try:
            record=history_row(sku,product,price,url,employee)
            st.session_state.price_history.append(record)
            st.success('Цена записана в историю текущей сессии')
        except ValueError as exc: st.error(str(exc))
    if st.session_state.price_history:
        history=pd.DataFrame(st.session_state.price_history)
        st.dataframe(history,hide_index=True,use_container_width=True)
        st.download_button('Скачать историю цен CSV',history.to_csv(index=False).encode('utf-8-sig'),'petrovich_price_history.csv','text/csv')
        current=history.drop_duplicates(subset=['Артикул'],keep='last')[PRICE_COLS]
        st.download_button('Скачать актуальный прайс CSV для вкладки «Исходные данные»',current.to_csv(index=False).encode('utf-8-sig'),'petrovich_prices.csv','text/csv')
    st.caption('История хранится только в текущей сессии браузера. Скачайте CSV: при перезапуске облачного приложения данные могут исчезнуть.')
with tabs[4]:
    st.markdown('''**Правила:**\n\n1. Норматив расхода вносится из технической карты конкретного производителя и версии продукта.\n2. Расход умножается на объём и на коэффициент потерь, затем округляется до целых упаковок.\n3. Цена за упаковку загружается вручную после проверки карточки товара Петровича в регионе Москва.\n4. Для каждой позиции сохраняются ссылки на техническую карту и товар, дата цены и статус согласования.\n5. Расчёт с непроверенными позициями считается предварительным.\n\n**Ограничения демо:** без живого API Петровича, без распознавания PDF-техкарт, без постоянной БД и разграничения доступа. Для промышленного использования нужен отдельный защищённый сервер и аудит норм.\n''')
