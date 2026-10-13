"""
Siyanür liçi (CIL/CIP) kinetik analizi ve CIL tank boyutlandırma
==================================================================

Bu modül deney verisinden (süre - ekstraksiyon) kinetik model uydurur ve CIL devresi için
tank hacmi hesaplar. Yalnızca numpy kullanır (ek bağımlılık yoktur).

Veri kaynağı notu
-----------------
Kinetik model denklemleri genel hidrometalurji literatürünün standart ifadeleridir
(Levenspiel, Chemical Reaction Engineering; Habashi, Principles of Extractive Metallurgy;
Marsden & House, Chemistry of Gold Extraction). Burada bir NI 43-101 raporundan türetilmiş
sayı YOKTUR; parametreler kullanıcının deney verisinden hesaplanır.

CIL tasarım referans değerleri (bekleme süresi, katı oranı, NaCN ve kireç tüketimi, tank
adedi) Enchi Gold Project PFS (Lycopodium, Ağustos 2026), Tablo 17.1.1'den alınmıştır.

Modeller (X = ekstraksiyon oranı, t = süre, k = hız sabiti)
-----------------------------------------------------------
birinci_derece : X = Xmax * (1 - exp(-k t))
avrami         : X = Xmax * (1 - exp(-(k t)^n))
scm_kimyasal   : 1 - (1 - X)^(1/3) = k t          (büzülen çekirdek, kimyasal reaksiyon kontrolü)
scm_difuzyon   : 1 - 3(1-X)^(2/3) + 2(1-X) = k t  (büzülen çekirdek, ürün tabakası difüzyonu)
film_difuzyon  : X = k t                           (büzülen çekirdek, film difüzyonu)
SCM modellerinde X, ulaşılabilir maksimuma (Xmax) bölünerek normalize edilir.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import math
import numpy as np

R_GAZ = 8.314  # J/(mol K)

MODELLER = {
    "birinci_derece": "Birinci derece: X = Xmax(1 - exp(-kt))",
    "avrami": "Avrami (JMAK): X = Xmax(1 - exp(-(kt)^n))",
    "scm_kimyasal": "Büzülen çekirdek, kimyasal reaksiyon kontrolü: 1-(1-X)^(1/3) = kt",
    "scm_difuzyon": "Büzülen çekirdek, ürün tabakası difüzyonu: 1-3(1-X)^(2/3)+2(1-X) = kt",
    "film_difuzyon": "Büzülen çekirdek, film difüzyonu: X = kt",
}
# Serbest parametre sayısı (AICc için); Xmax SCM modellerinde sabit tutulur
_PARAM_SAYISI = {"birinci_derece": 2, "avrami": 3, "scm_kimyasal": 1, "scm_difuzyon": 1, "film_difuzyon": 1}

# CIL tasarım referansları: Enchi PFS Tablo 17.1.1 (Lycopodium, Ağustos 2026)
ENCHI_CIL_REFERANS = {
    "kaynak": "Enchi Gold Project PFS (Lycopodium, Ağustos 2026), Tablo 17.1.1",
    "senaryolar": ["Oksit P80 75 µm", "Oksit P80 53 µm", "Sert (fresh) P80 53 µm"],
    "bekleme_suresi_h": [24, 24, 48],
    "katı_orani_pct_w": [45, 45, 50],
    "nacn_kg_t": [0.83, 1.00, 1.49],
    "kirec_kg_t": [2.61, 2.54, 1.41],
    "tank_adedi": 7,
    "kullanilabilirlik_ogutme_pct": 91.3,
    "not": ("NaCN değerlerinde rapor, laboratuvarın fazla dozladığı gerekçesiyle test sonucuna %50 indirim "
            "uygulandığını belirtir."),
}


@dataclass
class KinetikSonuc:
    model: str
    ad: str
    parametreler: Dict[str, float]
    rmse: float          # ekstraksiyon yüzde puanı
    r2: float            # ekstraksiyon (X) uzayında
    aicc: Optional[float]
    n_nokta: int
    uyari: str = ""

    def tahmin(self, t) -> np.ndarray:
        return _tahmin(self.model, self.parametreler, np.asarray(t, dtype=float))


# ----------------------------------------------------------------------
# Veri temizleme
# ----------------------------------------------------------------------
def temizle(sure: Sequence[float], ekstraksiyon: Sequence[float]):
    """NaN satırlarını atar, süreye göre sıralar, aralık kontrolü yapar."""
    t = np.asarray(sure, dtype=float)
    x = np.asarray(ekstraksiyon, dtype=float)
    if t.shape != x.shape:
        raise ValueError("Süre ve ekstraksiyon sütunları aynı uzunlukta olmalı.")
    ok = np.isfinite(t) & np.isfinite(x)
    t, x = t[ok], x[ok]
    if np.any(t < 0):
        raise ValueError("Süre negatif olamaz.")
    if np.any((x < 0) | (x > 100)):
        raise ValueError("Ekstraksiyon %0-100 aralığında olmalı.")
    sira = np.argsort(t, kind="stable")
    t, x = t[sira], x[sira]
    if int(np.sum(t > 0)) < 4:
        raise ValueError("Kinetik uydurma için süresi sıfırdan büyük en az 4 ölçüm gerekir.")
    if len(np.unique(t[t > 0])) < 4:
        raise ValueError("Birbirinden farklı en az 4 süre değeri gerekir.")
    return t, x


# ----------------------------------------------------------------------
# Model tahminleri
# ----------------------------------------------------------------------
def _g_scm_difuzyon(x: np.ndarray) -> np.ndarray:
    y = 1.0 - x
    return 1.0 - 3.0 * y ** (2.0 / 3.0) + 2.0 * y


def _x_scm_difuzyon(g: np.ndarray) -> np.ndarray:
    """g(x) = 1 - 3(1-x)^(2/3) + 2(1-x) denkleminin x için ters çözümü (bisection)."""
    g = np.clip(np.asarray(g, dtype=float), 0.0, 1.0)
    lo = np.zeros_like(g)
    hi = np.ones_like(g)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        yuksek = _g_scm_difuzyon(mid) > g
        hi = np.where(yuksek, mid, hi)
        lo = np.where(yuksek, lo, mid)
    return 0.5 * (lo + hi)


def _tahmin(model: str, p: Dict[str, float], t: np.ndarray) -> np.ndarray:
    k = p["k"]
    xm = p["Xmax"]
    if model == "birinci_derece":
        return xm * (1.0 - np.exp(-k * t))
    if model == "avrami":
        return xm * (1.0 - np.exp(-np.power(np.maximum(k * t, 0.0), p["n"])))
    kt = np.clip(k * t, 0.0, 1.0)
    if model == "scm_kimyasal":
        return xm * (1.0 - (1.0 - kt) ** 3)
    if model == "film_difuzyon":
        return xm * kt
    if model == "scm_difuzyon":
        return xm * _x_scm_difuzyon(kt)
    raise KeyError(model)


# ----------------------------------------------------------------------
# Sayısal yardımcılar (numpy-only)
# ----------------------------------------------------------------------
def _golden(f, a: float, b: float, iters: int = 80) -> float:
    gr = (math.sqrt(5.0) - 1.0) / 2.0
    c, d = b - gr * (b - a), a + gr * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(iters):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - gr * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + gr * (b - a)
            fd = f(d)
    return 0.5 * (a + b)


def _min_log_k(sse_fn, k0: float) -> float:
    """k için SSE'yi log-ızgara + altın oran ile minimize eder."""
    kler = k0 * np.logspace(-2.0, 2.0, 160)
    sse = np.array([sse_fn(k) for k in kler])
    i = int(np.argmin(sse))
    lo = kler[max(i - 1, 0)]
    hi = kler[min(i + 1, len(kler) - 1)]
    return math.exp(_golden(lambda lk: sse_fn(math.exp(lk)), math.log(lo), math.log(hi), 60))


def _nelder_mead(f, x0: np.ndarray, adim: float = 0.3, iters: int = 400) -> np.ndarray:
    n = len(x0)
    s = [np.array(x0, dtype=float)]
    for i in range(n):
        v = np.array(x0, dtype=float)
        v[i] += adim if v[i] == 0 else adim * abs(v[i]) + 0.05
        s.append(v)
    fs = [f(v) for v in s]
    for _ in range(iters):
        sira = np.argsort(fs)
        s = [s[i] for i in sira]
        fs = [fs[i] for i in sira]
        merkez = np.mean(s[:-1], axis=0)
        xr = merkez + (merkez - s[-1])
        fr = f(xr)
        if fr < fs[0]:
            xe = merkez + 2.0 * (merkez - s[-1])
            fe = f(xe)
            s[-1], fs[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < fs[-2]:
            s[-1], fs[-1] = xr, fr
        else:
            xc = merkez + 0.5 * ((s[-1] if fr >= fs[-1] else xr) - merkez)
            fc = f(xc)
            if fc < min(fr, fs[-1]):
                s[-1], fs[-1] = xc, fc
            else:
                for i in range(1, len(s)):
                    s[i] = s[0] + 0.5 * (s[i] - s[0])
                    fs[i] = f(s[i])
        if max(abs(fs[-1] - fs[0]), 0.0) < 1e-12:
            break
    return s[int(np.argmin(fs))]


def _metrikler(t, x, tahmin, param_sayisi):
    n = len(x)
    sse = float(np.sum((x - tahmin) ** 2))
    sst = float(np.sum((x - np.mean(x)) ** 2))
    r2 = 1.0 - sse / sst if sst > 0 else float("nan")
    rmse = math.sqrt(sse / n)
    aicc = None
    if n - param_sayisi - 1 > 0 and sse > 0:
        aicc = n * math.log(sse / n) + 2 * param_sayisi + 2.0 * param_sayisi * (param_sayisi + 1) / (n - param_sayisi - 1)
    return rmse, r2, aicc


# ----------------------------------------------------------------------
# Uydurma
# ----------------------------------------------------------------------
def _fit_birinci_derece(t, x):
    xmax_alt = float(np.max(x)) + 1e-3
    xmax_ust = 100.0
    if xmax_alt >= xmax_ust:
        xmax_alt = xmax_ust - 1e-3
    k0 = 1.0 / max(float(np.median(t[t > 0])), 1e-9)

    def profil(xm):
        sse_fn = lambda k: float(np.sum((x - xm * (1 - np.exp(-k * t))) ** 2))
        k = _min_log_k(sse_fn, k0)
        return sse_fn(k), k

    xm = _golden(lambda v: profil(v)[0], xmax_alt, xmax_ust, 60)
    _, k = profil(xm)
    return {"Xmax": float(xm), "k": float(k)}


def _fit_avrami(t, x, baslangic):
    xmax_alt = float(np.max(x)) + 1e-3
    aralik = 100.0 - xmax_alt
    if aralik <= 0:
        aralik = 1e-3

    def coz(p):
        k = math.exp(p[0])
        n = float(np.clip(math.exp(p[1]), 0.2, 5.0))
        xm = xmax_alt + aralik / (1.0 + math.exp(-p[2]))
        return k, n, xm

    def hedef(p):
        k, n, xm = coz(p)
        return float(np.sum((x - _tahmin("avrami", {"k": k, "n": n, "Xmax": xm}, t)) ** 2))

    xm0 = min(max(baslangic["Xmax"], xmax_alt + 1e-6), 100.0 - 1e-6)
    oran = (xm0 - xmax_alt) / aralik
    oran = min(max(oran, 1e-3), 1 - 1e-3)
    p0 = np.array([math.log(baslangic["k"]), 0.0, math.log(oran / (1 - oran))])
    en_iyi = None
    for dn in (0.0, -0.6, 0.6):
        p_ilk = p0.copy()
        p_ilk[1] += dn
        p = _nelder_mead(hedef, p_ilk, 0.3, 600)
        if en_iyi is None or hedef(p) < hedef(en_iyi):
            en_iyi = p
    k, n, xm = coz(en_iyi)
    return {"Xmax": float(xm), "k": float(k), "n": float(n)}


def _fit_scm(model, t, x, xmax):
    xf = np.clip(x / xmax, 0.0, 1.0 - 1e-6)
    pos = t > 0
    if model == "scm_kimyasal":
        g = 1.0 - (1.0 - xf) ** (1.0 / 3.0)
    elif model == "film_difuzyon":
        g = xf
    else:
        g = _g_scm_difuzyon(xf)
    k0 = float(np.sum(g[pos] * t[pos]) / np.sum(t[pos] ** 2))
    k0 = k0 if k0 > 0 else 1.0 / float(np.median(t[pos]))
    sse_fn = lambda k: float(np.sum((x - _tahmin(model, {"k": k, "Xmax": xmax}, t)) ** 2))
    k = _min_log_k(sse_fn, k0)
    return {"Xmax": float(xmax), "k": float(k)}


def modelleri_uydur(sure: Sequence[float], ekstraksiyon: Sequence[float], xmax_scm: float = 100.0,
                    modeller: Optional[Sequence[str]] = None) -> List[KinetikSonuc]:
    """Seçili modelleri uydurur, AICc (yoksa RMSE) sırasıyla döndürür.

    xmax_scm: SCM ve film difüzyonu modellerinde X'i normalize eden ulaşılabilir maksimum ekstraksiyon (%).
    """
    t, x = temizle(sure, ekstraksiyon)
    if not (0 < xmax_scm <= 100):
        raise ValueError("Xmax %0-100 arasında olmalı.")
    if xmax_scm < float(np.max(x)):
        raise ValueError("Xmax, ölçülen en yüksek ekstraksiyondan küçük olamaz.")
    istenen = list(modeller) if modeller else list(MODELLER)
    sonuclar: List[KinetikSonuc] = []
    bd = None
    for m in istenen:
        uyari = ""
        if m == "birinci_derece":
            p = _fit_birinci_derece(t, x)
            bd = p
        elif m == "avrami":
            if bd is None:
                bd = _fit_birinci_derece(t, x)
            p = _fit_avrami(t, x, bd)
        else:
            p = _fit_scm(m, t, x, xmax_scm)
        tah = _tahmin(m, p, t)
        rmse, r2, aicc = _metrikler(t, x, tah, _PARAM_SAYISI[m])
        n_nokta = len(x)
        if n_nokta <= _PARAM_SAYISI[m] + 2:
            uyari = "Nokta sayısı bu model için az; sonuç güvenilir değil."
        if m in ("birinci_derece", "avrami") and p["Xmax"] > 99.5 and float(np.max(x)) < 90:
            uyari = (uyari + " Xmax %100'e dayandı: veri platoya ulaşmamış, Xmax belirsiz.").strip()
        sonuclar.append(KinetikSonuc(m, MODELLER[m], p, rmse, r2, aicc, n_nokta, uyari))
    def anahtar(s):
        return (s.aicc if s.aicc is not None else 1e9, s.rmse)
    if all(s.aicc is not None for s in sonuclar):
        sonuclar.sort(key=anahtar)
    else:
        sonuclar.sort(key=lambda s: s.rmse)
    return sonuclar


def sure_hesapla(sonuc: KinetikSonuc, hedef_ekstraksiyon: float, t_ust: float = 10_000.0) -> Optional[float]:
    """Modelin hedef ekstraksiyona ulaştığı süre (h). Hedef modelin asimptotuna ulaşılamıyorsa None."""
    xm = sonuc.parametreler["Xmax"]
    if hedef_ekstraksiyon <= 0:
        return 0.0
    if sonuc.model in ("birinci_derece", "avrami") and hedef_ekstraksiyon >= xm - 1e-9:
        return None
    if sonuc.model in ("scm_kimyasal", "scm_difuzyon", "film_difuzyon") and hedef_ekstraksiyon > xm:
        return None
    lo, hi = 0.0, t_ust
    if float(sonuc.tahmin(hi)) < hedef_ekstraksiyon:
        return None
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if float(sonuc.tahmin(mid)) < hedef_ekstraksiyon:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ----------------------------------------------------------------------
# Sıcaklık etkisi: Arrhenius
# ----------------------------------------------------------------------
@dataclass
class ArrheniusSonuc:
    ea_kj_mol: float
    ln_a: float
    r2: float
    n_sicaklik: int
    yorum: str
    sicakliklar_C: List[float] = field(default_factory=list)
    k_degerleri: List[float] = field(default_factory=list)


def arrhenius(sicakliklar_C: Sequence[float], k_degerleri: Sequence[float]) -> ArrheniusSonuc:
    """ln k = ln A - Ea/(R T) doğrusu. En az 3 farklı sıcaklık gerekir."""
    T = np.asarray(sicakliklar_C, dtype=float) + 273.15
    k = np.asarray(k_degerleri, dtype=float)
    ok = np.isfinite(T) & np.isfinite(k) & (k > 0)
    T, k = T[ok], k[ok]
    if len(np.unique(T)) < 3:
        raise ValueError("Arrhenius analizi için en az 3 farklı sıcaklık ve pozitif k değeri gerekir.")
    xs = 1.0 / T
    ys = np.log(k)
    egim, kesisim = np.polyfit(xs, ys, 1)
    tah = egim * xs + kesisim
    sst = float(np.sum((ys - np.mean(ys)) ** 2))
    r2 = 1.0 - float(np.sum((ys - tah) ** 2)) / sst if sst > 0 else float("nan")
    ea = -egim * R_GAZ / 1000.0
    if ea < 0:
        yorum = "Ea negatif çıktı: hız sıcaklıkla artmıyor. Veriyi ve deney koşullarını kontrol et."
    elif ea < 20:
        yorum = ("Ea yaklaşık 20 kJ/mol'ün altında: genel yaklaşıma göre difüzyon kontrolünü düşündürür "
                 "(karıştırma ve tane boyutu etkili olabilir).")
    elif ea > 40:
        yorum = "Ea yaklaşık 40 kJ/mol'ün üzerinde: genel yaklaşıma göre kimyasal reaksiyon kontrolünü düşündürür."
    else:
        yorum = "Ea 20-40 kJ/mol arasında: genel yaklaşıma göre karma kontrol olabilir."
    return ArrheniusSonuc(float(ea), float(kesisim), r2, int(len(np.unique(T))), yorum,
                          [float(v) for v in (T - 273.15)], [float(v) for v in k])


# ----------------------------------------------------------------------
# CIL tank boyutlandırma ve reaktif tüketimi
# ----------------------------------------------------------------------
def cil_boyutlandirma(tpd: float, kullanilabilirlik: float, kati_orani_pct_w: float, sg_kati: float,
                      bekleme_suresi_h: float, tank_adedi: int, doluluk_orani: float = 0.9) -> Dict[str, float]:
    """CIL devresi için toplam ve tank başına hacim.

    tpd                 : tasarım besleme miktarı, kuru t/gün (takvim günü ortalaması)
    kullanilabilirlik   : 0-1, devre çalışma oranı (saatlik besleme miktarı = tpd / (24 * kullanilabilirlik))
    kati_orani_pct_w    : pulpta % katı (kütlece)
    sg_kati             : katı özgül ağırlığı (t/m3)
    bekleme_suresi_h    : toplam CIL bekleme süresi (h)
    doluluk_orani       : pulp hacmi / tank geometrik hacmi
    """
    if not (0 < kullanilabilirlik <= 1):
        raise ValueError("Kullanılabilirlik 0-1 arasında olmalı.")
    if not (0 < kati_orani_pct_w < 100):
        raise ValueError("Katı oranı %0-100 arasında olmalı.")
    if sg_kati <= 0 or bekleme_suresi_h <= 0 or tpd <= 0 or tank_adedi < 1:
        raise ValueError("Besleme miktarı, özgül ağırlık, bekleme süresi ve tank adedi pozitif olmalı.")
    if not (0 < doluluk_orani <= 1):
        raise ValueError("Doluluk oranı 0-1 arasında olmalı.")
    tph = tpd / (24.0 * kullanilabilirlik)
    pulp_m3_h = tph * (1.0 / sg_kati + (100.0 - kati_orani_pct_w) / kati_orani_pct_w)
    v_pulp = pulp_m3_h * bekleme_suresi_h
    v_geo = v_pulp / doluluk_orani
    return {
        "katı_debisi_t_h": tph,
        "pulp_debisi_m3_h": pulp_m3_h,
        "pulp_hacmi_m3": v_pulp,
        "toplam_geometrik_hacim_m3": v_geo,
        "tank_basina_hacim_m3": v_geo / tank_adedi,
        "tank_basina_bekleme_h": bekleme_suresi_h / tank_adedi,
    }


def reaktif_tuketimi(tpd: float, nacn_kg_t: float, kirec_kg_t: float,
                     nacn_fiyat_usd_t: float = 0.0, kirec_fiyat_usd_t: float = 0.0) -> Dict[str, float]:
    """NaCN ve kireç tüketimi; fiyat girilmişse maliyet de verir (fiyat kullanıcı girişidir)."""
    if tpd <= 0 or nacn_kg_t < 0 or kirec_kg_t < 0:
        raise ValueError("Besleme miktarı pozitif, tüketimler negatif olmayan sayılar olmalı.")
    nacn_t_gun = tpd * nacn_kg_t / 1000.0
    kirec_t_gun = tpd * kirec_kg_t / 1000.0
    out = {
        "nacn_t_gun": nacn_t_gun,
        "kirec_t_gun": kirec_t_gun,
        "nacn_t_yil": nacn_t_gun * 365.0,
        "kirec_t_yil": kirec_t_gun * 365.0,
    }
    if nacn_fiyat_usd_t > 0 or kirec_fiyat_usd_t > 0:
        out["nacn_usd_t_cevher"] = nacn_kg_t / 1000.0 * nacn_fiyat_usd_t
        out["kirec_usd_t_cevher"] = kirec_kg_t / 1000.0 * kirec_fiyat_usd_t
        out["toplam_usd_t_cevher"] = out["nacn_usd_t_cevher"] + out["kirec_usd_t_cevher"]
    return out


# ----------------------------------------------------------------------
# Örnek (sentetik) veri: yalnızca arayüzü denemek için, gerçek ölçüm DEĞİLDİR
# ----------------------------------------------------------------------
def ornek_sentetik_veri() -> Dict[str, List[float]]:
    """Birinci derece (Xmax=92, k=0.12 1/h) eğrisinden üretilmiş yapay veri."""
    sureler = [0.5, 1, 2, 4, 6, 8, 12, 24, 36, 48]
    xs = [round(92.0 * (1 - math.exp(-0.12 * t)), 1) for t in sureler]
    return {"sure_h": sureler, "ekstraksiyon_pct": xs}


if __name__ == "__main__":
    # --- Kendi kendine test: bilinen parametrelerle üretilmiş veriyi geri bulabiliyor mu? ---
    t = np.array([0.5, 1, 2, 3, 4, 6, 8, 12, 18, 24, 36, 48], dtype=float)

    # 1) Birinci derece
    x1 = 92.0 * (1 - np.exp(-0.12 * t))
    s = modelleri_uydur(t, x1)
    en_iyi = s[0]
    print("Birinci derece verisi -> en iyi model:", en_iyi.model, en_iyi.parametreler, "RMSE", round(en_iyi.rmse, 4))
    bd = [r for r in s if r.model == "birinci_derece"][0]
    assert abs(bd.parametreler["k"] - 0.12) < 0.005 and abs(bd.parametreler["Xmax"] - 92.0) < 0.5, bd
    assert bd.rmse < 0.1

    # 2) Avrami (n=0.7)
    xa = 90.0 * (1 - np.exp(-(0.1 * t) ** 0.7))
    s = modelleri_uydur(t, xa)
    av = [r for r in s if r.model == "avrami"][0]
    print("Avrami verisi        ->", av.parametreler, "RMSE", round(av.rmse, 4), "| sıralama:", [r.model for r in s])
    assert abs(av.parametreler["n"] - 0.7) < 0.05 and abs(av.parametreler["k"] - 0.1) < 0.01
    assert s[0].model == "avrami"

    # 3) SCM kimyasal kontrol (k=0.02, Xmax=100)
    xs_ = 100.0 * (1 - (1 - np.minimum(0.02 * t, 1.0)) ** 3)
    s = modelleri_uydur(t, xs_)
    sc = [r for r in s if r.model == "scm_kimyasal"][0]
    print("SCM kimyasal verisi  ->", sc.parametreler, "RMSE", round(sc.rmse, 4))
    assert abs(sc.parametreler["k"] - 0.02) < 0.001 and sc.rmse < 0.2

    # 4) SCM difüzyon (k=0.015)
    kt = np.minimum(0.015 * t, 1.0)
    xd = 100.0 * _x_scm_difuzyon(kt)
    s = modelleri_uydur(t, xd)
    sd = [r for r in s if r.model == "scm_difuzyon"][0]
    print("SCM difüzyon verisi  ->", sd.parametreler, "RMSE", round(sd.rmse, 4))
    assert abs(sd.parametreler["k"] - 0.015) < 0.001 and sd.rmse < 0.3

    # 5) Hedefe ulaşma süresi
    sure90 = sure_hesapla(bd, 80.0)
    teorik = -math.log(1 - 80.0 / 92.0) / 0.12
    print("Birinci derece %80 için süre:", round(sure90, 2), "h (teorik", round(teorik, 2), ")")
    assert abs(sure90 - teorik) < 0.2
    assert sure_hesapla(bd, 95.0) is None  # Xmax'ın üstü

    # 6) Arrhenius: Ea = 35 kJ/mol ile üretilmiş k değerleri
    Ts = [25.0, 35.0, 45.0, 60.0]
    ks = [3.0e5 * math.exp(-35000.0 / (R_GAZ * (T + 273.15))) for T in Ts]
    ar = arrhenius(Ts, ks)
    print("Arrhenius Ea:", round(ar.ea_kj_mol, 2), "kJ/mol, R2", round(ar.r2, 5), "|", ar.yorum)
    assert abs(ar.ea_kj_mol - 35.0) < 0.1 and ar.r2 > 0.9999

    # 7) CIL boyutlandırma: elle hesapla
    #    5,500,000 t/yıl ~ 15,068 t/gün; %91.3; %45 katı; SG 2.7; 24 h; 7 tank; %90 doluluk
    r = cil_boyutlandirma(15_068, 0.913, 45.0, 2.7, 24.0, 7, 0.9)
    tph = 15_068 / (24 * 0.913)
    beklenen = tph * (1 / 2.7 + 55 / 45) * 24 / 0.9
    print("CIL toplam hacim:", round(r["toplam_geometrik_hacim_m3"]), "m3, tank başına", round(r["tank_basina_hacim_m3"]), "m3")
    assert abs(r["toplam_geometrik_hacim_m3"] - beklenen) < 1e-6

    # 8) Reaktif
    rt = reaktif_tuketimi(15_068, 0.83, 2.61, 2500.0, 150.0)
    assert abs(rt["nacn_t_gun"] - 15_068 * 0.83 / 1000) < 1e-9
    print("Reaktif:", {k_: round(v, 3) for k_, v in rt.items()})

    # 9) Hata kontrolleri
    for kotu in (lambda: modelleri_uydur([1, 2, 3], [10, 20, 30]),
                 lambda: modelleri_uydur([1, 2, 3, 4], [10, 20, 30, 120]),
                 lambda: arrhenius([25, 35], [0.1, 0.2]),
                 lambda: cil_boyutlandirma(1000, 1.2, 45, 2.7, 24, 7)):
        try:
            kotu()
            raise SystemExit("Hata beklenirdi")
        except ValueError:
            pass
    print("Tüm testler geçti.")
