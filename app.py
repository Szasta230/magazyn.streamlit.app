import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import os
from PIL import Image, ImageOps
import io
import base64
import urllib.parse

# --- KONFIGURACJA STRONY ---
# Ustawiamy szerszy layout, żeby zdjęcia ładnie wyglądały
st.set_page_config(page_title="Asystent Zamówień", layout="centered", initial_sidebar_state="collapsed")

# --- STYL CSS (Dla ładniejszego wyglądu przycisków) ---
st.markdown("""
<style>
    /* Powiększenie przycisków na mobilkach */
    .stButton button {
        min-height: 60px;
        font-size: 18px;
    }
    /* Styl dla linku WhatsApp */
    .whatsapp-btn {
        display: inline-block;
        background-color: #25D366;
        color: white;
        padding: 15px 32px;
        text-align: center;
        text-decoration: none;
        font-size: 18px;
        border-radius: 8px;
        width: 100%;
        border: none;
        cursor: pointer;
        font-weight: bold;
    }
    .whatsapp-btn:hover {
        background-color: #128C7E;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNKCJE POMOCNICZE ---

# 1. Ładowanie danych z Excela
def load_data():
    excel_path = "produkty.xlsx"
    if os.path.exists(excel_path):
        try:
            # Wymuszamy wczytanie kolumn jako string, żeby uniknąć problemów z liczbami
            df = pd.read_excel(excel_path, dtype=str)
            # Konwertujemy ewentualne puste wartości na puste stringi
            return df.fillna("")
        except Exception as e:
            st.error(f"Błąd odczytu pliku Excel: {e}")
            return pd.DataFrame()
    else:
        st.warning(f"Nie znaleziono pliku: {excel_path}. Utwórz go, aby zacząć.")
        # Pusta ramka danych, jeśli plik nie istnieje
        return pd.DataFrame(columns=["Nazwa", "Kategoria", "Jednostka", "Zdjecie"])

# 2. Obróbka zdjęć (NOWOŚĆ: Stała wielkość)
def load_and_process_image(image_name, target_size=(500, 500)):
    """Ładuje zdjęcie, przycina do kwadratu i skaluje do stałego rozmiaru."""
    img_path = os.path.join("images", image_name)
    if not os.path.exists(img_path) or not image_name:
        return None
    
    try:
        img = Image.open(img_path)
        # ImageOps.fit przycina zdjęcie do zadanego formatu (jak 'object-fit: cover' w CSS)
        # centering=(0.5, 0.5) oznacza, że środek zdjęcia jest najważniejszy
        processed_img = ImageOps.fit(img, target_size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        return processed_img
    except Exception as e:
        st.error(f"Błąd przetwarzania zdjęcia {image_name}: {e}")
        return None

# 3. Generowanie PDF (używamy fpdf2)
def generate_pdf_bytes(order_list):
    pdf = FPDF()
    pdf.add_page()
    
    # UWAGA: fpdf2 ma wbudowane czcionki, ale do polskich znaków
    # najlepiej dodać własną (np. DejaVuSans.ttf w folderze projektu).
    # Poniżej wersja uproszczona bez polskich znaków diakrytycznych, 
    # żeby działało "od ręki".
    # Aby dodać polskie znaki:
    # pdf.add_font('DejaVu', '', 'DejaVuSans.ttf')
    # pdf.set_font('DejaVu', '', 14)
    pdf.set_font('Helvetica', 'B', 16) # Używamy standardowej czcionki

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    # Używamy encode/decode, aby pozbyć się znaków których standardowy Helvetica nie obsługuje
    title = f"Zamowienie - {date_str}".encode('latin-1', 'ignore').decode('latin-1')
    pdf.cell(0, 10, txt=title, new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(10)
    
    pdf.set_font('Helvetica', '', 12)
    for item in order_list:
        # Proste czyszczenie polskich znaków dla standardowej czcionki
        clean_name = item['nazwa'].replace('ł', 'l').replace('ą', 'a').replace('ę', 'e').replace('ś', 's').replace('ć', 'c').replace('ż', 'z').replace('ź', 'z').replace('ń', 'n').replace('ó', 'o')
        clean_unit = item['jednostka'].replace('ł', 'l').replace('ą', 'a').replace('ę', 'e').replace('ś', 's').replace('ć', 'c').replace('ż', 'z').replace('ź', 'z').replace('ń', 'n').replace('ó', 'o')

        text = f"- {clean_name}: {item['ilosc']} {clean_unit}"
        # Ponowne czyszczenie dla pewności
        safe_text = text.encode('latin-1', 'ignore').decode('latin-1')
        pdf.cell(0, 10, txt=safe_text, new_x="LMARGIN", new_y="NEXT")
    
    # Zwracamy bajty pliku PDF
    return bytes(pdf.output())

# 4. Generowanie linku WhatsApp (NOWOŚĆ)
def get_whatsapp_link(phone_number=None):
    """Generuje link wa.me z predefiniowaną wiadomością."""
    date_str = datetime.now().strftime("%d-%m-%Y")
    message = f"Cześć, przesyłam zamówienie z dnia {date_str}. Plik PDF w załączniku."
    encoded_message = urllib.parse.quote(message)
    
    # Jeśli podasz numer (np. "48123456789"), link otworzy czat z tą osobą.
    # Jeśli nie podasz numeru, WhatsApp pozwoli Ci wybrać kontakt z listy.
    if phone_number:
        return f"https://wa.me/{phone_number}?text={encoded_message}"
    else:
        # Wersja uniwersalna - wybierasz kontakt po kliknięciu
        return f"https://wa.me/?text={encoded_message}"

# --- INICJALIZACJA STANU APLIKACJI ---
# To są "zmienne globalne" w sesji użytkownika
if 'step' not in st.session_state:
    st.session_state.step = 'start' # start, checking, ordering, summary
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'order_list' not in st.session_state:
    st.session_state.order_list = []
if 'data_loaded' not in st.session_state:
     st.session_state.df = load_data()
     st.session_state.data_loaded = True

df = st.session_state.df

# --- GŁÓWNY INTERFEJS ---

st.title("📦 Magazynier Pro")

# --- KROK 1: EKRAN STARTOWY ---
if st.session_state.step == 'start':
    st.info("Witaj! Przygotuj się do szybkiego sprawdzenia stanów.")
    st.write(f"Znaleziono produktów w bazie: {len(df)}")
    
    if len(df) > 0:
        if st.button("🚀 Rozpocznij sprawdzanie", use_container_width=True):
            st.session_state.step = 'checking'
            st.rerun()
    else:
        st.warning("Dodaj produkty do pliku 'produkty.xlsx' aby rozpocząć.")

# --- KROK 2: SPRAWDZANIE PRODUKTÓW (Tinder-style) ---
elif st.session_state.step == 'checking':
    if st.session_state.current_index < len(df):
        product = df.iloc[st.session_state.current_index]
        
        # Pasek postępu
        progress = (st.session_state.current_index + 1) / len(df)
        st.progress(progress, text=f"Produkt {st.session_state.current_index + 1} z {len(df)}")

        # --- WYŚWIETLANIE ZDJĘCIA (Nowa implementacja) ---
        img_container = st.container()
        with img_container:
            processed_img = load_and_process_image(product['Zdjecie'])
            if processed_img:
                # Wyświetlamy wyśrodkowane zdjęcie o stałej wielkości
                st.image(processed_img, width=350) # Szerokość wyświetlania w aplikacji
            else:
                # Placeholder, jeśli brak zdjęcia
                st.markdown("""
                    <div style="width:350px; height:350px; background-color:#f0f2f6; display:flex; justify-content:center; align-items:center; border-radius:10px; border: 2px dashed #ccc;">
                        <h3 style="color:#999;">Brak zdjęcia 📷</h3>
                    </div>
                """, unsafe_allow_html=True)
        # -------------------------------------------------

        st.header(product['Nazwa'])
        st.caption(f"Kategoria: {product['Kategoria']} | Jednostka: {product['Jednostka']}")
        
        st.write("") # Odstęp

        # Przyciski akcji (duże na mobilki)
        col_skip, col_order = st.columns(2)
        
        with col_skip:
            # Używamy type="secondary" dla mniej ważnej akcji
            if st.button("⏭️ POMIŃ\n(Mamy to)", use_container_width=True, type="secondary"):
                st.session_state.current_index += 1
                st.rerun()
        
        with col_order:
            # Używamy type="primary" dla głównej akcji
            if st.button("🛒 ZAMÓW\n(Potrzeba)", use_container_width=True, type="primary"):
                st.session_state.step = 'ordering'
                st.rerun()
    else:
        # Koniec listy produktów
        st.session_state.step = 'summary'
        st.rerun()

# --- KROK 3: WPROWADZANIE ILOŚCI ---
elif st.session_state.step == 'ordering':
    product = df.iloc[st.session_state.current_index]
    st.subheader(f"Ile zamawiamy: {product['Nazwa']}?")
    st.write(f"Jednostka: **{product['Jednostka']}**")
    
    # Zmieniono: min_value, value i step na liczby całkowite (int)
    qty = st.number_input("Wpisz ilość:", min_value=0, value=1, step=1)
    
    st.write("") 
    
    col_back, col_confirm = st.columns(2)
    
    with col_back:
        if st.button("⬅️ Cofnij", use_container_width=True):
            st.session_state.step = 'checking'
            st.rerun()
            
    with col_confirm:
        # Przycisk zatwierdź
        if st.button("✅ Zatwierdź", use_container_width=True, type="primary", disabled=(qty <= 0)):
            if qty > 0:
                st.session_state.order_list.append({
                    "nazwa": product['Nazwa'],
                    "ilosc": int(qty), # Upewniamy się, że zapisujemy jako int
                    "jednostka": product['Jednostka']
                })
                st.success(f"Dodano: {product['Nazwa']} ({qty})")
            st.session_state.current_index += 1
            st.session_state.step = 'checking'
            st.rerun()

# --- KROK 4: PODSUMOWANIE I WYSYŁKA ---
elif st.session_state.step == 'summary':
    st.balloons() # Mały efekt na koniec
    st.success("🎉 Przegląd zakończony!")
    st.subheader("Twoja lista zamówień:")
    
    if st.session_state.order_list:
        # Wyświetlamy ładną tabelkę
        order_df = pd.DataFrame(st.session_state.order_list)
        # Zmieniamy nazwy kolumn na ładniejsze
        order_df.columns = ['Produkt', 'Ilość', 'Jm']
        st.dataframe(order_df, use_container_width=True, hide_index=True)
        
        st.write("---")
        st.subheader("📤 Wyślij zamówienie")
        st.info("👉 **Krok 1:** Pobierz plik PDF na telefon.\n\n👉 **Krok 2:** Kliknij przycisk WhatsApp i załącz pobrany plik w czacie.")
        
        # 1. Generowanie PDF w pamięci
        pdf_bytes = generate_pdf_bytes(st.session_state.order_list)
        file_name = f"Zamowienie_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        
        col_pdf, col_wa = st.columns(2)

        with col_pdf:
             # Przycisk pobierania PDF (Streamlit native)
            st.download_button(
                label="📄 1. Pobierz PDF",
                data=pdf_bytes,
                file_name=file_name,
                mime='application/pdf',
                use_container_width=True,
            )

        with col_wa:
            # Przycisk WhatsApp (HTML/CSS)
            # Jeśli chcesz wysyłać zawsze do szefa, wpisz tu jego numer: get_whatsapp_link("48600100200")
            wa_link = get_whatsapp_link() 
            st.markdown(f"""
                <a href="{wa_link}" target="_blank" class="whatsapp-btn">
                    📱 2. Otwórz WhatsApp
                </a>
            """, unsafe_allow_html=True)

    else:
        st.warning("Lista zamówień jest pusta. Nic nie wybrano.")
    
    st.write("")
    st.write("")
    if st.button("🔄 Zacznij sprawdzanie od nowa", use_container_width=True, type="secondary"):
        # Resetujemy stan aplikacji
        st.session_state.step = 'start'
        st.session_state.current_index = 0
        st.session_state.order_list = []
        # Opcjonalnie: przeładuj dane z excela jeśli mogły się zmienić
        st.session_state.df = load_data()
        st.rerun()