import streamlit as st
import pandas as pd
import numpy as np
import calendar
st.set_page_config(layout="wide", page_title="Stratejik Nöbet Analizi")
# --- CSS Stil ---
st.markdown("""
<style>
.kpi-card { background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-top: 5px solid #1a73e8; text-align: center; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
.kpi-val { font-size: 28px; font-weight: bold; color: #1a73e8; }
.kpi-label { font-size: 14px; color: #555; font-weight: 600; margin-bottom: 5px; }
.kpi-gain { border-top: 5px solid #28a745; }
.kpi-gain .kpi-val { color: #28a745; }
.kpi-risk { border-top: 5px solid #dc3545; }
.kpi-risk .kpi-val { color: #dc3545; }
</style>
""", unsafe_allow_html=True)
def get_shift_group(hour):
   if pd.isna(hour): return "Belirsiz"
   if 2 <= hour < 5: return "02:00 - 05:00"
   elif 5 <= hour < 8: return "05:00 - 08:00"
   elif 8 <= hour < 11: return "08:00 - 11:00"
   elif 11 <= hour < 14: return "11:00 - 14:00"
   elif 14 <= hour < 18: return "14:00 - 18:00"
   elif 18 <= hour < 22: return "18:00 - 22:00"
   else: return "22:00 - 02:00"
st.title("🛡️ Stratejik Nöbet Kapasite Analizi")
uploaded_file = st.sidebar.file_uploader("Nöbet Verisi Yükle (Excel/CSV)", type=['xlsx', 'csv'])
if uploaded_file:
   df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file)
   df.columns = df.columns.str.strip()
   if 'Nöbet Başlangıç Tarihi' in df.columns:
       df['Nobet_Bas_DT'] = pd.to_datetime(df['Nöbet Başlangıç Tarihi'], errors='coerce')
       df['Ay_Yil'] = df['Nobet_Bas_DT'].dt.strftime('%Y-%m')
   else:
       st.error("Excel'de 'Nöbet Başlangıç Tarihi' kolonu bulunamadı!")
       st.stop()
   aylar = sorted(df['Ay_Yil'].dropna().unique())
   sel_aylar = st.sidebar.multiselect("Aylar", options=aylar, default=aylar)
   sel_base = st.sidebar.multiselect("Base", options=sorted(df['Base'].unique()), default=df['Base'].unique())
   sel_filo = st.sidebar.multiselect("Baz Filo", options=sorted(df['Baz Filo'].unique()), default=df['Baz Filo'].unique())
   sel_sinif = st.sidebar.multiselect("Uçucu Sınıfı", options=sorted(df['Uçucu Sınıfı'].unique()), default=df['Uçucu Sınıfı'].unique())
   sel_tur = st.sidebar.multiselect("Nöbet Türü", options=sorted(df['Nöbet Türü'].unique()), default=df['Nöbet Türü'].unique())
   confidence = st.sidebar.select_slider("Güven Aralığı (Percentile %)", options=[70, 75, 80, 85, 90, 95, 100], value=95)
   mask = (df['Ay_Yil'].isin(sel_aylar)) & (df['Base'].isin(sel_base)) & \
          (df['Baz Filo'].isin(sel_filo)) & (df['Uçucu Sınıfı'].isin(sel_sinif)) & \
          (df['Nöbet Türü'].isin(sel_tur))
   f_all = df[mask].copy()
   if not f_all.empty:
       f_all['Nobetten Goreve Gitti mi?'] = f_all['Nobetten Goreve Gitti mi?'].astype(str).str.strip().str.upper()
       total_planned_rows = len(f_all)
       total_calendar_days = 0
       for ay_yil in sel_aylar:
           y, m = map(int, ay_yil.split('-'))
           total_calendar_days += calendar.monthrange(y, m)[1]
       if total_calendar_days == 0: total_calendar_days = 1
       f_all['Imza Saati DT'] = pd.to_datetime(f_all['Imza Saati'], errors='coerce')
       f_all['Imza_Tarih'] = f_all['Imza Saati DT'].dt.date
       f_all['Saat_Grubu'] = f_all['Imza Saati DT'].dt.hour.apply(get_shift_group)
       f_giden = f_all[f_all['Nobetten Goreve Gitti mi?'] == 'Y'].copy()
       total_used_rows = len(f_giden)
       f_giden_analiz = f_giden.dropna(subset=['Imza Saati DT'])
       avg_planned_daily = total_planned_rows / total_calendar_days
       avg_used_daily = total_used_rows / total_calendar_days
       # Risk Hesaplama Alanı
       risk_orani = 0
       if not f_giden_analiz.empty:
           usage_counts = f_giden_analiz.groupby(['Imza_Tarih', 'Saat_Grubu']).size().reset_index(name='Gerçek Kullanım')
           recommended_stats = usage_counts.groupby('Saat_Grubu')['Gerçek Kullanım'].quantile(confidence / 100).apply(np.ceil).to_dict()
           daily_total_recommended = sum(recommended_stats.values())
           usage_counts['Önerilen Adet'] = usage_counts['Saat_Grubu'].map(recommended_stats).astype(int)
           usage_counts['Risk Durumu'] = usage_counts['Gerçek Kullanım'] > usage_counts['Önerilen Adet']
           # Risk Oranı: Riskli satır sayısı / Toplam gözlem (tarih-saat grubu kombinasyonu) sayısı
           risk_orani = (usage_counts['Risk Durumu'].sum() / len(usage_counts)) * 100
       else:
           usage_counts = pd.DataFrame()
           recommended_stats = {}
           daily_total_recommended = 0
       gain = avg_planned_daily - daily_total_recommended
       # --- KPI PANELİ ---
       st.markdown(f"### 📊 Operasyonel Performans Özeti ({total_calendar_days} Gün)")
       k1, k2, k3, k4, k5 = st.columns(5)
       with k1:
           st.markdown(f'<div class="kpi-card"><div class="kpi-label">Günlük Ort. Planlanan</div><div class="kpi-val">{avg_planned_daily:.1f}</div></div>', unsafe_allow_html=True)
       with k2:
           st.markdown(f'<div class="kpi-card"><div class="kpi-label">Günlük Ort. Kullanılan</div><div class="kpi-val">{avg_used_daily:.1f}</div></div>', unsafe_allow_html=True)
       with k3:
           st.markdown(f'<div class="kpi-card"><div class="kpi-label">Günlük Ort. Önerilen</div><div class="kpi-val">{daily_total_recommended:.1f}</div></div>', unsafe_allow_html=True)
       with k4:
           st.markdown(f'<div class="kpi-card kpi-gain"><div class="kpi-label">Günlük Ort. Kazanç</div><div class="kpi-val">{max(0, gain):.1f}</div></div>', unsafe_allow_html=True)
       with k5:
           st.markdown(f'<div class="kpi-card kpi-risk"><div class="kpi-label">Genel Risk Oranı</div><div class="kpi-val">%{risk_orani:.1f}</div></div>', unsafe_allow_html=True)
       # --- TABLOLAR ---
       if not usage_counts.empty:
           st.divider()
           st.subheader("📅 Tarih Bazlı Kullanım ve Risk Detayı")
           st.dataframe(
               usage_counts.style.apply(lambda row: ['background-color: #ffcccc' if row['Risk Durumu'] else '' for _ in row], axis=1).format(precision=0),
               use_container_width=True
           )
           st.subheader("🕒 Vardiya Grubu Bazlı İstatistikler")
           shift_summary = usage_counts.groupby('Saat_Grubu').agg(
               Ortalama_Kullanim=('Gerçek Kullanım', 'mean'),
               Maksimum_Kullanim=('Gerçek Kullanım', 'max'),
               Ideal_Kapasite=('Önerilen Adet', 'first'),
               Riskli_Gun_Sayisi=('Risk Durumu', 'sum')
           ).reset_index()
           st.table(shift_summary.style.format({'Ortalama_Kullanim': '{:.1f}'}))
       with st.expander("🔍 Veri Kontrolü (N Satırları Dahil)"):
           st.write(f"Toplam Filtrelenmiş Satır: {total_planned_rows}")
           st.write(f_all['Nobetten Goreve Gitti mi?'].value_counts())
   else:
       st.warning("Filtrelere uygun veri bulunamadı.")