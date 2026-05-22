import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import plotly.express as px  
import plotly.graph_objects as row_go
from datetime import timedelta
# HATA COZUMU
pd.set_option("styler.render.max_elements", 1000000)
# SAYFA DUZENI
st.set_page_config(layout="wide", page_title="Nöbet Risk Analiz & Planlama")
# SAYFA TASARIMI
st.markdown("""
<style>
.kpi-card { background-color: #f8f9fa; padding: 20px; border-radius: 15px; border-left: 6px solid #a3b18a; text-align: center; margin-bottom: 15px; }
.kpi-title { font-size: 11px; color: #6c757d; font-weight: bold; text-transform: uppercase; }
.kpi-value { font-size: 24px; color: #344e41; font-weight: bold; }
.calendar-table { width: 100%; border-collapse: separate; border-spacing: 8px; table-layout: fixed; }
.calendar-td { height: 110px; vertical-align: top; padding: 10px; border-radius: 10px; border: 1px solid #ddd; transition: 0.3s; }
.day-num { font-weight: bold; font-size: 18px; margin-bottom: 5px; color: #2d6a4f; }
.risk-text { font-size: 11px; line-height: 1.3; font-weight: 500; }
th { background-color: #344e41; color: white; padding: 10px; border-radius: 5px; text-align: center; }
div.stButton > button { font-size: 12px; height: 35px; }
</style>
""", unsafe_allow_html=True)
# AY
AY_MAP = {1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran',
          7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'}
# VERI TANIMLARI&DONUSTURME
@st.cache_data
def veriyi_hazirla(file):
    df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
    df.columns = df.columns.str.strip()
    df['Base'] = df['Base'].astype(str).str.strip().str.upper()
    df['Baz Filo'] = df['Baz Filo'].astype(str).str.strip()
    df['Nöbet Kodu'] = df['Nobet Kodu'].astype(str).str.strip()
    df['Uçucu Sınıfı'] = df['Uçucu Sınıfı'].astype(str).str.strip()
          
    # Nobet Bitis Tarihi'ni datetime formatına çevirelim
    df["Nobet Baslangic"] = pd.to_datetime(
        df["Nobet Baslangic"],
        errors="coerce"
        )      
        # Kalkis Tarihi varsa datetime yap
        # Kalkis Tarihi yoksa Nobet Bitis Tarihi üzerinden üret
    df["Nobet Bitis"] = pd.to_datetime(
        df["Nobet Bitis"],
        errors="coerce",
        dayfirst=True
        )
 
    if "Kalkis Tarihi" in df.columns:
        df["Kalkis Tarihi"] = pd.to_datetime(
            df["Kalkis Tarihi"],
            errors="coerce",
            dayfirst=True
        )
 
        df["Kalkis Tarihi"] = df["Kalkis Tarihi"].fillna(
            df["Nobet Bitis"] + pd.Timedelta(hours=1, minutes=30)
        )
 
    else:
        df["Kalkis Tarihi"] = df["Nobet Bitis"] + pd.Timedelta(hours=1,minutes=30)

    #NOBET KODU TANIMLARI
    def nobet_parcala(kod):
        kod = str(kod).upper()
        if len(kod) < 5: return "Bilinmiyor", "Bilinmiyor", "0", "Bilinmiyor", "Bilinmiyor"
        lokasyon = "Home" if kod[0] == 'H' else "Airport" if kod[0] == 'A' else "Diğer"
        tip = "ER" if kod[1] == 'E' else "Layover" if kod[1] == 'L' else "Gitgel" if kod[1] == 'G' else "Diğer"
        return lokasyon, tip, kod[2], kod[3], kod[4]
    df[['N_Lokasyon', 'N_Tipi', 'N_Gun', 'N_Filo', 'N_Rol']] = df['Nöbet Kodu'].apply(lambda x: pd.Series(nobet_parcala(x)))
    df['Nobet Baslangic Tarihi'] = pd.to_datetime(df['Nobet Baslangic Tarihi'], errors='coerce')
    df['Kalkis Tarihi'] = pd.to_datetime(df['Kalkis Tarihi'], errors='coerce')
    df = df.dropna(subset=['Nobet Baslangic Tarihi'])
    #TARIH TANIMI&DONUSTURMELERI
    df['Tarih'] = df['Nobet Baslangic Tarihi'].dt.date
    df['Saat'] = df['Nobet Baslangic Tarihi'].dt.hour
    df['Yıl'] = df['Nobet Baslangic Tarihi'].dt.year
    df['Ay_No'] = df['Nobet Baslangic Tarihi'].dt.month
    df['Ay_TR'] = df['Ay_No'].map(AY_MAP)
    df['Gitti_Mi'] = df['Nobetten Goreve Gitti mi?'].apply(lambda x: 1 if str(x).strip().upper() == 'Y' else 0)
    #UCUSU SINIFI SINIFLANDIRMA
    def pozisyon_ata(sinif):
        val = str(sinif).strip().upper()
        if val.startswith('C'): return 'Kaptan'
        if val.startswith('P') and any(c.isdigit() for c in val): return 'Pilot'
        if val == 'P' or val.startswith(('V', 'K')): return 'Kabin Amiri'
        if val.startswith(('E', 'F', 'N', 'Q', 'Y', 'Z')): return 'Kabin Memuru'
        return 'Diğer'
    df['Pozisyon'] = df['Uçucu Sınıfı'].apply(pozisyon_ata)
    return df
#HESAPLAMA
@st.cache_data
def hesaplamalari_yap(f_df, risk_profile, lead_time, nobet_suresi, opt_saatler):
    num_days = f_df['Tarih'].nunique()
    daily_hourly = f_df.groupby(['Yıl', 'Tarih', 'Ay_No', 'Saat'], as_index=False).agg(
        Mevcut_Planlanan=('Gitti_Mi', 'count'), 
        Fiili_Kullanilan=('Gitti_Mi', 'sum')
    )
    # GUVEN ARALIGI TANIMLAMA
    master_plan = daily_hourly.groupby(['Yıl', 'Ay_No', 'Saat'], as_index=False).agg(
        Percentile_Kullanim=('Fiili_Kullanilan', lambda x: np.percentile(x, risk_profile))
    )
    master_plan['Onerilen_Güvenli_Kapasite'] = master_plan['Percentile_Kullanim'].apply(np.ceil).astype(int)
    daily_detail = pd.merge(
        daily_hourly, 
        master_plan[['Yıl', 'Ay_No', 'Saat', 'Onerilen_Güvenli_Kapasite']], 
        on=['Yıl', 'Ay_No', 'Saat'], 
        how='left'
    )
    daily_detail['Final_Kapasite'] = daily_detail.apply(
        lambda x: x['Onerilen_Güvenli_Kapasite'] if x['Saat'] in opt_saatler else x['Mevcut_Planlanan'], 
        axis=1
    )

    daily_detail['Timestamp'] = pd.to_datetime(daily_detail['Tarih'].astype(str) + ' ' + daily_detail['Saat'].astype(str) + ':00:00')
    daily_detail = daily_detail.sort_values('Timestamp').reset_index(drop=True)

    #TRANSFER ALGORITMASI
    #Önerilen adetlerin yetersiz kaldığı saatlerde nöbetlerin hangi saat başlangıçlı seferlerde kullanıldığına bakar, ilgili nöbet diliminden gidilen seferleri
    #kalkış tarihine göre sıralar. Örneğin 02:00 başlangıçlı nöbet 06:00 ve 08:00 başlangıçlı seferlerde kullanılmış, ve 02:00 için 1 adet öneride bulunduysa sistem,
    #06:00 başlangıçlı seferde o 1 adedin kullanıldığı değerlendirilir, 08:00 için ise önerilen adedin kullanılan adedin üstünde kalarak fazladan öneri bulununan
    #ilgili saat diliminden transfer yapılır. Bu yapılırken nöbet süreleri ve lead time saatlerine göre değerlendirilir.
    #Nöbet süresi dinamik olarak seçilir, örneğin 8 saat ise 02:00'de başlayan nöbetin 10:00'da sonlandığı değerlendirilir dolayısıyla 08:00 başlangıçlı seferde bu
    #nöbet dilimi kullanılabilir. Bunun kontrolü için nöbet süresi filtresi eklenmiştir. Ek olarak lead_time süresi eklenmiştir. Bu ise seferin kalkış tarihinden ortalama
    #4 saat öncesini ifade eder. Kişi nöbetten göreve en erken o saatte çağrılabilir. Görevi 08:00'de başlıyor ise en erken 04:00'da tebliğ yapılarak kişinin
    #sefere yetişeceği varsayılmıştır.
    daily_detail['Kalan_Bos_Kapasite'] = (daily_detail['Final_Kapasite'] - daily_detail['Fiili_Kullanilan']).clip(lower=0)
    daily_detail['Transfer_Detay'] = ""; daily_detail['Cozulen_Adet'] = 0
    went_df = f_df[f_df['Gitti_Mi'] == 1].copy()
    for idx, row in daily_detail[daily_detail['Fiili_Kullanilan'] > daily_detail['Final_Kapasite']].iterrows():
        tarih_saat = row['Timestamp']
        bu_saatteki_seferler = went_df[(went_df['Nobet Baslangic Tarihi'] == tarih_saat)].sort_values('Kalkis Tarihi', ascending=False)
        limit = int(row['Final_Kapasite'])
        fazla_seferler = bu_saatteki_seferler.iloc[0 : (int(row['Fiili_Kullanilan']) - limit)]
        cozulen = 0; notlar = []
        for _, sefer in fazla_seferler.iterrows():
            kalkis = sefer['Kalkis Tarihi']
            if pd.isna(kalkis): continue
            # Eski kısıtlı mantık yerine:
            cagri_saati = kalkis - timedelta(hours=lead_time) # Örn: 12:30 - 4 = 08:30

            aday_saatler = daily_detail[
                # KURAL 1: Nöbet, çağrı saatinden önce başlamış olmalı
                (daily_detail['Timestamp'] <= cagri_saati) & 
                
                # KURAL 2: Nöbetin bitişi, çağrı saatinden sonra olmalı 
                # (Yani kişi o an hala görevde olmalı)
                (daily_detail['Timestamp'] > cagri_saati - timedelta(hours=nobet_suresi)) &
                
                (daily_detail['Kalan_Bos_Kapasite'] > 0)
            ].sort_values('Timestamp', ascending=True)
            if not aday_saatler.empty:
                p_idx = aday_saatler.index[0]
                daily_detail.at[p_idx, 'Kalan_Bos_Kapasite'] -= 1
                cozulen += 1
                v_saat = daily_detail.at[p_idx, 'Timestamp'].strftime('%H:00')
                notlar.append(f"{kalkis.strftime('%H:%M')} seferi {v_saat} nöbetinden transfer edildi.")
                # Yenisi (Hangi satırdan veri çektiğini ifşa eder):
                n_baslama = sefer['Nobet Baslangic Tarihi']
                notlar.append(f"Kalkış:{kalkis} (Kaynak Nöbet:{n_baslama}) -> Yeni Nöbet:{v_saat}")
        daily_detail.at[idx, 'Cozulen_Adet'] = cozulen
        if notlar: daily_detail.at[idx, 'Transfer_Detay'] = " | ".join(notlar)
    # RISK TANIMI
    daily_detail['Riskli_mi?'] = daily_detail.apply(lambda r: 'Güvenli' if (r['Fiili_Kullanilan'] - r['Final_Kapasite']) <= 0 else ('TRANSFER İLE ÇÖZÜLDÜ' if r['Cozulen_Adet'] >= (r['Fiili_Kullanilan'] - r['Final_Kapasite']) else 'GERÇEK RİSK'), axis=1)
    daily_detail['Gercek_Fark'] = daily_detail.apply(lambda x: (x['Fiili_Kullanilan'] - x['Final_Kapasite'] - x['Cozulen_Adet']) if x['Riskli_mi?'] == 'GERÇEK RİSK' else 0, axis=1)
    return daily_detail, master_plan, num_days
# SIDEBAR FILTRELERI
uploaded_file = st.sidebar.file_uploader("Nöbet Verisi Yükle", type=["csv", "xlsx"])
if uploaded_file:
    df = veriyi_hazirla(uploaded_file)
    if 'opt_saatler_btn' not in st.session_state:
        st.session_state.opt_saatler_btn = set()
    tab_ana, tab_grafik, tab_planlamaci, tab_strateji = st.tabs(["🔍 Operasyonel Analiz", "📈 Görsel Analiz (Dashboard)", "📅 Planlamacı Ekranı", "🏆 Yönetici Strateji Özeti"])
    st.sidebar.header("🎯 Analiz Filtreleri")
    sel_yil = st.sidebar.multiselect("Yıl", sorted(df['Yıl'].unique(), reverse=True), default=sorted(df['Yıl'].unique(), reverse=True))
    sel_base = st.sidebar.selectbox("Base", sorted(df['Base'].unique()))
    sel_filo = st.sidebar.selectbox("Baz Filo", sorted(df['Baz Filo'].unique()))
    with st.sidebar.expander("🛡️ Nöbet Özellikleri", expanded=False):
        sel_n_tipi = st.multiselect("Nöbet Tipi", sorted(df['N_Tipi'].unique()), default=sorted(df['N_Tipi'].unique()))
        sel_n_lokasyon = st.multiselect("Lokasyon", sorted(df['N_Lokasyon'].unique()), default=sorted(df['N_Lokasyon'].unique()))
        sel_n_filo_detay = st.multiselect("Nöbet Filo", sorted(df['N_Filo'].unique()), default=sorted(df['N_Filo'].unique()))
        sel_n_rol = st.multiselect("Nöbet Rolü", sorted(df['N_Rol'].unique()), default=sorted(df['N_Rol'].unique()))
    available_positions = sorted(df[df['Pozisyon'] != 'Diğer']['Pozisyon'].unique())
    sel_poz = st.sidebar.selectbox("Pozisyon", available_positions)
    relevant_classes = sorted(df[df['Pozisyon'] == sel_poz]['Uçucu Sınıfı'].unique())
    sel_ucucu_sinifi_filtre = st.sidebar.multiselect(f"Uçucu Sınıfı Alt Detayı", options=relevant_classes, default=relevant_classes)
    sel_tur = st.sidebar.selectbox("Nöbet Türü", sorted(df['Nöbet Türü'].unique()))
    sel_aylar = st.sidebar.multiselect("Aylar", list(AY_MAP.values()), default=list(AY_MAP.values()))
    risk_profile = st.sidebar.select_slider("Güven Aralığı (%)", options=[70,75,80, 85, 90, 95, 100], value=100)
    nobet_suresi = st.sidebar.slider("Nöbet Mesai Süresi (Saat)", 4, 12, 8)
    lead_time = 4
    opt_saatler = st.session_state.opt_saatler_btn
    mask = (df['Yıl'].isin(sel_yil)) & (df['Base'] == sel_base) & (df['Baz Filo'] == sel_filo) & \
            (df['N_Tipi'].isin(sel_n_tipi)) & (df['N_Lokasyon'].isin(sel_n_lokasyon)) & \
            (df['N_Filo'].isin(sel_n_filo_detay)) & (df['N_Rol'].isin(sel_n_rol)) & \
            (df['Uçucu Sınıfı'].isin(sel_ucucu_sinifi_filtre)) & (df['Pozisyon'] == sel_poz) & \
            (df['Nöbet Türü'] == sel_tur) & (df['Ay_TR'].isin(sel_aylar))
    f_df = df[mask].copy()
    if f_df.empty:
        st.warning("⚠️ Seçilen kriterlere uygun veri bulunamadı.")
    else:
        # HESAPLAMALAR BURADA TEK SEFERDE YAPILIYOR
        daily_detail, master_plan, num_days = hesaplamalari_yap(f_df, risk_profile, lead_time, nobet_suresi, opt_saatler)
        # ORTAK METRİKLER
        total_k_sum = daily_detail['Fiili_Kullanilan'].sum()
        avg_p = daily_detail['Mevcut_Planlanan'].sum() / num_days
        avg_k = total_k_sum / num_days
        avg_final = daily_detail['Final_Kapasite'].sum() / num_days
        # Risk Hesaplamaları (Saatlik ve Yöneticinin Kişi Bazlı Mantığı)
        risk_adet_sonrasi = (daily_detail['Riskli_mi?'] == 'GERÇEK RİSK').sum()
        risk_orani_sonrasi = (risk_adet_sonrasi / len(daily_detail) * 100) if len(daily_detail) > 0 else 0
        yeni_risk_tanimi = (daily_detail['Gercek_Fark'].sum() / total_k_sum * 100) if total_k_sum > 0 else 0

        #KPI KARTLARI TASARIMI
        with tab_ana:
            st.title(f"📊 {sel_base} | {sel_filo} | {sel_poz} Analizi")
            k1, k2, k3, k4, k5, k6 = st.columns(6)
            k1.markdown(f'<div class="kpi-card"><div class="kpi-title">Mevcut Ort. Plan</div><div class="kpi-value">{avg_p:.1f}</div></div>', unsafe_allow_html=True)
            k2.markdown(f'<div class="kpi-card"><div class="kpi-title">Mevcut Ort. Kullanım</div><div class="kpi-value">{avg_k:.1f}</div></div>', unsafe_allow_html=True)
            k3.markdown(f'<div class="kpi-card"><div class="kpi-title">Yeni Ort. Kapasite</div><div class="kpi-value">{avg_final:.1f}</div></div>', unsafe_allow_html=True)
            k4.markdown(f'<div class="kpi-card"><div class="kpi-title">Net Tasarruf (Günlük Kişi)</div><div class="kpi-value">{max(0, avg_p - avg_final):.1f}</div></div>', unsafe_allow_html=True)
            k5.markdown(f'<div class="kpi-card" style="border-left-color: #bc4749;"><div class="kpi-title">Efektif Saatlik Risk</div><div class="kpi-value">%{risk_orani_sonrasi:.1f}</div></div>', unsafe_allow_html=True)
            k6.markdown(f'<div class="kpi-card" style="border-left-color: #2a9d8f;"><div class="kpi-title">Yön. Risk Endeksi</div><div class="kpi-value">%{yeni_risk_tanimi:.1f}</div></div>', unsafe_allow_html=True)
            st.dataframe(daily_detail[['Tarih', 'Saat', 'Mevcut_Planlanan', 'Fiili_Kullanilan', 'Final_Kapasite', 'Riskli_mi?', 'Gercek_Fark', 'Transfer_Detay']], use_container_width=True, hide_index=True)
        
        #OPERASYONEL ANALIZ SAYFASI
        with tab_grafik:
            st.title("📈 Stratejik Operasyon Paneli")
            c1, c2, c3 = st.columns(3)
            with c1:
                tasarruf_yuzde = ((avg_p - avg_final) / avg_p) * 100 if avg_p > 0 else 0
                fig_g1 = row_go.Figure(row_go.Indicator(
                    mode = "gauge+number", value = tasarruf_yuzde,
                    title = {'text': "Kapasite Tasarrufu (%)", 'font': {'size': 16}},
                    gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#2a9d8f"}}))
                fig_g1.update_layout(height=250, margin=dict(t=30, b=0, l=30, r=30))
                st.plotly_chart(fig_g1, use_container_width=True)
            with c2:
                fig_g2 = row_go.Figure(row_go.Indicator(
                    mode = "gauge+number", value = yeni_risk_tanimi,
                    title = {'text': "Yönetsel Risk Endeksi (%)", 'font': {'size': 16}},
                    gauge = {'axis': {'range': [0, 10]}, 'bar': {'color': "#bc4749"}}))
                fig_g2.update_layout(height=250, margin=dict(t=30, b=0, l=30, r=30))
                st.plotly_chart(fig_g2, use_container_width=True)
            with c3:
                fig_g3 = row_go.Figure(row_go.Indicator(
                    mode = "gauge+number", value = 100 - risk_orani_sonrasi,
                    title = {'text': "Operasyonel Güvenlik (%)", 'font': {'size': 16}},
                    gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#264653"}}))
                fig_g3.update_layout(height=250, margin=dict(t=30, b=0, l=30, r=30))
                st.plotly_chart(fig_g3, use_container_width=True)
            st.divider()
            st.subheader("🕵️ Detaylı Kapasite İncelemesi")
            fig_main = row_go.Figure()
            fig_main.add_trace(row_go.Scatter(x=daily_detail['Timestamp'], y=daily_detail['Final_Kapasite'], 
                                              name='Seçili Limit', line=dict(color='#2a9d8f', width=3, shape='hv'),
                                              fill='tozeroy', fillcolor='rgba(42, 157, 143, 0.1)'))
            fig_main.add_trace(row_go.Scatter(x=daily_detail['Timestamp'], y=daily_detail['Fiili_Kullanilan'], 
                                              name='Gerçek İhtiyaç', line=dict(color='#bc4749', width=2)))
            fig_main.update_xaxes(rangeslider_visible=True)
            fig_main.update_layout(hovermode="x unified", height=500, template="plotly_white")
            st.plotly_chart(fig_main, use_container_width=True)
            st.divider()
            st.subheader("🔥 Saatlik Risk ve Yoğunluk Haritası")
            heatmap_data = daily_detail.pivot_table(index='Saat', columns='Tarih', values='Gercek_Fark', aggfunc='sum')
            fig_heat = px.imshow(heatmap_data, labels=dict(x="Gün", y="Saat", color="Eksik Kişi"),
                                color_continuous_scale='Reds', aspect="auto")
            st.plotly_chart(fig_heat, use_container_width=True)

            # --- 📈 Outlier ve Dağılım Analizi (tab_grafik bloğunun sonuna ekle) ---
            st.divider()
            st.subheader("🕵️ Saatlik Detaylı İhtiyaç Analizi & Outliers")
            st.caption("Bu bölüm, seçilen saatteki ihtiyacın ay içindeki dağılımını gösterir. Noktaların ana kümeden uzaklaşması aykırı (extreme) günleri temsil eder.")
            # 1. Saat Seçimi (Box Plot ve Scatter için ortak)
            selected_hour = st.selectbox("Dağılımını incelemek istediğiniz saati seçin:", 
                                         options=range(24), 
                                         format_func=lambda x: f"Saat {x:02d}:00",
                                         key="analysis_hour_select")
            # 2. Veriyi Hazırla ve Hataları Temizle
            hour_data = daily_detail[daily_detail['Saat'] == selected_hour].copy()
            hour_data['Fiili_Kullanilan'] = hour_data['Fiili_Kullanilan'].fillna(0) # NaN Hatası önlemi
            if not hour_data.empty:
                col_graph1, col_graph2 = st.columns(2)
                with col_graph1:
                    # Kutu Grafiği (Dağılımın karakterini anlamak için)
                    fig_box = px.box(
                        hour_data, 
                        y="Fiili_Kullanilan", 
                        points="all", 
                        title=f"Saat {selected_hour:02d}:00 Dağılım Karakteristiği",
                        labels={'Fiili_Kullanilan': 'İhtiyaç Adedi'},
                        color_discrete_sequence=['#2a9d8f']
                    )
                    st.plotly_chart(fig_box, use_container_width=True)
                with col_graph2:
                    # Zaman Serisi Dağılımı (Hangi gün patlama yaşanmış?)
                    fig_scatter_detail = px.scatter(
                        hour_data, 
                        x='Tarih', 
                        y='Fiili_Kullanilan',
                        color='Fiili_Kullanilan',
                        size='Fiili_Kullanilan',
                        title=f"Saat {selected_hour:02d}:00 Günlük Değişim",
                        color_continuous_scale='Reds'
                    )
                    # Ortalama Çizgisi
                    avg_val = hour_data['Fiili_Kullanilan'].mean()
                    fig_scatter_detail.add_hline(y=avg_val, line_dash="dash", line_color="blue", annotation_text="Ortalama")
                    st.plotly_chart(fig_scatter_detail, use_container_width=True)
                # Özet Bilgi Notu
                st.info(f"💡 **Analiz:** Saat {selected_hour:02d}:00 için maksimum ihtiyaç **{int(hour_data['Fiili_Kullanilan'].max())}** kişi iken, günlerin çoğunda ihtiyaç **{int(hour_data['Fiili_Kullanilan'].quantile(0.75))}** kişinin altında kalmıştır.")
            else:
                st.warning("Bu saat dilimi için veri bulunamadı.")
            # --- Tab Grafik İçine Eklenecek Scatter Plot ---
            # --- Saat Bazlı Outlier Analizi ---
            st.divider()
            st.subheader("🕵️ Saatlik Detaylı İhtiyaç Analizi")
            # 1. Saat Seçimi
            selected_hour = st.selectbox("Analiz etmek istediğiniz saati seçin:", 
                                         options=range(24), 
                                         format_func=lambda x: f"Saat {x:02d}:00")
            # 2. Sadece o saate ait veriyi filtrele
            hour_data = daily_detail[daily_detail['Saat'] == selected_hour].copy()
            if not hour_data.empty:
                # Saatin genel karakteristiğini hesapla (Ortalama ve Max)
                avg_req = hour_data['Fiili_Kullanilan'].mean()
                max_req = hour_data['Fiili_Kullanilan'].max()
                st.info(f"Seçilen saatte ortalama ihtiyaç **{avg_req:.1f}**, maksimum ihtiyaç ise **{max_req}** kişi olmuştur.")
                # İhtiyaç Dağılım Grafiği (Scatter + Trend)
                fig_hour = px.scatter(
                    hour_data, 
                    x='Tarih', 
                    y='Fiili_Kullanilan',
                    title=f"Saat {selected_hour:02d}:00 için Günlük İhtiyaç Değişimi",
                    labels={'Fiili_Kullanilan': 'İhtiyaç Duyulan Adet', 'Tarih': 'Günler'},
                    color='Fiili_Kullanilan',
                    color_continuous_scale='Reds'
                )
                # Ortalama referans çizgisi ekle
                fig_hour.add_hline(y=avg_req, line_dash="dash", line_color="blue", annotation_text="Ortalama")
                st.plotly_chart(fig_hour, use_container_width=True)
            else:
                st.warning("Seçilen saat için veri bulunamadı.")
        with tab_planlamaci:
            st.title("📅 Planlamacı Karar Destek")
            cal_df = daily_detail.groupby(['Tarih', 'Ay_No']).agg(Toplam_Risk=('Gercek_Fark', 'sum'), Risk_Saat_Sayisi=('Riskli_mi?', lambda x: (x == 'GERÇEK RİSK').sum())).reset_index()
            cal_df['Tarih'] = pd.to_datetime(cal_df['Tarih'])
            cal_df['Gün'] = cal_df['Tarih'].dt.day
            cal_df['H_Gunu'] = cal_df['Tarih'].dt.weekday
            cal_df['H_No'] = cal_df['Tarih'].dt.isocalendar().week
            sel_m = st.selectbox("Görüntülenecek Ay", sorted(cal_df['Ay_No'].unique()), format_func=lambda x: AY_MAP.get(x))
            m_df = cal_df[cal_df['Ay_No'] == sel_m]
            gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
            rows_html = []
            for w in sorted(m_df['H_No'].unique()):
                cols_html = []
                for d_idx in range(7):
                    day_item = m_df[(m_df['H_No'] == w) & (m_df['H_Gunu'] == d_idx)]
                    if not day_item.empty:
                        rv, rh, dn = day_item['Toplam_Risk'].values[0], day_item['Risk_Saat_Sayisi'].values[0], day_item['Gün'].values[0]
                        bg_color = "#d8f3dc" if rv == 0 else "#ffadad" if rv > 5 else "#ffd6a5"
                        cols_html.append(f'<td class="calendar-td" style="background-color:{bg_color};"><div class="day-num">{dn}</div><div class="risk-text">Eksik: {int(rv)}<br>Saat: {int(rh)}</div></td>')
                    else:
                        cols_html.append('<td class="calendar-td" style="background-color:#f9f9f9;"></td>')
                rows_html.append(f"<tr>{''.join(cols_html)}</tr>")
            st.markdown(f'<table class="calendar-table"><thead><tr>{"".join([f"<th>{g}</th>" for g in gunler])}</tr></thead><tbody>{"".join(rows_html)}</tbody></table>', unsafe_allow_html=True)
        
        #YONETICI STRATEJI OZETI SAYFASI
        
        
        with tab_strateji:
            st.title("🎯 Senaryo & Kapasite Simülatörü")
            st.markdown("##### 🕑 Optimizasyon Saatlerini Seçin")
            st.caption("Seçilen saatlerde önerilen güvenli kapasiteye düşülür, diğer saatlerde plan korunur.")
            # --- TÜMÜNÜ SEÇ / KALDIR BUTONLARI ---
            col_all1, col_all2, _ = st.columns([1, 1, 6])
            if col_all1.button("✅ Tümünü Seç", use_container_width=True):
                st.session_state.opt_saatler_btn = set(range(24))
                st.rerun()
            if col_all2.button("❌ Seçimleri Kaldır", use_container_width=True):
                st.session_state.opt_saatler_btn = set()
                st.rerun()
            st.write("") # Boşluk
            for row_idx in range(3): 
                cols = st.columns(8)
                for col_idx in range(8):
                    hour = row_idx * 8 + col_idx
                    is_active = hour in st.session_state.opt_saatler_btn
                    btn_type = "primary" if is_active else "secondary"
                    btn_label = f"{hour:02d}:00"
                    if cols[col_idx].button(btn_label, key=f"btn_h_{hour}", use_container_width=True, type=btn_type):
                        if is_active: st.session_state.opt_saatler_btn.remove(hour)
                        else: st.session_state.opt_saatler_btn.add(hour)
                        st.rerun()
            st.divider()
            res1, res2, res3 = st.columns(3)
            # Strateji sekmesi metriklerini ana hesaplamadan alıyoruz
            with res1:
                # Aylık tasarruf tahmini
                günlük_tasarruf_kişi = avg_p - avg_final
                aylik_toplam_tasarruf = günlük_tasarruf_kişi * 30
                st.markdown(f"""
<div style="background-color:#f8f9fa; padding:15px; border-radius:12px; text-align:center; border-left:6px solid #C2272D;">
<div style="color:#C2272D; font-weight:bold; font-size:12px;">AYLIK TOPLAM TASARRUF</div>
<div style="font-size:28px; font-weight:bold;">{int(aylik_toplam_tasarruf)} <span style="font-size:14px;">Nöbet</span></div>
</div>
                """, unsafe_allow_html=True)
            with res2:
                # Yöneticinin risk endeksi
                risk_color = "#C2272D" if yeni_risk_tanimi > 5 else "#f4a261" if yeni_risk_tanimi > 2 else "#2a9d8f"
                st.markdown(f"""
<div style="background-color:#f8f9fa; padding:15px; border-radius:12px; text-align:center; border-left:6px solid {risk_color};">
<div style="color:{risk_color}; font-weight:bold; font-size:12px;">YÖNETSEL RİSK ENDEKSİ (Eksik/Toplam)</div>
<div style="font-size:28px; font-weight:bold;">%{yeni_risk_tanimi:.2f}</div>
<div style="font-size:11px; color:gray;">Toplam {int(daily_detail['Gercek_Fark'].sum())} kişi karşılanamadı.</div>
</div>
                """, unsafe_allow_html=True)
            with res3:
                st.markdown(f"""
<div style="background-color:#f8f9fa; padding:15px; border-radius:12px; text-align:center; border-left:6px solid #4A4A4A;">
<div style="color:#4A4A4A; font-weight:bold; font-size:12px;">GÜNLÜK ORT. TASARRUF</div>
<div style="font-size:28px; font-weight:bold;">{max(0, avg_p - avg_final):.1f} <span style="font-size:14px;">Kişi</span></div>
</div>
                """, unsafe_allow_html=True)
            st.subheader("📊 Kapasite ve İhtiyaç Kıyaslaması (Ortalama)")
            # Ortalama saatlik görünüm
            hourly_summary = daily_detail.groupby('Saat').agg(
                Mevcut_Ort_Plan=('Mevcut_Planlanan', 'mean'),
                Fiili_Ort_Kullanim=('Fiili_Kullanilan', 'mean'),
                Final_Kapasite_Ort=('Final_Kapasite', 'mean'),
                Efektif_Risk_Ort=('Gercek_Fark', 'mean')
            ).reset_index()
            # --- YENİ GRAFİK KODUN BURAYA GELİYOR ---
            fig_sim = row_go.Figure()
            # Mevcut Planlanan (Arka Plan - Koyu Renk)
            fig_sim.add_trace(row_go.Bar(
                x=hourly_summary['Saat'],
                y=hourly_summary['Mevcut_Ort_Plan'],
                name='Mevcut Planlanan Kapasite',
                marker_color='dimgray',
                opacity=0.7
            ))
            # Önerilen Kapasite (Ön Plan - Açık Renk)
            fig_sim.add_trace(row_go.Bar(
                x=hourly_summary['Saat'],
                y=hourly_summary['Final_Kapasite_Ort'],
                name='Önerilen Güvenli Kapasite',
                marker_color='lightsteelblue',
                offsetgroup=0
            ))
            # Fiili İhtiyaç (Çizgi)
            fig_sim.add_trace(row_go.Scatter(
                x=hourly_summary['Saat'],
                y=hourly_summary['Fiili_Ort_Kullanim'],
                name='Fiili İhtiyaç (Ortalama)',
                line=dict(color='firebrick', width=3)
            ))
            fig_sim.update_layout(
                barmode='overlay', 
                height=500, 
                hovermode="x unified", 
                template="plotly_white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_sim, use_container_width=True)

            st.markdown("##### 📋 Seçili Saatlerin Kapasite Detayları")
            selected_hours_table = hourly_summary[hourly_summary['Saat'].isin(opt_saatler)].copy()
            if not selected_hours_table.empty:
                selected_hours_table.columns = ["Saat", "Mevcut Plan (Ort)", "İhtiyaç (Ort)", "Yeni Kapasite (Ort)", "Gerçek Risk (Kişi)"]
                st.dataframe(selected_hours_table.round(2).style.background_gradient(subset=["Gerçek Risk (Kişi)"], cmap="Reds"), use_container_width=True, hide_index=True)
            else:
                st.info("Saat seçimi yapıldığında detaylı tablo burada belirecektir.")

            # --- 📊 Nöbetçi Kullanım Frekans Analizi (YENİ EKLEME) ---
            st.divider()
            st.subheader("🔢 Nöbetçi Kullanım Frekansları")
            st.caption("Seçilen saatte, geçmişte kaç gün kaç adet nöbetçi kullanıldığını gösterir. (Örn: Saat 05:00'te 8 kişinin kullanıldığı toplam gün sayısı)")
            # Saat seçimi için küçük bir kolon yapısı
            f_col1, f_col2 = st.columns([1, 3])
            with f_col1:
                freq_hour = st.selectbox(
                    "İstatistik için Saat Seçin:", 
                    options=range(24), 
                    format_func=lambda x: f"{x:02d}:00",
                    key="freq_hour_selector"
                )
            # Veriyi hesapla: O saatteki fiili kullanım adetlerini say
            freq_data = daily_detail[daily_detail['Saat'] == freq_hour]['Fiili_Kullanilan'].value_counts().reset_index()
            freq_data.columns = ['Kullanılan_Nöbetçi_Adedi', 'Gün_Sayısı']
            freq_data = freq_data.sort_values('Kullanılan_Nöbetçi_Adedi')
            with f_col2:
                # Frekans Grafiği
                fig_freq = row_go.Figure()
                fig_freq.add_trace(row_go.Bar(
                    x=freq_data['Kullanılan_Nöbetçi_Adedi'],
                    y=freq_data['Gün_Sayısı'],
                    text=freq_data['Gün_Sayısı'],
                    textposition='auto',
                    marker_color='teal'
                ))
                fig_freq.update_layout(
                    title=f"Saat {freq_hour:02d}:00 için Kullanım Dağılımı",
                    xaxis_title="Fiili Kullanılan Nöbetçi Sayısı",
                    yaxis_title="Gün Adedi",
                    height=350,
                    template="plotly_white"
                )
                st.plotly_chart(fig_freq, use_container_width=True)
            # Detay Tablosu (Opsiyonel)
            with st.expander(f"Saat {freq_hour:02d}:00 İstatistik Detay Tablosu"):
                st.table(freq_data.set_index('Kullanılan_Nöbetçi_Adedi').T)
    st.sidebar.success("💡 Analiz başarıyla güncellendi.") 
