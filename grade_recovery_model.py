"""
Tenör-Verim (Grade-Recovery) Modülü
========================================
Kaynak: Aranzazu Mine NI 43-101 Teknik Raporu (Aura Minerals Inc. / SLR
Consulting, 28 Mart 2025, geçerlilik tarihi 31 Aralık 2024) - Bölüm 13.5
(Recovery Projections for the Cash Flow Model), Tablo 13-18/13-19 ve
Şekil 13-14/13-15/13-16/13-20/13-21/13-22.

GÜNCELLEME NOTU (2025 rapor verisiyle değiştirildi): Bu modülün önceki
versiyonu basit doğrusal korelasyonlar içeriyordu (kaynağı tam net
belirtilmemiş). Bu versiyon, raporun AÇIKÇA "mevcut nakit akışı modelinde
kullanıldığı" belirtilen RESMİ denklemleri (Tablo 13-19) kullanır -
LOGARİTMİK form (Cu, Au için), doğrusal (Ag için). Ayrıca çok daha geniş
bir tenör aralığını (0.70-1.60% Cu - Tablo 13-18'de tablo halinde
verilmiş) kapsar; önceki sürümdeki 1.0-1.8% sınırından çok daha geniştir.

İKİ FARKLI VERİ SETİ MEVCUT (rapor ikisini de sunuyor, farklı amaçlarla):

1. PLANT_DATA (resmi model) - Eylül-Aralık 2024 günlük işletme verisinden
   türetilmiş, raporun "nakit akışı modelinde kullanılacak" diye AÇIKÇA
   seçtiği denklem (Tablo 13-19). Bu donemde flotasyon devresi dizel
   katkılı çalışıyordu (molibden verim için eklenmişti, bakır
   verimi da olumlu etkiledi) - yani PLANT_DATA denklemi bu spesifik
   işletme koşuluna özeldir.

2. DRILL_DATA (variability test) - 210 karot örneğinden (TÜM yatak
   genelinde, farklı mineralojik zonlardan - GH Pillar, BW, Mexicana
   South, AA) türetilmiş denklem (Şekil 13-14/13-15/13-16). ÇOK DÜŞÜK
   R^2 (0.05-0.11) - yani tenör tek başına verimi zayıf açıklamakta,
   saha/mineraloji değişkenliği çok daha baskın bir faktördür. Buna
   karşın çok daha geniş bir tenör aralığını (gerçek karot örneklerinin
   gözlemlenen aralığı) kapsar ve FARKLI ZONLARIN mineralojik
   çeşitliliğini içerir - bu da onu "benzer olmayan/değişken
   yataklanma" senaryoları için KABA bir referans yapar. Kesinlikle
   PLANT_DATA modelinin yerine geçmez, sadece tamamlayıcı/ihtiyatlı bir
   ikinci görüş olarak kullanılmalıdır.

ÖNEMLİ UYARI: DRILL_DATA denklemlerinin R^2 değerleri ÇOK DÜŞÜKTÜR
(0.05-0.11). Bu denklemler "kesin tahmin" değil, KABA BİR EĞİLİM
GÖSTERGESİDİR - kullanıcılar bu modelle yapılan tahminlerin geniş bir
belirsizlik aralığı taşıdığını bilmelidir.

NOT: Bu korelasyonlar Aranzazu'ya (skarn tipi Cu-Au-Ag yatağı, kalkopirit
ağırlıklı) özeldir. Farklı mineralojide (orn. porfiri) başka bir maden
için doğrudan kullanılmamalıdır - her maden/proje kendi korelasyonuyla
çalışmalı (DRILL_DATA modeli bile, aynı yatağın ic değişkenliğini
yansıtır - farklı bir yatağın değil).
"""

import math
from dataclasses import dataclass


@dataclass
class GradeRecoveryModel:
    metal: str
    form: str  # "log" -> a*ln(grade)+b, "linear" -> a*grade+b
    a: float
    b: float
    valid_grade_min: float
    valid_grade_max: float
    source: str
    r_squared: float = None
    dataset: str = ""  # "plant_data" veya "drill_data"

    def predict_recovery(self, head_grade: float) -> float:
        """Tenöre (head grade) bağlı verim oranını tahmin eder (0-1 aralığında)."""
        if head_grade <= 0:
            raise ValueError("Tenör pozitif olmalı.")
        if self.form == "log":
            recovery = self.a * math.log(head_grade) + self.b
        else:
            recovery = self.a * head_grade + self.b
        return max(0.0, min(1.0, recovery))

    def is_extrapolating(self, head_grade: float) -> bool:
        """Verilen tenör, modelin test edildiği aralık dışında mi kontrol eder."""
        return not (self.valid_grade_min <= head_grade <= self.valid_grade_max)


# ============================================================
# 1) PLANT_DATA (RESMİ MODEL) - Tablo 13-19, Eylül-Aralık 2024
#    günlük işletme verisi - raporun nakit akışı modelinde
#    FİİLEN KULLANDIĞI denklemler
# ============================================================

ARANZAZU_CU = GradeRecoveryModel(
    metal="Cu", form="log", a=0.0448, b=0.9089,
    valid_grade_min=0.70, valid_grade_max=1.60,
    source=(
        "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Tablo 13-19 - "
        "Eylül-Aralık 2024 günlük işletme verisi (resmi nakit akışı "
        "modeli denklemi, Şekil 13-20)"
    ),
    r_squared=0.2423,
    dataset="plant_data",
)

ARANZAZU_AU = GradeRecoveryModel(
    metal="Au", form="log", a=0.077, b=0.8432,
    valid_grade_min=0.10, valid_grade_max=1.00,
    source=(
        "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Tablo 13-19 - "
        "Eylül-Aralık 2024 günlük işletme verisi (resmi nakit akışı "
        "modeli denklemi, Şekil 13-21)"
    ),
    r_squared=0.1449,
    dataset="plant_data",
)

ARANZAZU_AG = GradeRecoveryModel(
    metal="Ag", form="linear", a=0.0089, b=0.4601,
    valid_grade_min=8.00, valid_grade_max=26.00,
    source=(
        "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Tablo 13-19 - "
        "Eylül-Aralık 2024 günlük işletme verisi (resmi nakit akışı "
        "modeli denklemi, Şekil 13-22)"
    ),
    r_squared=0.4640,
    dataset="plant_data",
)

MODELS = {"Cu": ARANZAZU_CU, "Au": ARANZAZU_AU, "Ag": ARANZAZU_AG}


# ============================================================
# 2) DRILL_DATA (ALTERNATİF / VARIABILITY TEST) - 210 karot
#    örneğinden (Şekil 13-14/13-15/13-16), TÜM yatak genelinde
#    (farklı mineralojik zonlar dahil) - ÇOK DÜŞÜK R^2, ama ÇOK
#    DAHA GENİŞ tenör aralığı. "Değişken/farklı yataklanma"
#    senaryoları için KABA bir referans - PLANT_DATA'nin yerine
#    GEÇMEZ.
# ============================================================

ARANZAZU_CU_DRILLDATA = GradeRecoveryModel(
    metal="Cu", form="log", a=0.05726, b=0.85589,
    valid_grade_min=0.5, valid_grade_max=3.0,
    source=(
        "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Şekil 13-14 - 210 karot "
        "örneğinden (2024 variability test, tüm yatak/zonlar) türetilmiş "
        "eğilim - DÜŞÜK R^2 (0.107), sadece kaba eğilim göstergesi"
    ),
    r_squared=0.1073,
    dataset="drill_data",
)

ARANZAZU_AU_DRILLDATA = GradeRecoveryModel(
    metal="Au", form="linear", a=0.040202, b=0.75054,
    valid_grade_min=0.1, valid_grade_max=2.0,
    source=(
        "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Şekil 13-15 - 210 karot "
        "örneğinden (2024 variability test) türetilmiş eğilim - ÇOK DÜŞÜK "
        "R^2 (0.055), sadece kaba eğilim göstergesi"
    ),
    r_squared=0.0545,
    dataset="drill_data",
)

ARANZAZU_AG_DRILLDATA = GradeRecoveryModel(
    metal="Ag", form="linear", a=0.002738, b=0.62084,
    valid_grade_min=6.0, valid_grade_max=70.0,
    source=(
        "Aranzazu NI 43-101 (SLR, 28 Mart 2025), Şekil 13-16 - 210 karot "
        "örneğinden (2024 variability test) türetilmiş eğilim - DÜŞÜK R^2 "
        "(0.089), sadece kaba eğilim göstergesi"
    ),
    r_squared=0.0894,
    dataset="drill_data",
)

DRILLDATA_MODELS = {
    "Cu": ARANZAZU_CU_DRILLDATA,
    "Au": ARANZAZU_AU_DRILLDATA,
    "Ag": ARANZAZU_AG_DRILLDATA,
}


def predict_recovery(metal: str, head_grade: float, dataset: str = "plant_data") -> dict:
    """
    Verilen metal ve tenör için verim tahmini döndürür.

    metal: "Cu", "Au" veya "Ag"
    head_grade: Cu için % cinsinden, Au/Ag için g/t cinsinden
    dataset: "plant_data" (varsayılan, RESMİ model - Tablo 13-19) veya
             "drill_data" (variability test, geniş aralık, DÜŞÜK R^2 -
             kaba eğilim göstergesi, kesin tahmin değil)
    """
    if dataset not in ("plant_data", "drill_data"):
        raise ValueError('dataset "plant_data" veya "drill_data" olmalı.')

    models = MODELS if dataset == "plant_data" else DRILLDATA_MODELS
    if metal not in models:
        raise ValueError(f"Desteklenmeyen metal: {metal}. Seçenekler: {list(models)}")

    model = models[metal]
    recovery = model.predict_recovery(head_grade)
    extrapolating = model.is_extrapolating(head_grade)

    warning_parts = []
    if extrapolating:
        warning_parts.append(
            f"UYARI: Girilen tenör ({head_grade}) modelin test edildiği aralık "
            f"[{model.valid_grade_min}-{model.valid_grade_max}] dışında - "
            f"tahmin güvenilirliği düşük olabilir."
        )
    if dataset == "drill_data":
        warning_parts.append(
            f"DİKKAT: Bu model düşük R^2 ({model.r_squared}) ile kaba bir "
            f"eğilimdir - tenör, verimi zayıf açıklamaktadır (saha/"
            f"mineraloji değişkenliği çok daha baskındır). Kesin tahmin "
            f"değil, sadece yön göstergesi olarak kullanılmalıdır."
        )

    return {
        "metal": metal,
        "head_grade": head_grade,
        "dataset": dataset,
        "predicted_recovery_pct": round(recovery * 100, 2),
        "extrapolating": extrapolating,
        "r_squared": model.r_squared,
        "warning": " ".join(warning_parts) if warning_parts else None,
        "source": model.source,
    }


if __name__ == "__main__":
    print("Aranzazu Tenör-Verim Modeli - Doğrulama (2025 TR verisi)\n" + "-" * 60)

    print("\n=== 1) PLANT_DATA (resmi model, Tablo 13-19) ===")
    test_cases_plant = [
        ("Cu", 0.70, "LOM plan alt sınır (2031 civarı)"),
        ("Cu", 1.40, "LOM plan üst sınır (2025 başlangıcı)"),
        ("Cu", 1.51, "2022-24 fiili ortalama (doğrulama)"),
        ("Au", 0.40, "LOM plan (2032 civarı)"),
        ("Au", 0.90, "LOM plan (2025 civarı)"),
        ("Ag", 14.0, "LOM plan alt sınır (2030 civarı)"),
        ("Ag", 20.0, "LOM plan üst sınır (2025 civarı)"),
    ]
    for metal, grade, label in test_cases_plant:
        result = predict_recovery(metal, grade, dataset="plant_data")
        flag = " <-- EKSTRAPOLASYON" if result["extrapolating"] else ""
        print(f"[{label}] {metal} tenör: {grade} -> Verim: %{result['predicted_recovery_pct']}{flag}")

    print("\n=== 2) DRILL_DATA (variability test, geniş aralık, DÜŞÜK R^2) ===")
    test_cases_drill = [
        ("Cu", 0.53, "En düşük gözlemlenen variability tenörü"),
        ("Cu", 8.71, "En yüksek gözlemlenen variability tenörü"),
        ("Cu", 0.47, "Altar Project (farklı maden, extrapolasyon testi)"),
        ("Au", 5.40, "En yüksek gözlemlenen Au variability tenörü"),
        ("Ag", 111.0, "En yüksek gözlemlenen Ag variability tenörü"),
    ]
    for metal, grade, label in test_cases_drill:
        result = predict_recovery(metal, grade, dataset="drill_data")
        flag = " <-- EKSTRAPOLASYON" if result["extrapolating"] else ""
        print(f"[{label}] {metal} tenör: {grade} -> Verim: %{result['predicted_recovery_pct']}{flag}")
        if result["warning"]:
            print(f"    {result['warning']}")
