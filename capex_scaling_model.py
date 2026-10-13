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
    # Alanın kendi besleme kapasitesi (t/gün). Verilmezse noktanın cevher kapasitesi kullanılır. Yalnızca raporun
    # tasarım değerlerinden doğrudan türetilebiliyorsa girilir (ör. konsantre liçi = cevher x tasarım ağırlık verimi).
    kapasite_tpd: Optional[float] = None


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
    # True: nokta yalnızca alan bazlı OPEX referansıdır (raporda alan bazlı CAPEX yok); CAPEX tablolarına ve grafiğine girmez
    yalniz_opex: bool = False

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
        if self.yalniz_opex and self.opex_alanlari:
            return "Yalnızca alan bazlı OPEX referansı (CAPEX yok)"
        if self.yalniz_opex and self.isleme_opex_usd_t is not None:
            return "Yalnızca işleme OPEX toplamı referansı (alan bazlı CAPEX ve OPEX yok)"
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
    # Bazı alanlar için az sayıda rapordan veri var (heap_leach: Cactus, Santa Fe; sx_ew: Cactus; cil, adr,
    # on_koyulastirma: Enchi, Cerro Blanco, Springpole, Tocantinzinho, Lemhi; karbon_adsorpsiyon: Santa Fe; gravite: Tocantinzinho;
    # cil_kons: Springpole, Tocantinzinho, Courageous Lake; pox: Courageous Lake). asit_tesisi, dms ve manyetik için
    # henüz doğrulanmış rapor verisi yok; bu üç alan KAPALI_ALAN_TURLERI'nde tutulur ve kullanıcıya gösterilmez.
    "heap_leach": "Heap leach (aglomerasyon, istif, pad)",
    "sx_ew": "SX-EW",
    "on_koyulastirma": "Liç öncesi koyulaştırma ve kaba ayıklama (trash screen)",
    "cil": "Siyanür liçi, CIP/CIL ve detoks (tüm cevher veya flotasyon atığı)",
    "cil_kons": "Konsantre siyanür liçi (CIP/CIL veya Merrill-Crowe) ve detoks",
    "pox": "Konsantre ön işlemi: asidülasyon ve basınçlı oksidasyon (POX)",
    "karistirmali_lic": "Karıştırmalı (agitated) asit liçi, flotasyon atığı (Cu)",
    "karbon_adsorpsiyon": "Karbon adsorpsiyonu (CIC kolonları, yığın liçi sonrası)",
    "adr": "ADR (karbon geri kazanım) ve rafineri",
    "gravite": "Gravite ayırma (jig, spiral, masa, santrifüj)",
}

# Rapor verisi olmadığı için kullanıcıya KAPALI alanlar. Veri ağacı genişleyince bu girdileri ALAN_TURLERI'ne taşı
# (ve process_chain_model.py'deki KAPALI_ASAMA_TURLERI / TUR_ALANLARI karşılıklarını geri aç).
KAPALI_ALAN_TURLERI = {
    "asit_tesisi": "Sülfürik asit tesisi",
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

# ------------------------------------------------------------------
# Springpole Au - PFS (AGP/SRK, First Mining Gold, 26 Şubat 2021), Tablo 21-10 (Process Plant Capital Cost Estimate, CDN$)
# 30,000 t/gün: kırma, SAG + bilyalı, flotasyon (ağırlık verimi %15), konsantre yeniden öğütme + liç + CIP, flotasyon atığı
# liçi + CIP, ADR, rafineri, atık koyulaştırma + basınçlı filtre. Maliyet CDN$ olarak hazırlanmış; raporun kendi kuruyla
# (Tablo 21-6: 1.00 CDN = 0.750 USD) USD'ye çevrildi. Tahmin baz tarihi Q4 2020, AACE Class 4 (-%20/+%30).
# ------------------------------------------------------------------
_SP_KAYNAK = "Springpole PFS (AGP/SRK, 26 Şubat 2021), Tablo 21-10 (WBS 3000, ilk yatırım, CDN$M)"
_SP_KUR = 0.75               # Tablo 21-6
_SP_TPD = 30_000.0           # Tablo 17-1
_SP_KONS_TPD = _SP_TPD * 0.15          # Tablo 17-1: final konsantre kütle verimi %15
_SP_ATIK_TPD = _SP_TPD * (1 - 0.15)


def _sp(kod, ad, cad_m, **kw):
    return CapexAlan(kod, ad, cad_m * _SP_KUR * 1e6, kaynak=_SP_KAYNAK,
                     not_=f"Rapor değeri CDN${cad_m}M; x{_SP_KUR} (raporun kuru). " + kw.pop("not_", ""), **kw)


SPRINGPOLE_DATA_POINT = CapexDataPoint(
    project="Springpole Gold Project",
    capacity_tpd=_SP_TPD,
    base_year=2020,
    basslik_capex_usd=718_300_000,          # Tablo 21-1: ilk yatırım toplamı (USD), proje geneli
    kapsam=CapexKapsam(tsf_dahil=False, dis_altyapi_dahil=False, gider_payi_dahil=False, dolayli_dahil=False,
                       sahip_maliyeti_dahil=False),
    alanlar=[
        _sp("kirma", "Crushing, Stockpile, Reclaim (WBS 3100)", 29.7,
            not_="Kırma, stok ve geri alma tek satırda; stok ayrı verilmemiş."),
        _sp("ogutme", "Grinding (WBS 3200)", 66.4,
            not_="SAG + bilyalı değirmen + siklon. Konsantre yeniden öğütme (3 x 3 MW IsaMill) alan ekipman listelerinde "
                 "geçmiyor; hangi WBS'de olduğu raporda belirtilmemiş. PFS, daha sert cevher verisi için büyük bilyalı değirmen "
                 "payını gider payına (contingency) koymuş."),
        _sp("flotasyon", "Flotation (WBS 3300)", 25.5),
        _sp("cil", "Flotation Tailings Leaching (WBS 3400)", 71.2, kapasite_tpd=_SP_ATIK_TPD,
            not_=f"Flotasyon atığı liçi + CIP. Besleme = {_SP_TPD:,.0f} x (1 - %15) = {_SP_ATIK_TPD:,.0f} t/gün "
                 "(raporun tasarım ağırlık verimi %15'inden türetildi)."),
        _sp("cil_kons", "Concentrate Leaching (WBS 3500)", 60.3, kapasite_tpd=_SP_KONS_TPD,
            not_=f"Konsantre liçi + CIP. Besleme = {_SP_TPD:,.0f} x %15 = {_SP_KONS_TPD:,.0f} t/gün (raporun tasarım ağırlık "
                 "verimi %15'inden türetildi)."),
        _sp("adr", "ADR Plant (WBS 3600)", 15.0),
        _sp("adr", "Refinery (WBS 3700)", 7.2, not_="Elektrokazanım, altın odası, dökümhane."),
        _sp("reaktif", "Reagents and Services (WBS 3800)", 10.7),
        _sp("atik_koyulastirma", "Tailings Filtration (WBS 3900)", 109.7,
            not_="Yüksek hızlı koyulaştırıcı + basınçlı filtre presler (12 adet) + yükleme konveyörü; kuru istif sahası bu "
                 "alana dahil değil. Siyanür yok etme (detoks) ünitesinin hangi alanda olduğu raporda ayrıca belirtilmemiş."),
    ],
    source="Springpole Gold Project NI 43-101 Teknik Rapor ve Ön Fizibilite Çalışması (AGP Mining Consultants, First Mining "
           "Gold için), 26 Şubat 2021; AACE Class 4 (-%20/+%30); tahmin baz tarihi Q4 2020; CDN$ ile hazırlanmış, USD'ye "
           "raporun kuruyla çevrildi",
    notlar=(
        "Process plant ilk yatırım doğrudan toplamı CDN$395.7M (USD 296.7M, Tablo 21-1/21-3). Dolaylı maliyet "
        "(indirects CDN$63.8M, EPCM 50.0M, sahip maliyeti 21.4M) ve gider payı (CDN$107.9M, contingency + management reserve) "
        "proje düzeyinde, alanlara dağıtılmamış; bu nedenle yalnızca doğrudan alan maliyetleri kullanılır. Raporun sunduğu "
        "bu akış (flotasyon -> konsantre yeniden öğütme + liç, flotasyon atığı liçi) kombine rota için tek tam referanstır; "
        "konsantre ve atık liçi için alan bazlı kapasite raporun %15 ağırlık veriminden türetilmiştir."
    ),
    seviyeler=(),
    proses="Au flotasyon + konsantre liçi + flotasyon atığı liçi (CIP)",
    isleme_opex_usd_t=10.87,        # Tablo 21-2 (USD); CDN$14.50/t x 0.75
    opex_kirilim={"Reaktif ve sarf": 7.05, "Güç": 2.07, "İşçilik": 0.86, "Bakım": 0.53, "Su arıtma": 0.32,
                  "Laboratuvar": 0.04, "Mobil ekipman": 0.02},    # Tablo 21-29, CDN$/t x 0.75
)

# ------------------------------------------------------------------
# Tocantinzinho Au - FS (GMS/SRK, G Mining Ventures, 9 Şubat 2022), Tablo 21.7 (k USD, geri alınabilir vergiler düşülmüş)
# 11,890 t/gün granit cevher: kırma, SAG + bilyalı, gravite (KC-QS48 x2 + intensif liç), flotasyon (ağırlık verimi %4.5),
# yalnızca flotasyon konsantresi CIL'e gider (yeniden öğütme yok, yalnızca yer ayrılmış). Baz tarihi Q1 2022, AACE Class 3.
# ------------------------------------------------------------------
_TZ_KAYNAK = "Tocantinzinho FS (GMS/SRK, 9 Şubat 2022), Tablo 21.7 (WBS 600, k USD, geri alınabilir vergiler düşülmüş)"
_TZ_TPD = 11_890.0                      # Tablo 17.1, nominal günlük kapasite
_TZ_KONS_TPD = round(_TZ_TPD * 0.045, 1)   # Tablo 17.1: toplam flotasyon ağırlık verimi (granit) %4.5 -> ~535 t/gün


def _tz(kod, ad, kusd, **kw):
    return CapexAlan(kod, ad, kusd * 1e3, kaynak=_TZ_KAYNAK, **kw)


TOCANTINZINHO_DATA_POINT = CapexDataPoint(
    project="Tocantinzinho Gold Project",
    capacity_tpd=_TZ_TPD,
    base_year=2022,
    basslik_capex_usd=457_845_000,          # Tablo 21.1: ilk yatırım toplamı (geri alınabilir vergi ve kredi düşülmüş)
    kapsam=CapexKapsam(tsf_dahil=False, dis_altyapi_dahil=False, gider_payi_dahil=False, dolayli_dahil=False,
                       sahip_maliyeti_dahil=False),
    alanlar=[
        _tz("kirma", "611 Primary Crusher", 6969),
        _tz("stok", "612 Ore Reclaim", 4409),
        _tz("ogutme", "613 Primary Grinding", 18046),
        _tz("ogutme", "614 Pebble Conveyors", 948),
        _tz("ogutme", "615 Secondary Grinding (& Cyclone)", 9035),
        _tz("gravite", "621 Gravity", 1600, not_="2 x KC-QS48 santrifüj konsantratör; siklon altının %40'ını işler."),
        _tz("gravite", "622 Intensive Leach", 883, not_="Gravite konsantresi için intensif siyanürleme reaktörü (ILR)."),
        _tz("flotasyon", "631 Rougher & Scavenger Flotation", 7859),
        _tz("flotasyon", "632 Cleaner Flotation", 1797),
        _tz("flotasyon", "639 Flotation Services", 1005),
        _tz("reaktif", "638 Flotation Reagent", 966),
        _tz("reaktif", "650 Reagents (651-657)", 4487),
        _tz("on_koyulastirma", "641 Pre-Leach", 1584, kapasite_tpd=_TZ_KONS_TPD,
            not_="Konsantre liç öncesi koyulaştırıcı (21 m çaplı)."),
        _tz("cil_kons", "642 CIL (Carbon in Leach)", 5044, kapasite_tpd=_TZ_KONS_TPD,
            not_=f"Yalnızca flotasyon konsantresi (+ ILR kalıntısı) işlenir. Besleme = {_TZ_TPD:,.0f} x %4.5 = "
                 f"{_TZ_KONS_TPD:,.0f} t/gün (raporun tasarım ağırlık veriminden türetildi)."),
        _tz("cil_kons", "644 Cyanide Recovery", 996, kapasite_tpd=_TZ_KONS_TPD),
        _tz("cil_kons", "645 Detox", 1023, kapasite_tpd=_TZ_KONS_TPD),
        _tz("adr", "661 ADR", 1022),
        _tz("adr", "662 Carbon Regeneration", 3726),
        _tz("adr", "663 Gold Room", 1475),
        _tz("adr", "664 HCL", 107),
        _tz("boru", "602 Pipe Rack", 1416),
        _tz("yardimci", "601 Site Preparation / Road / Berms + 603 Buried Services + 604 ROM Pad", 1046 + 576 + 61),
        _tz("yardimci", "680 Tailings Management (680, 682-685)", 352 + 98 + 1701 + 2474 + 603,
            not_="Atık boru hatları ve geri kazanım suyu (FTSF/CTSF); depolama tesislerinin kendisi dahil değil."),
        _tz("yardimci", "690 Process Plant Services (691-697)", 4731),
    ],
    source="Tocantinzinho Gold Project Fizibilite Çalışması NI 43-101 Teknik Rapor (GMS/SRK, G Mining Ventures için), "
           "efektif tarih 10 Aralık 2021, yayın 9 Şubat 2022; AACE Class 3 (-%10/+%15); baz tarihi Q1 2022; USD",
    notlar=(
        "Process plant (WBS 600) doğrudan toplamı $86.0M (geri alınabilir vergiler ve krediler düşülmüş; vergi dahil "
        "$88.6M, vergi hariç $78.5M). İnşaat dolayları (WBS 700 $55.4M), sahip/genel hizmetler (WBS 800 $57.0M), üretim "
        "öncesi (WBS 900 $46.3M) ve contingency (WBS 990 $38.3M) proje düzeyinde, alanlara dağıtılmamış. Konsantre yeniden "
        "öğütme ekipmanı kurulmamış (yalnızca yer ayrılmış). Gravite devresi siklon altının %40'ını işlediği için gravite "
        "alanının besleme kapasitesi cevher kapasitesi olarak alındı. Bu nokta, küçük ölçekli konsantre CIL için "
        "(~535 t/gün) gerçek bir referanstır."
    ),
    seviyeler=(),
    proses="Au gravite + flotasyon + konsantre CIL (konsantre ~535 t/gün)",
    isleme_opex_usd_t=8.83,         # Tablo 21.19, ömür boyu, geri alınamayan vergiler (NRT) dahil
)

# ------------------------------------------------------------------
# Courageous Lake Au - PFS/PEA (Ausenco, 5 Ocak 2024; değiştirilmiş 23 Mart 2026), Tablo 21-5 (US$M, ilk yatırım)
# 7,500 t/gün: kırma, çubuk/bilyalı öğütme, flotasyon + yeniden öğütme (konsantre ağırlık verimi azami %4.2, Au verimi %88),
# konsantre ön işlemi (asidülasyon + basınçlı oksidasyon, POX), siyanür liçi + CCD + Merrill-Crowe, detoks.
# Baz tarihi Q3-Q4 2023, AACE Class 4 (-%20/+%25). Değerler raporda tam milyon dolara yuvarlanmış.
# ------------------------------------------------------------------
_CL_KAYNAK = "Courageous Lake PFS/PEA (Ausenco, 5 Ocak 2024), Tablo 21-5 (WBS 2000, ilk yatırım, US$M)"
_CL_TPD = 7_500.0
_CL_KONS_TPD = round(_CL_TPD * 0.042, 1)       # Tablo 17: genel devre azami konsantre ağırlık verimi %4.2


def _cl(kod, ad, musd, **kw):
    return CapexAlan(kod, ad, musd * 1e6, kaynak=_CL_KAYNAK, **kw)


COURAGEOUS_LAKE_DATA_POINT = CapexDataPoint(
    project="Courageous Lake Project",
    capacity_tpd=_CL_TPD,
    base_year=2023,
    basslik_capex_usd=747_000_000,          # Tablo 21-1: ilk yatırım toplamı
    kapsam=CapexKapsam(tsf_dahil=False, dis_altyapi_dahil=False, gider_payi_dahil=False, dolayli_dahil=False,
                       sahip_maliyeti_dahil=False),
    alanlar=[
        _cl("kirma", "Crushing (WBS 2100)", 20),
        _cl("stok", "Stockpile and Reclaim (WBS 2200)", 10),
        _cl("ogutme", "Grinding (WBS 2300)", 30),
        _cl("flotasyon", "Flotation and Regrind (WBS 2400)", 19, not_="Konsantre yeniden öğütme bu satıra dahil."),
        _cl("pox", "Concentrate Pre-Treatment (WBS 2500)", 75, kapasite_tpd=_CL_KONS_TPD,
            not_=f"Asidülasyon + basınçlı oksidasyon (POX) devresi. Besleme = {_CL_TPD:,.0f} x %4.2 = {_CL_KONS_TPD:,.0f} t/gün "
                 "(raporun azami konsantre ağırlık veriminden türetildi). Refrakter konsantre."),
        _cl("cil_kons", "Leaching and Merrill-Crowe (WBS 2600)", 18, kapasite_tpd=_CL_KONS_TPD,
            not_="Siyanür liçi, CCD, Merrill-Crowe çinko çökeltme ve rafineri (karbon adsorpsiyonu yok)."),
        _cl("yardimci", "Neutralization, Cyanide Detox and Tailings (WBS 2700)", 4),
        _cl("yardimci", "Process Plant Services and Common (WBS 2800, yalnızca ilk yatırım)", 27),
    ],
    source="Courageous Lake Project ÖFS ve PEA NI 43-101 Teknik Rapor (Ausenco, Valor Gold için), efektif tarih 5 Ocak 2024, "
           "değiştirilmiş 23 Mart 2026; AACE Class 4 (-%20/+%25); Q3-Q4 2023; US$ (C$ için kur 0.74)",
    notlar=(
        "Process plant ilk yatırım doğrudan toplamı $204M (alan satırları yuvarlama nedeniyle $203M eder). Proje dolayları "
        "($146M), sahip maliyeti ($25M) ve contingency ($105M) proje düzeyinde, alanlara dağıtılmamış. Konsantre liçi, "
        "POX ile birlikte refrakter konsantre içindir; oksit/serbest altın konsantre liçine doğrudan uygulanmaz. Yardımcı "
        "alanı 2800'ün sürdürme yatırımı (oksijen tesisi kirası, $48M) kullanılmadı."
    ),
    seviyeler=(),
    proses="Au flotasyon + konsantre POX + siyanür liçi + Merrill-Crowe (konsantre ~315 t/gün)",
    isleme_opex_usd_t=26.85,        # Tablo 21-21, ömür boyu, US$/t işlenen cevher
    opex_kirilim={"İşçilik": 6.49, "Bakım": 1.80, "Reaktif ve sarf": 4.51, "Güç": 13.23, "Atık sahası": 0.82},
)

# ------------------------------------------------------------------
# Lemhi Au - FS (Ausenco, Freeman Gold, 13 Ağustos 2026), Tablo 21-4 (US$M, ilk yatırım, Faz 1)
# Tüm cevher siyanür liçi (CIL) + elüsyon; flotasyon yok. Faz 1: 6,849 t/gün (2.5 Mt/yıl), Faz 2: 8,219 t/gün.
# Kırma devresi baştan Faz 2 kapasitesine göre boyutlandırılmış. Baz tarihi Q1 2026, AACE Class 3 (-%15/+%15).
# ------------------------------------------------------------------
_LE_KAYNAK = "Lemhi FS (Ausenco, 13 Ağustos 2026), Tablo 21-4 (WBS 3000, ilk yatırım, US$M)"
_LE_TPD = 6_849.0
_LE_TPD_F2 = 8_219.0


def _le(kod, ad, musd, **kw):
    return CapexAlan(kod, ad, musd * 1e6, kaynak=_LE_KAYNAK, **kw)


LEMHI_DATA_POINT = CapexDataPoint(
    project="Lemhi Gold Project",
    capacity_tpd=_LE_TPD,
    base_year=2026,
    basslik_capex_usd=329_700_000,          # Tablo 21-1: ilk yatırım toplamı
    kapsam=CapexKapsam(tsf_dahil=False, dis_altyapi_dahil=False, gider_payi_dahil=False, dolayli_dahil=False,
                       sahip_maliyeti_dahil=False),
    alanlar=[
        _le("kirma", "Crushing (WBS 3100)", 12.1, kapasite_tpd=_LE_TPD_F2,
            not_="Kırma devresi Faz 2 işleme hızına (8,219 t/gün) göre boyutlandırılmış (rapor, Bölüm 17.3.2.1)."),
        _le("ogutme", "Grinding (WBS 3200)", 27.2,
            not_="Faz 1 ilk yatırımı; üçüncül değirmen (6.0 M$) genişleme yatırımında, buraya dahil değil."),
        _le("cil", "Leach and Adsorption (WBS 3300)", 16.5),
        _le("cil", "Detox (WBS 3500)", 10.4),
        _le("adr", "Elution/Goldroom (WBS 3400)", 14.3),
        _le("atik_koyulastirma", "Tailings Dewatering (WBS 3600)", 30.8),
        _le("reaktif", "Reagents (WBS 3700)", 7.6),
        _le("yardimci", "Services (WBS 3800)", 8.9),
    ],
    source="Lemhi Gold Project NI 43-101 Teknik Rapor ve Fizibilite Çalışması (Ausenco, Freeman Gold için), efektif tarih "
           "29 Haziran 2026, yayın 13 Ağustos 2026; AACE Class 3 (-%15/+%15); Q1 2026 USD",
    notlar=(
        "Process plant ilk yatırım doğrudan toplamı $127.8M (Faz 1). Proje dolayları ($40.1M), sahip maliyeti ($8.03M) ve "
        "contingency/kapanış ($31.8M) proje düzeyinde, alanlara dağıtılmamış. Diğer alanların Faz 1 mi Faz 2 mi "
        "kapasitesine göre boyutlandırıldığı raporda ayrıca belirtilmemiş; nokta kapasitesi Faz 1 (6,849 t/gün) alındı. İşleme "
        "işletme gideri: raporun metni ömür boyu ortalamayı $14.49/t veriyor; Tablo 21-16 toplamları (Faz 1 $17.57/t, Faz 2 "
        "$14.12/t) metindeki Faz 1/Faz 2 değerleriyle ($18.24/$14.85) birebir tutmuyor."
    ),
    seviyeler=(),
    proses="Au tüm cevher siyanür liçi (CIL) - flotasyon yok",
    isleme_opex_usd_t=14.49,        # Bölüm 21 metni: ömür boyu ortalama
)

# ------------------------------------------------------------------
# Kingking Cu-Au - PFS (M3 Engineering, St. Augustine, 29 Temmuz 2025). Yalnızca alan bazlı OPEX (Tablo 21-9, 21-10, 21-11).
# CAPEX raporda alan bazında verilmemiş (süreç tesisi + genel altyapı tek rakam: $1,638.25M, EPCM/nakliye/gümrük dahil).
# 60,000 t/gün değirmen (flotasyon + gravite + flotasyon atığı karıştırmalı asit liçi + SX-EW) ve 40,000 t/gün yığın liçi
# (+ SX-EW). Fiyatlar Q4 2024 USD. İşletme gideri elemanları: işçilik, reaktif, güç, aşınma malzemesi, bakım, sarf.
# ------------------------------------------------------------------
_KK_KAYNAK = "Kingking PFS (M3, Temmuz 2025), "
_KK_NOT_DEGIRMEN = "$/t değirmen cevheri (848.9 Mt, 38 yıl)."
KINGKING_DATA_POINT = CapexDataPoint(
    project="Kingking Copper-Gold Project",
    capacity_tpd=60_000.0,
    base_year=2024,
    basslik_capex_usd=1_638_250_000,        # Tablo 21-1: süreç tesisi + genel altyapı (EPCM, nakliye, gümrük dahil); alan kırılımı yok
    kapsam=CapexKapsam(),
    alanlar=[],
    source="Kingking Copper-Gold Project NI 43-101 Teknik Rapor, Ön Fizibilite Çalışması (M3 Engineering, St. Augustine Gold "
           "and Copper için), efektif tarih 10 Temmuz 2025; Q4 2024 USD",
    notlar=(
        "Yalnızca alan bazlı OPEX referansı: raporda alan bazlı CAPEX yok. İşletme gideri alanları $/t o alanın beslemesi "
        "(değirmen cevheri, yığın liçi cevheri veya liç edilen cevher); işçilik, reaktif, güç, aşınma malzemesi, bakım ve "
        "sarf dahil ('tam' kapsam). Atık istifleme maliyeti ($3.56/t, 1-20. yıl) dahil değildir."
    ),
    seviyeler=(),
    proses="Cu-Au flotasyon + gravite + atık karıştırmalı asit liçi (SX-EW) + yığın liçi (SX-EW)",
    isleme_opex_usd_t=5.61,         # Tablo 21-10: değirmen (konsantratör) toplamı, atık istifleme hariç
    opex_kirilim={"Kırma ve konveyör": 0.38, "Öğütme ve sınıflandırma": 3.48, "Flotasyon ve yeniden öğütme": 0.63,
                  "Konsantre koyulaştırma, filtrasyon": 0.20, "Atık filtrasyonu": 0.72, "Gravite": 0.01,
                  "Rafineri": 0.01, "Yardımcı hizmetler": 0.18},
    opex_alanlari=[
        OpexAlan("kirma", "Crushing & Conveying", 0.38, "tam", kaynak=_KK_KAYNAK + "Tablo 21-10", not_=_KK_NOT_DEGIRMEN),
        OpexAlan("ogutme", "Grinding & Classification", 3.48, "tam", kaynak=_KK_KAYNAK + "Tablo 21-10", not_=_KK_NOT_DEGIRMEN),
        OpexAlan("flotasyon", "Flotation & Regrind", 0.63, "tam", kaynak=_KK_KAYNAK + "Tablo 21-10", not_=_KK_NOT_DEGIRMEN),
        OpexAlan("konsantre_koyulastirma", "Concentrate Thickening, Filtration & Dewatering", 0.20, "tam",
                 kaynak=_KK_KAYNAK + "Tablo 21-10", not_=_KK_NOT_DEGIRMEN + " Koyulaştırma + filtrasyon + susuzlaştırma tek satır."),
        OpexAlan("atik_koyulastirma", "Tailing Filtration", 0.72, "tam", kaynak=_KK_KAYNAK + "Tablo 21-10",
                 not_=_KK_NOT_DEGIRMEN + " Atık istifleme maliyeti hariç."),
        OpexAlan("gravite", "Gravity Gold Circuit", 0.01, "tam", kaynak=_KK_KAYNAK + "Tablo 21-10",
                 not_=_KK_NOT_DEGIRMEN + " Rapor 2 ondalığa yuvarlamış (toplam $9.09M)."),
        OpexAlan("adr", "Gold Refinery", 0.01, "tam", kaynak=_KK_KAYNAK + "Tablo 21-10",
                 not_=_KK_NOT_DEGIRMEN + " Yalnızca rafineri; rapor 2 ondalığa yuvarlamış (toplam $10.25M)."),
        OpexAlan("heap_leach", "Heap Leach & Crushing & Conveying", 2.93, "tam", kaynak=_KK_KAYNAK + "Tablo 21-9",
                 not_="$/t yığın liçi cevheri (110.5 Mt, 25 yıl). Kırma ve konveyör bu satıra dahil."),
        OpexAlan("sx_ew", "Solvent Extraction + Electrowinning (yığın liçi)", 0.49 + 1.91, "tam", senaryo="yığın liçi",
                 kaynak=_KK_KAYNAK + "Tablo 21-9",
                 not_="SX $0.49 + EW $1.91 /t yığın liçi cevheri. Tank farm ($0.15) ve yardımcı hizmetler ($0.14) hariç."),
        OpexAlan("karistirmali_lic", "Agitated Tailing Leach", 2.41, "tam", kaynak=_KK_KAYNAK + "Tablo 21-11",
                 not_="$/t liç edilen değirmen cevheri. Flotasyon atığının karıştırmalı asit liçi (50 kg/t asit, 50 °C testleri)."),
        OpexAlan("sx_ew", "SX-EW Tailing Leach", 0.27, "tam", senaryo="atık liçi", kaynak=_KK_KAYNAK + "Tablo 21-11",
                 not_="$/t liç edilen değirmen cevheri (atık liçi PLS'si için SX-EW)."),
    ],
    yalniz_opex=True,
)

# ------------------------------------------------------------------
# Segilola (Thor Explorations, FS, RPA, 18 Mart 2019) ve Douta (Thor Explorations, PFS, AMC, Mart 2026)
# Her ikisi de gravite + CIL altın tesisi (Norinco EPC). Raporlarda proses alanı bazlı CAPEX dökümü yok: tesis
# bölüm toplamı tek kalem. Bu nedenle yalnızca işleme OPEX toplamı referansı olarak girildi; CAPEX hesaba katılmaz.
# ------------------------------------------------------------------
SEGILOLA_DATA_POINT = CapexDataPoint(
    project="Segilola Gold Project",
    capacity_tpd=round(650_000 / 365, 1),     # tesis anma kapasitesi 650,000 t/yıl (revize tasarım), 365 güne bölündü
    base_year=2019,                            # rapor tarihi; maliyet baz tarihi raporda ayrıca belirtilmemiş
    basslik_capex_usd=87_600_000,              # Tablo 21-1 toplam geliştirme harcaması (madencilik, altyapı, sahip maliyeti dahil)
    kapsam=CapexKapsam(),
    alanlar=[],
    source="Segilola Gold Project NI 43-101 Teknik Rapor, Fizibilite Çalışması (RPA, Thor Explorations için), 18 Mart 2019; "
           "AACE Class 3 (+/-%10); USD",
    notlar=(
        "Yalnızca işleme OPEX toplamı referansı. Tesis gravite + CIL (kırma, SAG + bilyalı değirmen, gravite, CIL, "
        "elüsyon); flotasyon yok. Tablo 21-1'deki 'Process' kalemi $19.8M (anma kapasitesi 650,000 t/yıl) proses alanlarına "
        "ayrılmamış tek kalemdir ve Norinco EPC sözleşmesinin parçasıdır (altyapı $28.6M, dolaylı $13.0M, TMF $3.7M ve sahip "
        "maliyeti $11.0M ayrı), bu yüzden alan bazlı CAPEX verisi olarak kullanılmadı. OPEX: Tablo 21-3 (sarf ve aşınma "
        "malzemesi, bakım, işçilik, güç, laboratuvar); işçilikte keyfe bağlı yıllık prim ($0.83/t) dahil değil."
    ),
    seviyeler=(),
    proses="Au gravite + CIL (flotasyon yok)",
    isleme_opex_usd_t=18.58,
    opex_kirilim={"Reaktif ve sarf (aşınma malzemesi dahil)": 6.47, "Bakım": 1.39, "İşçilik": 5.26, "Güç": 4.85, "Laboratuvar": 0.61},
    yalniz_opex=True,
)

DOUTA_DATA_POINT = CapexDataPoint(
    project="Douta Gold Project (Faz 1, oksit)",
    capacity_tpd=round(4_000_000 / 365, 1),   # Faz 1 tasarım kapasitesi 4 Mt/yıl, 365 güne bölündü
    base_year=2026,                            # rapor tarihi; maliyetler gerçek (reel) dolarla, enflasyon uygulanmamış
    basslik_capex_usd=253_500_000,             # Tablo 1.7 Faz 1 toplamı (madencilik, TSF, diğer ve sahip maliyeti dahil)
    kapsam=CapexKapsam(),
    alanlar=[],
    source="Thor Douta Gold Project NI 43-101 Teknik Rapor, Ön Fizibilite Çalışması (AMC Consultants, Thor Explorations için), "
           "Mart 2026; USD, enflasyon uygulanmamış",
    notlar=(
        "Yalnızca işleme OPEX toplamı referansı (Faz 1: oksit ve geçiş cevheri, gravite + CIL). Faz 1 process plant CAPEX "
        "$177.9M (Tablo 21.3) bölümlere göre (mekanik, inşaat, çelik, boru, E,C&I, genel giderler) verilmiş, proses alanlarına "
        "ayrılmamış, bu yüzden alan bazlı CAPEX verisi olarak kullanılmadı. Faz 2 (kavurma devresi + yeniden öğütme + küçük "
        "CIL, 2.4 Mt/yıl taze cevher) için $60.1M de alanlara ayrılmamış. OPEX: Tablo 1.10 / 21.8, $/t cevher; rapor "
        "tesis atık izleme ve yönetim maliyetini ($0.22/t) işleme maliyetine dahil edildiğini söylüyor, tablo değerine dahil "
        "olup olmadığı belirsiz. İşçilik, güç ve sarf kırılımı raporda yok."
    ),
    seviyeler=(),
    proses="Au gravite + CIL (Faz 1 oksit); Faz 2 kavurma + CIL ayrı",
    isleme_opex_usd_t=16.14,
    opex_kirilim={"Oksit ve geçiş cevheri (Faz 1)": 16.14, "Taze cevher, Baraka (Faz 2)": 17.14,
                  "Taze cevher, Makosa, kavurma dahil (Faz 2)": 33.35},
    yalniz_opex=True,
)

# ------------------------------------------------------------------
# Blackwater Au-Ag - Updated FS (Ausenco, Artemis Gold, etkin tarih 10 Eylül 2021, yayın 25 Ekim 2021), Tablo 21-6
# (WBS 2100-5700, Faz 1 ilk yatırım, C$M, taban Q2-2021, kur 1 C$ = 0.79 US$, Tablo 21-4).
# Gravite + yoğun siyanür liçi + CIL; flotasyon yok. Faz 1: 16,438 t/gün (6.0 Mt/yıl), Faz 2: 33,000 t/gün, Faz 3: 55,000 t/gün.
# Faz 1 kırma devresi, Faz 2 kapasitesine minimum değişiklikle genişleyecek şekilde tasarlanmış (gyratory ön kırıcı).
# ------------------------------------------------------------------
_BW_KAYNAK = "Blackwater FS (Ausenco, 10 Eylül 2021), Tablo 21-6 (WBS, Faz 1 ilk yatırım, C$M x 0.79)"
_BW_KUR = 0.79
_BW_TPD = 16_438.0


def _bw(kod, ad, cad_m, **kw):
    return CapexAlan(kod, ad, cad_m * _BW_KUR * 1e6, kaynak=_BW_KAYNAK, **kw)


BLACKWATER_DATA_POINT = CapexDataPoint(
    project="Blackwater Gold Project (Faz 1)",
    capacity_tpd=_BW_TPD,
    base_year=2021,
    basslik_capex_usd=round(645.2 * _BW_KUR * 1e6),     # Tablo 21-1: Faz 1 ilk yatırım toplamı (madencilik, altyapı, sahip dahil), C$645.2M
    kapsam=CapexKapsam(tsf_dahil=False, dis_altyapi_dahil=False, gider_payi_dahil=False, dolayli_dahil=False,
                       sahip_maliyeti_dahil=False),
    alanlar=[
        _bw("kirma", "Crushing (WBS 3100)", 48.8,
            not_="Faz 1 kırma devresi Faz 2 kapasitesine minimum değişiklikle genişleyecek şekilde tasarlanmış; kırma "
                 "alanının tasarım kapasitesi raporda ayrıca verilmiyor, nokta kapasitesi (Faz 1) kullanıldı."),
        _bw("stok", "Crushed ore stockpile and reclaim (WBS 3200)", 6.8),
        _bw("ogutme", "Grinding / gravity concentration / intensive leaching (WBS 4200)", 38.5,
            not_="Raporda tek satır: öğütme, gravite ve yoğun liç birlikte; ayrıştırılamadı."),
        _bw("cil", "Gold leaching (WBS 4300)", 13.0),
        _bw("cil", "Carbon-in-leach / adsorption (WBS 4400)", 17.8),
        _bw("adr", "Carbon reactivation and regeneration (WBS 4500)", 15.6),
        _bw("adr", "Electrowinning and smelting (WBS 4600)", 1.6),
        _bw("reaktif", "Reagent make-up area (WBS 4800)", 8.3),
        _bw("yardimci", "Cyanide destruction and tailings (WBS 4700)", 9.6,
            not_="Siyanür yıkımı ve tesis içi atık borulaması tek satır; detoks tek başına ayrılamadığı için yardımcıya alındı."),
        _bw("yardimci", "Process plant buildings (WBS 4100)", 22.7),
        _bw("yardimci", "Process plant utilities (WBS 4900)", 14.2),
        _bw("yardimci", "Oxygen plant (WBS 5100)", 0.3),
    ],
    source="Blackwater Gold Project NI 43-101 Teknik Rapor, Güncellenmiş Fizibilite Çalışması (Ausenco, Artemis Gold için), "
           "etkin tarih 10 Eylül 2021, SEDAR+ yayın 25 Ekim 2021; taban Q2-2021, -%10/+%15, escalation yok; C$ (1 C$ = 0.79 US$)",
    notlar=(
        "Tablo 21-6 doğrudan alt toplamı C$250.8M; bunun C$197.2M'si (x 0.79 = US$155.8M) alanlara alındı. Alanlara DAHİL DEĞİL "
        "(C$53.6M): toprak işleri (C$9.3M), tesis içi yollar (C$0.3M), TSF (C$5.4M), tesis yan binaları, truck shop, güç ve su "
        "sistemleri, atık yönetimi, IT ve kalıcı kamp. Proje dolayları (C$115.7M: EP, CM, spares, contingency vb.) alanlara "
        "dağıtılmamış. İşleme OPEX: Tablo 21-11/21-12, Faz 1 C$9.47/t, US$'a 0.79 ile çevrildi; "
        "rapor yıllık C$62.5M (6.6 Mt'a denk) yazıyor, tasarım hızı 6.0 Mt/yıl, bu fark raporda açıklanmamış. "
        "Faz 2 ve 3 genişleme yatırımları kullanılmadı."
    ),
    seviyeler=(),
    proses="Au gravite + yoğun liç + CIL (flotasyon yok)",
    isleme_opex_usd_t=round(9.47 * _BW_KUR, 2),
    opex_kirilim={k: round(v * _BW_KUR, 2) for k, v in
                  {"Reaktif ve sarf": 5.54, "Bakım": 0.32, "Güç": 1.69, "İşçilik": 1.49, "Proses G&A giderleri": 0.43}.items()},
)

# ------------------------------------------------------------------
# Los Azules Cu - FS (AGP / McEwen Copper, etkin tarih 3 Eylül 2025, rapor 7 Kasım 2025), Tablo 21.1 (US$M, Q3 2025, AACE Class 3 +/-%15).
# Cu yığın liçi + SX-EW + sülfürik asit tesisi; flotasyon yok. İlk yatırım kırma/liç kapasitesi 25 Mt/yıl; 50 Mt/yıl'a genişleme
# Yıl 3'te SÜRDÜRME yatırımı olarak ayrı (Tablo 21.3), bu yüzden ilk yatırım 25 Mt/yıl'a aittir.
# Asit tesisi (US$114.3M) kapalı alan olduğu için hiçbir alana alınmadı. 'Ore Storage & Handling' kırma, konveyör, aglomerasyon
# ve istifi ayrıştırılmadan içeriyor: yardımcıya alındı.
# ------------------------------------------------------------------
_LA_KAYNAK = "Los Azules FS (AGP, 3 Eylül 2025), Tablo 21.1 (doğrudan tesis içi, ilk yatırım, US$M)"
_LA_TPD = round(25_000_000 / 365, 1)


def _la(kod, ad, musd, **kw):
    return CapexAlan(kod, ad, musd * 1e6, kaynak=_LA_KAYNAK, **kw)


LOS_AZULES_DATA_POINT = CapexDataPoint(
    project="Los Azules Copper Project (ilk yatırım, 25 Mt/yıl)",
    capacity_tpd=_LA_TPD,
    base_year=2025,
    basslik_capex_usd=3_167_900_000,        # Tablo 21.1: toplam ilk yatırım (madencilik, altyapı, dolaylar, sahip, contingency dahil)
    kapsam=CapexKapsam(tsf_dahil=False, dis_altyapi_dahil=False, gider_payi_dahil=False, dolayli_dahil=False,
                       sahip_maliyeti_dahil=False),
    alanlar=[
        _la("heap_leach", "Heap Leach", 331.6,
            not_="Liç sahası, istifleme ve çözelti sistemi; raporda alt kırılım yok."),
        _la("sx_ew", "SX-EW", 188.5),
        _la("yardimci", "Ore Storage & Handling", 283.3,
            not_="Kırma, konveyör, aglomerasyon ve stok birlikte olabilir; raporda alt kırılım yok, kırma alanına alınmadı."),
    ],
    source="Los Azules Copper Project 2025 Feasibility Study NI 43-101 Teknik Rapor (AGP, McEwen Copper için), etkin tarih "
           "3 Eylül 2025, rapor 7 Kasım 2025; AACE Class 3 (+/-%15); 2025 Q3 US$, escalation yok",
    notlar=(
        "Doğrudan tesis içi alan toplamı: yığın liçi + SX-EW + cevher depolama ve taşıma = US$803.4M. Alanlara DAHİL "
        "DEĞİL: sülfürik asit tesisi (US$114.3M, kapalı alan), anciller tesisler (US$123.4M), saha geliştirme (US$101.6M), su temini, "
        "dış altyapı, madencilik (US$805.9M), proje dolayları (US$691.0M), tasarım payı ve contingency. Kapasite 25 Mt/yıl / 365. "
        "İşleme OPEX: Tablo 21.12 ömür boyu (LOM) değerleri; rapor toplamı US$3.83/t, ancak bunun US$0.88/t'u YPF güç altyapısı "
        "finansman geri ödemesi (proses işletme gideri değil) olduğu için hariç tutuldu: 3.83 - 0.88 = 2.95 US$/t. "
        "İşleme OPEX kırma, yığın liçi, SX-EW ve asit tesisini birlikte kapsıyor (alan bazlı kırılım yok); LOM ortalaması 25 ve "
        "50 Mt/yıl dönemlerini içerir."
    ),
    seviyeler=(),
    proses="Cu yığın liçi + SX-EW + asit tesisi - flotasyon yok",
    isleme_opex_usd_t=2.95,
    opex_kirilim={"İşçilik": 0.27, "Reaktif": 1.38, "Güç": 0.87, "Bakım": 0.36, "Sarf": 0.07},
)

# ------------------------------------------------------------------
# Gramalote Au - FS (B2Gold, NI 43-101 Teknik Rapor, etkin tarih 14 Temmuz 2025). Kırma + SAG/bilyalı + gravite + flotasyon + konsantre CIL.
# 6 Mt/yıl, flotasyon konsantre kütle verimi %5. Raporda proses alanı bazlı CAPEX dökümü yok: 'Processing' tek satır (US$313M).
# ------------------------------------------------------------------
GRAMALOTE_DATA_POINT = CapexDataPoint(
    project="Gramalote Gold Project",
    capacity_tpd=round(6_000_000 / 365, 1),
    base_year=2025,
    basslik_capex_usd=740_000_000,          # Tablo 21-1: ilk (non-sustaining, üretim öncesi) inşaat toplamı, US$740.1M
    kapsam=CapexKapsam(),
    alanlar=[],
    source="Gramalote Project, Colombia, NI 43-101 Teknik Rapor (B2Gold), etkin tarih 14 Temmuz 2025, rapor Ağustos 2025; US$",
    notlar=(
        "Yalnızca işleme OPEX toplamı referansı. Tesis gravite + flotasyon + konsantre siyanür liçi. Tablo 21-1'de 'Processing' "
        "ilk yatırımı US$313M tek satırdır; proses alanlarına ayrılmamış, TSF ve çökeltme havuzlarının içerip içermediği belli "
        "değil, bu yüzden alan bazlı CAPEX verisi olarak kullanılmadı. OPEX: Tablo 21-3, US$8.16/t işlenen cevher (ömür boyu); "
        "rapor bu rakamın stok yeniden taşıma ve cevher nakliyesini içerdiğini söylüyor; işçilik, güç, sarf kırılımı raporda yok. "
        "Maliyet taban tarihi ve doğruluk sınıfı raporda net bulunamadı (inşaat 2027-2028 varsayılmış)."
    ),
    seviyeler=(),
    proses="Au gravite + flotasyon + konsantre CIL",
    isleme_opex_usd_t=8.16,
    yalniz_opex=True,
)

ALL_DATA_POINTS = [ALTAR_DATA_POINT, FURNAS_DATA_POINT, CERRO_BLANCO_DATA_POINT, ENCHI_DATA_POINT, CACTUS_DATA_POINT,
                   SANTA_FE_DATA_POINT, LA_MINA_DATA_POINT, SPRINGPOLE_DATA_POINT, TOCANTINZINHO_DATA_POINT,
                   COURAGEOUS_LAKE_DATA_POINT, LEMHI_DATA_POINT, KINGKING_DATA_POINT,
                   SEGILOLA_DATA_POINT, DOUTA_DATA_POINT,
                   BLACKWATER_DATA_POINT, LOS_AZULES_DATA_POINT, GRAMALOTE_DATA_POINT]


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
                                         "dolayli_var": True, "gider_payi_var": True, "rapor_adlari": [],
                                         "_kap": set()})
        d["_kap"].add(a.kapasite_tpd if a.kapasite_tpd else p.capacity_tpd)
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
    # Alan kapasitesi: tüm satırlar aynı kapasiteyi veriyorsa o; karışıksa noktanın cevher kapasitesi
    for d in out.values():
        kap = d.pop("_kap")
        d["kapasite_tpd"] = next(iter(kap)) if len(kap) == 1 else p.capacity_tpd
    # Birleşik kırma+öğütme: ayrı satır veren raporlardan türetilir (kırma, stok, öğütme)
    if turetilmis and "kirma_ogutme" not in out:
        parcalar = [out[k] for k in ("kirma", "stok", "ogutme") if k in out]
        if parcalar and "kirma" in out and "ogutme" in out:
            out["kirma_ogutme"] = {
                "dogrudan": sum(x["dogrudan"] for x in parcalar), "dolayli": 0.0, "gider_payi": 0.0,
                "dolayli_var": False, "gider_payi_var": False,
                "rapor_adlari": ["türetilmiş: kırma + stok + öğütme"],
                "kapasite_tpd": p.capacity_tpd,
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
        kap = d.get("kapasite_tpd") or p.capacity_tpd
        olcekli = d["dogrudan"] * (target_capacity_tpd / kap) ** exponent * duzeltme_carpani
        refs.append({
            "project": p.project, "capacity_tpd": kap, "plant_capacity_tpd": p.capacity_tpd, "base_year": p.base_year,
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
        if not (p.kapsam_dogrulandi or p.alan_dogrulandi or p.yalniz_opex):
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
    assert {r["project"] for r in ko["referanslar"]} == {"Altar Project", "Furnas Project", "Cerro Blanco Project", "Enchi Gold Project",
                                                          "Springpole Gold Project", "Tocantinzinho Gold Project",
                                                          "Courageous Lake Project", "Lemhi Gold Project",
                                                          "Blackwater Gold Project (Faz 1)"}
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
    assert not estimate_area_opex("dms")["veri_var"] and not estimate_area_opex("manyetik")["veri_var"]
    assert not (set(KAPALI_ALAN_TURLERI) & set(ALAN_TURLERI)) and set(KAPALI_ALAN_TURLERI) == {"asit_tesisi", "dms", "manyetik"}

    # --- Springpole / Tocantinzinho / Courageous Lake / Lemhi / Kingking (yeni raporlar) ---
    for p, rapor in ((SPRINGPOLE_DATA_POINT, 296.7e6), (TOCANTINZINHO_DATA_POINT, 86.036e6),
                     (COURAGEOUS_LAKE_DATA_POINT, 204e6), (LEMHI_DATA_POINT, 127.8e6)):
        t = sum(a.dogrudan_usd for a in p.alanlar)
        print(f"{p.project}: alan toplamı {t:,.0f} (rapor ~{rapor:,.0f}); durum: {p.durum}")
        assert p.alan_dogrulandi and not p.kapsam_dogrulandi and p.capex_seviye("A") is None
        assert abs(t - rapor) <= max(0.003 * rapor, 1.1e6 if p is COURAGEOUS_LAKE_DATA_POINT else 0.2e6), (p.project, t)
    # Springpole: raporun kendi kuru (0.75) ve alan başına kapasite
    sp = alan_dokumu(SPRINGPOLE_DATA_POINT)
    assert abs(sp["cil_kons"]["dogrudan"] - 60.3e6 * 0.75) < 1 and sp["cil_kons"]["kapasite_tpd"] == 4500.0
    assert sp["cil"]["kapasite_tpd"] == 25500.0 and sp["flotasyon"]["kapasite_tpd"] == 30000.0
    assert abs(sp["adr"]["dogrudan"] - (15.0 + 7.2) * 0.75e6) < 1
    # Tocantinzinho: konsantre CIL ~535 t/gün; satır toplamları raporun grup toplamlarıyla tutuyor
    tz = alan_dokumu(TOCANTINZINHO_DATA_POINT)
    assert abs(tz["cil_kons"]["kapasite_tpd"] - 535.1) < 0.2
    assert abs(tz["kirma"]["dogrudan"] + tz["stok"]["dogrudan"] + tz["ogutme"]["dogrudan"] - 39_407e3) < 1
    assert abs(tz["gravite"]["dogrudan"] - 2_483e3) < 1 and abs(tz["adr"]["dogrudan"] - 6_330e3) < 1
    assert abs(tz["on_koyulastirma"]["dogrudan"] + tz["cil_kons"]["dogrudan"] - (8_648e3 - 0)) < 2e3 + 1
    # Courageous Lake: POX/konsantre alanları 315 t/gün, diğerleri 7,500
    cl = alan_dokumu(COURAGEOUS_LAKE_DATA_POINT)
    assert cl["pox"]["kapasite_tpd"] == 315.0 and cl["cil_kons"]["kapasite_tpd"] == 315.0 and cl["ogutme"]["kapasite_tpd"] == 7500.0
    # Lemhi: kırma Faz 2 kapasitesine göre
    le = alan_dokumu(LEMHI_DATA_POINT)
    assert le["kirma"]["kapasite_tpd"] == 8219.0 and le["cil"]["kapasite_tpd"] == 6849.0
    assert abs(le["cil"]["dogrudan"] - 26.9e6) < 1
    # Alan kapasitesi ölçeklemeye girer: konsantre liçi 2,000 t/gün hedef
    ck = estimate_area_capex("cil_kons", 2000.0, exponent=0.6)
    assert {r["project"] for r in ck["referanslar"]} == {"Springpole Gold Project", "Tocantinzinho Gold Project", "Courageous Lake Project"}
    r_sp = next(r for r in ck["referanslar"] if r["project"].startswith("Springpole"))
    assert r_sp["capacity_tpd"] == 4500.0 and r_sp["plant_capacity_tpd"] == 30000.0
    assert abs(r_sp["scaled_usd"] - 60.3e6 * 0.75 * (2000 / 4500) ** 0.6) < 1
    r_tz = next(r for r in ck["referanslar"] if r["project"].startswith("Tocantinzinho"))
    assert abs(r_tz["capacity_tpd"] - 535.1) < 0.2
    print("  cil_kons @2,000 t/gün:", [(r['project'].replace(' Project', ''), r['capacity_tpd'], round(r['scaled_usd'] / 1e6, 1)) for r in ck["referanslar"]])
    # POX yalnızca Courageous Lake
    assert [r["project"] for r in estimate_area_capex("pox", 300.0)["referanslar"]] == ["Courageous Lake Project"]
    # Gravite CAPEX artık Tocantinzinho'dan
    assert [r["project"] for r in estimate_area_capex("gravite", 10000.0)["referanslar"]] == ["Tocantinzinho Gold Project"]
    # Kingking: yalnızca OPEX referansı; CAPEX'e ve nokta listelerine girmez
    kk = KINGKING_DATA_POINT
    assert kk.yalniz_opex and not kk.alan_dogrulandi and not kk.kapsam_dogrulandi and "OPEX" in kk.durum
    assert all(estimate_area_capex(k, 60000.0)["referanslar"] == [] or
               all(r["project"] != kk.project for r in estimate_area_capex(k, 60000.0)["referanslar"]) for k in ALAN_TURLERI)
    assert kk not in dogrulanmis_noktalar(seviye="A") and kk not in dogrulanmis_noktalar(seviye="C")
    ho = estimate_area_opex("heap_leach")
    assert any(r["project"].startswith("Kingking") and abs(r["usd_t"] - 2.93) < 1e-9 for r in ho["referanslar"])
    so = estimate_area_opex("sx_ew")
    assert {r["senaryo"] for r in so["referanslar"]} == {"yığın liçi", "atık liçi"} and all(r["kapsam"] == "tam" for r in so["referanslar"])
    assert abs(next(r["usd_t"] for r in so["referanslar"] if r["senaryo"] == "yığın liçi") - 2.40) < 1e-9
    assert estimate_area_opex("karistirmali_lic")["veri_var"] and estimate_area_opex("gravite")["veri_var"]
    toplam_kk = sum(kk.opex_kirilim.values())
    assert abs(toplam_kk - 5.61) < 0.015, toplam_kk
    # Segilola ve Douta: yalnızca işleme OPEX toplamı; CAPEX ve alan OPEX'ine girmez
    for tp in (SEGILOLA_DATA_POINT, DOUTA_DATA_POINT):
        assert tp.yalniz_opex and not tp.alanlar and not tp.opex_alanlari and "işleme OPEX" in tp.durum
        assert tp not in dogrulanmis_noktalar(seviye="A") and tp not in dogrulanmis_noktalar(seviye="C")
        assert all(all(r["project"] != tp.project for r in estimate_area_capex(k, tp.capacity_tpd)["referanslar"])
                   for k in ALAN_TURLERI)
    assert abs(sum(SEGILOLA_DATA_POINT.opex_kirilim.values()) - 18.58) < 1e-9
    assert abs(SEGILOLA_DATA_POINT.capacity_tpd - 1780.8) < 0.1 and abs(DOUTA_DATA_POINT.capacity_tpd - 10958.9) < 0.1
    # Uygulamada gösterilen başlık değil: yalniz_opex işaretli
    print("\nYeni referans testleri geçti.")
    # --- Blackwater / Los Azules / Gramalote (v5) ---
    bw = BLACKWATER_DATA_POINT
    bw_t = sum(a.dogrudan_usd for a in bw.alanlar)
    print(f"Blackwater alan toplamı: {bw_t:,.0f} (rapor 197.2 C$M x 0.79); durum: {bw.durum}")
    assert abs(bw_t - 197.2e6 * 0.79) < 0.1e6 and bw.alan_dogrulandi and not bw.kapsam_dogrulandi
    assert abs(bw.isleme_opex_usd_t - 7.48) < 0.01 and abs(sum(bw.opex_kirilim.values()) - bw.isleme_opex_usd_t) < 0.02
    la = LOS_AZULES_DATA_POINT
    la_t = sum(a.dogrudan_usd for a in la.alanlar)
    print(f"Los Azules alan toplamı: {la_t:,.0f} (rapor 803.4 M$, asit tesisi hariç); durum: {la.durum}")
    assert abs(la_t - 803.4e6) < 0.01e6 and la.alan_dogrulandi and abs(la.capacity_tpd - 68493.2) < 0.1
    assert abs(sum(la.opex_kirilim.values()) - la.isleme_opex_usd_t) < 0.005
    assert not any(a.alan_kodu in KAPALI_ALAN_TURLERI for p in ALL_DATA_POINTS for a in p.alanlar)
    gr = GRAMALOTE_DATA_POINT
    assert gr.yalniz_opex and not gr.alanlar and gr not in dogrulanmis_noktalar() and abs(gr.capacity_tpd - 16438.4) < 0.1
    print("Blackwater, Los Azules, Gramalote: testler geçti")
