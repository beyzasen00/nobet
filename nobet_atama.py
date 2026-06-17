# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
from pulp import *
from datetime import datetime, date
import calendar
from io import BytesIO
# ================= SAYFA AYARLARI ================= #
st.set_page_config(layout="wide", page_title="Sadeleştirilmiş Akıllı Planlayıcı", page_icon="📅")
st.markdown("""
<style>
 .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
 .block-container { padding-top: 2rem; }
 /* Gün kutularını estetikleştirmek için küçük CSS dokunuşu */
 div[data-testid="stCheckbox"] { background: #f8f9fa; padding: 6px; border-radius: 5px; margin-bottom: 2px; }
</style>
""", unsafe_allow_html=True)
# ================= YARDIMCI FONKSİYONLAR ================= #
def get_all_days_of_month(year, month):
  """Seçilen ay ve yıldaki tüm günleri döndürür."""
  num_days = calendar.monthrange(year, month)[1]
  return [date(year, month, day) for day in range(1, num_days + 1)]
def auto_get_hours(d):
  """Gün türüne göre saati otomatik belirler."""
  if d.weekday() == 5:    # Cumartesi
      return 4.5
  elif d.weekday() == 6:  # Pazar
      return 8.0
  else:                   # Hafta içi resmi tatil/özel gün
      return 8.0
# ================= STREAMLIT ARAYÜZÜ ================= #
st.title("🧠 Nisan 2026 Blok Mesai Optimizasyonu")
st.info("💡 **Nasıl Çalışır?** Planlama yapılacak günleri takvimden seçip doğrudan butona basmanız yeterlidir. Sistem mesai saatlerini ve hafta sonu bloklarını otomatik ayarlar.")
# Sidebar - Dosya ve Tarih Seçimi
st.sidebar.header("📂 1. Veri Girişi & Zaman Ayarı")
uploaded_file = st.sidebar.file_uploader("Talepler Excel Dosyası", type=["xlsx"])
current_year = datetime.now().year
selected_year = st.sidebar.selectbox("Yıl", options=range(current_year, current_year + 2), index=0)
selected_month = st.sidebar.selectbox("Ay", options=range(1, 13), format_func=lambda x: calendar.month_name[x], index=3) # Varsayılan Nisan
required_per_day = st.sidebar.number_input("Günlük Gerekli Kişi Sayısı", value=5, min_value=1)
if uploaded_file:
  try:
      # Excel sayfalarını oku
      xl = pd.ExcelFile(uploaded_file)
      plan_df = pd.read_excel(uploaded_file, sheet_name="3.Planlama_Nisan sayfası")
      emp_df = pd.read_excel(uploaded_file, sheet_name="2.Çalışan Sayfası")
      plan_df["AD SOYAD"] = plan_df["AD SOYAD"].astype(str).str.strip()
      emp_df["AD SOYAD"] = emp_df["AD SOYAD"].astype(str).str.strip()
      people = emp_df["AD SOYAD"].tolist()
      group_map = dict(zip(emp_df["AD SOYAD"], emp_df["Grup"].str.upper()))
      mesai_map = dict(zip(emp_df["AD SOYAD"], emp_df["Yıllık Harcanan Mesai"].fillna(0)))
      # --- TEK TEK SEÇİLEBİLEN GÖRSEL TAKVİM ALANI ---
      st.subheader("🛠️ 2. Planlama Yapılacak Günleri Seçin")
      st.write("📅 *Hafta sonları otomatik seçilmiştir. İstediğiniz günün işaretini kaldırabilir veya yeni günler ekleyebilirsiniz:*")
      all_month_days = get_all_days_of_month(selected_year, selected_month)
      active_days_pure = []
      # Günleri 7'şerli sütunlar halinde (Pazartesi-Pazar takvim düzeni) ekrana basıyoruz
      cols = st.columns(7)
      days_of_week = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
      # Takvim başlıkları
      for idx, day_name in enumerate(days_of_week):
          cols[idx].markdown(f"**{day_name}**")
      # Ayın ilk gününün haftanın hangi günü başladığını bulup boşluk bırakıyoruz
      first_day_weekday = all_month_days[0].weekday()
      col_idx = first_day_weekday
      # Boş gün kutuları için ilk sütunları atla
      for i in range(first_day_weekday):
          cols[i].write("")
      # Tüm günleri takvime yerleştir
      for d in all_month_days:
          # Hafta sonu ise (Cumartesi=5, Pazar=6) varsayılanı True (Seçili) yapıyoruz
          is_weekend = d.weekday() in [5, 6]
          # Kullanıcının tıklayarak seçeceği kutucuk
          day_label = d.strftime('%d %b')
          if cols[col_idx].checkbox(day_label, value=is_weekend, key=f"day_{d.day}"):
              active_days_pure.append(d)
          # Sütun yönetimini yap (7 günde bir alt satıra geç)
          col_idx += 1
          if col_idx > 6:
              col_idx = 0
      active_days = sorted([datetime.combine(d, datetime.min.time()) for d in active_days_pure])
      # Seçilen günlerin kısa özeti
      if active_days:
          st.success(f"✅ **Toplam {len(active_days)} gün planlamaya dahil edilmek üzere seçildi.**")
      else:
          st.warning("⚠️ Lütfen takvimden en az 1 gün seçin.")
      # --- OPTİMİZASYON VE HAFIZA YÖNETİMİ ---
      if "df_plan_state" not in st.session_state:
          st.session_state.df_plan_state = None
      if active_days and st.button("🚀 Planı Oluştur"):
          with st.spinner("Model optimize ediliyor..."):
              d_range = range(len(active_days))
              # 1. Talep Puanlaması
              pref_penalty = {}
              date_map = {c.date(): c for c in pd.to_datetime(plan_df.columns, errors='coerce') if not pd.isna(c)}
              for p in people:
                  row = plan_df[plan_df["AD SOYAD"] == p]
                  for d_idx, date_val in enumerate(active_days):
                      val = str(row.iloc[0][date_map[date_val.date()]]).lower() if not row.empty and date_val.date() in date_map else ""
                      if any(k in val for k in ["çalışırım", "calisirim"]):
                          pref_penalty[p, d_idx] = -100
                      elif any(k in val for k in ["çalışamam", "izin", "mazeret"]):
                          pref_penalty[p, d_idx] = 999999
                      else:
                          pref_penalty[p, d_idx] = 0
              # 2. Model Kurulumu
              prob = LpProblem("Sade_Mesai_Modeli", LpMinimize)
              x = LpVariable.dicts("x", (people, d_range), cat='Binary')
              dev = LpVariable.dicts("dev", people, lowBound=0)
              group_slack = LpVariable.dicts("g_slack", (d_range, ["GRUP 1", "GRUP 2", "GRUP 3", "GRUP 4"]), lowBound=0)
              justice_slack = LpVariable.dicts("j_slack", people, lowBound=0)
              # Kısıt A: Günlük Kişi Sayısı
              for d_idx in d_range:
                  prob += lpSum([x[p][d_idx] for p in people]) == required_per_day
              # Kısıt B: OTOMATİK ARDIŞIK HAFTA SONU BLOK KISITI
              for p in people:
                  for i in range(len(active_days) - 1):
                      curr = active_days[i]
                      nxt = active_days[i+1]
                      if (nxt - curr).days == 1 and curr.weekday() == 5 and nxt.weekday() == 6:
                          prob += x[p][i] == x[p][i+1]
              # Kısıt C: Grup Limitleri (Yumuşak Kısıt)
              base_limits = {"GRUP 1": 1, "GRUP 2": 2, "GRUP 3": 2, "GRUP 4": 1}
              for d_idx in d_range:
                  for g, lim in base_limits.items():
                      prob += lpSum([x[p][d_idx] for p in people if group_map.get(p) == g]) <= lim + group_slack[d_idx][g]
              # Kısıt D: Otomatik Saat Hesaplamalı Mesai Dengesi
              toplam_saat = sum(auto_get_hours(d) for d in active_days) * required_per_day
              hedef_ort = np.mean(list(mesai_map.values())) + (toplam_saat / len(people))
              for p in people:
                  p_toplam = mesai_map[p] + lpSum([x[p][d_idx] * auto_get_hours(active_days[d_idx]) for d_idx in d_range])
                  prob += dev[p] >= p_toplam - hedef_ort
                  prob += dev[p] >= hedef_ort - p_toplam
                  prob += lpSum([x[p][d_idx] for d_idx in d_range]) + justice_slack[p] >= 2
              # Amaç Fonksiyonu
              prob += (
                  lpSum([dev[p] for p in people]) * 10 +
                  lpSum([pref_penalty[p, d_idx] * x[p][d_idx] for p in people for d_idx in d_range]) +
                  lpSum([group_slack[d_idx][g] * 100000 for d_idx in d_range for g in base_limits]) +
                  lpSum([justice_slack[p] * 200000 for p in people])
              )
              # --- GÜVENLİ ÇÖZÜCÜ TETİKLEME ALANI ---
              try:
                  prob.solve(PULP_CBC_CMD(msg=False, timeLimit=30))
                  if LpStatus[prob.status] in ['Optimal', 'Unbounded']:
                      res_rows = []
                      for p in people:
                          r = {"AD SOYAD": p, "GRUP": group_map.get(p)}
                          for d_idx, date_val in enumerate(active_days):
                              r[date_val.strftime('%d-%m (%a)')] = "NÖBET" if value(x[p][d_idx]) > 0.5 else ""
                          res_rows.append(r)
                      st.session_state.df_plan_state = pd.DataFrame(res_rows)
                      st.success("✅ Plan başarıyla oluşturuldu!")
                  else:
                      st.error(f"⚠️ Matematiksel Model Çözülemedi. Durum: {LpStatus[prob.status]}. Seçilen gün sayısına kıyasla 'Günlük Gerekli Kişi Sayısı' çok yüksek veya grup limitleri yetersiz kalıyor olabilir.")
              except Exception as solver_error:
                  st.error(f"🚨 Çözücü Hatası: Matematiksel kısıt yoğunluğundan dolayı sistem yanıt vermedi. Lütfen kısıtlarınızı veya günlük kişi sayısını esneterek tekrar deneyin.")
      # Düzenleme ve Canlı Güncelleme Ekranı
      if st.session_state.df_plan_state is not None and active_days:
          t1, t2 = st.tabs(["📅 Düzenlenebilir Plan Çizelgesi", "📊 Canlı Mesai İstatistikleri"])
          with t1:
              st.subheader("👇 Hücreleri Manuel Düzenleyebilirsiniz:")
              edited_df = st.data_editor(st.session_state.df_plan_state, use_container_width=True)
              st.session_state.df_plan_state = edited_df
          with t2:
              updated_summary = []
              for p in people:
                  p_row = edited_df[edited_df["AD SOYAD"] == p]
                  bu_ay_saat = 0
                  nobet_gun_sayisi = 0
                  if not p_row.empty:
                      for d_idx, date_val in enumerate(active_days):
                          col_name = date_val.strftime('%d-%m (%a)')
                          if str(p_row.iloc[0][col_name]).strip().upper() == "NÖBET":
                              bu_ay_saat += auto_get_hours(date_val)
                              nobet_gun_sayisi += 1
                  updated_summary.append({
                      "AD SOYAD": p,
                      "Grup": group_map.get(p),
                      "Eski Mesai": mesai_map[p],
                      "Bu Ayın Mesaisi": bu_ay_saat,
                      "Yeni Toplam": mesai_map[p] + bu_ay_saat,
                      "Nöbet Günü Sayısı": nobet_gun_sayisi
                  })
              df_summary_edited = pd.DataFrame(updated_summary)
              st.dataframe(df_summary_edited.sort_values("Yeni Toplam"), use_container_width=True)
          output = BytesIO()
          with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
              edited_df.to_excel(writer, sheet_name="Nobet_Plani", index=False)
              df_summary_edited.to_excel(writer, sheet_name="Ozet", index=False)
          st.download_button("📥 Güncel Planı İndir", output.getvalue(), f"{selected_month}_{selected_year}_Nobet_Plani.xlsx")
  except Exception as e:
      st.error(f"Sistemsel Hata: {e}")
else:
    st.info("👋 Başlamak için lütfen Excel dosyasını sol menüden yükleyin.")
