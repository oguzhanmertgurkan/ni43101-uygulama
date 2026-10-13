"""
Kombine akış modeli (kütle ve metal dengesi, aşama bazlı CAPEX ve OPEX referansları)
====================================================================================
Flotasyon + konsantre liçi, gravite + CIL gibi birden çok birim işlemden oluşan akışlar için.

Kapsam
------
- Bir ya da birden çok metal izlenir (ör. Au g/t ve Cu %). Her aşamada metal başına verim girilir.
- Her aşama bir "besleme" akımı alır: cevher beslemesi ya da önceki bir aşamanın çıkış akımı.
- Ayırma aşamalarında (flotasyon, gravite, DMS, manyetik) kullanıcı konsantreye giden AĞIRLIK verimini ve
  her metal için konsantreye giden METAL verimini girer. Tenörler bunlardan hesaplanır:
      konsantre tenörü = besleme tenörü * metal verimi / ağırlık verimi
      atık tenörü      = besleme tenörü * (1 - metal verimi) / (1 - ağırlık verimi)
- Liç aşamasında her metal için ekstraksiyon (%) girilir. Çözünen metal ürün sayılır; katı artığın kütlesi
  besleme kütlesine eşit alınır (çözünen kütle ihmal edilir).
- Kırma ve öğütme aşamaları kütle ve metal bakımından geçiş aşamasıdır; yalnızca CAPEX alanı kapasitesini
  belirlemek için akışta yer alır.
- Hiçbir aşamaya beslenmeyen konsantre ürün (satılan konsantre) sayılır. Hiçbir aşamaya beslenmeyen atıktaki
  metal kayıptır.
- Verimler ve ağırlık verimleri ZORUNLU girdidir; girilmemişse hesap yapılmaz (varsayılan değer yoktur).

CAPEX ve OPEX
-------------
- Her alan, kendi aşamasının besleme miktarında (raporlar tesis besleme miktarına göre verdiği için bu tabandır)
  estimate_area_capex ile ölçeklenir. Yalnızca referans kapasitesinin belirli bir katı aralığındaki referanslar
  (varsayılan 0.25-4) "güvenilir toplam"a girer; aralık dışı referanslar ayrı gösterilir ve toplama katılmaz.
- OPEX, raporların alan bazlı $/t değerlerinden alınır (yalnızca bu tür veri olan alanlar). 'tam' ve 'sarf_guc'
  kapsamları toplanmaz. Birim maliyetin ölçekle değişmediği varsayılır.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from capex_scaling_model import ALAN_TURLERI, estimate_area_capex, estimate_area_opex

CEVHER = "cevher"

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

# Her aşama türünde seçilebilecek CAPEX/OPEX alanları (ALAN_TURLERI anahtarları)
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

# Referans kapasitesinin bu katları dışındaki referanslar güvenilir toplama girmez
VARSAYILAN_ORAN_ARALIGI = (0.25, 4.0)
GUN_YIL = 365.0


@dataclass
class Metal:
    ad: str
    birim: str          # "g/t" veya "%"
    tenor: Optional[float] = None


@dataclass
class Asama:
    uid: str                       # benzersiz kısa kod, akım adlarında kullanılır
    ad: str                        # kullanıcıya gösterilen ad
    tur: str                       # ASAMA_TURLERI anahtarı
    besleme: str = CEVHER          # "cevher" veya "<uid>:kons" / "<uid>:atik" / "<uid>:cikis"
    agirlik_verimi_pct: Optional[float] = None   # yalnızca ayırma: konsantreye giden kütle yüzdesi
    verimler: dict = field(default_factory=dict)  # metal adı -> %; ayırmada konsantreye metal verimi, liçte ekstraksiyon
    alanlar: Optional[list] = None               # seçilen CAPEX/OPEX alanları; None = varsayılan


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
    """Aşama türüne göre varsayılan alanlar."""
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


def eksik_girdiler(metaller: List[Metal], asamalar: List[Asama]) -> list:
    """Girilmemiş zorunlu değerlerin listesi (boşsa hesap yapılabilir)."""
    eksik = []
    for m in metaller:
        if m.tenor is None:
            eksik.append(f"Besleme tenörü ({m.ad})")
    for a in asamalar:
        if a.tur in AYIRMA_TURLERI:
            if a.agirlik_verimi_pct is None:
                eksik.append(f"{a.ad}: konsantreye giden ağırlık verimi")
            for m in metaller:
                if a.verimler.get(m.ad) is None:
                    eksik.append(f"{a.ad}: {m.ad} için konsantreye metal verimi")
        elif a.tur in LIC_TURLERI:
            for m in metaller:
                if a.verimler.get(m.ad) is None:
                    eksik.append(f"{a.ad}: {m.ad} ekstraksiyonu")
    return eksik


def dogrula(cevher_tpd: float, metaller: List[Metal], asamalar: List[Asama]) -> list:
    """Yapısal ve sayısal hata listesi (boşsa akış hesaplanabilir). Eksik girdiler ayrıca eksik_girdiler ile bakılır."""
    hatalar = []
    if cevher_tpd is None or cevher_tpd <= 0:
        hatalar.append("Cevher besleme miktarı pozitif olmalı.")
    if not metaller:
        hatalar.append("En az bir metal gerekli.")
    adlar = [m.ad for m in metaller]
    if len(set(adlar)) != len(adlar) or any(not a for a in adlar):
        hatalar.append("Metal adları boş olmamalı ve tekrarlanmamalı.")
    for m in metaller:
        if m.tenor is not None:
            if m.tenor <= 0:
                hatalar.append(f"{m.ad}: besleme tenörü pozitif olmalı.")
            if m.birim == "%" and m.tenor >= 100:
                hatalar.append(f"{m.ad}: tenör % biriminde 100'den küçük olmalı.")
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
            if a.agirlik_verimi_pct is not None and not (0 < a.agirlik_verimi_pct < 100):
                hatalar.append(f"{a.ad}: ağırlık verimi 0 ile 100 arasında (sınırlar hariç) olmalı.")
        if a.tur in AYIRMA_TURLERI or a.tur in LIC_TURLERI:
            for ad, v in a.verimler.items():
                if v is not None and not (0 <= v <= 100):
                    hatalar.append(f"{a.ad}: {ad} değeri 0-100 arasında olmalı.")
        gorulen.update(akim_adlari(a))
    return hatalar


def akis_hesapla(cevher_tpd: float, metaller: List[Metal], asamalar: List[Asama]) -> dict:
    """
    Kütle ve metal dengesi (metal başına). Dönüş:
      asamalar : aşama sırasıyla satırlar (besleme, konsantre, atık miktarı; metal başına tenörler ve ürün metali)
      akimlar  : akım kimliği -> {tpd, tenor: {metal: değer}}
      toplam_verim_pct, kayip_metal_pct : {metal: %}
      uyarilar : liste
    """
    hatalar = dogrula(cevher_tpd, metaller, asamalar) + [f"Girilmemiş: {e}" for e in eksik_girdiler(metaller, asamalar)]
    if hatalar:
        raise ValueError(" | ".join(hatalar))
    ad = [m.ad for m in metaller]
    birim = {m.ad: m.birim for m in metaller}
    akimlar = {CEVHER: {"tpd": cevher_tpd, "tenor": {m.ad: m.tenor for m in metaller}}}
    toplam = {m.ad: cevher_tpd * m.tenor for m in metaller}
    uyarilar, satirlar = [], []
    urun = {m: 0.0 for m in ad}
    tuketilen = {a.besleme for a in asamalar}
    for a in asamalar:
        b = akimlar[a.besleme]
        metal_in = {m: b["tpd"] * b["tenor"][m] for m in ad}
        satir = {"uid": a.uid, "ad": a.ad, "tur": a.tur, "besleme": a.besleme,
                 "besleme_tpd": b["tpd"], "besleme_tenor": dict(b["tenor"]),
                 "kons_tpd": None, "kons_tenor": None, "atik_tpd": None, "atik_tenor": None,
                 "urun_metal_pct": {m: 0.0 for m in ad}}
        if a.tur in GECIS_TURLERI:
            akimlar[f"{a.uid}:cikis"] = {"tpd": b["tpd"], "tenor": dict(b["tenor"])}
        elif a.tur in AYIRMA_TURLERI:
            y = a.agirlik_verimi_pct / 100.0
            k_ten, t_ten = {}, {}
            for m in ad:
                r = a.verimler[m] / 100.0
                k_ten[m] = b["tenor"][m] * r / y
                t_ten[m] = b["tenor"][m] * (1 - r) / (1 - y)
                if r < y:
                    uyarilar.append(f"{a.ad}: {m} verimi ağırlık veriminden küçük; konsantre tenörü beslemeden düşük çıkıyor.")
                if birim[m] == "%" and k_ten[m] > 100:
                    uyarilar.append(f"{a.ad}: {m} konsantre tenörü %100'ü aşıyor ({k_ten[m]:,.1f}); ağırlık veya metal verimi tutarsız.")
                if f"{a.uid}:kons" not in tuketilen:
                    pay = metal_in[m] * r
                    urun[m] += pay
                    satir["urun_metal_pct"][m] = pay / toplam[m] * 100.0
            akimlar[f"{a.uid}:kons"] = {"tpd": b["tpd"] * y, "tenor": k_ten}
            akimlar[f"{a.uid}:atik"] = {"tpd": b["tpd"] * (1 - y), "tenor": t_ten}
            satir.update(kons_tpd=b["tpd"] * y, kons_tenor=k_ten, atik_tpd=b["tpd"] * (1 - y), atik_tenor=t_ten)
        elif a.tur in LIC_TURLERI:
            t_ten = {}
            for m in ad:
                x = a.verimler[m] / 100.0
                t_ten[m] = b["tenor"][m] * (1 - x)
                pay = metal_in[m] * x
                urun[m] += pay
                satir["urun_metal_pct"][m] = pay / toplam[m] * 100.0
            akimlar[f"{a.uid}:atik"] = {"tpd": b["tpd"], "tenor": t_ten}
            satir.update(atik_tpd=b["tpd"], atik_tenor=t_ten)
        satirlar.append(satir)
    return {
        "asamalar": satirlar, "akimlar": akimlar,
        "toplam_verim_pct": {m: urun[m] / toplam[m] * 100.0 for m in ad},
        "kayip_metal_pct": {m: (toplam[m] - urun[m]) / toplam[m] * 100.0 for m in ad},
        "uyarilar": uyarilar,
    }


def _alanlar(a: Asama, tuketilen: set) -> list:
    return a.alanlar if a.alanlar is not None else varsayilan_alanlar(a, f"{a.uid}:kons" in tuketilen)


def asama_capex(asamalar: List[Asama], sonuc: dict, exponent: float, duzeltme: float = 1.0,
                oran_araligi: tuple = VARSAYILAN_ORAN_ARALIGI) -> dict:
    """
    Her aşamanın seçili alanlarını, o aşamanın besleme miktarında estimate_area_capex ile ölçekler.
    Her referans için ölçek oranı (hedef / referans kapasitesi) oran_araligi içindeyse "güvenilir", dışındaysa
    "aralık dışı" sayılır. Güvenilir toplam yalnızca aralık içi referanslardan hesaplanır.
    """
    lo_ok, hi_ok = oran_araligi
    tuketilen = {a.besleme for a in asamalar}
    satirlar, eksik, disarda = [], [], []
    g_alt = g_ust = k_alt = k_ust = 0.0
    for a, s in zip(asamalar, sonuc["asamalar"]):
        for kod in _alanlar(a, tuketilen):
            tpd = s["besleme_tpd"]
            e = estimate_area_capex(kod, tpd, exponent=exponent, duzeltme_carpani=duzeltme)
            etiket = ALAN_TURLERI.get(kod, kod)
            satir = {"asama": a.ad, "alan_kodu": kod, "alan": etiket, "kapasite_tpd": tpd, "n_ref": len(e["referanslar"]),
                     "n_ici": 0, "min_usd": None, "max_usd": None, "kaba_min": None, "kaba_max": None,
                     "oran": "", "durum": "", "referanslar": ""}
            if not e["veri_var"]:
                satir["durum"] = "veri yok"
                satir["referanslar"] = "-"
                eksik.append(f"{a.ad}: {etiket}")
                satirlar.append(satir)
                continue
            for r in e["referanslar"]:
                r["oran"] = tpd / r["capacity_tpd"]
                r["aralikta"] = lo_ok <= r["oran"] <= hi_ok
            ici = [r for r in e["referanslar"] if r["aralikta"]]
            oranlar = [r["oran"] for r in e["referanslar"]]
            satir["oran"] = (f"{min(oranlar):.2f}-{max(oranlar):.2f}" if abs(max(oranlar) - min(oranlar)) > 0.005
                             else f"{min(oranlar):.2f}")
            satir["n_ici"] = len(ici)
            satir["kaba_min"] = min(r["scaled_usd"] for r in e["referanslar"])
            satir["kaba_max"] = max(r["scaled_usd"] for r in e["referanslar"])
            k_alt += satir["kaba_min"]
            k_ust += satir["kaba_max"]
            satir["referanslar"] = ", ".join(
                f"{r['project']} (${r['scaled_usd'] / 1e6:,.1f}M, {r['oran']:.2f}x{'' if r['aralikta'] else ' aralık dışı'})"
                for r in e["referanslar"])
            if ici:
                satir["min_usd"] = min(r["scaled_usd"] for r in ici)
                satir["max_usd"] = max(r["scaled_usd"] for r in ici)
                g_alt += satir["min_usd"]
                g_ust += satir["max_usd"]
                satir["durum"] = "tek referans" if len(ici) == 1 else f"{len(ici)} referans"
                if len(ici) < len(e["referanslar"]):
                    satir["durum"] += f" ({len(e['referanslar']) - len(ici)} aralık dışı hariç)"
            else:
                satir["durum"] = "aralık dışı (toplama girmedi)"
                disarda.append(f"{a.ad}: {etiket} ({tpd:,.0f} t/gün; referansların {min(oranlar):.2f}-{max(oranlar):.2f} katı)")
            satirlar.append(satir)
    return {"satirlar": satirlar, "alt_usd": g_alt, "ust_usd": g_ust, "kaba_alt_usd": k_alt, "kaba_ust_usd": k_ust,
            "eksik": eksik, "aralik_disi": disarda, "oran_araligi": oran_araligi}


def asama_opex(asamalar: List[Asama], sonuc: dict) -> dict:
    """
    Seçili alanlar için raporlardaki alan bazlı OPEX ($/t, o aşamanın besleme miktarına uygulanır). 'tam' ve
    'sarf_guc' kapsamları ayrı tutulur. Toplam, o kapsamda seçili TÜM alanlar için veri varsa 'tam_kapsam' olur.
    """
    tuketilen = {a.besleme for a in asamalar}
    satirlar = []
    kap = {"tam": {"alt": 0.0, "ust": 0.0, "var": 0}, "sarf_guc": {"alt": 0.0, "ust": 0.0, "var": 0}}
    secili = 0
    for a, s in zip(asamalar, sonuc["asamalar"]):
        for kod in _alanlar(a, tuketilen):
            secili += 1
            e = estimate_area_opex(kod)
            satir = {"asama": a.ad, "alan_kodu": kod, "alan": ALAN_TURLERI.get(kod, kod), "tpd": s["besleme_tpd"]}
            for kapsam in ("tam", "sarf_guc"):
                refs = [r for r in e["referanslar"] if r["kapsam"] == kapsam]
                if refs:
                    lo, hi = min(r["usd_t"] for r in refs), max(r["usd_t"] for r in refs)
                    satir[kapsam] = {"usd_t": (lo, hi), "usd_yil": (lo * s["besleme_tpd"] * GUN_YIL, hi * s["besleme_tpd"] * GUN_YIL),
                                     "referanslar": ", ".join(
                                         f"{r['project'].replace(' Project', '')}{' ' + r['senaryo'] if r['senaryo'] else ''} {r['usd_t']:.2f}"
                                         for r in refs)}
                    kap[kapsam]["alt"] += lo * s["besleme_tpd"] * GUN_YIL
                    kap[kapsam]["ust"] += hi * s["besleme_tpd"] * GUN_YIL
                    kap[kapsam]["var"] += 1
                else:
                    satir[kapsam] = None
            satirlar.append(satir)
    toplam = {}
    for kapsam, d in kap.items():
        toplam[kapsam] = {"alt_usd_yil": d["alt"], "ust_usd_yil": d["ust"], "kapsanan": d["var"], "secili": secili,
                          "tam_kapsam": d["var"] == secili and secili > 0}
    return {"satirlar": satirlar, "toplam": toplam}


def veri_kapsami() -> list:
    """Her alan için hangi referans, hangi kapasitede var (arayüzdeki güvenilirlik tablosu için)."""
    out = []
    for kod, etiket in ALAN_TURLERI.items():
        e = estimate_area_capex(kod, 1000.0)
        o = estimate_area_opex(kod)
        refs = e["referanslar"]
        out.append({
            "alan_kodu": kod, "alan": etiket, "n_capex": len(refs),
            "capex_kapasite": (f"{min(r['capacity_tpd'] for r in refs):,.0f}-{max(r['capacity_tpd'] for r in refs):,.0f}"
                               if refs else "-"),
            "capex_projeler": ", ".join(r["project"].replace(" Project", "") for r in refs) or "veri yok",
            "n_opex": len(o["referanslar"]),
        })
    return out


# ------------------------------------------------------------------
# Hazır şablonlar: yapı + yalnızca raporlardan gelen değerler (kaynağıyla). Rapor değeri olmayan her
# verim ve tenör BOŞ bırakılır, kullanıcı girer.
# ------------------------------------------------------------------
def _sablon(adlar, asamalar, cevher_tpd=None, notlar=()):
    return {"metaller": adlar, "asamalar": asamalar, "cevher_tpd": cevher_tpd, "notlar": list(notlar)}


def _a(uid, ad, tur, besleme=CEVHER, agirlik=None, **verim):
    return Asama(uid=uid, ad=ad, tur=tur, besleme=besleme, agirlik_verimi_pct=agirlik, verimler=dict(verim))


_ENCHI_GRAV = 25.4
_ENCHI_TOPLAM = 93.61
_ENCHI_CIL = round((_ENCHI_TOPLAM - _ENCHI_GRAV) / (100.0 - _ENCHI_GRAV) * 100.0, 2)   # 91.43

SABLONLAR = {
    "Gravite + CIL (Enchi referanslı)": lambda: _sablon(
        [Metal("Au", "g/t", 0.93)],
        [_a("k", "Kırma", "kirma"), _a("o", "Öğütme", "ogutme", "k:cikis"),
         _a("g", "Gravite", "gravite", "o:cikis", None, Au=_ENCHI_GRAV),
         _a("l", "CIL", "lic_cil", "g:atik", None, Au=_ENCHI_CIL)],
        cevher_tpd=15_068,
        notlar=["Enchi PFS (Lycopodium, 2026): tasarım besleme tenörü 0.93 g/t Au, 5.5 Mtpa (15,068 t/gün), gravite altın verimi "
                f"%{_ENCHI_GRAV} (tasarım, test verisi/anlaşılan), gravite + CIL toplam altın verimi %{_ENCHI_TOPLAM} (hesaplanan).",
                f"CIL ekstraksiyonu %{_ENCHI_CIL} raporda doğrudan verilmemiştir; (93.61 - 25.4) / (100 - 25.4) ile türetilmiştir.",
                "Raporda gravite devresi öğütme devresinin yan akımıdır (siklon altı akımının bir kısmı, artık değirmene döner). "
                "Burada ardışık ayırma olarak modellenmiştir; toplam metal verimi için eşdeğerdir.",
                "Gravite konsantresinin ağırlık verimi raporda tasarım değeri olarak verilmediği için boş bırakıldı; sen gir."]),
    "Yığın liçi, Au (Santa Fe referanslı)": lambda: _sablon(
        [Metal("Au", "g/t", None)],
        [_a("k", "Kırma", "kirma"), _a("l", "Yığın liçi (Au)", "lic_yigin_au", "k:cikis", None, Au=60.1)],
        cevher_tpd=12_500,
        notlar=["Santa Fe PEA (KCA/RESPEC, 2025): işleme miktarı yaklaşık 12,500 t/gün, ömür boyu ortalama yığın liçi altın verimi %60.1. "
                "Besleme tenörünü kendi cevherin için gir."]),
    "Yığın liçi, Cu + SX-EW (Cactus referanslı)": lambda: _sablon(
        [Metal("Cu", "%", 0.517)],
        [_a("k", "Kırma", "kirma"), _a("l", "Yığın liçi (Cu)", "lic_yigin_cu", "k:cikis", None, Cu=75.0)],
        cevher_tpd=69_593,
        notlar=["Cactus PFS (M3, 2025): ömür boyu ağırlıklı ortalama tenör %0.517 CuT, ömür boyu toplam bakır verimi %75 (yığın verimliliği "
                "dahil, 76,713 st/gün = 69,593 t/gün)."]),
    "Flotasyon + konsantre liçi (değerleri sen gir)": lambda: _sablon(
        [Metal("Au", "g/t", None)],
        [_a("k", "Kırma", "kirma"), _a("o", "Öğütme", "ogutme", "k:cikis"),
         _a("f", "Flotasyon", "flotasyon", "o:cikis", None, Au=None),
         _a("l", "Konsantre liçi (CIL)", "lic_cil", "f:kons", None, Au=None)],
        notlar=["Yalnızca akış yapısı. Hiçbir rapor değeri yok: ağırlık verimi, flotasyon metal verimi ve liç ekstraksiyonu senin deney ya da "
                "rapor verinle girilir."]),
    "Flotasyon atığı liçi (değerleri sen gir)": lambda: _sablon(
        [Metal("Au", "g/t", None)],
        [_a("k", "Kırma", "kirma"), _a("o", "Öğütme", "ogutme", "k:cikis"),
         _a("f", "Flotasyon", "flotasyon", "o:cikis", None, Au=None),
         _a("l", "Atık liçi (CIL)", "lic_cil", "f:atik", None, Au=None)],
        notlar=["Yalnızca akış yapısı."]),
    "Gravite + flotasyon (değerleri sen gir)": lambda: _sablon(
        [Metal("Au", "g/t", None)],
        [_a("k", "Kırma", "kirma"), _a("o", "Öğütme", "ogutme", "k:cikis"),
         _a("g", "Gravite", "gravite", "o:cikis", None, Au=None),
         _a("f", "Flotasyon", "flotasyon", "g:atik", None, Au=None)],
        notlar=["Yalnızca akış yapısı."]),
}


if __name__ == "__main__":
    def tam(sablon_adi, tpd=10_000.0, tenorler=None, doldur=None):
        s = SABLONLAR[sablon_adi]()
        ms = s["metaller"]
        for m in ms:
            if m.tenor is None:
                m.tenor = (tenorler or {}).get(m.ad, 2.0)
        for a in s["asamalar"]:
            for k in list(a.verimler):
                if a.verimler[k] is None and doldur:
                    a.verimler[k] = doldur.get((a.uid, k))
            if a.tur in AYIRMA_TURLERI and a.agirlik_verimi_pct is None and doldur:
                a.agirlik_verimi_pct = doldur.get((a.uid, "w"))
        return s["cevher_tpd"] or tpd, ms, s["asamalar"]

    # --- Girilmemiş değerler hesabı engeller ---
    tpd, ms, ast = tam("Flotasyon + konsantre liçi (değerleri sen gir)")
    assert eksik_girdiler(ms, ast), "boş şablon eksik girdi bildirmeli"
    try:
        akis_hesapla(tpd, ms, ast)
    except ValueError as e:
        assert "Girilmemiş" in str(e)
    else:
        raise AssertionError("boş değerlerle hesap yapılmamalı")

    # --- Tek metal: flotasyon + konsantre liçi, elle hesapla ---
    tpd, ms, ast = tam("Flotasyon + konsantre liçi (değerleri sen gir)", 10_000, {"Au": 2.0},
                       {("f", "w"): 10.0, ("f", "Au"): 85.0, ("l", "Au"): 90.0})
    r = akis_hesapla(tpd, ms, ast)
    f = next(x for x in r["asamalar"] if x["uid"] == "f")
    l = next(x for x in r["asamalar"] if x["uid"] == "l")
    assert abs(f["kons_tpd"] - 1000) < 1e-9 and abs(f["kons_tenor"]["Au"] - 17.0) < 1e-9
    assert abs(f["atik_tenor"]["Au"] - 2.0 * 0.15 / 0.9) < 1e-9 and abs(l["besleme_tpd"] - 1000) < 1e-9
    assert abs(r["toplam_verim_pct"]["Au"] - 76.5) < 1e-9 and abs(r["kayip_metal_pct"]["Au"] - 23.5) < 1e-9
    assert abs(f["kons_tpd"] + f["atik_tpd"] - f["besleme_tpd"]) < 1e-9
    assert abs(f["kons_tpd"] * f["kons_tenor"]["Au"] + f["atik_tpd"] * f["atik_tenor"]["Au"] - 10_000 * 2.0) < 1e-6
    # konsantre satılıyorsa (liç yok): ürün = konsantre metali
    r2 = akis_hesapla(tpd, ms, ast[:3])
    assert abs(r2["toplam_verim_pct"]["Au"] - 85.0) < 1e-9

    # --- Enchi şablonu: toplam verim raporun 93.61 değerini geri verir ---
    s = SABLONLAR["Gravite + CIL (Enchi referanslı)"]()
    s["asamalar"][2].agirlik_verimi_pct = 0.5
    r3 = akis_hesapla(s["cevher_tpd"], s["metaller"], s["asamalar"])
    assert abs(r3["toplam_verim_pct"]["Au"] - 93.61) < 0.01, r3["toplam_verim_pct"]
    assert abs(_ENCHI_CIL - 91.43) < 1e-9

    # --- Çok metalli akış: Cu-Au, flotasyon + konsantre liçi (Au çözünür, Cu çözünmez) ---
    ms2 = [Metal("Cu", "%", 0.5), Metal("Au", "g/t", 1.0)]
    ast2 = [_a("k", "Kırma", "kirma"), _a("o", "Öğütme", "ogutme", "k:cikis"),
            _a("f", "Flotasyon", "flotasyon", "o:cikis", 4.0, Cu=90.0, Au=70.0),
            _a("l", "Konsantre liçi", "lic_cil", "f:kons", None, Cu=0.0, Au=80.0)]
    r4 = akis_hesapla(5000, ms2, ast2)
    f4 = next(x for x in r4["asamalar"] if x["uid"] == "f")
    assert abs(f4["kons_tenor"]["Cu"] - 0.5 * 0.9 / 0.04) < 1e-9 and abs(f4["kons_tenor"]["Au"] - 1.0 * 0.7 / 0.04) < 1e-9
    assert abs(r4["toplam_verim_pct"]["Au"] - 56.0) < 1e-9 and abs(r4["toplam_verim_pct"]["Cu"] - 0.0) < 1e-9
    for m in ("Cu", "Au"):   # metal başına kütle dengesi tutuyor
        assert abs(f4["kons_tpd"] * f4["kons_tenor"][m] + f4["atik_tpd"] * f4["atik_tenor"][m] - 5000 * {"Cu": 0.5, "Au": 1.0}[m]) < 1e-6
    # Eksik metal verimi (Cu girilmemiş) hesabı engeller
    ast3 = [_a("f", "Flotasyon", "flotasyon", CEVHER, 4.0, Au=70.0)]
    try:
        akis_hesapla(5000, ms2, ast3)
    except ValueError as e:
        assert "Cu" in str(e)
    else:
        raise AssertionError("Cu verimi eksik olduğu için hata beklenirdi")

    # --- Hata durumları ---
    for kotu, mesaj in [
        ([_a("a", "A", "flotasyon", "yok:kons", 10, Au=80)], "tanımlı değil"),
        ([_a("a", "A", "flotasyon", CEVHER, 10, Au=80), _a("b", "B", "flotasyon", CEVHER, 10, Au=80)], "yalnızca bir aşamaya"),
        ([_a("a", "A", "flotasyon", CEVHER, 100, Au=80)], "ağırlık verimi"),
        ([_a("a", "A", "lic_cil", CEVHER, None, Au=120)], "0-100"),
    ]:
        try:
            akis_hesapla(1000, [Metal("Au", "g/t", 1.0)], kotu)
        except ValueError as e:
            assert mesaj in str(e), (mesaj, str(e))
        else:
            raise AssertionError("hata beklenirdi: " + mesaj)
    r5 = akis_hesapla(1000, [Metal("Cu", "%", 1.0)], [_a("a", "A", "flotasyon", CEVHER, 0.5, Cu=95.0)])
    assert any("%100" in u for u in r5["uyarilar"])

    # --- CAPEX: aşamanın kendi besleme miktarında, aralık süzmesiyle ---
    c = asama_capex(ast, r, 0.6)
    kap = {(x["asama"], x["alan_kodu"]): x["kapasite_tpd"] for x in c["satirlar"]}
    assert abs(kap[("Konsantre liçi (CIL)", "cil")] - 1000) < 1e-9
    assert abs(kap[("Kırma", "kirma")] - 10_000) < 1e-9 and abs(kap[("Flotasyon", "flotasyon")] - 10_000) < 1e-9
    assert abs(kap[("Flotasyon", "atik_koyulastirma")] - 10_000) < 1e-9     # taban: aşama besleme miktarı
    cil = next(x for x in c["satirlar"] if x["alan_kodu"] == "cil")
    assert cil["durum"].startswith("aralık dışı") and cil["min_usd"] is None and cil["kaba_min"] > 0   # 1,000 t/gün: oran ~0.07-0.09
    assert c["kaba_ust_usd"] > c["ust_usd"] and c["kaba_alt_usd"] <= c["alt_usd"] + sum(
        x["kaba_min"] for x in c["satirlar"] if x["min_usd"] is None and x["kaba_min"])   # kaba aralık güvenilir aralığı kapsar
    assert any("Konsantre liçi" in x for x in c["aralik_disi"])
    # Enchi şablonu, 15,068 t/gün: CIL aralık içi
    c2 = asama_capex(s["asamalar"], r3, 0.6)
    cil2 = next(x for x in c2["satirlar"] if x["alan_kodu"] == "cil")
    assert cil2["min_usd"] is not None and cil2["n_ici"] == 2
    assert any("Gravite" in e for e in c2["eksik"])                          # gravite verisi yok: toplama girmez
    # aralık genişletilirse konsantre liçi de güvenilir toplama girer
    c3 = asama_capex(ast, r, 0.6, oran_araligi=(0.05, 20.0))
    assert next(x for x in c3["satirlar"] if x["alan_kodu"] == "cil")["min_usd"] is not None and c3["ust_usd"] >= c["ust_usd"]

    # --- OPEX: yalnızca alan bazlı veri olan alanlar ---
    ox = asama_opex(ast, r)
    sat = {(x["asama"], x["alan_kodu"]): x for x in ox["satirlar"]}
    assert sat[("Flotasyon", "flotasyon")]["tam"] is not None and sat[("Flotasyon", "flotasyon")]["sarf_guc"] is None
    assert sat[("Konsantre liçi (CIL)", "cil")]["sarf_guc"] is not None and sat[("Konsantre liçi (CIL)", "cil")]["tam"] is None
    assert not ox["toplam"]["tam"]["tam_kapsam"]      # reaktif/stok vb. için alan OPEX'i yok: toplam kısmi
    o_cil = sat[("Konsantre liçi (CIL)", "cil")]["sarf_guc"]
    assert abs(o_cil["usd_t"][0] - 2.087) < 1e-9 and abs(o_cil["usd_t"][1] - 3.43) < 1e-9
    assert abs(o_cil["usd_yil"][0] - 2.087 * 1000 * 365) < 1e-6

    # --- Veri kapsamı tablosu ---
    vk = {x["alan_kodu"]: x for x in veri_kapsami()}
    assert vk["sx_ew"]["n_capex"] == 1 and vk["heap_leach"]["n_capex"] == 2 and vk["gravite"]["n_capex"] == 0
    print("Kombine akış modeli: tüm testler geçti")
    print(f"  Flotasyon + konsantre liçi (test girişleriyle): toplam Au verimi %{r['toplam_verim_pct']['Au']:.1f}; "
          f"güvenilir CAPEX ${c['alt_usd'] / 1e6:,.1f}M-${c['ust_usd'] / 1e6:,.1f}M, kaba ${c['kaba_alt_usd'] / 1e6:,.1f}M-${c['kaba_ust_usd'] / 1e6:,.1f}M")
    for u in c["aralik_disi"]:
        print("  aralık dışı:", u)
