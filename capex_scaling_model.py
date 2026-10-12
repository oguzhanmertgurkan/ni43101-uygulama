"""
CAPEX Ölçekleme Modülü (kapsam bayraklı veri noktalarıyla)
==============================================================
Yöntem: "six-tenths rule" (güç yasası ölçekleme) - proses tesisi CAPEX
tahmininde standart bir mühendislik yaklaşımı:
    Cost_B = Cost_A * (Capacity_B / Capacity_A) ^ n

PROCESS PLANT SINIRI (bu projede kararlaştırılan tanım):
  DAHİL  : kırma, öğütme, flotasyon, koyulaştırma ve filtrasyon, konsantre
           depolama ve yükleme, tesis içi reaktif ve su sistemleri
  HARİÇ  : madencilik, TSF (atık depolama), dış altyapı (dış güç hattı, yol,
           kamp, su kuyuları), sahip maliyetleri, beklenmedik gider payı
  Gider payı (contingency) ve sahip maliyetleri istenirse kullanıcı girdisi
  olarak ayrıca eklenir; veri noktasının içine karıştırılmaz.

KAPSAM SEVİYELERİ (bir veri noktasının kalemleri varsa hepsi hesaplanabilir):
  A: Doğrudan (ekipman satın alma + montaj)
  B: A + saha tesisleri (tesis içi bina/yapı, tesis içi güç iletimi)
  C: B + dolaylı maliyetler (tasarım mühendisliği + inşaat yönetimi)   <- varsayılan
  D: C + raporun gider payı (işletme sermayesi hariç)
  (İşletme sermayesi hiçbir seviyeye girmez.)

VERİ NOKTASI KURALI: Kapsamı kalem kalem doğrulanamayan bir nokta "belirsiz"
sayılır, üstel (n) hesabına GİRMEZ, grafikte ayrı renkle gösterilir. Böyle bir
nokta yerine kapsamı net başka rapor bulunmalıdır.

NOT: Enflasyon / maliyet endeksi ve piyasa koşulları düzeltmesi için uygulama
bir değer varsaymaz; kullanıcı kendi çarpanını girer.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional

# Kalem kategorileri
EKIPMAN = "ekipman"
DOGRUDAN = "dogrudan"      # ekipman + montaj birleşik verilmişse (ör. Furnas)
MONTAJ = "montaj"
SAHA = "saha_tesisleri"
DOLAYLI = "dolayli"
ISLETME_SERMAYESI = "isletme_sermayesi"
GIDER_PAYI = "gider_payi"

KAPSAM_SEVIYELERI = {
    "A": "A - Doğrudan (ekipman + montaj)",
    "B": "B - Doğrudan + saha tesisleri",
    "C": "C - B + dolaylı maliyetler (mühendislik + inşaat yönetimi)",
    "D": "D - C + raporun gider payı (işletme sermayesi hariç)",
}
_SEVIYE_KATEGORILERI = {
    "A": {EKIPMAN, MONTAJ, DOGRUDAN},
    "B": {EKIPMAN, MONTAJ, DOGRUDAN, SAHA},
    "C": {EKIPMAN, MONTAJ, DOGRUDAN, SAHA, DOLAYLI},
    "D": {EKIPMAN, MONTAJ, DOGRUDAN, SAHA, DOLAYLI, GIDER_PAYI},
}
VARSAYILAN_SEVIYE = "C"

# Genel mühendislik kuralı (rapor verisi DEĞİL) - tek doğrulanmış nokta varken
# kullanıcı üstel girmezse kullanılan literatür değeri
LITERATUR_USTEL = 0.6

# Veriden hesaplanan üstelin fiziksel olarak makul sayılacağı aralık. Bu aralığın
# dışındaki sonuç (ör. negatif üstel) kapsam/yöntem farkını gösterir, ölçek etkisini
# değil; kullanılmaz.
USTEL_ARALIGI = (0.3, 1.0)


@dataclass
class CapexKalem:
    ad: str
    usd: float
    kategori: str
    kaynak: str


@dataclass
class CapexKapsam:
    """Kapsam bayrakları: True/False = raporda doğrulandı, None = belirsiz."""
    tsf_dahil: Optional[bool] = None
    dis_altyapi_dahil: Optional[bool] = None
    gider_payi_dahil: Optional[bool] = None
    dolayli_dahil: Optional[bool] = None
    sahip_maliyeti_dahil: Optional[bool] = None


@dataclass
class CapexDataPoint:
    project: str
    capacity_tpd: float
    base_year: int
    basslik_capex_usd: float          # raporun başlık (toplam) rakamı
    kapsam: CapexKapsam
    kalemler: List[CapexKalem] = field(default_factory=list)
    source: str = ""
    notlar: str = ""
    # Kalemlerden güvenilir biçimde hesaplanabilen kapsam seviyeleri
    seviyeler: tuple = ("A", "B", "C", "D")

    @property
    def kapsam_dogrulandi(self) -> bool:
        """Kalem kalem döküm yoksa veya bayraklardan biri belirsizse False."""
        k = self.kapsam
        bayraklar = [k.tsf_dahil, k.dis_altyapi_dahil, k.gider_payi_dahil,
                     k.dolayli_dahil, k.sahip_maliyeti_dahil]
        return bool(self.kalemler) and all(b is not None for b in bayraklar)

    @property
    def durum(self) -> str:
        return "Doğrulanmış" if self.kapsam_dogrulandi else "Belirsiz (hesaba katılmaz)"

    def capex_seviye(self, seviye: str = VARSAYILAN_SEVIYE) -> Optional[float]:
        """Kalemlerden istenen kapsam seviyesine göre CAPEX; döküm yoksa None."""
        if not self.kapsam_dogrulandi or seviye not in self.seviyeler:
            return None
        kat = _SEVIYE_KATEGORILERI[seviye]
        return sum(k.usd for k in self.kalemler if k.kategori in kat)


# ------------------------------------------------------------------
# Altar - Tablo 21-5 (Summary of Process Plant Capex), SRK, Eylül 2025
# ------------------------------------------------------------------
_ALTAR_KAYNAK = "Altar PEA, Tablo 21-5"
ALTAR_DATA_POINT = CapexDataPoint(
    project="Altar Project",
    capacity_tpd=60000,
    base_year=2025,
    basslik_capex_usd=578_564_166,
    kapsam=CapexKapsam(
        tsf_dahil=False,            # TSF, Tablo 21-6'da Altyapı kaleminde
        dis_altyapi_dahil=False,    # dış güç hattı/yol/kamp Tablo 21-6'da
        gider_payi_dahil=True,      # Tablo 21-5'te %20, ayrı satır olarak
        dolayli_dahil=True,         # mühendislik + inşaat yönetimi ayrı satır
        sahip_maliyeti_dahil=False, # sahip maliyetleri Tablo 21-6'da
    ),
    kalemler=[
        CapexKalem("Ekipman satın alma", 109_790_000, EKIPMAN, _ALTAR_KAYNAK),
        CapexKalem("Ekipman montajı", 130_215_930, MONTAJ, _ALTAR_KAYNAK),
        CapexKalem("Saha tesisleri (15.0M tesis içi güç iletimi + 43.0M bina/yapı)",
                   58_000_000, SAHA, _ALTAR_KAYNAK + ", Bölüm 21.2.2"),
        CapexKalem("Tasarım mühendisliği", 68_805_000, DOLAYLI, _ALTAR_KAYNAK),
        CapexKalem("İnşaat yönetimi", 50_042_000, DOLAYLI, _ALTAR_KAYNAK),
        CapexKalem("İşletme sermayesi", 18_062_000, ISLETME_SERMAYESI, _ALTAR_KAYNAK),
        CapexKalem("Gider payı (%20)", 86_982_986, GIDER_PAYI, _ALTAR_KAYNAK),
    ],
    source="Altar PEA (SRK, Eylül 2025), Tablo 21-5; 2025 USD baz, doğruluk sınıfı +/-%50",
    notlar=(
        "Raporun finansal tablolarındaki 'Initial Processing Capex' başlık rakamı "
        "578.6M USD (Tablo 21-1 / 22-9, nakit akışı), Tablo 21-5'teki process plant "
        "toplamından (521.9M USD, gider payı dahil) 56.7M USD fazladır ve metinde "
        "bu farkın açıklaması bulunamadı. Rapor kendi kıyaslamasında (Tablo 21-13) "
        "522M USD kullanır. Bu modül kalemleri izlenebilen Tablo 21-5'i kullanır."
    ),
)

# ------------------------------------------------------------------
# La Mina - sadece basın bülteni; kapsam bilinmiyor -> BELİRSİZ
# ------------------------------------------------------------------
LA_MINA_DATA_POINT = CapexDataPoint(
    project="La Mina Project",
    capacity_tpd=15000,
    base_year=2026,
    basslik_capex_usd=224_700_000,
    kapsam=CapexKapsam(),   # tüm bayraklar belirsiz
    kalemler=[],
    source="La Mina PEA basın bülteni (Nisan 2026) - tam NI 43-101 raporu henüz yok",
    notlar="Process Plant CAPEX kalem dökümü ve kapsamı bilinmiyor; hesaba katılmaz.",
)

# ------------------------------------------------------------------
# Furnas - Tablo 21-8 / 21-9 (Forecast Process Initial Capital Cost Estimate), PEA
# Ero Copper, rapor tarihi Mart 2026 (yürürlük 23 Şubat 2026)
# ------------------------------------------------------------------
_FURNAS_KAYNAK = "Furnas PEA (Ero Copper, Mart 2026), Tablo 21-9"
FURNAS_DATA_POINT = CapexDataPoint(
    project="Furnas Project",
    capacity_tpd=37000,     # 13.5 Mtpa, rapor: ~37,000 t/g
    base_year=2025,         # rapor, maliyetleri sabit 2025 2. çeyrek USD ile tahmin ettiğini belirtir
    basslik_capex_usd=1_280_000_000,   # proje toplamı (madencilik, altyapı dahil) - hesaba katılmaz
    kapsam=CapexKapsam(
        tsf_dahil=False,            # "Tailings management" ($48M) ayrı satır
        dis_altyapi_dahil=False,    # "Infrastructure" ($139M) ayrı satır
        gider_payi_dahil=True,      # Tablo 21-9'da alan bazında gider payı var
        dolayli_dahil=True,         # Tablo 21-9'da alan bazında dolaylı maliyet var
        sahip_maliyeti_dahil=False, # "Owners' team" ($8M) ayrı satır
    ),
    kalemler=[
        CapexKalem("Doğrudan maliyet (kırma, stok, öğütme, flotasyon, atık/macun koyulaştırma, "
                   "konsantre koyulaştırma+filtrasyon, reaktif, elektrik-kontrol, tesis içi boru)",
                   410_000_000, DOGRUDAN, _FURNAS_KAYNAK),
        CapexKalem("Dolaylı maliyet (process plant)", 109_000_000, DOLAYLI, _FURNAS_KAYNAK),
        CapexKalem("Gider payı (process plant)", 121_000_000, GIDER_PAYI, _FURNAS_KAYNAK),
    ],
    source="Furnas PEA, NI 43-101 teknik raporu (Mart 2026), Tablo 21-8/21-9; AACE Class 5 "
           "(-%20/-%50 ile +%30/+%100)",
    notlar=(
        "Kalemler arama alıntısından (rapor metninin bir bölümü) okundu; alan bazlı satırların "
        "toplamı raporun toplamıyla tutuyor (410 / 109 / 121 / 640 milyon USD, yuvarlama farkı 1). "
        "Ekipman ve montaj ayrılmamış, 'doğrudan' tek kalem. Saha tesisleri (bina, tesis içi güç) "
        "process plant tablosunda yok; 'Infrastructure' kaleminde ve ayrılamıyor, bu yüzden "
        "yalnızca seviye A (doğrudan) Altar ile karşılaştırılabilir. Doğrudan maliyete "
        "$94M'lik 'slimes & paste thickening (tailings)' alanı dahildir; atık koyulaştırma/macun "
        "tesisi sınırımızın dışında sayılırsa doğrudan maliyet yaklaşık $316M olur."
    ),
    seviyeler=("A",),
)

ALL_DATA_POINTS = [ALTAR_DATA_POINT, FURNAS_DATA_POINT, LA_MINA_DATA_POINT]


def kapsam_oranlari(p: CapexDataPoint) -> Optional[dict]:
    """
    Kalemlerden öğrenilen oranlar (kullanıcının dolaylı maliyet ve gider payı
    girdilerini seçerken referans alması için):
      dolayli_pct: dolaylı maliyet / (doğrudan + saha tesisleri)
      gider_payi_pct: gider payı / (doğrudan + saha tesisleri + dolaylı)
    İşletme sermayesi paydaya girmez. Kalem dökümü yoksa None.
    """
    if not p.kapsam_dogrulandi:
        return None
    topla = lambda kats: sum(k.usd for k in p.kalemler if k.kategori in kats)
    dogrudan = topla({EKIPMAN, MONTAJ, DOGRUDAN, SAHA})
    dolayli = topla({DOLAYLI})
    gider = topla({GIDER_PAYI})
    if dogrudan <= 0 or dolayli <= 0:
        return None
    return {"dolayli_pct": 100 * dolayli / dogrudan,
            "gider_payi_pct": 100 * gider / (dogrudan + dolayli)}


def dogrulanmis_noktalar(points=None, seviye: str = VARSAYILAN_SEVIYE) -> list:
    points = ALL_DATA_POINTS if points is None else points
    return [p for p in points if p.capex_seviye(seviye) is not None]


def fit_ham_ustel(points=None, seviye: str = VARSAYILAN_SEVIYE) -> Optional[float]:
    """Doğrulanmış noktalardan ln-ln en küçük kareler üsteli (aralık denetimi YOK)."""
    pts = dogrulanmis_noktalar(points, seviye)
    if len({p.capacity_tpd for p in pts}) < 2:
        return None
    xs = [math.log(p.capacity_tpd) for p in pts]
    ys = [math.log(p.capex_seviye(seviye)) for p in pts]
    xm, ym = sum(xs) / len(xs), sum(ys) / len(ys)
    return sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / sum((x - xm) ** 2 for x in xs)


def fit_scaling_exponent(points=None, seviye: str = VARSAYILAN_SEVIYE) -> Optional[float]:
    """
    Üstel (n) yalnızca >=2 farklı kapasitede doğrulanmış nokta varsa VE sonuç fiziksel
    aralıkta (USTEL_ARALIGI) ise döner; aksi halde None (aralık dışı üstel kullanılmaz).
    """
    n = fit_ham_ustel(points, seviye)
    if n is None or not (USTEL_ARALIGI[0] <= n <= USTEL_ARALIGI[1]):
        return None
    return n


def estimate_process_capex(
    target_capacity_tpd: float,
    seviye: str = VARSAYILAN_SEVIYE,
    exponent: Optional[float] = None,
    duzeltme_carpani: float = 1.0,
    gider_payi_pct: float = 0.0,
    sahip_maliyeti_usd: float = 0.0,
    points=None,
) -> dict:
    """
    Hedef kapasite için process plant CAPEX tahmini.

    exponent verilmezse: >=2 doğrulanmış nokta varsa veriden, yoksa genel
    literatür değeri (0.6) kullanılır ve bu açıkça belirtilir.
    duzeltme_carpani: kullanıcının enflasyon/maliyet endeksi/piyasa koşulları
        için girdiği çarpan (1.0 = düzeltme yok). Uygulama değer varsaymaz.
    gider_payi_pct, sahip_maliyeti_usd: kullanıcının ayrıca eklediği kalemler
        (seviye D zaten raporun gider payını içerir).
    """
    pts = dogrulanmis_noktalar(points, seviye)
    if not pts:
        raise ValueError("Bu kapsam seviyesi için doğrulanmış veri noktası yok.")
    if target_capacity_tpd <= 0:
        raise ValueError("Hedef kapasite pozitif olmalı.")

    # Referans: hedefe kapasite olarak en yakın doğrulanmış nokta
    ref = min(pts, key=lambda p: abs(math.log(target_capacity_tpd / p.capacity_tpd)))

    if exponent is not None:
        n, n_kaynak = exponent, "kullanıcı girdisi"
    else:
        fitted = fit_scaling_exponent(points, seviye)
        ham = fit_ham_ustel(points, seviye)
        if fitted is not None:
            n, n_kaynak = fitted, f"{len(pts)} doğrulanmış noktadan hesaplandı"
        else:
            n, n_kaynak = LITERATUR_USTEL, "genel literatür (six-tenths rule), veri değil"

    ref_capex = ref.capex_seviye(seviye)
    olceklenmis = ref_capex * (target_capacity_tpd / ref.capacity_tpd) ** n
    duzeltilmis = olceklenmis * duzeltme_carpani
    gider = duzeltilmis * gider_payi_pct / 100.0
    toplam = duzeltilmis + gider + sahip_maliyeti_usd

    kapasiteler = [p.capacity_tpd for p in pts]
    disarida = not (min(kapasiteler) <= target_capacity_tpd <= max(kapasiteler))

    # Her doğrulanmış referanstan ayrı tahmin (aynı n, aynı düzeltme): referanslar
    # birbirinden çok farklı çıkıyorsa kullanıcı bunu görmeli.
    referans_tahminleri = []
    for p in pts:
        c = p.capex_seviye(seviye)
        t = c * (target_capacity_tpd / p.capacity_tpd) ** n * duzeltme_carpani
        referans_tahminleri.append({
            "project": p.project, "capacity_tpd": p.capacity_tpd, "base_year": p.base_year,
            "reference_capex_usd": c, "scaled_capex_usd": round(t, 0),
        })
    degerler = [r["scaled_capex_usd"] for r in referans_tahminleri]
    yayilim = (max(degerler) / min(degerler)) if len(degerler) > 1 and min(degerler) > 0 else 1.0

    if exponent is None and ham is not None and fitted is None:
        uyari = (f"Veriden hesaplanan üstel ({ham:.2f}) fiziksel aralığın "
                 f"({USTEL_ARALIGI[0]}-{USTEL_ARALIGI[1]}) dışında, kullanılmadı: referans noktalar "
                 f"kapsam/yöntem farkı nedeniyle birbiriyle tutarlı değil. n={n} kullanıldı.")
    elif len(set(kapasiteler)) == 1:
        uyari = (f"Tek doğrulanmış veri noktası var ({ref.project}, "
                 f"{ref.capacity_tpd:,.0f} tpd): ölçekleme üsteli veriden doğrulanamaz.")
    elif disarida:
        uyari = (f"Hedef kapasite, doğrulanmış veri aralığının "
                 f"({min(kapasiteler):,.0f}-{max(kapasiteler):,.0f} tpd) dışında: ekstrapolasyon.")
    else:
        uyari = None
    if yayilim > 1.3:
        ek = (f"Doğrulanmış referanslardan yapılan tahminler arasında {yayilim:.1f} kat fark var "
              f"(ölçekleme dışındaki nedenler: bölge, çalışma sınıfı, kapsam).")
        uyari = ek if uyari is None else uyari + " " + ek

    return {
        "target_capacity_tpd": target_capacity_tpd,
        "seviye": seviye,
        "reference_project": ref.project,
        "reference_capacity_tpd": ref.capacity_tpd,
        "reference_capex_usd": ref_capex,
        "reference_base_year": ref.base_year,
        "scaling_exponent": round(n, 4),
        "exponent_source": n_kaynak,
        "scaled_capex_usd": round(olceklenmis, 0),
        "adjusted_capex_usd": round(duzeltilmis, 0),
        "contingency_usd": round(gider, 0),
        "owner_costs_usd": round(sahip_maliyeti_usd, 0),
        "estimated_process_capex_usd": round(toplam, 0),
        "extrapolating": disarida or len(set(kapasiteler)) == 1,
        "referans_tahminleri": referans_tahminleri,
        "referans_yayilimi": round(yayilim, 2),
        "warning": uyari,
        "note": (
            f"Tahmin, {ref.project} verisinden ({ref.base_year} USD baz, kapsam seviyesi {seviye}) "
            f"n={n:.3f} ({n_kaynak}) üsteliyle ölçeklenmiştir. Düzeltme çarpanı: "
            f"{duzeltme_carpani:.3f}. Referans PEA tahmininin doğruluk sınıfı +/-%50'dir."
        ),
    }


if __name__ == "__main__":
    print("CAPEX Ölçekleme Modeli - Doğrulama\n" + "-" * 55)
    a = ALTAR_DATA_POINT
    toplam_kalem = sum(k.usd for k in a.kalemler)
    print(f"Altar kalemleri toplamı (gider payı dahil): {toplam_kalem:,.0f} (rapor: 521,897,916)")
    assert abs(toplam_kalem - 521_897_916) < 5, "Tablo 21-5 toplamı tutmuyor"
    assert abs(sum(k.usd for k in a.kalemler if k.kategori != GIDER_PAYI) - 434_914_930) < 5
    for s, ad in KAPSAM_SEVIYELERI.items():
        print(f"  Seviye {s}: {a.capex_seviye(s):,.0f} USD  ({ad})")
    print(f"  Başlık rakamı (hesaba katılmaz): {a.basslik_capex_usd:,.0f}; "
          f"Tablo 21-5 ile fark: {a.basslik_capex_usd - 521_897_916:,.0f}")
    for _p in (ALTAR_DATA_POINT, FURNAS_DATA_POINT):
        print(f"  Oranlar {_p.project}: {kapsam_oranlari(_p)}")
    print(f"La Mina durum: {LA_MINA_DATA_POINT.durum}; seviye C = {LA_MINA_DATA_POINT.capex_seviye('C')}")

    f = FURNAS_DATA_POINT
    f_toplam = sum(k.usd for k in f.kalemler)
    print(f"\nFurnas kalemleri toplamı: {f_toplam:,.0f} (rapor Tablo 21-9: 640 milyon)")
    assert abs(f_toplam - 640_000_000) <= 1_000_000
    print(f"  Seviye A (doğrudan): {f.capex_seviye('A'):,.0f}; seviye C = {f.capex_seviye('C')} (saha tesisleri ayrılamıyor)")
    assert f.capex_seviye("A") == 410_000_000 and f.capex_seviye("C") is None

    ham = fit_ham_ustel(seviye="A")
    print(f"\nSeviye A, iki doğrulanmış nokta (Altar + Furnas): ham üstel = {ham:.2f}; "
          f"kullanılabilir mi: {fit_scaling_exponent(seviye='A') is not None}")
    assert ham < 0 and fit_scaling_exponent(seviye="A") is None
    print(f"Seviye C, doğrulanmış nokta sayısı: {len(dogrulanmis_noktalar(seviye='C'))} -> üstel {fit_scaling_exponent()}")

    for sv in ("A", "C"):
        r = estimate_process_capex(30000, seviye=sv)
        print(f"\n30,000 tpd (seviye {sv}): {r['estimated_process_capex_usd']:,.0f} USD, "
              f"n={r['scaling_exponent']} ({r['exponent_source']}), referans={r['reference_project']}")
        for t in r["referans_tahminleri"]:
            print(f"    {t['project']}: {t['scaled_capex_usd']:,.0f}")
        print("  UYARI:", r["warning"])
    r2 = estimate_process_capex(30000, seviye="D", duzeltme_carpani=1.1)
    print(f"\n30,000 tpd (seviye D, x1.10): {r2['estimated_process_capex_usd']:,.0f} USD")
