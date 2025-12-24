import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
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
   # Veri Hazırlık
   df['Base'] = df['Base'].astype(str).str.strip().str.upper()
   df['Baz Filo'] = df['Baz Filo'].astype(str).str.strip()
   df['Nobet Baslangic Tarihi'] = pd.to_datetime(df['Nobet Baslangic Tarihi'])
   df['Tarih'] = df['Nobet Baslangic Tarihi'].dt.date
   df['Saat'] = df['Nobet Baslangic Tarihi'].dt.hour
   ay_map = {'January': 'Ocak', 'February': 'Şubat', 'March': 'Mart', 'April': 'Nisan', 'May': 'Mayıs', 'June': 'Haziran',
             'July': 'Temmuz', 'August': 'Ağustos', 'September': 'Eylül', 'October': 'Ekim', 'November': 'Kasım', 'December': 'Aralık'}
   df['Ay_TR'] = df['Nobet Baslangic Tarihi'].dt.month_name().map(ay_map)
   df['Gitti_Mi'] = df['Nobetten Goreve Gitti mi?'].apply(lambda x: 1 if str(x).strip().upper() == 'Y' else 0)
   # Sezon Tanımı
   sezon_map = {'Kış': ['Aralık', 'Ocak', 'Şubat'], 'Bahar': ['Mart', 'Nisan', 'Mayıs'], 'Yaz': ['Haziran', 'Temmuz', 'Ağustos'], 'Güz': ['Eylül', 'Ekim', 'Kasım']}
   def get_sezon(ay):
       for s, aylar in sezon_map.items():
           if ay in aylar: return s
       return 'Diğer'
   df['Sezon'] = df['Ay_TR'].apply(get_sezon)
   # --- KESKİN POZİSYON AYRIMI ---
   def pozisyon_ata(sinif):
       val = str(sinif).strip().upper()
       if val.startswith('C'): return 'Kaptan'
       if val.startswith('P') and any(c.isdigit() for c in val): return 'Pilot'
       if val == 'P' or val.startswith(('V', 'K')): return 'Kabin Amiri'
       if val.startswith(('E', 'F', 'N', 'Q', 'Y', 'Z')): return 'Kabin Memuru'
       return 'Diğer'
   df['Pozisyon'] = df['Uçucu Sınıfı'].apply(pozisyon_ata)
   # --- SEKME YAPISI ---
   tab_ana, tab_planlamaci, tab_strateji = st.tabs(["🔍 Operasyonel Analiz", "📅 Planlamacı Ekranı", "🏆 Yönetici Strateji Özeti"])
   with tab_ana:
       # --- FİLTRELER ---
       st.sidebar.header("🎯 Analiz Filtreleri")
       sel_base = st.sidebar.selectbox("Base", sorted(df['Base'].unique()))
       sel_filo = st.sidebar.selectbox("Baz Filo", sorted(df['Baz Filo'].unique()))
       available_positions = sorted(df[df['Pozisyon'] != 'Diğer']['Pozisyon'].unique())
       sel_poz = st.sidebar.selectbox("Pozisyon", available_positions)
       sel_tur = st.sidebar.selectbox("Nöbet Türü", sorted(df['Nöbet Türü'].unique()))
       sel_aylar = st.sidebar.multiselect("Aylar", list(ay_map.values()), default=["Ocak"])
       risk_profile = st.sidebar.select_slider("Güven Aralığı (%)", options=[70,75,80, 85, 90, 95, 100], value=100)
       mask = (df['Base'] == sel_base) & (df['Baz Filo'] == sel_filo) & (df['Pozisyon'] == sel_poz) & \
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
           daily_detail['Fark'] = daily_detail['Mevcut_Planlanan'] - daily_detail['Onerilen_Güvenli_Kapasite']
           daily_detail['Riskli_mi?'] = daily_detail.apply(lambda x: 'RİSK' if x['Fiili_Kullanilan'] > x['Onerilen_Güvenli_Kapasite'] else 'Güvenli', axis=1)
           # KPI HESAPLARI (Günlük Ortalamalar)
           total_p_sum, total_k_sum = daily_detail['Mevcut_Planlanan'].sum(), daily_detail['Fiili_Kullanilan'].sum()
           # Kritik Düzeltme: avg_o artık saatlik önerilenlerin toplamıdır (günlük toplam ihtiyacı temsil eder)
           avg_p = total_p_sum / num_days
           avg_k = total_k_sum / num_days
           avg_o = master_plan['Onerilen_Güvenli_Kapasite'].sum()
           avg_s = avg_p - avg_o
           # Toplam önerilen sum hesaplaması (Tablo gösterimi için)
           total_o_sum = avg_o * num_days
           total_fark_sum = total_p_sum - total_o_sum
           risk_ratio = ((daily_detail['Riskli_mi?'] == 'RİSK').sum() / len(daily_detail) * 100) if len(daily_detail) > 0 else 0
           st.title(f"📊 {sel_base} | {sel_filo} | {sel_poz} | {sel_tur} Analiz Paneli")
           k1, k2, k3, k4, k5 = st.columns(5)
           k1.markdown(f'<div class="kpi-card"><div class="kpi-title">Mevcut Ort. Plan</div><div class="kpi-value">{avg_p:.1f}</div></div>', unsafe_allow_html=True)
           k2.markdown(f'<div class="kpi-card"><div class="kpi-title">Mevcut Ort. Kullanım</div><div class="kpi-value">{avg_k:.1f}</div></div>', unsafe_allow_html=True)
           k3.markdown(f'<div class="kpi-card"><div class="kpi-title">Önerilen Kapasite</div><div class="kpi-value">{avg_o:.1f}</div></div>', unsafe_allow_html=True)
           k4.markdown(f'<div class="kpi-card"><div class="kpi-title">Net Tasarruf (Gün)</div><div class="kpi-value">{avg_s:.1f}</div></div>', unsafe_allow_html=True)
           k5.markdown(f'<div class="kpi-card"><div class="kpi-title">Operasyonel Risk</div><div class="kpi-value">%{risk_ratio:.1f}</div></div>', unsafe_allow_html=True)
           st.subheader("📋 1. Günlük & Saatlik Operasyonel Detay")
           summary_rows = pd.DataFrame({'Tarih': ['DÖNEM TOPLAMI', 'GÜNLÜK ORTALAMA (KPI)'], 'Saat': ['-', '-'], 'Mevcut_Planlanan': [total_p_sum, avg_p], 'Fiili_Kullanilan': [total_k_sum, avg_k], 'Onerilen_Güvenli_Kapasite': [total_o_sum, avg_o], 'Fark': [total_fark_sum, avg_s], 'Riskli_mi?': ['-', '-']})
           final_daily = pd.concat([daily_detail, summary_rows], ignore_index=True)
           def style_risk(row):
               if row['Riskli_mi?'] == 'RİSK': return ['background-color: #ffcccc'] * len(row)
               elif 'TOPLAMI' in str(row['Tarih']): return ['font-weight: bold; background-color: #f0f2f6'] * len(row)
               elif 'ORTALAMA' in str(row['Tarih']): return ['font-weight: bold; background-color: #e9f5db; color: #2d6a4f'] * len(row)
               return [''] * len(row)
           st.dataframe(final_daily.style.apply(style_risk, axis=1).format(precision=1), use_container_width=True)
           riskli_satirlar = daily_detail[daily_detail['Riskli_mi?'] == 'RİSK']
           with st.expander(f"⚠️ Kritik Risk Analizi: Toplam {len(riskli_satirlar)} Riskli Saat"):
               if not riskli_satirlar.empty:
                   st.dataframe(riskli_satirlar.style.format(precision=1), use_container_width=True)
               else:
                   st.success("Risk bulunamadı.")
           st.divider()
           st.subheader("📋 2. Saatlik Stratejik Şablon (Referans)")
           master_plan['Mevcut_Ort_Planlanan'] = master_plan['Saat'].map(daily_detail.groupby('Saat')['Mevcut_Planlanan'].mean())
           master_plan['Mevcut_Ort_Kullanilan'] = master_plan['Saat'].map(daily_detail.groupby('Saat')['Fiili_Kullanilan'].mean())
           st.dataframe(master_plan[['Saat', 'Mevcut_Ort_Planlanan', 'Mevcut_Ort_Kullanilan', 'Onerilen_Güvenli_Kapasite']].style.format(precision=1), use_container_width=True)
   with tab_planlamaci:
       st.title("📅 Planlamacı Karar Destek Ekranı")
       if f_df.empty:
           st.warning("⚠️ Lütfen analiz için kriter seçiniz.")
       else:
           # Planlamacı KPI'ları
           p1, p2, p3 = st.columns(3)
           p1.markdown(f'<div class="kpi-card"><div class="kpi-title">Net Tasarruf (Günlük Adet)</div><div class="kpi-value">{avg_s:.1f}</div></div>', unsafe_allow_html=True)
           p2.markdown(f'<div class="kpi-card"><div class="kpi-title">Net Tasarruf (Dönem Toplam)</div><div class="kpi-value">{total_fark_sum:.0f}</div></div>', unsafe_allow_html=True)
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
           v_total = pd.DataFrame({'Saat Aralığı': ['GRAND TOTAL'], 'Toplam_Onerilen_Adet': [vardiya_ozet['Toplam_Onerilen_Adet'].sum()]})
           vardiya_final = pd.concat([vardiya_ozet, v_total], ignore_index=True)
           st.dataframe(vardiya_final.style.apply(lambda x: ['font-weight: bold; background-color: #f0f2f6' if x.name == len(vardiya_final)-1 else '' for _ in x], axis=1).format(precision=1), use_container_width=True, hide_index=True)
           st.divider()
           with st.expander("⏱️ 2. Saatlik Detay Plan Listesini Gör / Gizle"):
               detay_liste = plan_master[['Saat', 'Onerilen_Güvenli_Kapasite']].copy()
               detay_liste.columns = ['Saat', 'Önerilen Nöbetçi Sayısı']
               d_total = pd.DataFrame({'Saat': ['TOPLAM'], 'Önerilen Nöbetçi Sayısı': [detay_liste['Önerilen Nöbetçi Sayısı'].sum()]})
               detay_final = pd.concat([detay_liste, d_total], ignore_index=True)
               st.dataframe(detay_final.style.apply(lambda x: ['font-weight: bold; background-color: #f0f2f6' if x.name == len(detay_final)-1 else '' for _ in x], axis=1).format(precision=0), use_container_width=True, hide_index=True)
           st.warning("⚠️ **ÖNEMLİ NOT:** Yukarıdaki önerilen adetlerin oluşturacağı operasyonel risk oranını **Operasyonel Analiz** sayfasındaki KPI kartlarından ve risk tablosundan kontrol edebilirsiniz.")
   with tab_strateji:
       st.title("🚀 Global Senaryo ve Strateji Motoru")
       st.write("Tüm kombinasyonlar için optimum nöbet sayılarını belirleyin.")
       if 'strateji_sonuc' not in st.session_state:
           st.session_state.strateji_sonuc = None
       if st.button("Tüm Kombinasyonlar İçin Stratejik Analizi Başlat"):
           with st.spinner("Veriler işleniyor..."):
               global_exec_summary = []
               test_profiles = [70,75,80, 85, 90, 95, 100]
               levels = [('Aylık', 'Ay_TR'), ('Sezonluk', 'Sezon'), ('Yıllık', 'Hepsi')]
               for label, col in levels:
                   if col == 'Hepsi':
                       combos = df.groupby(['Base', 'Baz Filo', 'Pozisyon', 'Nöbet Türü']).size().reset_index().drop(columns=0)
                   else:
                       combos = df.groupby(['Base', 'Baz Filo', 'Pozisyon', 'Nöbet Türü', col]).size().reset_index().drop(columns=0)
                   for _, row in combos.iterrows():
                       c_mask = (df['Base'] == row['Base']) & (df['Baz Filo'] == row['Baz Filo']) & (df['Pozisyon'] == row['Pozisyon']) & (df['Nöbet Türü'] == row['Nöbet Türü'])
                       z_adi = "Tüm Yıl"
                       if col != 'Hepsi':
                           c_mask &= (df[col] == row[col])
                           z_adi = row[col]
                       c_df = df[c_mask].copy()
                       if c_df.empty: continue
                       c_num_days = c_df['Tarih'].nunique()
                       c_d_h = c_df.groupby(['Tarih', 'Saat']).agg(p=('Gitti_Mi', 'count'), f=('Gitti_Mi', 'sum')).reset_index()
                       # Mevcut Plan Ortalaması (Günlük)
                       c_avg_p = c_d_h['p'].sum() / c_num_days
                       for prof in test_profiles:
                           c_m_plan = c_d_h.groupby('Saat').agg(perc=('f', lambda x: np.percentile(x, prof))).reset_index()
                           c_m_plan['rec'] = np.ceil(c_m_plan['perc']).astype(int)
                           # Önerilen Plan Ortalaması (Günlük) - Kritik Düzeltme: Sum of 24h
                           c_avg_o = c_m_plan['rec'].sum()
                           c_d_det = pd.merge(c_d_h, c_m_plan[['Saat', 'rec']], on='Saat')
                           c_r_count = (c_d_det['f'] > c_d_det['rec']).sum()
                           c_r_ratio = (c_r_count / len(c_d_det) * 100) if len(c_d_det) > 0 else 0
                           global_exec_summary.append({
                               'Analiz Seviyesi': label, 'Zaman Dilimi': z_adi, 'Base': row['Base'], 'Filo': row['Baz Filo'],
                               'Pozisyon': row['Pozisyon'], 'Tür': row['Nöbet Türü'], 'Güven Aralığı (%)': prof,
                               'Mevcut Plan (Ort)': round(c_avg_p, 1), 'Önerilen Plan (Ort)': round(float(c_avg_o), 1),
                               'Net Tasarruf': round(c_avg_p - c_avg_o, 1), 'Risk Oranı (%)': round(c_r_ratio, 1)
                           })
               res_df = pd.DataFrame(global_exec_summary)
               def mark_best(group):
                   group['Optimum'] = False
                   positive_savings=group[group['Net Tasarruf'] > 0]
                   if not positive_savings.empty:
                       best_idx = positive_savings.sort_values(by=['Risk Oranı (%)' , 'Net Tasarruf'], ascending= [True,False]).index[0]
                       group.at[best_idx, 'Optimum'] = True
                   return group
               st.session_state.strateji_sonuc = res_df.groupby(['Analiz Seviyesi', 'Zaman Dilimi', 'Base', 'Filo', 'Pozisyon', 'Tür'], group_keys=False).apply(mark_best)
       if st.session_state.strateji_sonuc is not None:
           g_df = st.session_state.strateji_sonuc
           st.divider()
           st.subheader("🎯 Stratejik Filtreleme")
           f1, f2, f3, f4, f5 = st.columns(5)
           with f1: filter_seviye = st.multiselect("Analiz Seviyesi", sorted(g_df['Analiz Seviyesi'].unique()))
           with f2: filter_base = st.multiselect("Base", sorted(g_df['Base'].unique()))
           with f3: filter_pos = st.multiselect("Pozisyon", sorted(g_df['Pozisyon'].unique()))
           with f4: filter_tur = st.multiselect("Nöbet Türü", sorted(g_df['Tür'].unique()))
           with f5: only_optimum = st.checkbox("Sadece Optimum Önerileri Göster", value=False)
           filtered_df = g_df.copy()
           if filter_seviye: filtered_df = filtered_df[filtered_df['Analiz Seviyesi'].isin(filter_seviye)]
           if filter_base: filtered_df = filtered_df[filtered_df['Base'].isin(filter_base)]
           if filter_pos: filtered_df = filtered_df[filtered_df['Pozisyon'].isin(filter_pos)]
           if filter_tur: filtered_df = filtered_df[filtered_df['Tür'].isin(filter_tur)]
           if only_optimum: filtered_df = filtered_df[filtered_df['Optimum'] == True]
           st.subheader("📈 Karar Destek Tablosu")
           def style_optimum(row):
               if row['Optimum']: return ['background-color: #d8f3dc; font-weight: bold; color: black'] * len(row)
               return [''] * len(row)
           st.dataframe(filtered_df.style.apply(style_optimum, axis=1).format(precision=1), use_container_width=True, hide_index=True)
           st.markdown(f"""
<div class="highlight-box">
<b>💡 Öneri Nasıl Hesaplanıyor?</b><br>
               1. Veriler saatlik bazda gruplanır ve seçilen <b>Güven Aralığına</b> göre istatistiksel üst sınır (Percentile) belirlenir.<br>
               2. <b>Yeşil satırlar;</b> ilgili grup için operasyonel riskin en düşük ve tasarrufun en yüksek olduğu denge noktasını temsil eder.<br>
               3. Tabloyu yukarıdaki kutulardan filtreleyerek "Sadece Sezonluk" veya "Sadece Kaptan" gibi spesifik analizler yapabilirsiniz.
</div>
           """, unsafe_allow_html=True)
           output_g = BytesIO()
           with pd.ExcelWriter(output_g, engine='xlsxwriter') as writer:
               g_df.to_excel(writer, index=False, sheet_name='Strateji_Ozeti')
           st.download_button(label="📥 Yönetici Raporunu İndir", data=output_g.getvalue(), file_name="Sirket_Strateji_Raporu.xlsx")
else:
   st.info("Lütfen veri yükleyin.")

