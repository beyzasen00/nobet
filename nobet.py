import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import plotly.express as px  
import plotly.graph_objects as row_go
from datetime import timedelta

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
       
       available_positions = sorted(df[df['Pozisyon'] != 'Diğer']['Pozisyon'].unique())
       sel_poz = st.sidebar.selectbox("Pozisyon", available_positions)
       relevant_classes = sorted(df[df['Pozisyon'] == sel_poz]['Uçucu Sınıfı'].unique())
       sel_ucucu_sinifi_filtre = st.sidebar.multiselect(f"Uçucu Sınıfı ({sel_poz} Alt Detayı)", options=relevant_classes, default=relevant_classes)
       sel_tur = st.sidebar.selectbox("Nöbet Türü", sorted(df['Nöbet Türü'].unique()))
       sel_aylar = st.sidebar.multiselect("Aylar", list(ay_map.values()), default=list(ay_map.values())[:3])
       risk_profile = st.sidebar.select_slider("Güven Aralığı (%)", options=[70,75,80, 85, 90, 95, 100], value=100)
       
       st.sidebar.divider()
       nobet_suresi = st.sidebar.slider("Nöbet Mesai Süresi (Saat)", 2, 3, 4)

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

           for idx, row in daily_detail[daily_detail['Fiili_Kullanilan'] > daily_detail['Onerilen_Güvenli_Kapasite']].iterrows():
               ihtiyac = int(row['Fiili_Kullanilan'] - row['Onerilen_Güvenli_Kapasite'])
               su_an = row['Timestamp']
               limit_gecmis = su_an - timedelta(hours=(nobet_suresi - 1))
               
               potansiyel_saatler = daily_detail[(daily_detail['Timestamp'] >= limit_gecmis) & 
                                               (daily_detail['Timestamp'] < su_an) & 
                                               (daily_detail['Kalan_Bos_Kapasite'] > 0)].sort_values('Timestamp')
               
               transferler = []
               kalan_ihtiyac = ihtiyac
               
               for p_idx, p_row in potansiyel_saatler.iterrows():
                   if kalan_ihtiyac <= 0: break
                   alinan = min(int(p_row['Kalan_Bos_Kapasite']), kalan_ihtiyac)
                   daily_detail.at[p_idx, 'Kalan_Bos_Kapasite'] -= alinan
                   kalan_ihtiyac -= alinan
                   t_bilgi = f"{p_row['Timestamp'].strftime('%d %b %H:00')} ({alinan} kişi)"
                   transferler.append(t_bilgi)
               
               daily_detail.at[idx, 'Cozulen_Adet'] = ihtiyac - kalan_ihtiyac
               if transferler:
                   daily_detail.at[idx, 'Transfer_Detay'] = "Transfer Geldi: " + ", ".join(transferler)

           def risk_durumu(r):
               eksik = r['Fiili_Kullanilan'] - r['Onerilen_Güvenli_Kapasite']
               if eksik <= 0: return 'Güvenli'
               if r['Cozulen_Adet'] >= eksik: return 'TRANSFER İLE ÇÖZÜLDÜ'
               return 'GERÇEK RİSK'

           daily_detail['Riskli_mi?'] = daily_detail.apply(risk_durumu, axis=1)
           
           risk_adet_oncesi = (daily_detail['Fiili_Kullanilan'] > daily_detail['Onerilen_Güvenli_Kapasite']).sum()
           risk_adet_sonrasi = (daily_detail['Riskli_mi?'] == 'GERÇEK RİSK').sum()
           risk_orani_oncesi = (risk_adet_oncesi / len(daily_detail) * 100) if len(daily_detail) > 0 else 0
           risk_orani_sonrasi = (risk_adet_sonrasi / len(daily_detail) * 100) if len(daily_detail) > 0 else 0

           total_k_sum = daily_detail['Fiili_Kullanilan'].sum()
           total_p_sum = daily_detail['Mevcut_Planlanan'].sum()
           total_o_sum = daily_detail['Onerilen_Güvenli_Kapasite'].sum()
           
           daily_detail['Gercek_Fark'] = daily_detail.apply(lambda x: (x['Fiili_Kullanilan'] - x['Onerilen_Güvenli_Kapasite'] - x['Cozulen_Adet']) if x['Riskli_mi?'] == 'GERÇEK RİSK' else 0, axis=1)
           yeni_risk_tanimi = (daily_detail['Gercek_Fark'].sum() / total_k_sum * 100) if total_k_sum > 0 else 0

           avg_p = total_p_sum / num_days
           avg_k = total_k_sum / num_days
           avg_o = total_o_sum / num_days
           avg_s = avg_p - avg_o

           st.title(f"📊 {sel_base} | {sel_filo} | {sel_poz} | {sel_tur} Analiz Paneli")
           k1, k2, k3, k4, k5, k6 = st.columns(6)
           k1.markdown(f'<div class="kpi-card"><div class="kpi-title">Mevcut Ort. Plan</div><div class="kpi-value">{avg_p:.1f}</div></div>', unsafe_allow_html=True)
           k2.markdown(f'<div class="kpi-card"><div class="kpi-title">Mevcut Ort. Kullanım</div><div class="kpi-value">{avg_k:.1f}</div></div>', unsafe_allow_html=True)
           k3.markdown(f'<div class="kpi-card"><div class="kpi-title">Önerilen Kapasite</div><div class="kpi-value">{avg_o:.1f}</div></div>', unsafe_allow_html=True)
           k4.markdown(f'<div class="kpi-card"><div class="kpi-title">Net Tasarruf (Gün)</div><div class="kpi-value">{avg_s:.1f}</div></div>', unsafe_allow_html=True)
           k5.markdown(f'<div class="kpi-card" style="border-left-color: #bc4749;"><div class="kpi-title">Efektif Op. Risk</div><div class="kpi-value">%{risk_orani_sonrasi:.1f}</div></div>', unsafe_allow_html=True)
           k6.markdown(f'<div class="kpi-card" style="border-left-color: #2a9d8f;"><div class="kpi-title">Yön. Risk Endeksi</div><div class="kpi-value">%{yeni_risk_tanimi:.1f}</div></div>', unsafe_allow_html=True)

           st.subheader("📋 1. Günlük & Saatlik Operasyonel Detay")
           daily_detail['Fark_Mevcut_Onerilen'] = daily_detail['Mevcut_Planlanan'] - daily_detail['Onerilen_Güvenli_Kapasite']
           
           cols_to_show = ['Tarih', 'Saat', 'Mevcut_Planlanan', 'Fiili_Kullanilan', 'Onerilen_Güvenli_Kapasite', 'Fark_Mevcut_Onerilen', 'Riskli_mi?', 'Transfer_Detay']
           
           def style_risk(row):
               if row.get('Tarih') in ['TOTAL', 'AVERAGE']: return ['font-weight: bold; background-color: #f0f2f6'] * len(row)
               if row['Riskli_mi?'] == 'GERÇEK RİSK': return ['background-color: #ffcccc'] * len(row)
               elif row['Riskli_mi?'] == 'TRANSFER İLE ÇÖZÜLDÜ': return ['background-color: #e2ece9'] * len(row)
               return [''] * len(row)

           # Tablo Altı Toplam/Ortalama Satırları
           summary_df = daily_detail[cols_to_show].copy()
           numeric_cols = ['Mevcut_Planlanan', 'Fiili_Kullanilan', 'Onerilen_Güvenli_Kapasite', 'Fark_Mevcut_Onerilen']
           
           total_row = summary_df[numeric_cols].sum().to_frame().T
           total_row['Tarih'] = 'TOTAL'
           
           avg_row = summary_df[numeric_cols].mean().to_frame().T
           avg_row['Tarih'] = 'AVERAGE'
           
           styled_daily = pd.concat([summary_df, total_row, avg_row], ignore_index=True)
           st.dataframe(styled_daily.style.apply(style_risk, axis=1).format(precision=1), use_container_width=True, hide_index=True)
           
           st.info(f"💡 **Nöbetçi Transfer Analizi:** Transfer öncesi riskli saat oranı **%{risk_orani_oncesi:.1f} ({risk_adet_oncesi} saat)** iken, {nobet_suresi} saatlik mesai kaydırma simülasyonu sonrası risk oranı **%{risk_orani_sonrasi:.1f} ({risk_adet_sonrasi} saat)** seviyesine düşürülmüştür.")

           with st.expander(f"⚠️ Kritik Gerçek Risk Analizi: Toplam {risk_adet_sonrasi} Saat (Kaldırılamayan)"):
               gercek_riskli = daily_detail[daily_detail['Riskli_mi?'] == 'GERÇEK RİSK'].copy()
               if not gercek_riskli.empty:
                   st.dataframe(gercek_riskli[cols_to_show].style.format(precision=1), use_container_width=True)
               else:
                   st.success("Tüm riskli durumlar önceki nöbetçilerin transferiyle kapatılabiliyor.")

           st.divider()
           st.subheader("📋 2. Saatlik Stratejik Şablon (Referans)")
           master_plan['Mevcut_Ort_Planlanan'] = master_plan['Saat'].map(daily_detail.groupby('Saat')['Mevcut_Planlanan'].mean())
           master_plan['Mevcut_Ort_Kullanilan'] = master_plan['Saat'].map(daily_detail.groupby('Saat')['Fiili_Kullanilan'].mean())
           
           # Master Plan Toplam Satırı
           mp_cols = ['Saat', 'Mevcut_Ort_Planlanan', 'Mevcut_Ort_Kullanilan', 'Onerilen_Güvenli_Kapasite']
           mp_summary = master_plan[mp_cols].copy()
           mp_total = mp_summary[['Mevcut_Ort_Planlanan', 'Mevcut_Ort_Kullanilan', 'Onerilen_Güvenli_Kapasite']].sum().to_frame().T
           mp_total['Saat'] = 'TOTAL'
           mp_final = pd.concat([mp_summary, mp_total], ignore_index=True)
           st.dataframe(mp_final.style.apply(lambda x: ['font-weight: bold; background-color: #f0f2f6' if x['Saat'] == 'TOTAL' else '' for _ in x], axis=1).format(precision=1), use_container_width=True, hide_index=True)

   with tab_planlamaci:
       st.title("📅 Planlamacı Karar Destek Ekranı")
       if not f_df.empty:
           p1, p2, p3 = st.columns(3)
           p1.markdown(f'<div class="kpi-card"><div class="kpi-title">Net Tasarruf (Günlük Adet)</div><div class="kpi-value">{avg_s:.1f}</div></div>', unsafe_allow_html=True)
           p2.markdown(f'<div class="kpi-card"><div class="kpi-title">Net Tasarruf (Dönem Toplam)</div><div class="kpi-value">{total_p_sum - total_o_sum:.0f}</div></div>', unsafe_allow_html=True)
           p3.markdown(f'<div class="kpi-card" style="border-left-color: #bc4749;"><div class="kpi-title">Transfer Sonrası Operasyonel Risk</div><div class="kpi-value">%{risk_orani_sonrasi:.1f}</div></div>', unsafe_allow_html=True)
           
           st.subheader("⏰ 1. Saatlik Önerilen Nöbetçi Sayıları")
           hourly_plan = master_plan[['Saat', 'Onerilen_Güvenli_Kapasite']].sort_values('Saat').copy()
           h_total = pd.DataFrame({'Saat': ['TOTAL'], 'Onerilen_Güvenli_Kapasite': [hourly_plan['Onerilen_Güvenli_Kapasite'].sum()]})
           h_final = pd.concat([hourly_plan, h_total], ignore_index=True)
           st.dataframe(h_final.style.apply(lambda x: ['font-weight: bold; background-color: #f0f2f6' if x['Saat'] == 'TOTAL' else '' for _ in x], axis=1).format(precision=0), use_container_width=True, hide_index=True)

          
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
                               'Net Tasarruf': round(c_avg_p - c_avg_o, 1),
                               'Risk Adedi (Saat)': int(c_r_count),
                               'Op. Risk Oranı (%)': round(c_r_ratio, 1),
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

