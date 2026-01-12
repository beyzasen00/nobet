import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import plotly.express as px  
import plotly.graph_objects as row_go

st.set_page_config(layout="wide", page_title="Nöbet Risk Analiz")

# --- CSS ---
st.markdown("""
<style>
.kpi-card { background-color: #f8f9fa; padding: 20px; border-radius: 15px; border-left: 6px solid #a3b18a; text-align: center; margin-bottom: 15px; }
.kpi-title { font-size: 11px; color: #6c757d; font-weight: bold; text-transform: uppercase; }
.kpi-value { font-size: 24px; color: #344e41; font-weight: bold; }
.highlight-box { background-color: #e9f5db; padding: 15px; border-radius: 10px; border-left: 5px solid #2d6a4f; margin: 20px 0; font-size: 14px; }
</style>
""", unsafe_allow_html=True)

# --- VERİ YÜKLEME ---
uploaded_file = st.sidebar.file_uploader("Nöbet Verisi Yükle", type=["csv", "xlsx"])

if uploaded_file:
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip()

    # --- Veri Hazırlık ---
    df['Base'] = df['Base'].astype(str).str.strip().str.upper()
    df['Baz Filo'] = df['Baz Filo'].astype(str).str.strip()
    df['Nöbet Kodu'] = df['Nobet Kodu'].astype(str).str.strip()
    df['Uçucu Sınıfı'] = df['Uçucu Sınıfı'].astype(str).str.strip()
    
    def nobet_parcala(kod):
        kod = str(kod).upper()
        if len(kod) < 5: 
            return "Bilinmiyor", "Bilinmiyor", "0", "Bilinmiyor", "Bilinmiyor"
        lokasyon = "Home" if kod[0] == 'H' else "Airport" if kod[0] == 'A' else "Diğer"
        tip = "ER" if kod[1] == 'E' else "Layover" if kod[1] == 'L' else "Gitgel" if kod[1] == 'G' else "Diğer"
        gun = kod[2]
        filo = "A330" if kod[3] == 'E' else "B777" if kod[3] == 'J' else "B738/A320" if kod[3] == 'M' else "A320" if kod[3] == 'Z' else "Diğer"
        rol = "Amir/Memur" if kod[4] == 'S' else "A330 Arka Amir" if kod[4] == 'K' else "B777 Arka Amir" if kod[4] == 'V' else "Diğer"
        return lokasyon, tip, gun, filo, rol

    df[['N_Lokasyon', 'N_Tipi', 'N_Gun', 'N_Filo', 'N_Rol']] = df['Nöbet Kodu'].apply(lambda x: pd.Series(nobet_parcala(x)))
    df['Nobet Baslangic Tarihi'] = pd.to_datetime(df['Nobet Baslangic Tarihi'])
    df['Tarih'] = df['Nobet Baslangic Tarihi'].dt.date
    df['Saat'] = df['Nobet Baslangic Tarihi'].dt.hour
    df['Yıl'] = df['Nobet Baslangic Tarihi'].dt.year

    ay_map = {'January': 'Ocak', 'February': 'Şubat', 'March': 'Mart', 'April': 'Nisan', 'May': 'Mayıs', 'June': 'Haziran',
              'July': 'Temmuz', 'August': 'Ağustos', 'September': 'Eylül', 'October': 'Ekim', 'November': 'Kasım', 'December': 'Aralık'}
    df['Ay_TR'] = df['Nobet Baslangic Tarihi'].dt.month_name().map(ay_map)
    df['Gitti_Mi'] = df['Nobetten Goreve Gitti mi?'].apply(lambda x: 1 if str(x).strip().upper() == 'Y' else 0)

    sezon_map = {'Kış': ['Kasım','Aralık', 'Ocak', 'Şubat', 'Mart'], 'Yaz1': ['Haziran', 'Temmuz', 'Ağustos', 'Eylül'], 'Yaz2': ['Nisan', 'Mayıs', 'Ekim']}
    def get_sezon(ay):
        for s, aylar in sezon_map.items():
            if ay in aylar: return s
        return 'Diğer'
    df['Sezon'] = df['Ay_TR'].apply(get_sezon)

    def pozisyon_ata(sinif):
        val = str(sinif).strip().upper()
        if val.startswith('C'): return 'Kaptan'
        if val.startswith('P') and any(c.isdigit() for c in val): return 'Pilot'
        if val == 'P' or val.startswith(('V', 'K')): return 'Kabin Amiri'
        if val.startswith(('E', 'F', 'N', 'Q', 'Y', 'Z')): return 'Kabin Memuru'
        return 'Diğer'
    df['Pozisyon'] = df['Uçucu Sınıfı'].apply(pozisyon_ata)

    tab_ana, tab_planlamaci, tab_strateji = st.tabs(["🔍 Operasyonel Analiz", "📅 Planlamacı Ekranı", "🏆 Yönetici Strateji Özeti"])

    with tab_ana:
        st.sidebar.header("🎯 Analiz Filtreleri")
        sel_yil = st.sidebar.multiselect("Yıl", sorted(df['Yıl'].unique(), reverse=True), default=sorted(df['Yıl'].unique(), reverse=True))
        sel_base = st.sidebar.selectbox("Base", sorted(df['Base'].unique()))
        sel_filo = st.sidebar.selectbox("Baz Filo", sorted(df['Baz Filo'].unique()))
        
        with st.sidebar.expander("🛡️ Nöbet Kodu Özellikleri", expanded=False):
            sel_n_tipi = st.multiselect("Nöbet Tipi (E/L/G)", sorted(df['N_Tipi'].unique()), default=sorted(df['N_Tipi'].unique()))
            sel_n_lokasyon = st.multiselect("Lokasyon (H/A)", sorted(df['N_Lokasyon'].unique()), default=sorted(df['N_Lokasyon'].unique()))
            sel_n_filo_detay = st.multiselect("Nöbet Filo Karşılığı", sorted(df['N_Filo'].unique()), default=sorted(df['N_Filo'].unique()))
            sel_n_rol = st.multiselect("Nöbet Rolü", sorted(df['N_Rol'].unique()), default=sorted(df['N_Rol'].unique()))

        sel_ucucu_sinifi_filtre = st.sidebar.multiselect("Uçucu Sınıfı", sorted(df['Uçucu Sınıfı'].unique()), default=sorted(df['Uçucu Sınıfı'].unique()))
        available_positions = sorted(df[df['Pozisyon'] != 'Diğer']['Pozisyon'].unique())
        sel_poz = st.sidebar.selectbox("Pozisyon", available_positions)
        sel_tur = st.sidebar.selectbox("Nöbet Türü", sorted(df['Nöbet Türü'].unique()))
        sel_aylar = st.sidebar.multiselect("Aylar", list(ay_map.values()), default=list(ay_map.values())[:3])
        risk_profile = st.sidebar.select_slider("Güven Aralığı (%)", options=[70,75,80, 85, 90, 95, 100], value=100)

        mask = (df['Yıl'].isin(sel_yil)) & (df['Base'] == sel_base) & (df['Baz Filo'] == sel_filo) & \
               (df['N_Tipi'].isin(sel_n_tipi)) & (df['N_Lokasyon'].isin(sel_n_lokasyon)) & \
               (df['N_Filo'].isin(sel_n_filo_detay)) & (df['N_Rol'].isin(sel_n_rol)) & \
               (df['Uçucu Sınıfı'].isin(sel_ucucu_sinifi_filtre)) & (df['Pozisyon'] == sel_poz) & \
               (df['Nöbet Türü'] == sel_tur) & (df['Ay_TR'].isin(sel_aylar))
        
        f_df = df[mask].copy()

        if f_df.empty:
            st.warning("⚠️ Seçilen kriterlere uygun veri bulunamadı.")
        else:
            num_days = f_df['Tarih'].nunique()
            daily_hourly = f_df.groupby(['Tarih', 'Saat']).agg(Mevcut_Planlanan=('Gitti_Mi', 'count'), Fiili_Kullanilan=('Gitti_Mi', 'sum')).reset_index()
            master_plan = daily_hourly.groupby('Saat').agg(Percentile_Kullanim=('Fiili_Kullanilan', lambda x: np.percentile(x, risk_profile))).reset_index()
            master_plan['Onerilen_Güvenli_Kapasite'] = master_plan['Percentile_Kullanim'].apply(np.ceil).astype(int)
            
            daily_detail = pd.merge(daily_hourly, master_plan[['Saat', 'Onerilen_Güvenli_Kapasite']], on='Saat')
            daily_detail['Riskli_mi?'] = daily_detail.apply(lambda x: 'RİSK' if x['Fiili_Kullanilan'] > x['Onerilen_Güvenli_Kapasite'] else 'Güvenli', axis=1)
            
            total_k_sum = daily_detail['Fiili_Kullanilan'].sum()
            total_p_sum = daily_detail['Mevcut_Planlanan'].sum()
            total_o_sum = daily_detail['Onerilen_Güvenli_Kapasite'].sum()

            riskli_satirlar = daily_detail[daily_detail['Riskli_mi?'] == 'RİSK'].copy()
            riskli_satirlar['Fark'] = riskli_satirlar['Onerilen_Güvenli_Kapasite'] - riskli_satirlar['Fiili_Kullanilan']
            toplam_risk_fark = abs(riskli_satirlar['Fark'].sum())
            yeni_risk_tanimi = (toplam_risk_fark / total_k_sum * 100) if total_k_sum > 0 else 0
            
            # KPI TEMEL DEĞERLERİ
            avg_p = total_p_sum / num_days
            avg_k = total_k_sum / num_days
            avg_o = total_o_sum / num_days
            avg_s = avg_p - avg_o

            # KESİN DOĞRU FORMÜLASYONLAR:
            mevcut_doluluk = (avg_k / avg_p * 100) if avg_p > 0 else 0
            onerilen_doluluk = (avg_k / avg_o * 100) if avg_o > 0 else 0
            risk_ratio = ((daily_detail['Riskli_mi?'] == 'RİSK').sum() / len(daily_detail) * 100) if len(daily_detail) > 0 else 0

            st.title(f"📊 {sel_base} | {sel_filo} | {sel_poz} | {sel_tur} Analiz Paneli")

            k1, k2, k3, k4, k5, k6 = st.columns(6)
            k1.markdown(f'<div class="kpi-card"><div class="kpi-title">Mevcut Ort. Plan</div><div class="kpi-value">{avg_p:.1f}</div></div>', unsafe_allow_html=True)
            k2.markdown(f'<div class="kpi-card"><div class="kpi-title">Mevcut Ort. Kullanım</div><div class="kpi-value">{avg_k:.1f}</div></div>', unsafe_allow_html=True)
            k3.markdown(f'<div class="kpi-card"><div class="kpi-title">Önerilen Kapasite</div><div class="kpi-value">{avg_o:.1f}</div></div>', unsafe_allow_html=True)
            k4.markdown(f'<div class="kpi-card"><div class="kpi-title">Net Tasarruf (Gün)</div><div class="kpi-value">{avg_s:.1f}</div></div>', unsafe_allow_html=True)
            k5.markdown(f'<div class="kpi-card" style="border-left-color: #bc4749;"><div class="kpi-title">Op. Risk Oranı</div><div class="kpi-value">%{risk_ratio:.1f}</div></div>', unsafe_allow_html=True)
            k6.markdown(f'<div class="kpi-card" style="border-left-color: #2a9d8f;"><div class="kpi-title">Yön. Risk Endeksi</div><div class="kpi-value">%{yeni_risk_tanimi:.1f}</div></div>', unsafe_allow_html=True)

            m1, m2 = st.columns(2)
            m1.markdown(f'<div class="kpi-card" style="border-left-color: #6d597a;"><div class="kpi-title">Mevcut Plan Kullanım Oranı</div><div class="kpi-value">%{mevcut_doluluk:.1f}</div></div>', unsafe_allow_html=True)
            m2.markdown(f'<div class="kpi-card" style="border-left-color: #f4a261;"><div class="kpi-title">Önerilen Plan Kullanım Oranı</div><div class="kpi-value">%{onerilen_doluluk:.1f}</div></div>', unsafe_allow_html=True)

            st.subheader("📋 1. Günlük & Saatlik Operasyonel Detay")
            daily_detail['Fark_Mevcut_Onerilen'] = daily_detail['Mevcut_Planlanan'] - daily_detail['Onerilen_Güvenli_Kapasite']
            summary_rows = pd.DataFrame({'Tarih': ['DÖNEM TOPLAMI', 'GÜNLÜK ORTALAMA (KPI)'], 'Saat': ['-', '-'], 'Mevcut_Planlanan': [total_p_sum, avg_p], 'Fiili_Kullanilan': [total_k_sum, avg_k], 'Onerilen_Güvenli_Kapasite': [total_o_sum, avg_o], 'Fark_Mevcut_Onerilen': [total_p_sum - total_o_sum, avg_s], 'Riskli_mi?': ['-', '-']})
            final_daily = pd.concat([daily_detail, summary_rows], ignore_index=True)
            
            def style_risk(row):
                if row['Riskli_mi?'] == 'RİSK': return ['background-color: #ffcccc'] * len(row)
                elif 'TOPLAMI' in str(row['Tarih']): return ['font-weight: bold; background-color: #f0f2f6'] * len(row)
                elif 'ORTALAMA' in str(row['Tarih']): return ['font-weight: bold; background-color: #e9f5db; color: #2d6a4f'] * len(row)
                return [''] * len(row)
            
            st.dataframe(final_daily.style.apply(style_risk, axis=1).format(precision=1), use_container_width=True)

            # --- YENİ EKLENEN BÖLÜM: 2 SAATLİK ANALİZ TABLOSU ---
            st.subheader("⏱️ 1.1. İki Saatlik Periyot Analizi (Özet)")
            
            # Periyot oluşturma fonksiyonu
            def get_2hr_label(saat):
                start = (saat // 2) * 2
                end = start + 1
                return f"{start:02d}:00 - {end:02d}:59"

            # Master plan üzerinden ortalamaları alarak 2 saatlik gruplama yapıyoruz
            master_plan['Mevcut_Ort_Planlanan'] = master_plan['Saat'].map(daily_detail.groupby('Saat')['Mevcut_Planlanan'].mean())
            master_plan['Mevcut_Ort_Kullanilan'] = master_plan['Saat'].map(daily_detail.groupby('Saat')['Fiili_Kullanilan'].mean())
            master_plan['2_Saat_Araligi'] = master_plan['Saat'].apply(get_2hr_label)

            two_hour_analysis = master_plan.groupby('2_Saat_Araligi').agg({
                'Mevcut_Ort_Planlanan': 'sum',
                'Mevcut_Ort_Kullanilan': 'sum',
                'Onerilen_Güvenli_Kapasite': 'sum'
            }).reset_index()

            two_hour_analysis.columns = ['Saat Aralığı', 'Mevcut Planlanan', 'Fiili Kullanılan', 'Önerilen Güvenli Kapasite']
            two_hour_analysis['Fark (Mevcut-Önerilen)'] = two_hour_analysis['Mevcut Planlanan'] - two_hour_analysis['Önerilen Güvenli Kapasite']
            two_hour_analysis['Riskli mi?'] = two_hour_analysis.apply(lambda x: 'RİSK' if x['Fiili Kullanılan'] > x['Önerilen Güvenli Kapasite'] else 'Güvenli', axis=1)

            st.dataframe(two_hour_analysis.style.apply(lambda x: ['background-color: #ffcccc' if x['Riskli mi?'] == 'RİSK' else '' for _ in x], axis=1).format(precision=1), use_container_width=True, hide_index=True)
            # --------------------------------------------------

            with st.expander(f"⚠️ Kritik Risk Analizi: Toplam {len(riskli_satirlar)} Riskli Saat"):
                if not riskli_satirlar.empty:
                    risk_total_row = pd.DataFrame({'Tarih': ['GRAND TOTAL'],'Saat': ['-'],'Mevcut_Planlanan': [riskli_satirlar['Mevcut_Planlanan'].sum()],'Fiili_Kullanilan': [riskli_satirlar['Fiili_Kullanilan'].sum()],'Onerilen_Güvenli_Kapasite': [riskli_satirlar['Onerilen_Güvenli_Kapasite'].sum()],'Fark': [riskli_satirlar['Fark'].sum()], 'Riskli_mi?': ['-']})
                    st.dataframe(pd.concat([riskli_satirlar, risk_total_row], ignore_index=True).style.apply(lambda x: ['font-weight: bold; background-color: #f0f2f6' if x['Tarih'] == 'GRAND TOTAL' else '' for _ in x], axis=1).format(precision=1), use_container_width=True)
                else:
                    st.success("Risk bulunamadı.")

            st.divider()
            st.subheader("📋 2. Saatlik Stratejik Şablon (Referans)")
            st.dataframe(master_plan[['Saat', 'Mevcut_Ort_Planlanan', 'Mevcut_Ort_Kullanilan', 'Onerilen_Güvenli_Kapasite']].style.format(precision=1), use_container_width=True)

            st.divider()
            st.subheader("🔥 3. Kullanım Yoğunluğu ve Dağılım Analizi (Heat Map)")
            heat_data = daily_detail.groupby(['Saat', 'Fiili_Kullanilan']).size().reset_index(name='Frekans')
            fig = px.density_heatmap(heat_data, x='Saat', y='Fiili_Kullanilan', z='Frekans', labels={'Saat': 'Nöbet Başlangıç Saati', 'Fiili_Kullanilan': 'Kullanılan Adet', 'Frekans': 'Gün Sayısı'}, color_continuous_scale="YlOrRd", text_auto=True)
            avg_line = daily_detail.groupby('Saat')['Fiili_Kullanilan'].mean().reset_index()
            fig.add_trace(row_go.Scatter(x=avg_line['Saat'], y=avg_line['Fiili_Kullanilan'], name='Ortalama Kullanım', line=dict(color='red', width=3, dash='dot')))
            fig.update_layout(xaxis=dict(tickmode='linear', tick0=0, dtick=1, range=[-0.5, 23.5]), height=500)
            st.plotly_chart(fig, use_container_width=True)

    with tab_planlamaci:
        st.title("📅 Planlamacı Karar Destek Ekranı")
        if not f_df.empty:
            p1, p2, p3 = st.columns(3)
            p1.markdown(f'<div class="kpi-card"><div class="kpi-title">Net Tasarruf (Günlük Adet)</div><div class="kpi-value">{avg_s:.1f}</div></div>', unsafe_allow_html=True)
            p2.markdown(f'<div class="kpi-card"><div class="kpi-title">Net Tasarruf (Dönem Toplam)</div><div class="kpi-value">{total_p_sum - total_o_sum:.0f}</div></div>', unsafe_allow_html=True)
            p3.markdown(f'<div class="kpi-card" style="border-left-color: #bc4749;"><div class="kpi-title">Operasyonel Risk</div><div class="kpi-value">%{risk_ratio:.1f}</div></div>', unsafe_allow_html=True)
            
            def saat_grubu_ata(saat):
                if 0 <= saat <= 6: return "00:00 - 06:00"
                if 7 <= saat <= 12: return "07:00 - 12:00"
                if 13 <= saat <= 17: return "13:00 - 17:00"
                if 18 <= saat <= 23: return "18:00 - 23:00"
                return "Diğer"
            
            st.subheader("🏢 1. Vardiya Bazlı Önerilen Kapasite")
            plan_master = master_plan.copy()
            plan_master['Saat Aralığı'] = plan_master['Saat'].apply(saat_grubu_ata)
            vardiya_ozet = plan_master.groupby('Saat Aralığı').agg(Toplam_Onerilen_Adet=('Onerilen_Güvenli_Kapasite', 'sum')).reset_index()
            st.dataframe(pd.concat([vardiya_ozet, pd.DataFrame({'Saat Aralığı': ['GRAND TOTAL'], 'Toplam_Onerilen_Adet': [vardiya_ozet['Toplam_Onerilen_Adet'].sum()]})], ignore_index=True).style.apply(lambda x: ['font-weight: bold; background-color: #f0f2f6' if x.name == len(vardiya_ozet) else '' for _ in x], axis=1).format(precision=1), use_container_width=True, hide_index=True)
            
            with st.expander("⏱️ 2. Saatlik Detay Plan Listesini Gör / Gizle"):
                detay_liste = plan_master[['Saat', 'Onerilen_Güvenli_Kapasite']].copy()
                detay_liste.columns = ['Saat', 'Önerilen Nöbetçi Sayısı']
                st.dataframe(pd.concat([detay_liste, pd.DataFrame({'Saat': ['TOPLAM'], 'Önerilen Nöbetçi Sayısı': [detay_liste['Önerilen Nöbetçi Sayısı'].sum()]})], ignore_index=True).style.apply(lambda x: ['font-weight: bold; background-color: #f0f2f6' if x.name == len(detay_liste) else '' for _ in x], axis=1).format(precision=0), use_container_width=True, hide_index=True)

    with tab_strateji:
        st.title("🚀 Global Senaryo ve Strateji Motoru")
        if 'strateji_sonuc' not in st.session_state: st.session_state.strateji_sonuc = None
        
        if st.button("Tüm Kombinasyonlar İçin Stratejik Analizi Başlat"):
            with st.spinner("Veriler işleniyor..."):
                global_exec_summary = []
                test_profiles = [70,75,80, 85, 90, 95, 100]
                levels = [('Aylık', 'Ay_TR'), ('Sezonluk', 'Sezon'), ('Yıllık', 'Hepsi')]
                df_global = df[df['Yıl'].isin(sel_yil)].copy()
                
                for label, col in levels:
                    combos = df_global.groupby(['Base', 'Baz Filo', 'Pozisyon', 'Nöbet Türü']).size().reset_index().drop(columns=0) if col == 'Hepsi' else df_global.groupby(['Base', 'Baz Filo', 'Pozisyon', 'Nöbet Türü', col]).size().reset_index().drop(columns=0)
                    for _, row in combos.iterrows():
                        c_mask = (df_global['Base'] == row['Base']) & (df_global['Baz Filo'] == row['Baz Filo']) & (df_global['Pozisyon'] == row['Pozisyon']) & (df_global['Nöbet Türü'] == row['Nöbet Türü'])
                        z_adi = "Tüm Yıl" if col == 'Hepsi' else row[col]
                        if col != 'Hepsi': c_mask &= (df_global[col] == row[col])
                        c_df = df_global[c_mask].copy()
                        if c_df.empty: continue
                        
                        c_num_days = c_df['Tarih'].nunique()
                        c_d_h = c_df.groupby(['Tarih', 'Saat']).agg(p=('Gitti_Mi', 'count'), f=('Gitti_Mi', 'sum')).reset_index()
                        c_total_fiili = c_d_h['f'].sum()
                        c_avg_p = c_d_h['p'].sum() / c_num_days
                        
                        for prof in test_profiles:
                            c_m_plan = c_d_h.groupby('Saat').agg(perc=('f', lambda x: np.percentile(x, prof))).reset_index()
                            c_m_plan['rec'] = np.ceil(c_m_plan['perc']).astype(int)
                            c_avg_o = c_m_plan['rec'].sum()
                            c_d_det = pd.merge(c_d_h, c_m_plan[['Saat', 'rec']], on='Saat')
                            c_r_count = (c_d_det['f'] > c_d_det['rec']).sum()
                            c_r_ratio = (c_r_count / len(c_d_det) * 100) if len(c_d_det) > 0 else 0
                            c_riskli_farklar = c_d_det[c_d_det['f'] > c_d_det['rec']].copy()
                            c_riskli_farklar['fark'] = c_riskli_farklar['rec'] - c_riskli_farklar['f']
                            c_toplam_riskli_fark = abs(c_riskli_farklar['fark'].sum())
                            c_yönetici_risk_endeksi = (c_toplam_riskli_fark / c_total_fiili * 100) if c_total_fiili > 0 else 0
                            
                            global_exec_summary.append({
                                'Analiz Seviyesi': label, 'Zaman Dilimi': z_adi, 'Base': row['Base'], 'Filo': row['Baz Filo'],
                                'Pozisyon': row['Pozisyon'], 'Tür': row['Nöbet Türü'], 'Güven Aralığı (%)': prof,
                                'Mevcut Plan (Ort)': round(c_avg_p, 1), 'Önerilen Nöbetçi Sayısı': round(float(c_avg_o), 1),
                                'Net Tasarruf': round(c_avg_p - c_avg_o, 1), 'Op. Risk Oranı (%)': round(c_r_ratio, 1),
                                'Yön. Risk Endeksi (%)': round(c_yönetici_risk_endeksi, 2)
                            })
                
                res_df = pd.DataFrame(global_exec_summary)
                def mark_best(group):
                    group['Optimum'] = False
                    eligible = group[(group['Yön. Risk Endeksi (%)'] < 5) & (group['Net Tasarruf'] > 0)]
                    if not eligible.empty: group.at[eligible.sort_values(by=['Net Tasarruf', 'Yön. Risk Endeksi (%)'], ascending=[False, True]).index[0], 'Optimum'] = True
                    else:
                        first_saving = group[group['Net Tasarruf'] > 0].sort_values(by='Yön. Risk Endeksi (%)', ascending=True)
                        if not first_saving.empty: group.at[first_saving.index[0], 'Optimum'] = True
                    return group
                st.session_state.strateji_sonuc = res_df.groupby(['Analiz Seviyesi', 'Zaman Dilimi', 'Base', 'Filo', 'Pozisyon', 'Tür'], group_keys=False).apply(mark_best)

        if st.session_state.strateji_sonuc is not None:
            g_df = st.session_state.strateji_sonuc
            st.divider()
            f1, f2, f3, f4, f5, f6 = st.columns(6)
            with f1: filter_seviye = st.multiselect("Analiz Seviyesi", sorted(g_df['Analiz Seviyesi'].unique()))
            with f2: filter_base = st.multiselect("Base", sorted(g_df['Base'].unique()))
            with f3: filter_filo = st.multiselect("Baz Filo", sorted(g_df['Filo'].unique()))
            with f4: filter_pos = st.multiselect("Pozisyon", sorted(g_df['Pozisyon'].unique()))
            with f5: filter_tur = st.multiselect("Nöbet Türü", sorted(g_df['Tür'].unique()))
            with f6: only_optimum = st.checkbox("Sadece Optimum Önerileri Göster", value=False)
            
            filtered_df = g_df.copy()
            if filter_seviye: filtered_df = filtered_df[filtered_df['Analiz Seviyesi'].isin(filter_seviye)]
            if filter_base: filtered_df = filtered_df[filtered_df['Base'].isin(filter_base)]
            if filter_filo: filtered_df = filtered_df[filtered_df['Filo'].isin(filter_filo)]
            if filter_pos: filtered_df = filtered_df[filtered_df['Pozisyon'].isin(filter_pos)]
            if filter_tur: filtered_df = filtered_df[filtered_df['Tür'].isin(filter_tur)]
            if only_optimum: filtered_df = filtered_df[filtered_df['Optimum'] == True]
            
            st.dataframe(filtered_df.style.apply(lambda x: ['background-color: #d8f3dc; font-weight: bold; color: black'] * len(x) if x['Optimum'] else [''] * len(x), axis=1).format(precision=1), use_container_width=True, hide_index=True)
            output_g = BytesIO()
            with pd.ExcelWriter(output_g, engine='xlsxwriter') as writer: g_df.to_excel(writer, index=False, sheet_name='Strateji_Ozeti')
            st.download_button(label="📥 Yönetici Raporunu İndir", data=output_g.getvalue(), file_name="Sirket_Strateji_Raporu.xlsx")
else:
    st.info("Lütfen veri yükleyin.")
