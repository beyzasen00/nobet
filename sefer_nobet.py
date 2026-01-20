import streamlit as st
import pandas as pd
import numpy as np
import calendar
st.set_page_config(page_title="Nöbet Kapasite Analizi", layout="wide")
# --- STİL ---
st.markdown("""
<style>
.kpi-card { padding: 20px; border-radius: 10px; text-align: center; color: #2c3e50; margin-bottom: 10px; min-height: 100px; display: flex; flex-direction: column; justify-content: center; }
.kpi-blue { background-color: #e3f2fd; border: 1px solid #bbdefb; }
.kpi-green { background-color: #e8f5e9; border: 1px solid #c8e6c9; }
.kpi-red { background-color: #ffebee; border: 1px solid #ffcdd2; }
.kpi-purple { background-color: #f3e5f5; border: 1px solid #e1bee7; }
.kpi-orange { background-color: #fff3e0; border: 1px solid #ffe0b2; }
.kpi-val { font-size: 24px; font-weight: bold; }
.kpi-label { font-size: 14px; color: #546e7a; font-weight: 500; }
</style>
""", unsafe_allow_html=True)
st.title("🛡️ Stratejik Nöbet Kapasite ve Risk Yönetimi")
uploaded_file = st.sidebar.file_uploader("Nöbet Verilerini Yükleyin", type=['xlsx', 'csv'])
if uploaded_file:
 df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file)
 # Veri Hazırlama
 for col in ['Nobet Baslangic Tarihi', 'Nobet Bitis Tarihi', 'Kalkis Tarihi']:
     df[col] = pd.to_datetime(df[col], errors='coerce')
 df['Ay_Key'] = df['Nobet Baslangic Tarihi'].dt.strftime('%Y-%m')
 # --- Filtreler ---
 aylar = sorted(df['Ay_Key'].dropna().unique())
 selected_ay = st.sidebar.multiselect("Ay Seçiniz", options=aylar, default=aylar)
 # 1. BASE FİLTRESİ
 base_options = sorted(df['Base'].unique()) if 'Base' in df.columns else []
 selected_base = st.sidebar.multiselect("Base", options=base_options, default=base_options)
 filo = st.sidebar.multiselect("Filo", options=df['Baz Filo'].unique(), default=df['Baz Filo'].unique())
 # 2. UÇUCU SINIF GRUBU
 grup_opsiyonlari = ["Kaptan", "Pilot", "Kabin Amiri", "Kabin Memuru"]
 selected_grup = st.sidebar.selectbox("Uçucu Sınıf Grubu", options=["Hepsi"] + grup_opsiyonlari)
 # Gruplara göre sınıfların tanımlanması
 sinif_mapping = {
     "Kaptan": ["C1", "C2", "C3", "C4", "CI", "CN", "J1"],
     "Pilot": ["P3", "P4", "P5", "P6", "J2"],
     "Kabin Amiri": ["P", "V", "K"],
     "Kabin Memuru": ["E", "F", "N", "Q", "Y", "Z"]
 }
 # Verideki mevcut sınıflar
 mevcut_siniflar = sorted(df['Uçucu Sınıfı'].unique())
 # Seçilen gruba göre default listeyi belirle
 if selected_grup == "Hepsi":
     default_siniflar = mevcut_siniflar
 else:
     target_list = sinif_mapping.get(selected_grup, [])
     # Sadece veride gerçekten var olanları default seç
     default_siniflar = [s for s in mevcut_siniflar if s.upper() in [x.upper() for x in target_list]]
 # 3. UÇUCU SINIF DETAYI (İstenirse eklenip çıkarılabilir)
 sinif = st.sidebar.multiselect("Uçucu Sınıf Detayı", options=mevcut_siniflar, default=default_siniflar)
 # Maske Uygulama (Base Dahil Edildi)
 mask = (df['Ay_Key'].isin(selected_ay)) & \
        (df['Baz Filo'].isin(filo)) & \
        (df['Uçucu Sınıfı'].isin(sinif))
 if 'Base' in df.columns:
     mask = mask & (df['Base'].isin(selected_base))
 f_all = df[mask].copy()
 # Takvim Gün Sayısı Hesaplama
 total_days_in_period = 0
 for ay_str in selected_ay:
     y, m = map(int, ay_str.split('-'))
     total_days_in_period += calendar.monthrange(y, m)[1]
 if total_days_in_period == 0: total_days_in_period = 1
 f_giden = f_all[f_all['Nobetten Goreve Gitti mi?'].astype(str).str.strip().str.upper() == "Y"].copy()
 def calculate_need_time(row):
     if pd.isna(row['Kalkis Tarihi']): return pd.NaT
     # Uçucu sınıfı veya nöbet türüne göre offset belirleme
     val = str(row['Uçucu Sınıfı']).upper()
     is_kokpit = any(k in val for k in ["C1", "C2", "C3", "C4", "P3", "P4", "P5", "P6"])
     offset = 4 if is_kokpit or "EV" in str(row['Nöbet Türü']).upper() else 2
     return row['Kalkis Tarihi'] - pd.Timedelta(hours=offset)
 if not f_giden.empty:
     f_giden['Ihtiyac_Ani'] = f_giden.apply(calculate_need_time, axis=1)
     f_giden = f_giden.dropna(subset=['Ihtiyac_Ani'])
     f_giden['Ihtiyac_Tarihi'] = f_giden['Ihtiyac_Ani'].dt.date
     f_giden['Ihtiyac_Saati'] = f_giden['Ihtiyac_Ani'].dt.hour.astype(int)
     f_giden['Saat_Grubu'] = f_giden['Ihtiyac_Saati'].apply(lambda x: f"{x:02d}:00 - {x+1:02d}:00")
     confidence = st.sidebar.select_slider("Güven Düzeyi (%)", options=[80, 85, 90, 95, 100], value=95)
     # AI Önerisi
     daily_hourly_counts = f_giden.groupby(['Ihtiyac_Tarihi', 'Ihtiyac_Saati']).size().reset_index(name='Kullanim')
     dynamic_rec = daily_hourly_counts.groupby('Ihtiyac_Saati')['Kullanim'].quantile(confidence / 100).apply(np.ceil).to_dict()
     # Ana Tablo Oluşturma
     final_table = f_giden.groupby(['Ihtiyac_Tarihi', 'Saat_Grubu', 'Ihtiyac_Saati']).size().reset_index(name='Gerceklesen_Kullanim')
     final_table['Onerilen_Adet'] = final_table['Ihtiyac_Saati'].map(dynamic_rec).astype(int)
     # --- 6 SAAT SINIRLI TRANSFER ---
     final_table = final_table.sort_values(['Ihtiyac_Tarihi', 'Ihtiyac_Saati']).reset_index(drop=True)
     final_table['Net_Durum'] = final_table['Onerilen_Adet'] - final_table['Gerceklesen_Kullanim']
     final_table['Transfer_Edilen_Kapasite'] = 0
     final_table['Transfer_Detay'] = ""
     final_table['Final_Risk_Durumu'] = False
     for i in range(len(final_table)):
         current_net = final_table.at[i, 'Net_Durum']
         if current_net < 0:
             eksik = abs(current_net)
             lookback_range = range(max(0, i-6), i)
             logs = []
             for prev_idx in reversed(list(lookback_range)):
                 t1 = pd.to_datetime(f"{final_table.at[i, 'Ihtiyac_Tarihi']} {final_table.at[i, 'Ihtiyac_Saati']}:00")
                 t0 = pd.to_datetime(f"{final_table.at[prev_idx, 'Ihtiyac_Tarihi']} {final_table.at[prev_idx, 'Ihtiyac_Saati']}:00")
                 hour_diff = (t1 - t0).total_seconds() / 3600
                 if 0 < hour_diff <= 6:
                     surplus = final_table.at[prev_idx, 'Net_Durum']
                     if surplus > 0:
                         transfer = min(eksik, surplus)
                         final_table.at[prev_idx, 'Net_Durum'] -= transfer
                         final_table.at[i, 'Net_Durum'] += transfer
                         final_table.at[i, 'Transfer_Edilen_Kapasite'] += transfer
                         prev_saat = final_table.at[prev_idx, 'Saat_Grubu']
                         prev_tarih = final_table.at[prev_idx, 'Ihtiyac_Tarihi']
                         tarih_str = f" ({prev_tarih.strftime('%d %b')})" if prev_tarih != final_table.at[i, 'Ihtiyac_Tarihi'] else ""
                         logs.append(f"{prev_saat}{tarih_str} aralığından {int(transfer)} kişi")
                         eksik -= transfer
                 if eksik == 0: break
             if logs:
                 final_table.at[i, 'Transfer_Detay'] = " | ".join(logs) + " kaydırıldı."
         if final_table.at[i, 'Net_Durum'] < 0:
             final_table.at[i, 'Final_Risk_Durumu'] = True
     # --- KPI PANELİ ---
     avg_planned_daily = len(f_all) / total_days_in_period
     avg_used_daily = len(f_giden) / total_days_in_period
     avg_recommended_daily = final_table['Onerilen_Adet'].sum() / total_days_in_period
     st.markdown(f"### 📊 Günlük Operasyonel Ortalamalar ({total_days_in_period} Takvim Günü)")
     k1, k2, k3, k4 = st.columns(4)
     with k1: st.markdown(f'<div class="kpi-card kpi-blue"><div class="kpi-label">Günlük Ort. Planlanan Nöbet</div><div class="kpi-val">{avg_planned_daily:.1f}</div></div>', unsafe_allow_html=True)
     with k2: st.markdown(f'<div class="kpi-card kpi-purple"><div class="kpi-label">Günlük Ort. Göreve Giden</div><div class="kpi-val">{avg_used_daily:.1f}</div></div>', unsafe_allow_html=True)
     with k3: st.markdown(f'<div class="kpi-card kpi-green"><div class="kpi-label">Günlük Ort. Önerilen</div><div class="kpi-val">{avg_recommended_daily:.1f}</div></div>', unsafe_allow_html=True)
     with k4:
         savings = avg_planned_daily - avg_recommended_daily
         st.markdown(f'<div class="kpi-card kpi-orange"><div class="kpi-label">Günlük Potansiyel Tasarruf</div><div class="kpi-val">{max(0, savings):.1f} Kişi</div></div>', unsafe_allow_html=True)
     # Tablo Görüntüleme
     display_df = final_table[['Ihtiyac_Tarihi', 'Saat_Grubu', 'Gerceklesen_Kullanim',
                               'Onerilen_Adet', 'Transfer_Edilen_Kapasite', 'Transfer_Detay', 'Final_Risk_Durumu']]
     st.subheader("📋 İhtiyaç Bazlı Risk ve Kapasite Analizi (Maks. 6 Saat Kaydırma)")
     numeric_cols = ['Gerceklesen_Kullanim', 'Onerilen_Adet', 'Transfer_Edilen_Kapasite']
     grand_total = display_df[numeric_cols].sum().to_frame().T
     grand_total['Ihtiyac_Tarihi'] = "TOPLAM"
     grand_total['Saat_Grubu'] = ""
     grand_avg = display_df[numeric_cols].mean().to_frame().T
     grand_avg['Ihtiyac_Tarihi'] = "ORTALAMA"
     grand_avg['Saat_Grubu'] = ""
     final_display = pd.concat([display_df, grand_total, grand_avg], ignore_index=True)
     def highlight_final_risk(row):
         if str(row['Ihtiyac_Tarihi']) in ["TOPLAM", "ORTALAMA"]:
             return ['font-weight: bold; background-color: #f0f2f6'] * len(row)
         return ['background-color: #ffcccc' if row.Final_Risk_Durumu else '' for _ in row]
     st.dataframe(final_display.style.apply(highlight_final_risk, axis=1), use_container_width=True)
     # --- ALT RİSK KPI PANELİ ---
     st.markdown("### 🚨 Operasyonel Risk ve Çözüm Özeti")
     total_risks = len(final_table[final_table['Gerceklesen_Kullanim'] > final_table['Onerilen_Adet']])
     resolved = total_risks - final_table['Final_Risk_Durumu'].sum()
     critical_risks = final_table['Final_Risk_Durumu'].sum()
     total_rows = len(final_table)
     total_recommended_sum = final_table['Onerilen_Adet'].sum()
     op_risk_rate = (critical_risks / total_rows * 100) if total_rows > 0 else 0
     exec_risk_rate = (critical_risks / total_recommended_sum * 100) if total_recommended_sum > 0 else 0
     rk1, rk2, rk3, rk4, rk5 = st.columns(5)
     with rk1: st.markdown(f'<div class="kpi-card kpi-orange"><div class="kpi-label">Riskli Saatler</div><div class="kpi-val">{total_risks}</div></div>', unsafe_allow_html=True)
     with rk2: st.markdown(f'<div class="kpi-card kpi-green"><div class="kpi-label">Transferle Çözülen</div><div class="kpi-val">{resolved}</div></div>', unsafe_allow_html=True)
     with rk3: st.markdown(f'<div class="kpi-card kpi-red"><div class="kpi-label">Kritik Risk (Açık)</div><div class="kpi-val">{critical_risks}</div></div>', unsafe_allow_html=True)
     with rk4: st.markdown(f'<div class="kpi-card kpi-red"><div class="kpi-label">Operasyonel Risk Oranı</div><div class="kpi-val">%{op_risk_rate:.1f}</div></div>', unsafe_allow_html=True)
     with rk5: st.markdown(f'<div class="kpi-card kpi-red"><div class="kpi-label">Yönetici Risk Oranı</div><div class="kpi-val">%{exec_risk_rate:.2f}</div></div>', unsafe_allow_html=True)
 else:
     st.warning("Göreve giden personel verisi bulunamadı.")
else:
 st.info("Lütfen bir dosya yükleyin.")
