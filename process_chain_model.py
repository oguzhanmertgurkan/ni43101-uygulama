"""
Kombine akış modeli (kütle ve metal dengesi + aşama bazlı CAPEX alanları)
=========================================================================
Flotasyon + konsantre liçi, gravite + CIL gibi birden çok birim işlemden oluşan akışlar için.

Kapsam
------
- Tek metal izlenir (ör. Au g/t ya da Cu %). Çoklu metal (Cu-Au birlikte) bu sürümde yok.
- Her aşama bir "besleme" akımı alır: cevher beslemesi ya da önceki bir aşamanın çıkış akımı.
- Ayırma aşamalarında (flotasyon, gravite, DMS, manyetik) kullanıcı iki sayı girer:
  konsantreye giden AĞIRLIK verimi ve konsantreye giden METAL verimi. Tenörler bunlardan hesaplanır:
      konsantre tenörü = besleme tenörü * metal verimi / ağırlık verimi
      atık tenörü      = besleme tenörü * (1 - metal verimi) / (1 - ağırlık verimi)
- Liç aşamasında kullanıcı metal ekstraksiyonunu (%) girer. Çözünen metal ürün sayılır; katı artığın
  kütlesi besleme kütlesine eşit alınır (çözünen kütle ihmal edilir), artık tenörü
  besleme tenörü * (1 - ekstraksiyon) olur.
- Kırma ve öğütme aşamaları kütle ve metal bakımından geçiş aşamasıdır (verim %100); yalnızca CAPEX
  alanı kapasitesini belirlemek için akışta yer alır.
- Hiçbir aşamaya beslenmeyen konsantre akımı ürün (satılan konsantre) sayılır. Hiçbir aşamaya
  beslenmeyen atık akımındaki metal kayıptır.

Bu dosyada tahmini bir veri yoktur: verimler ve tenörler kullanıcı girdisidir.
"""

from dataclasses import dataclass
from typing import List, Optional

from capex_scaling_model import ALAN_TURLERI, estimate_area_capex

CEVHER = "cevher"

# Aşama türleri: (etiket, ayırma mı, liç mi)
ASAMA_TURLERI = {
    "kirma": "Kırma",
    "ogutme": "Öğütme",
    "flotasyon": "Flotasyon",
    "gravite": "Gravite ayırma",
    "dms": "Ağır ortam ayırma (DMS)",
    "manyetik": "Manyetik / elektrostatik ayırma",
    "lic_cil": "Siyanür liçi (CIL/CIP)",
    "lic_yigin_au": "Yığın liçi (Au, siyanür + ADR)",
    "lic_yigin_cu": "Yığın liçi (Cu, asit + SX-EW)",
}
AYIRMA_TURLERI = ("flotasyon", "gravite", "dms", "manyetik")
LIC_TURLERI = ("lic_cil", "lic_yigin_au", "lic_yigin_cu")
GECIS_TURLERI = ("kirma", "ogutme")

# Her aşama türünde seçilebilecek CAPEX alanları (ALAN_TURLERI anahtarları)
TUR_ALANLARI = {
    "kirma": ["kirma", "stok"],
    "ogutme": ["ogutme", "yeniden_ogutme"],
    "flotasyon": ["flotasyon", "konsantre_koyulastirma", "konsantre_filtrasyon", "atik_koyulastirma", "reaktif"],
    "gravite": ["gravite"],
    "dms": ["dms"],
    "manyetik": ["manyetik"],
    "lic_cil": ["on_koyulastirma", "cil", "adr", "reaktif"],
    "lic_yigin_au": ["heap_leach", "karbon_adsorpsiyon", "adr", "reaktif"],
    "lic_yigin_cu": ["heap_leach", "sx_ew", "asit_tesisi", "reaktif"],
}

# Alanın hangi akım miktarına göre ölçeklendiği
ALAN_TABANI = {
    "konsantre_koyulastirma": "konsantre",
    "konsantre_filtrasyon": "konsantre",
    "atik_koyulastirma": "atik",
}

# Referans kapasitesinden bu orandan fazla sapma "ekstrapolasyon" sayılır
EKSTRAPOLASYON_ARALIGI = (0.25, 4.0)


@dataclass
class Asama:
    uid: str                       # benzersiz kısa kod, akım adlarında kullanılır
    ad: str                        # kullanıcıya gösterilen ad
    tur: str                       # ASAMA_TURLERI anahtarı
    besleme: str = CEVHER          # "cevher" veya "<uid>:kons" / "<uid>:atik" / "<uid>:cikis"
    agirlik_verimi_pct: float = 100.0   # yalnızca ayırma: konsantreye giden kütle yüzdesi
    metal_verimi_pct: float = 100.0     # ayırma: konsantreye giden metal; liç: metal ekstraksiyonu
    alanlar: Optional[list] = None      # seçilen CAPEX alanları; None = varsayılan


def akim_adlari(asama: Asama) -> list:
    """Bir aşamanın üretebileceği akım kimlikleri."""
    if asama.tur in AYIRMA_TURLERI:
        return [f"{asama.uid}:kons", f"{asama.uid}:atik"]
    if asama.tur in LIC_TURLERI:
        return [f"{asama.uid}:atik"]
    return [f"{asama.uid}:cikis"]


def akim_etiketi(akim: str, asamalar: List[Asama]) -> str:
    if akim == CEVHER:
        return "Cevher beslemesi"
    uid, _, cins = akim.partition(":")
    ad = next((a.ad for a in asamalar if a.uid == uid), uid)
    return f"{ad} → " + {"kons": "konsantre", "atik": "atık", "cikis": "çıkış"}.get(cins, cins)


def varsayilan_alanlar(asama: Asama, konsantre_tuketiliyor: bool) -> list:
    """Aşama türüne göre varsayılan CAPEX alanları."""
    if asama.tur == "flotasyon":
        alanlar = ["flotasyon", "atik_koyulastirma"]
        if not konsantre_tuketiliyor:
            alanlar += ["konsantre_koyulastirma", "konsantre_filtrasyon"]
        return alanlar
    if asama.tur == "lic_cil":
        return ["on_koyulastirma", "cil", "adr", "reaktif"]
    if asama.tur == "lic_yigin_au":
        return ["heap_leach", "karbon_adsorpsiyon", "adr", "reaktif"]
    if asama.tur == "lic_yigin_cu":
        return ["heap_leach", "sx_ew", "reaktif"]
    if asama.tur == "kirma":
        return ["kirma", "stok"]
    return list(TUR_ALANLARI.get(asama.tur, [])[:1])


def dogrula(cevher_tpd: float, tenor: float, tenor_birimi: str, asamalar: List[Asama]) -> list:
    """Hata listesi döndürür (boşsa akış hesaplanabilir)."""
    hatalar = []
    if cevher_tpd <= 0:
        hatalar.append("Cevher besleme miktarı pozitif olmalı.")
    if tenor <= 0:
        hatalar.append("Besleme tenörü pozitif olmalı.")
    if tenor_birimi == "%" and tenor >= 100:
        hatalar.append("Tenör % biriminde 100'den küçük olmalı.")
    if not asamalar:
        hatalar.append("En az bir aşama gerekli.")
    gorulen = {CEVHER}
    kullanilan = {}
    uidler = set()
    for a in asamalar:
        if a.uid in uidler:
            hatalar.append(f"Aşama kodu tekrarlanıyor: {a.uid}")
        uidler.add(a.uid)
        if a.tur not in ASAMA_TURLERI:
            hatalar.append(f"{a.ad}: bilinmeyen aşama türü ({a.tur}).")
            continue
        if a.besleme not in gorulen:
            hatalar.append(f"{a.ad}: besleme akımı ({a.besleme}) bu aşamadan önce tanımlı değil.")
        elif a.besleme in kullanilan:
            hatalar.append(f"{a.ad}: besleme akımı '{a.besleme}' zaten '{kullanilan[a.besleme]}' aşamasına gidiyor; "
                           "bir akım yalnızca bir aşamaya beslenebilir.")
        else:
            kullanilan[a.besleme] = a.ad
        if a.tur in AYIRMA_TURLERI:
            if not (0 < a.agirlik_verimi_pct < 100):
                hatalar.append(f"{a.ad}: ağırlık verimi 0 ile 100 arasında (sınırlar hariç) olmalı.")
            if not (0 <= a.metal_verimi_pct <= 100):
                hatalar.append(f"{a.ad}: metal verimi 0-100 arasında olmalı.")
        elif a.tur in LIC_TURLERI:
            if not (0 <= a.metal_verimi_pct <= 100):
                hatalar.append(f"{a.ad}: ekstraksiyon 0-100 arasında olmalı.")
        gorulen.update(akim_adlari(a))
    return hatalar


def akis_hesapla(cevher_tpd: float, tenor: float, tenor_birimi: str, asamalar: List[Asama]) -> dict:
    """
    Kütle ve metal dengesi. Dönüş:
      asamalar : aşama sırasıyla satırlar (besleme, konsantre, atık miktarı ve tenörleri, ürün metali)
      akimlar  : akım kimliği -> {tpd, tenor}
      toplam_verim_pct, urun_metal_pct, kayip_metal_pct
      uyarilar : liste
    """
    hatalar = dogrula(cevher_tpd, tenor, tenor_birimi, asamalar)
    if hatalar:
        raise ValueError(" | ".join(hatalar))
    akimlar = {CEVHER: {"tpd": cevher_tpd, "tenor": tenor}}
    toplam_metal = cevher_tpd * tenor
    uyarilar = []
    satirlar = []
    urun_metal = 0.0
    tuketilen = {a.besleme for a in asamalar}
    for a in asamalar:
        b = akimlar[a.besleme]
        metal_in = b["tpd"] * b["tenor"]
        satir = {"uid": a.uid, "ad": a.ad, "tur": a.tur, "besleme": a.besleme,
                 "besleme_tpd": b["tpd"], "besleme_tenor": b["tenor"],
                 "kons_tpd": None, "kons_tenor": None, "atik_tpd": None, "atik_tenor": None,
                 "urun_metal_pct": 0.0, "kons_metal_pct": None, "asama_verimi_pct": None}
        if a.tur in GECIS_TURLERI:
            akimlar[f"{a.uid}:cikis"] = dict(b)
        elif a.tur in AYIRMA_TURLERI:
            y = a.agirlik_verimi_pct / 100.0
            r = a.metal_verimi_pct / 100.0
            k_tpd, t_tpd = b["tpd"] * y, b["tpd"] * (1 - y)
            k_ten = b["tenor"] * r / y
            t_ten = b["tenor"] * (1 - r) / (1 - y)
            akimlar[f"{a.uid}:kons"] = {"tpd": k_tpd, "tenor": k_ten}
            akimlar[f"{a.uid}:atik"] = {"tpd": t_tpd, "tenor": t_ten}
            satir.update(kons_tpd=k_tpd, kons_tenor=k_ten, atik_tpd=t_tpd, atik_tenor=t_ten,
                         kons_metal_pct=metal_in * r / toplam_metal * 100.0, asama_verimi_pct=a.metal_verimi_pct)
            if r < y:
                uyarilar.append(f"{a.ad}: metal verimi ağırlık veriminden küçük; konsantre tenörü beslemeden düşük çıkıyor. "
                                "Değerleri kontrol et.")
            if tenor_birimi == "%" and k_ten > 100:
                uyarilar.append(f"{a.ad}: konsantre tenörü %100'ü aşıyor ({k_ten:,.1f}); ağırlık veya metal verimi tutarsız.")
            if f"{a.uid}:kons" not in tuketilen:
                pay = metal_in * r
                urun_metal += pay
                satir["urun_metal_pct"] = pay / toplam_metal * 100.0
        elif a.tur in LIC_TURLERI:
            x = a.metal_verimi_pct / 100.0
            akimlar[f"{a.uid}:atik"] = {"tpd": b["tpd"], "tenor": b["tenor"] * (1 - x)}
            satir.update(atik_tpd=b["tpd"], atik_tenor=b["tenor"] * (1 - x), asama_verimi_pct=a.metal_verimi_pct)
            pay = metal_in * x
            urun_metal += pay
            satir["urun_metal_pct"] = pay / toplam_metal * 100.0
        satirlar.append(satir)
    kayip = toplam_metal - urun_metal
    return {
        "asamalar": satirlar, "akimlar": akimlar,
        "toplam_verim_pct": urun_metal / toplam_metal * 100.0,
        "kayip_metal_pct": kayip / toplam_metal * 100.0,
        "uyarilar": uyarilar,
    }


def _taban_tpd(alan: str, satir: dict) -> tuple:
    taban = ALAN_TABANI.get(alan, "besleme")
    if taban == "konsantre" and satir["kons_tpd"] is not None:
        return satir["kons_tpd"], "konsantre"
    if taban == "atik" and satir["atik_tpd"] is not None:
        return satir["atik_tpd"], "atık"
    return satir["besleme_tpd"], "besleme"


def asama_capex(asamalar: List[Asama], sonuc: dict, exponent: float, duzeltme: float = 1.0) -> dict:
    """
    Her aşamanın seçili alanlarını, o aşamanın kendi kapasitesinde (besleme, konsantre ya da atık
    akımı) estimate_area_capex ile ölçekler. Döner: satırlar, alt/ust toplam, eksik alanlar, ekstrapolasyon uyarıları.
    """
    tuketilen = {a.besleme for a in asamalar}
    satirlar, eksik, ekstra = [], [], []
    alt = ust = 0.0
    for a, s in zip(asamalar, sonuc["asamalar"]):
        alanlar = a.alanlar if a.alanlar is not None else varsayilan_alanlar(a, f"{a.uid}:kons" in tuketilen)
        for kod in alanlar:
            tpd, taban = _taban_tpd(kod, s)
            e = estimate_area_capex(kod, tpd, exponent=exponent, duzeltme_carpani=duzeltme)
            etiket = ALAN_TURLERI.get(kod, kod)
            if not e["veri_var"]:
                eksik.append(f"{a.ad}: {etiket}")
                satirlar.append({"asama": a.ad, "alan": etiket, "kapasite_tpd": tpd, "taban": taban,
                                 "min_usd": None, "max_usd": None, "referanslar": "veri yok", "oran": ""})
                continue
            oranlar = [tpd / r["capacity_tpd"] for r in e["referanslar"]]
            lo, hi = min(oranlar), max(oranlar)
            if lo < EKSTRAPOLASYON_ARALIGI[0] or hi > EKSTRAPOLASYON_ARALIGI[1]:
                ekstra.append(f"{a.ad}: {etiket} ({tpd:,.0f} t/gün, referans kapasitesinin {lo:.2f}-{hi:.2f} katı)")
            alt += e["min_usd"]
            ust += e["max_usd"]
            satirlar.append({"asama": a.ad, "alan": etiket, "kapasite_tpd": tpd, "taban": taban,
                             "min_usd": e["min_usd"], "max_usd": e["max_usd"],
                             "referanslar": ", ".join(f"{r['project']} (${r['scaled_usd'] / 1e6:,.1f}M)" for r in e["referanslar"]),
                             "oran": f"{lo:.2f}-{hi:.2f}" if abs(hi - lo) > 0.005 else f"{lo:.2f}"})
    return {"satirlar": satirlar, "alt_usd": alt, "ust_usd": ust, "eksik": eksik, "ekstrapolasyon": ekstra}




# ------------------------------------------------------------------
# Hazır şablonlar: yalnızca akış yapısı. Verim ve tenör değerleri YER TUTUCUDUR, veri değildir.
# ------------------------------------------------------------------
def _a(uid, ad, tur, besleme=CEVHER, agirlik=100.0, metal=100.0):
    return Asama(uid=uid, ad=ad, tur=tur, besleme=besleme, agirlik_verimi_pct=agirlik, metal_verimi_pct=metal)


SABLONLAR = {
    "Flotasyon + konsantre liçi": lambda: [
        _a("k", "Kırma", "kirma"),
        _a("o", "Öğütme", "ogutme", "k:cikis"),
        _a("f", "Flotasyon", "flotasyon", "o:cikis", 10.0, 85.0),
        _a("l", "Konsantre liçi (CIL)", "lic_cil", "f:kons", 100.0, 90.0),
    ],
    "Flotasyon atığı liçi (flotasyon + atık CIL)": lambda: [
        _a("k", "Kırma", "kirma"),
        _a("o", "Öğütme", "ogutme", "k:cikis"),
        _a("f", "Flotasyon", "flotasyon", "o:cikis", 10.0, 85.0),
        _a("l", "Atık liçi (CIL)", "lic_cil", "f:atik", 100.0, 60.0),
    ],
    "Gravite + CIL (gravite atığı liçe gider)": lambda: [
        _a("k", "Kırma", "kirma"),
        _a("o", "Öğütme", "ogutme", "k:cikis"),
        _a("g", "Gravite", "gravite", "o:cikis", 0.5, 30.0),
        _a("l", "CIL", "lic_cil", "g:atik", 100.0, 90.0),
    ],
    "Gravite + flotasyon (gravite atığı flotasyona gider)": lambda: [
        _a("k", "Kırma", "kirma"),
        _a("o", "Öğütme", "ogutme", "k:cikis"),
        _a("g", "Gravite", "gravite", "o:cikis", 0.5, 30.0),
        _a("f", "Flotasyon", "flotasyon", "g:atik", 10.0, 85.0),
    ],
    "Yığın liçi (Au, kırma + yığın)": lambda: [
        _a("k", "Kırma", "kirma"),
        _a("l", "Yığın liçi (Au)", "lic_yigin_au", "k:cikis", 100.0, 70.0),
    ],
}


if __name__ == "__main__":
    # --- Kütle/metal dengesi ---
    s = SABLONLAR["Flotasyon + konsantre liçi"]()
    r = akis_hesapla(10_000, 2.0, "g/t", s)
    f = next(x for x in r["asamalar"] if x["uid"] == "f")
    l = next(x for x in r["asamalar"] if x["uid"] == "l")
    assert abs(f["kons_tpd"] - 1000) < 1e-9 and abs(f["kons_tenor"] - 17.0) < 1e-9
    assert abs(f["atik_tenor"] - 2.0 * 0.15 / 0.9) < 1e-9
    assert abs(l["besleme_tpd"] - 1000) < 1e-9
    assert abs(r["toplam_verim_pct"] - 85 * 0.9) < 1e-9, r["toplam_verim_pct"]
    assert abs(r["kayip_metal_pct"] - (100 - 76.5)) < 1e-9
    # kütle dengesi: konsantre + atık = besleme; metal: kons*tenör + atık*tenör = besleme*tenör
    assert abs(f["kons_tpd"] + f["atik_tpd"] - f["besleme_tpd"]) < 1e-9
    assert abs(f["kons_tpd"] * f["kons_tenor"] + f["atik_tpd"] * f["atik_tenor"] - 10_000 * 2.0) < 1e-6
    # konsantre satılıyorsa (liç yok): ürün = konsantre metali
    r2 = akis_hesapla(10_000, 2.0, "g/t", s[:3])
    assert abs(r2["toplam_verim_pct"] - 85.0) < 1e-9
    # iki ürünlü akış: gravite konsantresi ürün + atığı CIL
    g = SABLONLAR["Gravite + CIL (gravite atığı liçe gider)"]()
    r3 = akis_hesapla(5_000, 1.5, "g/t", g)
    beklenen = 30 + 70 * 0.9
    assert abs(r3["toplam_verim_pct"] - beklenen) < 1e-9, (r3["toplam_verim_pct"], beklenen)
    gr = next(x for x in r3["asamalar"] if x["uid"] == "g")
    assert abs(gr["urun_metal_pct"] - 30.0) < 1e-9 and abs(gr["kons_tpd"] - 25.0) < 1e-9
    # hata durumları
    for kotu, mesaj in [
        ([_a("a", "A", "flotasyon", "yok:kons", 10, 80)], "tanımlı değil"),
        ([_a("a", "A", "flotasyon", CEVHER, 10, 80), _a("b", "B", "flotasyon", CEVHER, 10, 80)], "yalnızca bir aşamaya"),
        ([_a("a", "A", "flotasyon", CEVHER, 100, 80)], "ağırlık verimi"),
        ([_a("a", "A", "lic_cil", CEVHER, 100, 120)], "ekstraksiyon"),
    ]:
        try:
            akis_hesapla(1000, 1.0, "g/t", kotu)
        except ValueError as e:
            assert mesaj in str(e), (mesaj, str(e))
        else:
            raise AssertionError("hata beklenirdi: " + mesaj)
    r4 = akis_hesapla(1000, 1.0, "%", [_a("a", "A", "flotasyon", CEVHER, 0.5, 95)])
    assert any("%100" in u for u in r4["uyarilar"])
    # --- CAPEX alanları aşama kapasitesinde ---
    c = asama_capex(s, r, 0.6)
    kap = {(x["asama"], x["alan"]): x["kapasite_tpd"] for x in c["satirlar"]}
    assert abs(kap[("Kırma", ALAN_TURLERI["kirma"])] - 10_000) < 1e-9
    assert abs(kap[("Konsantre liçi (CIL)", ALAN_TURLERI["cil"])] - 1000) < 1e-9
    assert abs(kap[("Flotasyon", ALAN_TURLERI["flotasyon"])] - 10_000) < 1e-9
    assert abs(kap[("Flotasyon", ALAN_TURLERI["atik_koyulastirma"])] - 9000) < 1e-9
    assert c["alt_usd"] > 0 and c["ust_usd"] >= c["alt_usd"]
    # veri olmayan alan (gravite) toplama girmez ve eksik olarak bildirilir
    cg = asama_capex(g, r3, 0.6)
    assert any("Gravite" in e for e in cg["eksik"])
    print("Kombine akış modeli: tüm testler geçti")
    print(f"  Flotasyon + konsantre liçi: toplam verim %{r['toplam_verim_pct']:.1f}; CAPEX (doğrudan) "
          f"${c['alt_usd'] / 1e6:,.1f}M - ${c['ust_usd'] / 1e6:,.1f}M")
    for u in c["ekstrapolasyon"]:
        print("  ekstrapolasyon:", u)
