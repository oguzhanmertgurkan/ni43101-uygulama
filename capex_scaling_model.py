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
class CapexAlan:
    """Bir raporun tek bir proses alanı (unit operation) için maliyet satırı."""
    alan_kodu: str          # ALAN_TURLERI anahtarı
    rapor_adi: str          # raporun kendi alan adı
    dogrudan_usd: float     # doğrudan maliyet (ekipman + montaj / raporun doğrudan maliyeti)
    dolayli_usd: Optional[float] = None
    gider_payi_usd: Optional[float] = None
    kaynak: str = ""
    not_: str = ""


@dataclass
class OpexAlan:
    """Bir raporun tek bir proses alanı için işletme gideri ($/t besleme, o alanın kendi beslemesi).
    kapsam: 'tam' = raporun alan toplamı (işçilik, güç, sarf, bakım dahil); 'sarf_guc' = yalnızca sarf + güç
    (işçilik, bakım, laboratuvar hariç). Farklı kapsamlar toplanmaz."""
    alan_kodu: str
    rapor_adi: str
    usd_t: float
    kapsam: str = "tam"
    senaryo: str = ""
    kaynak: str = ""
    not_: str = ""


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
    # Alan (unit operation) bazlı döküm; yoksa boş
    alanlar: list = field(default_factory=list)
    proses: str = "Cu flotasyonu"
    # İşleme işletme gideri (OPEX) referansı: toplam $/t ve raporun kırılımı
    isleme_opex_usd_t: Optional[float] = None
    opex_kirilim: dict = field(default_factory=dict)
    # Alan bazlı işletme gideri (varsa)
    opex_alanlari: list = field(default_factory=list)

    @property
    def kapsam_dogrulandi(self) -> bool:
        """Kalem kalem döküm yoksa veya bayraklardan biri belirsizse False."""
        k = self.kapsam
        bayraklar = [k.tsf_dahil, k.dis_altyapi_dahil, k.gider_payi_dahil,
                     k.dolayli_dahil, k.sahip_maliyeti_dahil]
        return bool(self.kalemler) and all(b is not None for b in bayraklar)

    @property
    def alan_dogrulandi(self) -> bool:
        """Alan bazlı döküm var ve kapsam bayraklarının hiçbiri belirsiz değil."""
        k = self.kapsam
        bayraklar = [k.tsf_dahil, k.dis_altyapi_dahil, k.gider_payi_dahil,
                     k.dolayli_dahil, k.sahip_maliyeti_dahil]
        return bool(self.alanlar) and all(b is not None for b in bayraklar)

    @property
    def durum(self) -> str:
        if self.kapsam_dogrulandi:
            return "Doğrulanmış"
        if self.alan_dogrulandi:
            return "Yalnızca alan bazlı (tesis toplamına girmez)"
        return "Belirsiz (hesaba katılmaz)"

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

# ------------------------------------------------------------------
# PROSES ALANLARI (unit operation) - rota seçimi için standart alan kodları
# ------------------------------------------------------------------
# Rapor verisi olmayan alanlar uygulamada "veri yok" olarak gösterilir.
ALAN_TURLERI = {
    "kirma_ogutme": "Kırma + öğütme (birleşik: kırma, stok, öğütme)",
    "kirma": "Kırma",
    "stok": "Kırılmış cevher stoku ve geri alma",
    "ogutme": "Öğütme (SAG/bilyalı + siklon)",
    "yeniden_ogutme": "Yeniden öğütme",
    "flotasyon": "Flotasyon",
    "konsantre_koyulastirma": "Konsantre koyulaştırma",
    "konsantre_filtrasyon": "Konsantre filtrasyonu ve depolama",
    "atik_koyulastirma": "Atık koyulaştırma, filtrasyon veya macun (tesis içi)",
    "reaktif": "Reaktif ve flokülant tesisi",
    "elektrik_kontrol": "Elektrik ve kontrol",
    "boru": "Tesis içi borulama",
    "yardimci": "Pompa, konveyör ve diğer yardımcı (alanı belirsiz)",
    # Aşağıdaki alanların bir kısmı için tek rapordan veri var (heap_leach: Cactus, Santa Fe; sx_ew: Cactus; cil, adr,
    # on_koyulastirma: Enchi, Cerro Blanco; karbon_adsorpsiyon: Santa Fe). asit_tesisi, gravite, dms ve manyetik için
    # henüz doğrulanmış rapor verisi yok. Veri durumu için veri_kapsami() ve estimate_area_capex'e bak.
    "heap_leach": "Heap leach (aglomerasyon, istif, pad)",
    "sx_ew": "SX-EW",
    "asit_tesisi": "Sülfürik asit tesisi",
    "on_koyulastirma": "Liç öncesi koyulaştırma ve kaba ayıklama (trash screen)",
    "cil": "Siyanür liçi, CIP/CIL ve detoks",
    "karbon_adsorpsiyon": "Karbon adsorpsiyonu (CIC kolonları, yığın liçi sonrası)",
    "adr": "ADR (karbon geri kazanım) ve rafineri",
    "gravite": "Gravite ayırma (jig, spiral, masa, santrifüj)",
    "dms": "Ağır ortam ayırma (DMS)",
    "manyetik": "Manyetik / elektrostatik ayırma",
}

# Altar PEA, Şekil 21-1 (Summary of Process Equipment Supply and Installation).
# (ekipman, boyut, adet, satın alma USD, montaj USD, alan). Alan ataması,
# raporun tabloda alan başlığı vermemesi nedeniyle ekipman adı ve tablo sırasına
# göre yapıldı (küçük pompa/konveyör satırları için yorum içerir).
ALTAR_EKIPMAN_LISTESI = [
    ("Gyratory Crusher", "60 x 110 inç", 2, 20_260_200, 24_930_383, "kirma"),
    ("Crushed Ore Stockpile", "60,000 t", 1, 11_429_494, 13_050_721, "stok"),
    ("SAG Mill Reclaim Conveyor", "", 1, 1_420_800, 2_189_453, "stok"),
    ("SAG Mill & Motor", "12.1 x 7.9 m", 1, 23_102_300, 22_653_450, "ogutme"),
    ("Pebble Screen", "", 4, 2_624_300, 2_584_936, "ogutme"),
    ("Pebble Return Conveyor", "76,621 L/dk", 1, 99_200, 124_893, "ogutme"),
    ("Ball Mill & Motor", "7.9 x 12.3 m", 1, 12_854_000, 13_282_200, "ogutme"),
    ("Cyclone Feed Sump & Pump", "57,463 L/dk", 1, 99_200, 124_893, "ogutme"),
    ("Cyclones", "76.2 cm", 36, 1_887_480, 2_891_619, "ogutme"),
    ("Sump & Pump", "76,622 L/dk", 1, 99_200, 124_893, "ogutme"),
    ("Regrind Mill (Tower Mill)", "183 cm yarıçap x 13.5 m", 5, 19_000_000, 19_500_000, "yeniden_ogutme"),
    ("Concentrate Thickener", "20 m çap", 1, 437_400, 861_252, "konsantre_koyulastirma"),
    ("Sump & Pump", "15 L/dk", 1, 17_500, 22_033, "konsantre_koyulastirma"),
    ("Flotation Cells", "2,355 m3", 47, 12_026_370, 20_649_277, "flotasyon"),
    ("Sump & Pump", "15 L/dk", 1, 17_500, 22_033, "flotasyon"),
    ("Sump & Pump", "3 L/dk", 1, 17_500, 22_033, "flotasyon"),
    ("Concentrate Filter Press", "37 m2", 2, 2_154_100, 2_304_193, "konsantre_filtrasyon"),
    ("Cyclones", "10.2 cm", 6, 20_760, 31_804, "yardimci"),
    ("Conveyor", "36 cm", 1, 39_400, 60_715, "yardimci"),
    ("Sump & Pump", "76,606 L/dk", 1, 99_200, 124_893, "yardimci"),
    ("Conveyor", "36 cm", 1, 39_400, 60_715, "yardimci"),
    ("Tailing Thickener", "49 m çap", 1, 1_945_500, 4_474_650, "atik_koyulastirma"),
    ("Sump & Pump", "76,606 L/dk", 1, 99_200, 124_893, "yardimci"),
]


def _altar_alanlari() -> list:
    toplam = {}
    adlar = {}
    for ad, _boyut, _adet, alis, montaj, alan in ALTAR_EKIPMAN_LISTESI:
        toplam[alan] = toplam.get(alan, 0) + alis + montaj
        adlar.setdefault(alan, []).append(ad)
    return [
        CapexAlan(alan, ", ".join(dict.fromkeys(adlar[alan])), v,
                  kaynak="Altar PEA, Şekil 21-1 (ekipman satın alma + montaj)")
        for alan, v in toplam.items()
    ]


ALTAR_DATA_POINT.alanlar = _altar_alanlari()
ALTAR_DATA_POINT.isleme_opex_usd_t = 6.93   # Altar PEA, Tablo 21-10 (60,000 tpd)
ALTAR_DATA_POINT.opex_kirilim = {"Ekipman işletme": 1.07, "Güç": 2.31, "Reaktif ve aşınma malzemesi": 2.15,
                                 "Saatlik işçilik": 0.85, "Maaşlı personel": 0.11, "Çeşitli": 0.44}

# Furnas - Tablo 21-8 (doğrudan) ve 21-9 (maliyet tahsisi): alan bazlı
# (rapor alanı, alan_kodu, doğrudan, dolaylı, gider payı), milyon USD
_FURNAS_ALANLAR_MUSD = [
    ("Crushing plant", "kirma", 85, 21, 16),
    ("Stockpile", "stok", 4, 1, 2),
    ("Grinding", "ogutme", 108, 27, 38),
    ("Flotation", "flotasyon", 44, 11, 12),
    ("Slimes & paste thickening (tailings)", "atik_koyulastirma", 94, 23, 22),
    ("Concentrate thickening", "konsantre_koyulastirma", 2, 0, 1),
    ("Concentrate filtration and storage", "konsantre_filtrasyon", 32, 8, 10),
    ("Reagent plant and flocculant", "reaktif", 14, 4, 6),
    ("Electricity and control", "elektrik_kontrol", 19, 10, 10),
    ("Piping in-plant", "boru", 8, 3, 4),
]
FURNAS_DATA_POINT.isleme_opex_usd_t = 8.92    # Furnas PEA, Tablo 21-23
FURNAS_DATA_POINT.opex_kirilim = {"Kırma": 0.93, "Öğütme": 3.85, "Flotasyon": 1.38, "Tatlı su": 0.07,
                                  "Koyulaştırma ve konsantre filtrasyonu": 0.40, "İdari": 1.11, "Atık": 1.17}
_FURNAS_OPEX_KAYNAK = "Furnas PEA, Tablo 21-23"
FURNAS_DATA_POINT.opex_alanlari = [
    OpexAlan("kirma", "Kırma", 0.93, "tam", kaynak=_FURNAS_OPEX_KAYNAK),
    OpexAlan("ogutme", "Öğütme", 3.85, "tam", kaynak=_FURNAS_OPEX_KAYNAK),
    OpexAlan("flotasyon", "Flotasyon", 1.38, "tam", kaynak=_FURNAS_OPEX_KAYNAK),
    OpexAlan("konsantre_koyulastirma", "Koyulaştırma ve konsantre filtrasyonu", 0.40, "tam", kaynak=_FURNAS_OPEX_KAYNAK,
             not_="Koyulaştırma ve filtrasyon raporda tek satır; konsantre_filtrasyon alanını ayrıca seçersen çift sayma olur"),
    OpexAlan("atik_koyulastirma", "Atık", 1.17, "tam", kaynak=_FURNAS_OPEX_KAYNAK,
             not_="Rapor satırı 'Atık'; atık koyulaştırma/macun tesisini kapsadığı varsayıldı"),
]
FURNAS_DATA_POINT.alanlar = [
    CapexAlan(kod, ad, d * 1e6, di * 1e6, g * 1e6,
              kaynak="Furnas PEA, Tablo 21-8 / 21-9",
              not_="Milyon USD olarak yuvarlanmış değer")
    for ad, kod, d, di, g in _FURNAS_ALANLAR_MUSD
]

# ------------------------------------------------------------------
# Cerro Blanco - Tablo 21.1 (WBS 600 Process Plant), FS, GMS / Bluestone, 6 Nisan 2022
# Altın: kırma/öğütme, lixiviation (leach + CIP carousel), refinery. Flotasyon YOK.
# ------------------------------------------------------------------
_CB_KAYNAK = "Cerro Blanco FS (GMS/Bluestone, 6 Nisan 2022), Tablo 21.1, WBS 600"
CERRO_BLANCO_DATA_POINT = CapexDataPoint(
    project="Cerro Blanco Project",
    capacity_tpd=11747,
    base_year=2021,         # rapor: tahmin baz tarihi Q4 2021
    basslik_capex_usd=571_500_000,   # başlangıç yatırımı (üretim öncesi gelir düşülmüş), proje toplamı
    kapsam=CapexKapsam(
        tsf_dahil=False,            # kuru istif tesisi (DSTF) WBS 370'te, process plant dışı
        dis_altyapi_dahil=False,    # altyapı, güç, su yönetimi WBS 100-300'de
        gider_payi_dahil=False,     # proje gider payı ($60.7M) proje düzeyinde, alanlara dağıtılmamış
        dolayli_dahil=False,        # inşaat dolayları (WBS 700) proje düzeyinde
        sahip_maliyeti_dahil=False, # WBS 800 ayrı
    ),
    alanlar=[
        CapexAlan("kirma_ogutme", "Comminution (WBS 610)", 53.2e6, kaynak=_CB_KAYNAK),
        CapexAlan("cil", "Lixiviation (WBS 640)", 29.5e6, kaynak=_CB_KAYNAK,
                  not_="Rapora göre leach + CIP carousel devresi"),
        CapexAlan("reaktif", "Reagents (WBS 650)", 3.6e6, kaynak=_CB_KAYNAK),
        CapexAlan("adr", "Refinery (WBS 660)", 9.7e6, kaynak=_CB_KAYNAK,
                  not_="Elüsyon (Zadra) devresinin Lixiviation ya da Refinery içinde olduğu raporda alan "
                       "başlığıyla ayrılmamış"),
        CapexAlan("atik_koyulastirma", "Tailings Management (WBS 680)", 29.6e6, kaynak=_CB_KAYNAK,
                  not_="Kuru istif için atık filtrasyonu ve taşıma; TSF/DSTF'nin kendisi dahil değil"),
        CapexAlan("boru", "Pipe Rack (WBS 602)", 2.2e6, kaynak=_CB_KAYNAK),
        CapexAlan("yardimci", "Process Plant Services (WBS 690), yeraltı hizmetleri (603), ROM pad ve MSE duvarı (604), "
                              "son tesviye (605)", 7.4e6 + 0.2e6 + 1.3e6 + 0.3e6, kaynak=_CB_KAYNAK),
    ],
    source="Cerro Blanco N.I. 43-101 Teknik Rapor ve Fizibilite Çalışması (GMS, Bluestone için), "
           "6 Nisan 2022; AACE Class 3 (-%10/+%15); tahmin baz tarihi Q4 2021; USD",
    notlar=(
        "Process plant (WBS 600) doğrudan toplamı $136.9M. Process plant elektrik odaları ($18.8M, WBS 260), "
        "process plant altyapısı ($6.8M, WBS 160), proses üretim öncesi ($29.2M, WBS 950) ve ilk dolum/yedek "
        "($6.6M, WBS 960) bu alanlara DAHİL DEĞİL. Dolaylı maliyet (WBS 700 $66.3M) ve gider payı ($60.7M) "
        "proje düzeyinde, alanlara dağıtılmamış; bu nedenle yalnızca doğrudan alan maliyetleri kullanılır. "
        "Alan toplamı ($137.0M) rapor toplamıyla (136.9M) yuvarlama farkıyla tutuyor."
    ),
    seviyeler=(),
    proses="Au siyanürleme (CIP) - flotasyon yok",
    isleme_opex_usd_t=12.97,
    opex_kirilim={"İşçilik": 0.71, "Güç": 5.11, "Bakım ve sarf": 3.60, "Reaktif": 3.41, "Diğer": 0.09},
)

# ------------------------------------------------------------------
# Enchi Gold Project - Tablo 21.2.1 ve 21.3.2 / 21.3.3, PFS, Lycopodium, Ağustos 2026
# Altın: kırma/boyutlandırma, SAG+bilyalı (SAB), gravite, liç öncesi koyulaştırma, CIL, elüsyon. Flotasyon YOK.
# Rapor alan tablolarındaki tutarlar tahsis edilmiş proje gider payını (contingency) İÇERİR.
# Gider payı, Tablo 21.2.1'deki bölüm toplamlarından (gider payı hariç) bölüm bazında orantılı ayrıştırıldı.
# ------------------------------------------------------------------
_EN_KAYNAK = "Enchi PFS (Lycopodium, Ağustos 2026), Tablo 21.3.2 / 21.3.3 ve Tablo 21.2.1"
_EN_TESIS_ORAN = 113.5 / 127.3   # Tablo 21.2.1 (gider payı hariç) / Tablo 21.3.2 (gider payı dahil)
_EN_REAKTIF_ORAN = 18.7 / 21.1   # Tablo 21.2.1 / Tablo 21.3.3
_EN_ALANLAR_MUSD = [
    # (alan_kodu, rapor_adi, gider payı dahil MUSD, bölüm oranı, not)
    ("kirma", "120 Feed Preparation", 18.2, _EN_TESIS_ORAN,
     "Mineral sizer (oksit) ve çeneli kırıcı (sert cevher), ROM bunkerleri, konveyörler"),
    ("ogutme", "130 Milling", 51.9, _EN_TESIS_ORAN,
     "SAG + bilyalı değirmen + siklon; gravite devresinin bu kalemde mi 160/170'te mi olduğu raporda ayrılmamış"),
    ("on_koyulastirma", "140 Trash Removal and Thickening", 5.2, _EN_TESIS_ORAN, ""),
    ("cil", "160 Leaching", 25.1, _EN_TESIS_ORAN, "7 tanklı tek hat CIL"),
    ("adr", "170 Elution and Gold Room", 11.1, _EN_TESIS_ORAN, "Split-AARL elüsyon, EW, ergitme"),
    ("reaktif", "210 Reagents", 2.4, _EN_REAKTIF_ORAN, ""),
    ("elektrik_kontrol", "260 Electrical Services", 7.9, _EN_REAKTIF_ORAN, ""),
    ("yardimci", "110 Treatment Plant General + 180 Tails Handling + 220 Water + 230 Plant Services + 240 Air",
     14.5 + 1.4 + 6.3 + 0.4 + 4.1, None,
     "Karışık: 110 ve 180 tesis oranı, 220-240 reaktif/hizmet oranı ile ayrıştırıldı"),
]


def _en_alan(kod, ad, toplam, oran, not_):
    if oran is None:
        dogrudan = (14.5 + 1.4) * _EN_TESIS_ORAN + (6.3 + 0.4 + 4.1) * _EN_REAKTIF_ORAN
    else:
        dogrudan = toplam * oran
    return CapexAlan(kod, ad, round(dogrudan * 1e6), gider_payi_usd=round((toplam - dogrudan) * 1e6),
                     kaynak=_EN_KAYNAK, not_=not_)


ENCHI_DATA_POINT = CapexDataPoint(
    project="Enchi Gold Project",
    capacity_tpd=round(5_500_000 / 365),   # 5.5 Mtpa nominal, 15,068 t/gün
    base_year=2026,                         # rapor: Q1 2026 fiyatları, -%20/+%30
    basslik_capex_usd=351_200_000,          # başlangıç yatırımı (madencilik, TSF, EPCM, sahip dahil)
    kapsam=CapexKapsam(
        tsf_dahil=False,             # baraj (Alan 350) alan tablolarında yok
        dis_altyapi_dahil=False,     # Alan 300 ayrı
        gider_payi_dahil=False,      # alan tutarlarından ayrıştırıldı (orantılı)
        dolayli_dahil=False,         # EPCM (Alan 500) ayrı
        sahip_maliyeti_dahil=False,  # Alan 600 ayrı
    ),
    alanlar=[_en_alan(*a) for a in _EN_ALANLAR_MUSD],
    source="Enchi Gold Project PFS, N.I. 43-101 Teknik Rapor (Lycopodium, Ağustos 2026); "
           "doğruluk -%20/+%30; Q1 2026 fiyatları; USD",
    notlar=(
        "Alan tabloları (21.3.2, 21.3.3) 'allocated project contingency' içerir. Tablo 21.2.1'deki gider payı hariç "
        "bölüm toplamları (tesis 113.5, reaktif ve hizmetler 18.7) ile bölüm bazında oranlanıp (gider payı ayrı "
        "tutularak) doğrudan değere çevrildi; alan başına gider payı oranının eşit olduğu varsayımı yaklaşıktır. "
        "Alanlara DAHİL DEĞİL: inşaat dağıtımları ($34.3M), tesis binaları (370, $4.9M), TSF, EPCM ($38.6M), "
        "sahip maliyetleri ($37.4M), madencilik. Kapasite 5.5 Mtpa / 365 = 15,068 t/gün (nominal)."
    ),
    seviyeler=(),
    proses="Au siyanürleme (CIL) - flotasyon yok",
    isleme_opex_usd_t=12.61,
)

# Enchi: Tablo 21.4.7 (sarf maddeleri) ve 21.4.8 (güç) alan bazında, $/yıl; 5.5 Mtpa ile $/t'ye çevrildi.
# İşçilik, bakım ve laboratuvar alan bazında verilmediği için kapsam yalnızca 'sarf_guc'.
_EN_OPEX_KAYNAK = "Enchi PFS, Tablo 21.4.7 (sarf) + 21.4.8 (güç)"
_EN_TPA = 5_500_000.0
# alan: (senaryo -> (sarf $/yıl, güç $/yıl))
_EN_OPEX_YILLIK = {
    "Oksit, P80 53 µm": {
        "kirma": (153_197, 445_955), "ogutme": (14_633_706, 11_824_319),
        "on_koyulastirma": (278_857, 231_470), "cil": (9_663_173, 1_816_105), "adr": (3_891_551, 144_927),
    },
    # Taze cevherde 'Leaching' sarf satırının $/yıl değeri raporda oksit ile aynı basılmış (9,663,173), ancak
    # $/t (3.10) ve toplam (44,621,233) tutarlı; 3.10 $/t * 5.5 Mtpa = 17.07M $/yıl kullanıldı.
    "Taze (blast), P80 53 µm": {
        "kirma": (793_533, 417_345), "ogutme": (20_513_234, 21_766_323),
        "on_koyulastirma": (531_967, 231_470), "cil": (3.10 * _EN_TPA, 1_816_105), "adr": (3_891_551, 144_927),
    },
}
_EN_OPEX_ADLARI = {"kirma": "Feed Preparation (kırma/boyutlandırma)", "ogutme": "Milling",
                   "on_koyulastirma": "Trash Removal & Thickening", "cil": "Leaching", "adr": "Elution & Gold Room"}
ENCHI_DATA_POINT.opex_alanlari = [
    OpexAlan(kod, _EN_OPEX_ADLARI[kod], round((sarf + guc) / _EN_TPA, 3), "sarf_guc", senaryo=sen,
             kaynak=_EN_OPEX_KAYNAK,
             not_="Milling kalemi gravite devresini içerebilir; raporda ayrılmamış. Taze cevherde Feed Preparation "
                  "güç satırı kırmayı (0.08 $/t) içerir; stok ve geri alma (0.01 $/t) dahil değil." if kod in ("kirma", "ogutme") else "")
    for sen, d in _EN_OPEX_YILLIK.items() for kod, (sarf, guc) in d.items()
]

# ------------------------------------------------------------------
# Cactus Mine Project - Tablo 21-3 (Process Plant Direct Capital, initial), PFS, M3 Engineering, 17 Kasım 2025
# Cu yığın liçi (heap leach) + SX-EW. Kısa ton (st) ve USD. Flotasyon YOK.
# Tablo 21-3 'Direct Infrastructure Cost Excluded' başlığını taşır: altyapı (Tablo 21-4), dolaylı (21-5),
# gider payı (21-6) ve sahip maliyeti ayrı. Madencilik alanlara dahil değil.
# ------------------------------------------------------------------
_ST_T = 0.90718474   # 1 kısa ton = 0.9072 metrik ton
_CA_KAYNAK = "Cactus PFS (M3 Engineering, 17 Kasım 2025), Tablo 21-3 (initial)"
_CA_ALANLAR_KUSD = [
    # (alan_kodu, rapor_adi, kUSD, not)
    ("kirma", "Primary Crusher + Primary Crusher Discharge Conveyor + Secondary Screening + Secondary Crushing + "
              "Crushing Control Room", 15_398 + 3_770 + 21_649 + 28_826 + 645,
     "Rapor iki kademeli kırma diyor; kırma kontrol odası dahil"),
    ("stok", "Reclaim", 7_083, "Kırılmış cevher geri alma"),
    ("heap_leach", "Leach Pad + Solution Collection + Leach Pad Piping & Stacking",
     60_526 + 15_113 + 29_122, "Yığın liçi tesisi (HLF): pad, solüsyon toplama, borulama ve istif"),
    ("sx_ew", "SX & Raffinate + SX Tank Farm + Electrowinning + SX/EW Control Room",
     38_008 + 41_852 + 53_672 + 931, "SX, tank çiftliği ve EW birlikte; raporda ayrı SX ve EW kalemleri var"),
    ("reaktif", "SX/EW Reagents + Sulfuric Acid", 887 + 2_935,
     "Sülfürik asit satın alınıyor; kalem asit depolama/dağıtım, asit üretim tesisi DEĞİL"),
    ("yardimci", "Loadout + Process Maintenance Building + Well Fields", 4_878 + 1_896 + 586, ""),
]
CACTUS_DATA_POINT = CapexDataPoint(
    project="Cactus Mine Project",
    capacity_tpd=round(76_713 * _ST_T),    # 76,713 st/gün (28 Mst/yıl yığına) -> metrik t/gün
    base_year=2025,                         # rapor: 2025 3. çeyrek maliyetleri, -%20/+%20
    basslik_capex_usd=976_977_000,          # başlangıç yatırımı, gider payı dahil (madencilik, altyapı, sahip dahil)
    kapsam=CapexKapsam(
        tsf_dahil=False,             # yığın liçi pad'i proses alanı olarak dahil; atık barajı bu rapor türünde yok
        dis_altyapi_dahil=False,     # Tablo 21-4 (123.4M$) ayrı
        gider_payi_dahil=False,      # Tablo 21-6 ayrı (plant+altyapı %18)
        dolayli_dahil=False,         # Tablo 21-5 ayrı (EPCM, nakliye, geçici tesisler vb.)
        sahip_maliyeti_dahil=False,  # sahip maliyetleri ayrı
    ),
    alanlar=[CapexAlan(k, ad, kusd * 1000, kaynak=_CA_KAYNAK, not_=n) for k, ad, kusd, n in _CA_ALANLAR_KUSD],
    source="Cactus Mine Project NI 43-101 Teknik Rapor - Pre-Feasibility Study (M3 Engineering, yayın 17 Kasım 2025, "
           "geçerlilik 20 Ekim 2025); AACE Class 4 (-%20/+%20); 2025 Q3 fiyatları; USD, kısa ton",
    notlar=(
        "Process plant doğrudan toplamı raporda (Tablo 21-3, initial) 335.7M$; ancak tablodaki 18 satırın toplamı 327.8M$ (7.9M$ fark raporun kendi içinde tutarsız, kaynağı bilinmiyor). Alan değerleri satır toplamlarından alındı. Alanlara DAHİL DEĞİL: onsite altyapı "
        "123.4M$ (Tablo 21-4, APS bağlantısı 49M$ dahil), dolaylı 149.7M$ (Tablo 21-5), gider payı (Tablo 21-6, "
        "plant+altyapı %18), sahip maliyetleri, arazi ve madencilik. Rapor metnine göre ekipman ve dökme malzeme "
        "maliyetine %8 nakliye payı dahil; Tablo 21-5'te ayrıca nakliye kalemi de var, çift sayım olup olmadığı "
        "belirsiz. Kapasite 76,713 st/gün (28 Mst/yıl yığına istif) metrik t/gün'e çevrildi. OPEX $/st metrik "
        "$/t'a çevrildi. İşleme OPEX'i yalnızca proses (madencilik ve G&A hariç)."
    ),
    seviyeler=(),
    proses="Cu yığın liçi + SX-EW (asit) - flotasyon yok",
    isleme_opex_usd_t=round(2.53 / _ST_T, 2),
    opex_kirilim={k: round(v / _ST_T, 2) for k, v in
                  {"İşçilik": 0.41, "Güç": 1.02, "Reaktif": 0.54, "Aşınma parçaları": 0.02,
                   "Bakım parçaları": 0.42, "Sarf ve hizmetler": 0.12}.items()},
)

# ------------------------------------------------------------------
# Santa Fe Project - Tablo 21-4 (Processing and Infrastructure, pre-production), PEA, KCA / RESPEC,
# Lahontan Gold Corp., rapor tarihi 24 Ocak 2025 (geçerlilik 10 Aralık 2024). Nevada, ABD.
# Au yığın liçi + karbon adsorpsiyonu + ADR. Flotasyon YOK. 12,500 t/gün (metrik).
# Tablodaki alan tutarları disiplin bazlı doğrudan maliyettir (toprak işleri, inşaat, çelik, ekipman, boru,
# elektrik, enstrümantasyon); gider payı ve yedek parça tabloda ayrı satırdır.
# ------------------------------------------------------------------
_SF_KAYNAK = "Santa Fe PEA (KCA/RESPEC, 24 Ocak 2025), Tablo 21-4 (pre-production)"
_SF_ALANLAR_KUSD = [
    # (alan_kodu, rapor_adi, kUSD, not)
    ("kirma", "Crushing", 21_718, "Üç kademeli kırma, P80 12.7 mm"),
    ("stok", "Crushed Ore, Reclaim & Stacking", 14_072, "Kırılmış cevher geri alma ve istif konveyörleri"),
    ("heap_leach", "Heap Leach Pad & Ponds", 20_373, "Pad, astar ve havuzlar (toprak işleri ağırlıklı)"),
    ("karbon_adsorpsiyon", "Carbon Adsorption", 2_649, "Yığın liçi pregnant solüsyonu için karbon kolonları"),
    ("adr", "Carbon Desorption & Reactivation + Refinery", 8_800 + 5_086,
     "Elüsyon, karbon rejenerasyonu ve rafineri; ADR tedarikçi paketi (mühendislik ve devreye alma dahil)"),
    ("reaktif", "Reagents", 965, ""),
    ("yardimci", "Water Supply, Storage & Distribution", 1_747, "Yalnızca su temini ve dağıtımı"),
]
SANTA_FE_DATA_POINT = CapexDataPoint(
    project="Santa Fe Project",
    capacity_tpd=12_500,                   # 4.5625 Mtpa; rapor metrik ton
    base_year=2024,                         # rapor: 2024 4. çeyrek dolar, -%30/+%30
    basslik_capex_usd=135_066_000,          # Tablo 21-1 pre-production toplamı (işletme sermayesi dahil)
    kapsam=CapexKapsam(
        tsf_dahil=False,             # yığın liçi pad'i proses alanı; atık barajı yok (heap)
        dis_altyapi_dahil=False,     # güç, tesis binaları ve laboratuvar alanlara dahil değil
        gider_payi_dahil=False,      # Tablo 21-4'te ayrı satır (16.2M$), alanlara dağıtılmamış
        dolayli_dahil=False,         # EPCM (8.7M$) ve inşaat dolayları (1.4M$) ayrı
        sahip_maliyeti_dahil=False,  # sahip maliyetleri (4.5M$) ayrı
    ),
    alanlar=[CapexAlan(k, ad, kusd * 1000, kaynak=_SF_KAYNAK, not_=n) for k, ad, kusd, n in _SF_ALANLAR_KUSD],
    source="Santa Fe Project NI 43-101 PEA Teknik Raporu (KCA ve RESPEC, Lahontan Gold Corp. için), "
           "24 Ocak 2025; doğruluk -%30/+%30; 2024 Q4 fiyatları; USD, metrik ton",
    notlar=(
        "Tablo 21-4'te disiplin bazlı doğrudan maliyetler toplamı 88.3M$. Alanlara DAHİL DEĞİL: laboratuvar "
        "(2.4M$), güç (1.9M$), tesis binaları (2.6M$), hareketli ekipman (5.9M$), yedek parça (1.2M$), gider payı "
        "(16.2M$), EPCM (8.7M$), inşaat dolayları (1.4M$), sahip maliyetleri (4.5M$), ilk dolumlar (0.5M$) ve "
        "işletme sermayesi (10.7M$). Küçük ölçekli (12,500 t/gün) Nevada yığın liçi projesidir; PEA düzeyi "
        "(-%30/+%30) olduğundan güvenilirlik fizibilite çalışmalarından düşüktür."
    ),
    seviyeler=(),
    proses="Au yığın liçi + karbon adsorpsiyonu + ADR - flotasyon yok",
    isleme_opex_usd_t=4.98,
    opex_kirilim={"İşçilik": 1.60, "Güç": 0.41, "Sarf": 0.52, "Reaktif": 2.24, "Bakım": 0.21},
)

ALL_DATA_POINTS = [ALTAR_DATA_POINT, FURNAS_DATA_POINT, CERRO_BLANCO_DATA_POINT, ENCHI_DATA_POINT, CACTUS_DATA_POINT,
                   SANTA_FE_DATA_POINT, LA_MINA_DATA_POINT]


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


def alan_dokumu(p: CapexDataPoint, turetilmis: bool = False) -> dict:
    """Bir veri noktasının alanlarını alan_kodu'na göre toplar (doğrudan, dolaylı, gider payı).
    turetilmis=True ise ayrı satır veren raporlar için birleşik 'kirma_ogutme' satırı da türetilir
    (toplamlara karıştırılmaması için varsayılan kapalı)."""
    out = {}
    for a in p.alanlar:
        d = out.setdefault(a.alan_kodu, {"dogrudan": 0.0, "dolayli": 0.0, "gider_payi": 0.0,
                                         "dolayli_var": True, "gider_payi_var": True, "rapor_adlari": []})
        d["dogrudan"] += a.dogrudan_usd
        if a.dolayli_usd is None:
            d["dolayli_var"] = False
        else:
            d["dolayli"] += a.dolayli_usd
        if a.gider_payi_usd is None:
            d["gider_payi_var"] = False
        else:
            d["gider_payi"] += a.gider_payi_usd
        d["rapor_adlari"].append(a.rapor_adi)
    # Birleşik kırma+öğütme: ayrı satır veren raporlardan türetilir (kırma, stok, öğütme)
    if turetilmis and "kirma_ogutme" not in out:
        parcalar = [out[k] for k in ("kirma", "stok", "ogutme") if k in out]
        if parcalar and "kirma" in out and "ogutme" in out:
            out["kirma_ogutme"] = {
                "dogrudan": sum(x["dogrudan"] for x in parcalar), "dolayli": 0.0, "gider_payi": 0.0,
                "dolayli_var": False, "gider_payi_var": False,
                "rapor_adlari": ["türetilmiş: kırma + stok + öğütme"],
            }
    return out


def estimate_area_capex(
    alan_kodu: str,
    target_capacity_tpd: float,
    exponent: float = LITERATUR_USTEL,
    duzeltme_carpani: float = 1.0,
    points=None,
) -> dict:
    """
    Tek bir proses alanının DOĞRUDAN maliyetini, o alan için verisi olan her
    doğrulanmış referanstan (kapsamı doğrulanmış nokta) ayrı ayrı ölçekler.
    Dolaylı maliyet ve gider payı buraya karışmaz (kullanıcı ekler).
    Veri yoksa referanslar boştur.
    """
    points = ALL_DATA_POINTS if points is None else points
    refs = []
    for p in points:
        if not (p.kapsam_dogrulandi or p.alan_dogrulandi):
            continue
        d = alan_dokumu(p, turetilmis=True).get(alan_kodu)
        if d is None or d["dogrudan"] <= 0:
            continue
        olcekli = d["dogrudan"] * (target_capacity_tpd / p.capacity_tpd) ** exponent * duzeltme_carpani
        refs.append({
            "project": p.project, "capacity_tpd": p.capacity_tpd, "base_year": p.base_year,
            "reference_direct_usd": d["dogrudan"], "scaled_usd": round(olcekli, 0),
            "proses": p.proses,
            "rapor_adlari": d["rapor_adlari"],
        })
    degerler = [r["scaled_usd"] for r in refs]
    return {
        "alan_kodu": alan_kodu, "etiket": ALAN_TURLERI.get(alan_kodu, alan_kodu),
        "referanslar": refs, "veri_var": bool(refs),
        "min_usd": min(degerler) if degerler else None,
        "max_usd": max(degerler) if degerler else None,
        "exponent": exponent,
    }


def estimate_area_opex(alan_kodu: str, points=None) -> dict:
    """
    Bir proses alanının raporlardaki alan bazlı işletme gideri ($/t o alanın beslemesi). Kapsamlar ('tam' ve
    'sarf_guc') ayrı tutulur ve toplanmaz. Veri yoksa referanslar boştur.
    """
    points = ALL_DATA_POINTS if points is None else points
    refs = []
    for p in points:
        if not (p.kapsam_dogrulandi or p.alan_dogrulandi):
            continue
        for o in p.opex_alanlari:
            if o.alan_kodu == alan_kodu and o.usd_t > 0:
                refs.append({"project": p.project, "base_year": p.base_year, "proses": p.proses,
                             "rapor_adi": o.rapor_adi, "usd_t": o.usd_t, "kapsam": o.kapsam,
                             "senaryo": o.senaryo, "kaynak": o.kaynak, "not": o.not_})
    return {"alan_kodu": alan_kodu, "etiket": ALAN_TURLERI.get(alan_kodu, alan_kodu),
            "referanslar": refs, "veri_var": bool(refs)}


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
    # Altar ekipman listesi toplamları (Şekil 21-1)
    alis = sum(i[3] for i in ALTAR_EKIPMAN_LISTESI)
    montaj = sum(i[4] for i in ALTAR_EKIPMAN_LISTESI)
    print(f"Altar ekipman listesi: satın alma {alis:,.0f}, montaj {montaj:,.0f} (rapor: 109,790,004 / 130,215,932)")
    assert alis == 109_790_004 and montaj == 130_215_932
    assert abs(sum(a.dogrudan_usd for a in ALTAR_DATA_POINT.alanlar) - (alis + montaj)) < 1
    fd = alan_dokumu(FURNAS_DATA_POINT)
    print("Furnas alanları toplamı: doğrudan %.0f, dolaylı %.0f, gider payı %.0f (rapor: 410 / 109 / 121 milyon)" % (
        sum(v["dogrudan"] for v in fd.values()), sum(v["dolayli"] for v in fd.values()),
        sum(v["gider_payi"] for v in fd.values())))
    assert sum(v["dogrudan"] for v in fd.values()) == 410e6
    assert sum(v["gider_payi"] for v in fd.values()) == 121e6
    cb = CERRO_BLANCO_DATA_POINT
    cb_toplam = sum(a.dogrudan_usd for a in cb.alanlar)
    print(f"Cerro Blanco alanları toplamı: {cb_toplam:,.0f} (rapor WBS 600: 136.9 milyon); durum: {cb.durum}")
    assert abs(cb_toplam - 136.9e6) <= 0.2e6 and cb.alan_dogrulandi and not cb.kapsam_dogrulandi
    assert cb.capex_seviye("A") is None
    assert all(p.project != cb.project for p in dogrulanmis_noktalar(seviye="A"))
    ko = estimate_area_capex("kirma_ogutme", 11747)
    print("  kirma_ogutme @11,747 tpd: " + ", ".join(f"{r['project']} {r['scaled_usd']:,.0f}" for r in ko["referanslar"]))
    assert {r["project"] for r in ko["referanslar"]} == {"Altar Project", "Furnas Project", "Cerro Blanco Project", "Enchi Gold Project"}
    print("  cil @11,747 tpd:", [(r['project'], r['scaled_usd']) for r in estimate_area_capex("cil", 11747)["referanslar"]])
    for kod in ("kirma", "ogutme", "flotasyon", "heap_leach"):
        e = estimate_area_capex(kod, 30000)
        print(f"  Alan {kod} @30,000 tpd: " + (", ".join(f"{r['project']} {r['scaled_usd']:,.0f}" for r in e["referanslar"]) or "VERİ YOK"))
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


    # --- Alan bazlı OPEX ---
    en = {(o.alan_kodu, o.senaryo): o.usd_t for o in ENCHI_DATA_POINT.opex_alanlari}
    print("\nEnchi alan OPEX (sarf+güç, $/t):", en)
    # oksit 53 µm: tabloda sarf toplamı 30.44M, güç toplamı 17.56M (tüm alanlar, çeşitli kalemler dahil)
    assert abs(en[("cil", "Oksit, P80 53 µm")] - (9_663_173 + 1_816_105) / 5.5e6) < 0.002
    assert abs(en[("ogutme", "Taze (blast), P80 53 µm")] - (20_513_234 + 21_766_323) / 5.5e6) < 0.002
    f_toplam = sum(o.usd_t for o in FURNAS_DATA_POINT.opex_alanlari)
    print(f"Furnas alan OPEX toplamı (5 alan): {f_toplam:.2f} $/t (kırılım toplamı 8.92 içinde tatlı su ve idari hariç)")
    assert abs(f_toplam - (0.93 + 3.85 + 1.38 + 0.40 + 1.17)) < 1e-9
    eo = estimate_area_opex("cil")
    assert eo["veri_var"] and all(r["kapsam"] == "sarf_guc" for r in eo["referanslar"])
    assert not estimate_area_opex("gravite")["veri_var"]
