import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import plotly.express as px  
import plotly.graph_objects as row_go
from datetime import timedelta
# --- Hata Çözümü İçin Eklenen Satır ---
pd.set_option("styler.render.max_elements", 1000000)

# ... (Kodun geri kalanı tamamen aynı kalacak)
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
   df['Nobet Baslangic Tarihi'] = pd.to_datetime(df['Nobet Baslangic Tarihi'], errors='coerce')
   df['Kalkis Tarihi'] = pd.to_datetime(df['Kalkis Tarihi'], errors='coerce')
   df = df.dropna(subset=['Nobet Baslangic Tarihi'])
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
       available_positions = sorted(df[df['Pozisyon'] != 'Diğer']['Pozisyon'].unique())
       sel_poz = st.sidebar.selectbox("Pozisyon", available_positions)
       relevant_classes = sorted(df[df['Pozisyon'] == sel_poz]['Uçucu Sınıfı'].unique())
       sel_ucucu_sinifi_filtre = st.sidebar.multiselect(f"Uçucu Sınıfı ({sel_poz} Alt Detayı)", options=relevant_classes, default=relevant_classes)
       sel_tur = st.sidebar.selectbox("Nöbet Türü", sorted(df['Nöbet Türü'].unique()))
       sel_aylar = st.sidebar.multiselect("Aylar", list(ay_map.values()), default=list(ay_map.values())[:3])
       risk_profile = st.sidebar.select_slider("Güven Aralığı (%)", options=[70,75,80, 85, 90, 95, 100], value=100)
       st.sidebar.divider()
       nobet_suresi = st.sidebar.slider("Nöbet Mesai Süresi (Saat)", 4, 12, 8)
       lead_time = 4
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
           daily_detail['Timestamp'] = pd.to_datetime(daily_detail['Tarih'].astype(str) + ' ' + daily_detail['Saat'].astype(str) + ':00:00')
           daily_detail = daily_detail.sort_values('Timestamp').reset_index(drop=True)
           daily_detail['Kalan_Bos_Kapasite'] = (daily_detail['Onerilen_Güvenli_Kapasite'] - daily_detail['Fiili_Kullanilan']).clip(lower=0)
           daily_detail['Transfer_Detay'] = ""
           daily_detail['Cozulen_Adet'] = 0
           went_df = f_df[f_df['Gitti_Mi'] == 1].copy()
           for idx, row in daily_detail[daily_detail['Fiili_Kullanilan'] > daily_detail['Onerilen_Güvenli_Kapasite']].iterrows():
               tarih_saat = row['Timestamp']
               bu_saatteki_seferler = went_df[(went_df['Nobet Baslangic Tarihi'] == tarih_saat)].sort_values('Kalkis Tarihi', ascending=False)
               limit = int(row['Onerilen_Güvenli_Kapasite'])
               fazla_seferler = bu_saatteki_seferler.iloc[0 : (int(row['Fiili_Kullanilan']) - limit)]
               cozulen = 0
               notlar = []
               for _, sefer in fazla_seferler.iterrows():
                   kalkis = sefer['Kalkis Tarihi']
                   if pd.isna(kalkis): continue
                   aday_saatler = daily_detail[
                       (daily_detail['Timestamp'] <= kalkis - timedelta(hours=lead_time)) &
                       (daily_detail['Timestamp'] > kalkis - timedelta(hours=nobet_suresi)) &
                       (daily_detail['Kalan_Bos_Kapasite'] > 0)
                   ].sort_values('Timestamp', ascending=False)
                   if not aday_saatler.empty:
                       p_idx = aday_saatler.index[0]
                       daily_detail.at[p_idx, 'Kalan_Bos_Kapasite'] -= 1
                       cozulen += 1
                       v_saat = daily_detail.at[p_idx, 'Timestamp'].strftime('%H:00')
                       notlar.append(f"{kalkis.strftime('%H:%M')} başlangıçlı seferin ihtiyacı {v_saat} saatli nöbetinden transfer edilerek karşılanmıştır.")
               daily_detail.at[idx, 'Cozulen_Adet'] = cozulen
               if notlar:
                   daily_detail.at[idx, 'Transfer_Detay'] = " | ".join(notlar)
           def risk_durumu(r):
               eksik = r['Fiili_Kullanilan'] - r['Onerilen_Güvenli_Kapasite']
               if eksik <= 0: return 'Güvenli'
               if r['Cozulen_Adet'] >= eksik: return 'TRANSFER İLE ÇÖZÜLDÜ'
               return 'GERÇEK RİSK'
           daily_detail['Riskli_mi?'] = daily_detail.apply(risk_durumu, axis=1)
           daily_detail['Gercek_Fark'] = daily_detail.apply(lambda x: (x['Fiili_Kullanilan'] - x['Onerilen_Güvenli_Kapasite'] - x['Cozulen_Adet']) if x['Riskli_mi?'] == 'GERÇEK RİSK' else 0, axis=1)
           risk_adet_sonrasi = (daily_detail['Riskli_mi?'] == 'GERÇEK RİSK').sum()
           risk_orani_sonrasi = (risk_adet_sonrasi / len(daily_detail) * 100) if len(daily_detail) > 0 else 0
           total_k_sum = daily_detail['Fiili_Kullanilan'].sum()
           avg_p = daily_detail['Mevcut_Planlanan'].sum() / num_days
           avg_k = total_k_sum / num_days
           avg_o = float(master_plan['Onerilen_Güvenli_Kapasite'].sum())
           yeni_risk_tanimi = (daily_detail['Gercek_Fark'].sum() / total_k_sum * 100) if total_k_sum > 0 else 0
           st.title(f"📊 {sel_base} | {sel_filo} | {sel_poz} Analiz Paneli")
           k1, k2, k3, k4, k5, k6 = st.columns(6)
           k1.markdown(f'<div class="kpi-card"><div class="kpi-title">Mevcut Ort. Plan</div><div class="kpi-value">{avg_p:.1f}</div></div>', unsafe_allow_html=True)
           k2.markdown(f'<div class="kpi-card"><div class="kpi-title">Mevcut Ort. Kullanım</div><div class="kpi-value">{avg_k:.1f}</div></div>', unsafe_allow_html=True)
           k3.markdown(f'<div class="kpi-card"><div class="kpi-title">Önerilen Kapasite</div><div class="kpi-value">{int(avg_o)}</div></div>', unsafe_allow_html=True)
           k4.markdown(f'<div class="kpi-card"><div class="kpi-title">Net Tasarruf (Gün)</div><div class="kpi-value">{avg_p - avg_o:.1f}</div></div>', unsafe_allow_html=True)
           k5.markdown(f'<div class="kpi-card" style="border-left-color: #bc4749;"><div class="kpi-title">Efektif Op. Risk</div><div class="kpi-value">%{risk_orani_sonrasi:.1f}</div></div>', unsafe_allow_html=True)
           k6.markdown(f'<div class="kpi-card" style="border-left-color: #2a9d8f;"><div class="kpi-title">Yön. Risk Endeksi</div><div class="kpi-value">%{yeni_risk_tanimi:.1f}</div></div>', unsafe_allow_html=True)
           st.subheader("📋 1. Günlük & Saatlik Operasyonel Detay")
           daily_detail['Fark_Mevcut_Onerilen'] = daily_detail['Mevcut_Planlanan'] - daily_detail['Onerilen_Güvenli_Kapasite']
           cols_to_show = ['Tarih', 'Saat', 'Mevcut_Planlanan', 'Fiili_Kullanilan', 'Onerilen_Güvenli_Kapasite', 'Fark_Mevcut_Onerilen', 'Riskli_mi?', 'Transfer_Detay']
           st.dataframe(daily_detail[cols_to_show], use_container_width=True, hide_index=True)
   with tab_planlamaci:
       st.title("📅 Planlamacı Karar Destek Ekranı")
       if not f_df.empty:
           st.write("Planlamacı detayları yüklenen verilere göre optimize edilmiştir.")
   with tab_strateji:
       st.title("🚀 Global Senaryo ve Strateji Motoru")
       if 'strateji_sonuc' not in st.session_state:
           st.session_state.strateji_sonuc = None
       if 'strateji_saatlik_sonuc' not in st.session_state:
           st.session_state.strateji_saatlik_sonuc = None
       if st.button("Tüm Kombinasyonlar İçin Stratejik Analizi Başlat"):
           with st.spinner("Veriler işleniyor..."):
               global_exec_summary = []
               hourly_exec_summary = [] # EK: Saatlik detayları biriktireceğimiz liste
               test_profiles = [70,75,80, 85, 90, 95, 100]
               levels = [('Aylık', 'Ay_TR'), ('Sezonluk', 'Sezon'), ('Yıllık', 'Hepsi')]
               df_global = df[df['Yıl'].isin(sel_yil)].copy()
               for label, col in levels:
                   if col == 'Hepsi':
                       combos = df_global.groupby(['Base', 'Baz Filo', 'Pozisyon', 'Nöbet Türü']).size().reset_index().drop(columns=0)
                   else:
                       combos = df_global.groupby(['Base', 'Baz Filo', 'Pozisyon', 'Nöbet Türü', col]).size().reset_index().drop(columns=0)
                   for _, row in combos.iterrows():
                       c_mask = (df_global['Base'] == row['Base']) & (df_global['Baz Filo'] == row['Baz Filo']) & \
                                (df_global['Pozisyon'] == row['Pozisyon']) & (df_global['Nöbet Türü'] == row['Nöbet Türü'])
                       z_adi = "Tüm Yıl" if col == 'Hepsi' else row[col]
                       if col != 'Hepsi': c_mask &= (df_global[col] == row[col])
                       c_df = df_global[c_mask].copy()
                       if c_df.empty: continue
                       c_num_days = c_df['Tarih'].nunique()
                       c_d_h = c_df.groupby(['Tarih', 'Saat']).agg(p=('Gitti_Mi', 'count'), f=('Gitti_Mi', 'sum')).reset_index()
                       c_total_planlanan = c_d_h['p'].sum()
                       c_total_fiili = c_d_h['f'].sum()
                       c_avg_p = c_total_planlanan / c_num_days
                       c_avg_k = c_total_fiili / c_num_days
                       c_df['Timestamp'] = pd.to_datetime(c_df['Tarih'].astype(str) + ' ' + c_df['Saat'].astype(str) + ':00:00')
                       c_went_df = c_df[c_df['Gitti_Mi'] == 1].copy()
                       for prof in test_profiles:
                           c_m_plan = c_d_h.groupby('Saat').agg(perc=('f', lambda x: np.percentile(x, prof))).reset_index()
                           c_m_plan['rec'] = np.ceil(c_m_plan['perc']).astype(int)
                           c_avg_o = c_m_plan['rec'].sum()
                           c_d_det = pd.merge(c_d_h, c_m_plan[['Saat', 'rec']], on='Saat')
                           net_tasarruf_total = (c_d_det['p'] - c_d_det['rec']).sum()
                           c_d_det['Timestamp'] = pd.to_datetime(c_d_det['Tarih'].astype(str) + ' ' + c_d_det['Saat'].astype(str) + ':00:00')
                           c_d_det = c_d_det.sort_values('Timestamp').reset_index(drop=True)
                           c_d_det['Kalan_Bos'] = (c_d_det['rec'] - c_d_det['f']).clip(lower=0)
                           c_d_det['Cozulen'] = 0
                           for idx_r, row_r in c_d_det[c_d_det['f'] > c_d_det['rec']].iterrows():
                               t_s = row_r['Timestamp']
                               f_sef = c_went_df[c_went_df['Nobet Baslangic Tarihi'] == t_s].sort_values('Kalkis Tarihi', ascending=False)
                               f_adet = int(row_r['f'] - row_r['rec'])
                               f_sef = f_sef.iloc[0:f_adet]
                               coz = 0
                               for _, s_v in f_sef.iterrows():
                                   k_t = s_v['Kalkis Tarihi']
                                   if pd.isna(k_t): continue
                                   ad_s = c_d_det[(c_d_det['Timestamp'] <= k_t - timedelta(hours=4)) &
                                                 (c_d_det['Timestamp'] > k_t - timedelta(hours=8)) &
                                                 (c_d_det['Kalan_Bos'] > 0)].sort_values('Timestamp', ascending=False)
                                   if not ad_s.empty:
                                       c_d_det.at[ad_s.index[0], 'Kalan_Bos'] -= 1
                                       coz += 1
                                   c_d_det.at[idx_r, 'Cozulen'] = coz
                           c_d_det['Gercek_Fark'] = c_d_det.apply(lambda x: (x['f'] - x['rec'] - x['Cozulen']) if (x['f'] > (x['rec'] + x['Cozulen'])) else 0, axis=1)
                           riskli_saat_sayisi = (c_d_det['Gercek_Fark'] > 0).sum()
                           toplam_eksik_adet = c_d_det['Gercek_Fark'].sum()
                           c_r_count_final = riskli_saat_sayisi
                           c_r_ratio_final = (c_r_count_final / len(c_d_det) * 100) if len(c_d_det) > 0 else 0
                           c_yönetici_risk_endeksi = (toplam_eksik_adet / c_total_fiili * 100) if c_total_fiili > 0 else 0
                           global_exec_summary.append({
                               'Analiz Seviyesi': label, 'Zaman Dilimi': z_adi, 'Base': row['Base'], 'Filo': row['Baz Filo'],
                               'Pozisyon': row['Pozisyon'], 'Tür': row['Nöbet Türü'], 'Güven Aralığı (%)': prof,
                               'Mevcut Plan (Ort)': round(c_avg_p, 1),
                               'Mevcut Ort Kullanım': round(c_avg_k, 1),
                               'Önerilen Nöbetçi Sayısı': int(c_avg_o),
                               'Net Tasarruf': int(net_tasarruf_total),
                               'Risk Adedi (Saat)': int(c_r_count_final),
                               'Toplam Eksik Kapasite (Şiddet)': int(toplam_eksik_adet),
                               'Op. Risk Oranı (%)': round(c_r_ratio_final, 1),
                               'Yön. Risk Endeksi (%)': round(c_yönetici_risk_endeksi, 2)
                           })
                           # EK: Saatlik Kırılım Hesaplaması ve Listeye Eklenmesi
                           saatlik_grup = c_d_det.groupby('Saat')
                           for saat, s_df in saatlik_grup:
                               s_p_mean = s_df['p'].mean()
                               s_f_mean = s_df['f'].mean()
                               s_rec = s_df['rec'].iloc[0]
                               s_net_tasarruf = (s_df['p'] - s_df['rec']).sum()
                               s_risk_count = (s_df['Gercek_Fark'] > 0).sum()
                               s_eksik = s_df['Gercek_Fark'].sum()
                               s_f_sum = s_df['f'].sum()
                               s_risk_ratio = (s_risk_count / len(s_df) * 100) if len(s_df) > 0 else 0
                               s_yon_risk = (s_eksik / s_f_sum * 100) if s_f_sum > 0 else 0
                               hourly_exec_summary.append({
                                   'Analiz Seviyesi': label, 'Zaman Dilimi': z_adi, 'Base': row['Base'], 'Filo': row['Baz Filo'],
                                   'Pozisyon': row['Pozisyon'], 'Tür': row['Nöbet Türü'], 'Güven Aralığı (%)': prof,
                                   'Saat': saat, # Yeni eklenen saat kolonu
                                   'Mevcut Plan (Ort)': round(s_p_mean, 1),
                                   'Mevcut Ort Kullanım': round(s_f_mean, 1),
                                   'Önerilen Nöbetçi Sayısı': int(s_rec),
                                   'Net Tasarruf': int(s_net_tasarruf),
                                   'Risk Adedi (Gün)': int(s_risk_count),
                                   'Toplam Eksik Kapasite (Şiddet)': int(s_eksik),
                                   'Op. Risk Oranı (%)': round(s_risk_ratio, 1),
                                   'Yön. Risk Endeksi (%)': round(s_yon_risk, 2)
                               })
               res_df = pd.DataFrame(global_exec_summary)
               res_hourly_df = pd.DataFrame(hourly_exec_summary) # EK: Saatlik DataFrame
               def mark_best(group):
                   group['Optimum'] = False
                   eligible = group[(group['Yön. Risk Endeksi (%)'] < 5) & (group['Net Tasarruf'] > 0)]
                   if not eligible.empty: group.at[eligible.sort_values(by=['Net Tasarruf', 'Yön. Risk Endeksi (%)'], ascending=[False, True]).index[0], 'Optimum'] = True
                   else:
                       first_saving = group[group['Net Tasarruf'] > 0].sort_values(by='Yön. Risk Endeksi (%)', ascending=True)
                       if not first_saving.empty: group.at[first_saving.index[0], 'Optimum'] = True
                   return group
               st.session_state.strateji_sonuc = res_df.groupby(['Analiz Seviyesi', 'Zaman Dilimi', 'Base', 'Filo', 'Pozisyon', 'Tür'], group_keys=False).apply(mark_best)
               st.session_state.strateji_saatlik_sonuc = res_hourly_df # EK: Saatlik sonuç state'e kaydediliyor
       if st.session_state.strateji_sonuc is not None:
           g_df = st.session_state.strateji_sonuc
           st.divider()
           st.subheader("📊 Yönetici Dinamik Pivot Analizi")
           p_col1, p_col2 = st.columns([2, 3])
           with p_col1:
               pivot_rows = st.multiselect("Satır Kırılımları (Hiyerarşi)", options=['Analiz Seviyesi', 'Zaman Dilimi', 'Base', 'Filo', 'Pozisyon', 'Tür', 'Güven Aralığı (%)'], default=['Güven Aralığı (%)', 'Zaman Dilimi'])
           with p_col2:
               pivot_metrics = st.multiselect("Sütun Değerleri", options=['Mevcut Plan (Ort)', 'Mevcut Ort Kullanım', 'Önerilen Nöbetçi Sayısı', 'Net Tasarruf', 'Risk Adedi (Saat)', 'Toplam Eksik Kapasite (Şiddet)', 'Op. Risk Oranı (%)', 'Yön. Risk Endeksi (%)'], default=['Mevcut Plan (Ort)', 'Net Tasarruf', 'Risk Adedi (Saat)', 'Toplam Eksik Kapasite (Şiddet)', 'Op. Risk Oranı (%)'])
           if pivot_rows and pivot_metrics:
               pivot_display = g_df.pivot_table(index=pivot_rows, values=pivot_metrics, aggfunc='mean')
               st.dataframe(pivot_display.style.format("{:.1f}"), use_container_width=True, height=450)
           st.divider()
           st.subheader("📋 Detaylı Veri Filtreleme")
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
           st.dataframe(filtered_df.style.apply(lambda x: ['background-color: #d8f3dc; font-weight: bold; color: black'] * len(x) if x['Optimum'] else [''] * len(x), axis=1).format({
               'Mevcut Plan (Ort)': "{:.1f}", 'Mevcut Ort Kullanım': "{:.1f}", 'Önerilen Nöbetçi Sayısı': "{:g}", 'Net Tasarruf': "{:g}",
               'Risk Adedi (Saat)': "{:g}", 'Toplam Eksik Kapasite (Şiddet)': "{:g}", 'Op. Risk Oranı (%)': "{:.1f}", 'Yön. Risk Endeksi (%)': "{:.2f}"
           }), use_container_width=True, hide_index=True)
           output_g = BytesIO()
           with pd.ExcelWriter(output_g, engine='xlsxwriter') as writer: g_df.to_excel(writer, index=False, sheet_name='Strateji_Ozeti')
           st.download_button(label="📥 Yönetici Raporunu İndir", data=output_g.getvalue(), file_name="Sirket_Strateji_Raporu.xlsx")
           # EK: Saat Kırılımlı Yeni Tablonun Eklenmesi
           if st.session_state.strateji_saatlik_sonuc is not None:
               st.divider()
               st.subheader("🕒 Saat Kırılımlı Yönetici Strateji Özeti")
               st.write("Aşağıdaki tablo, yöneticinin hangi saatlerden tasarruf yapılması gerektiğini net görebilmesi için stratejik özetin **saat bazlı** detaylandırılmış halidir.")
               h_df = st.session_state.strateji_saatlik_sonuc
               h_filtered_df = h_df.copy()
               # Kullanıcı deneyimini artırmak için yukarıda seçilen filtreler bu tabloya da yansısın
               if filter_seviye: h_filtered_df = h_filtered_df[h_filtered_df['Analiz Seviyesi'].isin(filter_seviye)]
               if filter_base: h_filtered_df = h_filtered_df[h_filtered_df['Base'].isin(filter_base)]
               if filter_filo: h_filtered_df = h_filtered_df[h_filtered_df['Filo'].isin(filter_filo)]
               if filter_pos: h_filtered_df = h_filtered_df[h_filtered_df['Pozisyon'].isin(filter_pos)]
               if filter_tur: h_filtered_df = h_filtered_df[h_filtered_df['Tür'].isin(filter_tur)]
               st.dataframe(h_filtered_df.style.format({
                   'Mevcut Plan (Ort)': "{:.1f}", 'Mevcut Ort Kullanım': "{:.1f}", 'Önerilen Nöbetçi Sayısı': "{:g}", 'Net Tasarruf': "{:g}",
                   'Risk Adedi (Gün)': "{:g}", 'Toplam Eksik Kapasite (Şiddet)': "{:g}", 'Op. Risk Oranı (%)': "{:.1f}", 'Yön. Risk Endeksi (%)': "{:.2f}"
               }), use_container_width=True, hide_index=True)
               output_h = BytesIO()
               with pd.ExcelWriter(output_h, engine='xlsxwriter') as writer2:
                   h_df.to_excel(writer2, index=False, sheet_name='Saatlik_Strateji_Ozeti')
               st.download_button(label="📥 Saat Kırılımlı Raporu İndir", data=output_h.getvalue(), file_name="Sirket_Strateji_Saatlik_Raporu.xlsx")
