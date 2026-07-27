"""
Tenor-Kurtarma (Grade-Recovery) Modulu
========================================
Kaynak: Aranzazu Mine NI 43-101 Teknik Raporu (Aura Minerals Inc., Mart 2025)
2024 gunluk isletme verilerinden turetilen dogrusal korelasyonlar.

Not: Bu korelasyonlar Aranzazu'ya (skarn tipi Cu-Au-Ag yatagi, kalkopirit
agirlikli) ozeldir. Farkli mineralojide (orn. porfiri) baska bir maden icin
dogrudan kullanilmamalidir - her maden/proje kendi korelasyonuyla calismali.
"""

from dataclasses import dataclass


@dataclass
class GradeRecoveryModel:
    metal: str
    slope: float
    intercept: float
    valid_grade_min: float
    valid_grade_max: float
    source: str

    def predict_recovery(self, head_grade: float) -> float:
        """Tenore (head grade) bagli kurtarma oranini tahmin eder (0-1 araliginda)."""
        recovery = self.slope * head_grade + self.intercept
        return max(0.0, min(1.0, recovery))

    def is_extrapolating(self, head_grade: float) -> bool:
        """Verilen tenor, modelin test edildigi aralik disinda mi kontrol eder."""
        return not (self.valid_grade_min <= head_grade <= self.valid_grade_max)


# --- Aranzazu Mine (2025) korelasyonlari ---
# Aralik, rapordaki gozlemlenen tenor senaryolarina gore belirlendi
# (LOM rezerv: 1.04, Kaynak M+I: 1.18, 2022-24 fiili: 1.51, variability test: 1.79)

ARANZAZU_CU = GradeRecoveryModel(
    metal="Cu", slope=0.0381, intercept=0.8529,
    valid_grade_min=1.0, valid_grade_max=1.8,
    source="Aranzazu NI 43-101 (2025), 2024 isletme verisi korelasyonu",
)

ARANZAZU_AU = GradeRecoveryModel(
    metal="Au", slope=0.0809, intercept=0.7325,
    valid_grade_min=0.6, valid_grade_max=1.0,
    source="Aranzazu NI 43-101 (2025), 2024 isletme verisi korelasyonu",
)

ARANZAZU_AG = GradeRecoveryModel(
    metal="Ag", slope=0.0062, intercept=0.5134,
    valid_grade_min=17.0, valid_grade_max=24.0,
    source="Aranzazu NI 43-101 (2025), 2024 isletme verisi korelasyonu",
)

MODELS = {"Cu": ARANZAZU_CU, "Au": ARANZAZU_AU, "Ag": ARANZAZU_AG}


def predict_recovery(metal: str, head_grade: float) -> dict:
    """
    Verilen metal ve tenor icin kurtarma tahmini dondurur.
    metal: "Cu", "Au" veya "Ag"
    head_grade: Cu icin % cinsinden, Au/Ag icin g/t cinsinden
    """
    if metal not in MODELS:
        raise ValueError(f"Desteklenmeyen metal: {metal}. Secenekler: {list(MODELS)}")

    model = MODELS[metal]
    recovery = model.predict_recovery(head_grade)
    extrapolating = model.is_extrapolating(head_grade)

    return {
        "metal": metal,
        "head_grade": head_grade,
        "predicted_recovery_pct": round(recovery * 100, 2),
        "extrapolating": extrapolating,
        "warning": (
            f"UYARI: Girilen tenor ({head_grade}) modelin test edildigi aralik "
            f"[{model.valid_grade_min}-{model.valid_grade_max}] disinda - "
            f"tahmin guvenilirligi dusuk olabilir."
            if extrapolating else None
        ),
        "source": model.source,
    }


if __name__ == "__main__":
    print("Aranzazu Tenor-Kurtarma Modeli - Dogrulama\n" + "-" * 55)

    # Rapordaki bilinen tenor senaryolariyla capraz kontrol
    test_cases = [
        ("Cu", 1.04, "LOM rezerv tenoru"),
        ("Cu", 1.18, "Kaynak (M+I) tenoru"),
        ("Cu", 1.51, "2022-2024 fiili ortalama"),
        ("Cu", 1.79, "Variability test besleme ortalamasi"),
        ("Au", 0.83, "2024 fiili uretim tenoru"),
        ("Ag", 21.6, "2024 fiili uretim tenoru"),
        ("Cu", 0.47, "Altar Project (farkli maden, extrapolasyon testi)"),
    ]

    for metal, grade, label in test_cases:
        result = predict_recovery(metal, grade)
        flag = " <-- EKSTRAPOLASYON" if result["extrapolating"] else ""
        print(f"[{label}]")
        print(f"  {metal} tenor: {grade} -> Kurtarma: %{result['predicted_recovery_pct']}{flag}")
