"""
Kombine Akış sekmesi (Streamlit arayüzü)
=========================================
Hesaplar process_chain_model.py içindedir; bu dosya yalnızca akış kurma ve gösterim yapar.
app.py içinden chain_tab.render() olarak çağrılır.
"""

import pandas as pd
import streamlit as st

from capex_scaling_model import ALAN_TURLERI, LITERATUR_USTEL
from process_chain_model import (
    CEVHER, ASAMA_TURLERI, AYIRMA_TURLERI, LIC_TURLERI, TUR_ALANLARI, SABLONLAR, VARSAYILAN_ORAN_ARALIGI,
    Metal, Asama, akim_adlari, akim_etiketi, varsayilan_alanlar, onceki_lic_mi, dogrula, eksik_girdiler, akis_hesapla,
    asama_capex, asama_opex, veri_kapsami,
)

_OZEL = "(Özel, boş akış)"
_AKIM_CINS = {"kons": "konsantre", "atik": "atık", "cikis": "çıkış"}
MAKS_METAL = 3


def _usd(x):
    return f"${x:,.0f}".replace("$", "\\$")


def _md(metin):
    return metin.replace("$", "\\$")


def _sablon_yukle(ad):
    st.session_state["kz_gen"] = st.session_state.get("kz_gen", 0) + 1
    st.session_state["kz_sayac"] = 10
    st.session_state["kz_sablon_yuklu"] = ad
    if ad == _OZEL:
        metaller = [Metal("Au", "g/t", None)]
        asamalar = [Asama(uid="s1", ad="Kırma", tur="kirma")]
        tpd, notlar = None, []
    else:
        s = SABLONLAR[ad]()
        metaller, asamalar, tpd, notlar = s["metaller"], s["asamalar"], s["cevher_tpd"], s["notlar"]
    st.session_state["kz_tpd"] = float(tpd) if tpd else None
    st.session_state["kz_notlar"] = notlar
    st.session_state["kz_metaller0"] = [{"ad": m.ad, "birim": m.birim, "tenor": m.tenor} for m in metaller]
    st.session_state["kz_nmetal"] = len(metaller)
    st.session_state["kz_liste"] = [
        {"uid": a.uid, "ad": a.ad, "tur": a.tur, "besleme": a.besleme, "agirlik": a.agirlik_verimi_pct,
         "verim": [a.verimler.get(m.ad) for m in metaller]} for a in asamalar
    ]


def _asama_ekle(tur_anahtari):
    liste = st.session_state["kz_liste"]
    st.session_state["kz_sayac"] += 1
    uid = f"s{st.session_state['kz_sayac']}"
    besleme = CEVHER
    if liste:
        onceki = liste[-1]
        besleme = akim_adlari(Asama(uid=onceki["uid"], ad=onceki["ad"], tur=onceki["tur"]))[0]
    liste.append({"uid": uid, "ad": ASAMA_TURLERI[tur_anahtari], "tur": tur_anahtari, "besleme": besleme,
                  "agirlik": None, "verim": [None] * MAKS_METAL})


def _asama_sil(uid):
    st.session_state["kz_liste"] = [a for a in st.session_state["kz_liste"] if a["uid"] != uid]


def _lic_aktar(deger):
    st.session_state["lic_tpd"] = float(min(max(deger, 100.0), 200_000.0))


def _dot(cevher_tpd, birimler, asamalar, sonuc):
    """Akış şeması (Graphviz DOT)."""
    satir = {s["uid"]: s for s in sonuc["asamalar"]}
    tuketilen = {a.besleme for a in asamalar}
    ten = lambda d: "\\n".join(f"{m} {v:,.2f} {birimler[m]}" for m, v in d.items())
    d = ["digraph G {", "rankdir=LR;", 'node [shape=box, style="rounded,filled", fillcolor="#eef2f7", fontname="Helvetica"];',
         'edge [fontname="Helvetica", fontsize=10];',
         f'cevher [label="Cevher\\n{cevher_tpd:,.0f} t/gün\\n{ten(sonuc["akimlar"][CEVHER]["tenor"])}", fillcolor="#fdf3d6"];']
    for a in asamalar:
        tur_ad = ASAMA_TURLERI[a.tur]
        d.append(f'{a.uid} [label="{a.ad}' + ("" if a.ad == tur_ad else f"\\n{tur_ad}") + '"];')
        kaynak = "cevher" if a.besleme == CEVHER else a.besleme.split(":")[0]
        akim = sonuc["akimlar"][a.besleme]
        cins = _AKIM_CINS.get(a.besleme.partition(":")[2], "")
        on_ek = f"{cins}\\n" if cins in ("konsantre", "atık") else ""
        d.append(f'{kaynak} -> {a.uid} [label="{on_ek}{akim["tpd"]:,.0f} t/gün\\n{ten(akim["tenor"])}"];')
    for a in asamalar:
        s = satir[a.uid]
        urun_metin = "\\n".join(f"{m} verimi %{v:.1f}" for m, v in s["urun_metal_pct"].items())
        if a.tur in AYIRMA_TURLERI and f"{a.uid}:kons" not in tuketilen:
            d.append(f'{a.uid}_urun [label="Konsantre (ürün)\\n{s["kons_tpd"]:,.0f} t/gün\\n{ten(s["kons_tenor"])}\\n'
                     f'{urun_metin}", fillcolor="#d9efd9"];')
            d.append(f'{a.uid} -> {a.uid}_urun;')
        if a.tur in LIC_TURLERI:
            d.append(f'{a.uid}_urun [label="Çözelti (ürün)\\n{urun_metin}", fillcolor="#d9efd9"];')
            d.append(f'{a.uid} -> {a.uid}_urun;')
        if a.tur in AYIRMA_TURLERI or a.tur in LIC_TURLERI:
            if f"{a.uid}:atik" not in tuketilen:
                d.append(f'{a.uid}_atik [label="Atık\\n{s["atik_tpd"]:,.0f} t/gün\\n{ten(s["atik_tenor"])}", fillcolor="#f3dada"];')
                d.append(f'{a.uid} -> {a.uid}_atik;')
    d.append("}")
    return "\n".join(d)


def render():
    st.header("Kombine Akış: kütle/metal dengesi, aşama bazlı CAPEX ve OPEX")
    st.markdown(
        "Flotasyon + liç, gravite + liç gibi çok aşamalı akışlar için. Aşamaları sırayla kurarsın; her aşama "
        "önceki bir aşamanın çıkışını (konsantre ya da atık) alır. Uygulama **aşamalar arası kütle ve metal "
        "dengesini** (metal başına) kurar, toplam verimi hesaplar ve her CAPEX alanını **o aşamanın kendi besleme "
        "miktarına** göre ölçekler."
    )
    with st.expander("Güvenilirlik kuralları ve sınırlar", expanded=False):
        st.markdown(
            "- **Varsayılan değer yok.** Ağırlık verimi, metal verimi, ekstraksiyon, tenör ve besleme miktarı girilmeden hesap yapılmaz. "
            "Şablonlar yalnızca bir rapordan gelen değerleri (kaynağıyla) getirir; rapor değeri olmayanlar boş kalır.\n"
            "- **CAPEX referansları:** Altar ve Furnas (Cu flotasyonu), Cerro Blanco (Au, CIP), Enchi (Au, gravite + CIL), Lemhi (Au, CIL), "
            "Cactus (Cu yığın liçi + SX-EW), Santa Fe (Au yığın liçi + ADR) ve konsantre liçli dört rapor: Springpole (flotasyon + konsantre liçi + "
            "atık liçi), Tocantinzinho (gravite + flotasyon + konsantre CIL), Courageous Lake (flotasyon + konsantre POX + liç). Alan bazlı "
            "kapasite: konsantre liçi referansları kendi konsantre miktarlarıyla (315-4,500 t/gün) karşılaştırılır, cevher kapasitesiyle değil.\n"
            "- **Ölçek aralığı:** Bir referans yalnızca hedef kapasite referansın 0.25-4 katı içindeyse **güvenilir toplama** girer (aralığı "
            "değiştirebilirsin). Dışındakiler ayrı gösterilir, toplama katılmaz. Bu, güç yasasının uzak ölçeklerde güvenilmez olmasından dolayıdır.\n"
            "- **Gravite ve POX alanları** tek rapora dayanır; verisi olmayan alanlar toplama girmez ve açıkça işaretlenir; gerçek toplam daha yüksektir.\n"
            "- **Ölçek tabanı:** Raporlar maliyeti tesis besleme miktarına göre verdiği için her alan, kendi aşamasının besleme miktarında ölçeklenir. "
            "Konsantre/atık kütle çekişi farkları ihmal edilir.\n"
            "- **OPEX** yalnızca raporlarda alan bazlı verilen alanlar için ($/t). İki kapsam ayrıdır ve toplanmaz: "
            "'tam' (Furnas, alan toplamı) ve 'sarf+güç' (Enchi; işçilik, bakım ve laboratuvar hariç). Birim maliyetin ölçekle değişmediği varsayılır.\n"
            "- **Konsantre liçi** üç referansa dayanır ve bunların ikisi (Tocantinzinho ~535 t/gün, Courageous Lake ~315 t/gün, ikincisi POX'lu) küçük "
            "ölçeklidir. Courageous Lake refrakter konsantre içindir; liç satırı Merrill-Crowe içerir (karbon adsorpsiyonu yok). Aralıkları kendin yorumla.\n"
            "- Birden fazla liç aşamasında ADR, reaktif ve liç öncesi koyulaştırma ortak tesis sayılır; varsayılan olarak yalnızca ilk liç aşamasında seçilir."
        )

    # ---- Şablon ----
    sablon = st.selectbox("Başlangıç şablonu", [_OZEL] + list(SABLONLAR), key="kz_sablon",
                          help="Şablon akış yapısını ve yalnızca rapordan gelen değerleri getirir; diğer değerler boş kalır.")
    if st.session_state.get("kz_sablon_yuklu") != sablon or "kz_liste" not in st.session_state:
        _sablon_yukle(sablon)
    gen = st.session_state["kz_gen"]
    for n in st.session_state.get("kz_notlar", []):
        st.info(_md(n))

    # ---- Metaller ve besleme ----
    g1, g2 = st.columns([1, 3])
    cevher_tpd = g1.number_input("Cevher besleme miktarı (kuru t/gün)", min_value=100.0, max_value=300_000.0,
                                 value=None, step=500.0, placeholder="girilmedi", key="kz_tpd")
    nm = g2.number_input("İzlenen metal sayısı", min_value=1, max_value=MAKS_METAL, step=1, key="kz_nmetal")
    metaller = []
    mc = st.columns(int(nm))
    m0 = st.session_state["kz_metaller0"]
    for i in range(int(nm)):
        d0 = m0[i] if i < len(m0) else {"ad": "", "birim": "g/t", "tenor": None}
        with mc[i]:
            ad = st.text_input(f"Metal {i + 1}", value=d0["ad"] or ["Au", "Cu", "Ag"][i], key=f"kz{gen}_m{i}_ad")
            birim = st.selectbox("Tenör birimi", ["g/t", "%"], index=["g/t", "%"].index(d0["birim"]), key=f"kz{gen}_m{i}_bi")
            tenor = st.number_input(f"Besleme tenörü ({birim})", min_value=0.0001, max_value=99.0, value=d0["tenor"],
                                    step=0.1, format="%.4f", placeholder="girilmedi", key=f"kz{gen}_m{i}_ten_{birim}")
        metaller.append(Metal(ad.strip(), birim, tenor))
    metal_adlari = [m.ad for m in metaller]

    # ---- Aşamalar ----
    st.subheader("Aşamalar")
    asamalar = []
    gecerli_akimlar = [CEVHER]
    liste = st.session_state["kz_liste"]
    for d in liste:
        uid = d["uid"]
        kp = f"kz{gen}_{uid}"
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 3, 4, 1])
            ad = c1.text_input("Aşama adı", value=d["ad"], key=f"{kp}_ad")
            tur_anahtarlari = list(ASAMA_TURLERI)
            tur = c2.selectbox("Aşama türü", tur_anahtarlari, index=tur_anahtarlari.index(d["tur"]),
                               format_func=ASAMA_TURLERI.get, key=f"{kp}_tur")
            besleme_key = f"{kp}_bes"
            if besleme_key in st.session_state and st.session_state[besleme_key] not in gecerli_akimlar:
                del st.session_state[besleme_key]
            varsayilan_bes = d["besleme"] if d["besleme"] in gecerli_akimlar else gecerli_akimlar[-1]
            onceki = list(asamalar)
            besleme = c3.selectbox("Besleme akımı", gecerli_akimlar, index=gecerli_akimlar.index(varsayilan_bes),
                                   format_func=lambda k, o=onceki: akim_etiketi(k, o), key=besleme_key)
            c4.button("Sil", key=f"{kp}_sil", on_click=_asama_sil, args=(uid,), help="Bu aşamayı sil")
            agirlik, verimler = None, {}
            ayni_tur = d["tur"] == tur
            if tur in AYIRMA_TURLERI:
                agirlik = st.number_input("Konsantreye giden ağırlık verimi (%)", min_value=0.0, max_value=100.0,
                                          value=d["agirlik"] if ayni_tur else None, step=0.5, placeholder="girilmedi",
                                          key=f"{kp}_{tur}_w")
            if tur in AYIRMA_TURLERI or tur in LIC_TURLERI:
                etiket = "Konsantreye giden metal verimi (%)" if tur in AYIRMA_TURLERI else "Metal ekstraksiyonu (%)"
                vc = st.columns(int(nm))
                for i, m in enumerate(metaller):
                    v0 = d["verim"][i] if ayni_tur and i < len(d["verim"]) else None
                    v = vc[i].number_input(f"{etiket}: {m.ad or i + 1}", min_value=0.0, max_value=100.0, value=v0,
                                           step=0.5, placeholder="girilmedi", key=f"{kp}_{tur}_m{i}")
                    verimler[m.ad] = v
        a = Asama(uid=uid, ad=ad.strip() or uid, tur=tur, besleme=besleme, agirlik_verimi_pct=agirlik, verimler=verimler)
        asamalar.append(a)
        gecerli_akimlar = gecerli_akimlar + akim_adlari(a)

    e1, e2 = st.columns([3, 1])
    yeni_tur = e1.selectbox("Eklenecek aşama türü", list(ASAMA_TURLERI), format_func=ASAMA_TURLERI.get,
                            key="kz_yeni_tur", label_visibility="collapsed")
    e2.button("Aşama ekle", key="kz_ekle", on_click=_asama_ekle, args=(yeni_tur,))

    if not asamalar:
        st.info("Akışta aşama yok. Yukarıdan bir aşama ekle.")
        return
    hatalar = dogrula(cevher_tpd, metaller, asamalar)
    hatalar = [h for h in hatalar if not (cevher_tpd is None and h.startswith("Cevher besleme"))]
    if hatalar:
        st.error("Akış hesaplanamadı:\n\n" + "\n".join(f"- {h}" for h in hatalar))
        return
    eksik = eksik_girdiler(metaller, asamalar) + (["Cevher besleme miktarı"] if cevher_tpd is None else [])
    if eksik:
        st.warning("Hesap için şu değerler girilmeli (varsayılan değer yoktur):\n\n" + "\n".join(f"- {e}" for e in eksik))
        return
    sonuc = akis_hesapla(cevher_tpd, metaller, asamalar)
    birimler = {m.ad: m.birim for m in metaller}

    # ---- Sonuçlar ----
    st.subheader("Kütle ve metal dengesi")
    mt = st.columns(len(metaller) + 1)
    for i, m in enumerate(metaller):
        mt[i].metric(f"Toplam {m.ad} verimi (ürüne)", f"%{sonuc['toplam_verim_pct'][m.ad]:.1f}",
                     help=f"Atıkta kalan {m.ad}: %{sonuc['kayip_metal_pct'][m.ad]:.1f}")
    mt[-1].metric("Aşama sayısı", f"{len(asamalar)}")
    if not any(a.tur in AYIRMA_TURLERI or a.tur in LIC_TURLERI for a in asamalar):
        st.info("Akışta henüz ürün veren aşama (ayırma ya da liç) yok.")
    for u in sonuc["uyarilar"]:
        st.warning(u)
    f2 = lambda v, n=2: "-" if v is None else f"{v:,.{n}f}"
    tablo = []
    for s in sonuc["asamalar"]:
        satir = {"Aşama": s["ad"], "Tür": ASAMA_TURLERI[s["tur"]], "Besleme akımı": akim_etiketi(s["besleme"], asamalar),
                 "Besleme (t/gün)": f2(s["besleme_tpd"], 0)}
        for m in metal_adlari:
            satir[f"Besleme {m} ({birimler[m]})"] = f2(s["besleme_tenor"][m])
        satir["Konsantre (t/gün)"] = f2(s["kons_tpd"], 0)
        for m in metal_adlari:
            satir[f"Konsantre {m} ({birimler[m]})"] = f2(s["kons_tenor"][m]) if s["kons_tenor"] else "-"
        satir["Atık (t/gün)"] = f2(s["atik_tpd"], 0)
        for m in metal_adlari:
            satir[f"Atık {m} ({birimler[m]})"] = f2(s["atik_tenor"][m]) if s["atik_tenor"] else "-"
        for m in metal_adlari:
            v = s["urun_metal_pct"][m]
            satir[f"Ürüne giden {m} (%)"] = f2(v, 1) if v else "-"
        tablo.append(satir)
    st.dataframe(pd.DataFrame(tablo), hide_index=True, width="stretch")
    try:
        st.graphviz_chart(_dot(cevher_tpd, birimler, asamalar, sonuc))
    except Exception:
        st.caption("Akış şeması çizilemedi; tablo geçerlidir.")

    lic_asamalar = [s for a, s in zip(asamalar, sonuc["asamalar"]) if a.tur == "lic_cil"]
    if lic_asamalar:
        s0 = lic_asamalar[0]
        st.button(f"'{s0['ad']}' besleme miktarını ({s0['besleme_tpd']:,.0f} t/gün) Liç Kinetiği sekmesindeki CIL boyutlandırmaya aktar",
                  key="kz_aktar", on_click=_lic_aktar, args=(s0["besleme_tpd"],))

    # ---- Aşama bazlı CAPEX ----
    st.subheader("Aşama bazlı CAPEX tahmini (doğrudan maliyet)")
    st.caption("Her alan, kendi aşamasının besleme miktarında, raporlardaki doğrudan maliyetten ayrı ayrı ölçeklenir. "
               "Dolaylı maliyet ve gider payı sana bırakılır.")
    tuketilen = {a.besleme for a in asamalar}
    for a in asamalar:
        a.alanlar = st.multiselect(
            f"{a.ad}: alanlar", options=TUR_ALANLARI[a.tur],
            default=varsayilan_alanlar(a, f"{a.uid}:kons" in tuketilen, onceki_lic_mi(asamalar, a)),
            format_func=lambda k: ALAN_TURLERI[k],
            key=f"kz{gen}_{a.uid}_{a.tur}_{int(f'{a.uid}:kons' in tuketilen)}_{int(onceki_lic_mi(asamalar, a))}_{a.besleme.endswith(':kons')}_alan")
    n1, n2, n3, n4 = st.columns(4)
    alan_n = n1.number_input("Ölçekleme üsteli (n)", min_value=0.3, max_value=1.0, value=LITERATUR_USTEL, step=0.01,
                             key="kz_n", help="Genel literatür değeri (veri değil).")
    duzeltme = n2.number_input("Maliyet düzeltme çarpanı", min_value=0.1, max_value=5.0, value=1.0, step=0.01,
                               key="kz_duzeltme", help="Enflasyon ve piyasa için senin gireceğin çarpan; uygulama endeks varsaymaz.")
    dolayli = n3.number_input("Dolaylı maliyet (% doğrudan)", min_value=0.0, max_value=100.0, value=0.0, step=1.0, key="kz_dol")
    gider = n4.number_input("Gider payı (% doğrudan+dolaylı)", min_value=0.0, max_value=100.0, value=0.0, step=1.0, key="kz_gid")
    o1, o2 = st.columns(2)
    lo = o1.number_input("Geçerli ölçek aralığı: alt sınır (referans kapasitesinin katı)", min_value=0.01, max_value=1.0,
                         value=VARSAYILAN_ORAN_ARALIGI[0], step=0.05, key="kz_lo")
    hi = o2.number_input("Geçerli ölçek aralığı: üst sınır", min_value=1.0, max_value=20.0,
                         value=VARSAYILAN_ORAN_ARALIGI[1], step=0.5, key="kz_hi")

    c = asama_capex(asamalar, sonuc, alan_n, duzeltme, (lo, hi))
    satirlar = []
    for r in c["satirlar"]:
        satirlar.append({
            "Aşama": r["asama"], "Alan": r["alan"], "Kapasite (t/gün)": f"{r['kapasite_tpd']:,.0f}",
            "En düşük (güvenilir)": "-" if r["min_usd"] is None else f"${r['min_usd']:,.0f}",
            "En yüksek (güvenilir)": "-" if r["max_usd"] is None else f"${r['max_usd']:,.0f}",
            "Durum": r["durum"], "Referans kapasitesine oran": r["oran"] or "-", "Referans(lar)": r["referanslar"],
        })
    if satirlar:
        st.dataframe(pd.DataFrame(satirlar), hide_index=True, width="stretch")
        carp = (1 + dolayli / 100.0) * (1 + gider / 100.0)
        t1, t2 = st.columns(2)
        t1.metric("Güvenilir toplam, doğrudan (en düşük)", f"${c['alt_usd']:,.0f}")
        t2.metric("Güvenilir toplam, doğrudan (en yüksek)", f"${c['ust_usd']:,.0f}")
        if dolayli or gider:
            st.caption(f"Dolaylı maliyet ve gider payı eklenmiş toplam: {_usd(c['alt_usd'] * carp)} - {_usd(c['ust_usd'] * carp)}")
        kapsam_notu = []
        if c["eksik"]:
            kapsam_notu.append("**Veri yok, toplama girmedi:** " + "; ".join(c["eksik"]))
        if c["aralik_disi"]:
            kapsam_notu.append(f"**Referans ölçeği dışında ({lo:g}-{hi:g} katı), toplama girmedi:** " + "; ".join(c["aralik_disi"]))
        if kapsam_notu:
            st.warning(_md("\n\n".join(kapsam_notu) + "\n\nBu yüzden güvenilir toplam gerçek CAPEX'i EKSİK gösterir."))
        if c["aralik_disi"]:
            st.caption(f"Aralık dışı satırlar dahil kaba aralık (güvenilir değil): {_usd(c['kaba_alt_usd'])} - {_usd(c['kaba_ust_usd'])}")
        st.caption("Referanslar farklı kapsam, bölge ve çalışma sınıfı taşır; iki uç arasındaki fark ölçek etkisi değildir. "
                   "Altar yalnızca ekipman satın alma + montajdır; Furnas, Cerro Blanco, Enchi, Cactus ve Santa Fe "
                   "raporların doğrudan maliyetidir.")

    # ---- Aşama bazlı OPEX ----
    st.subheader("Aşama bazlı OPEX referansı ($/t)")
    ox = asama_opex(asamalar, sonuc)
    orow = []
    for r in ox["satirlar"]:
        satir = {"Aşama": r["asama"], "Alan": r["alan"], "Besleme (t/gün)": f"{r['tpd']:,.0f}"}
        for kapsam, ad in (("tam", "Tam alan OPEX'i"), ("sarf_guc", "Yalnızca sarf + güç")):
            v = r[kapsam]
            satir[f"{ad} ($/t)"] = "-" if v is None else (f"{v['usd_t'][0]:.2f}" if abs(v['usd_t'][0] - v['usd_t'][1]) < 0.005
                                                       else f"{v['usd_t'][0]:.2f}-{v['usd_t'][1]:.2f}")
            satir[f"{ad} ($/yıl)"] = "-" if v is None else (f"${v['usd_yil'][0]:,.0f}" if abs(v['usd_yil'][0] - v['usd_yil'][1]) < 1
                                                         else f"${v['usd_yil'][0]:,.0f}-${v['usd_yil'][1]:,.0f}")
        satir["Referans(lar)"] = "; ".join(v["referanslar"] for k in ("tam", "sarf_guc") if (v := r[k]) is not None) or "veri yok"
        orow.append(satir)
    if orow:
        st.dataframe(pd.DataFrame(orow), hide_index=True, width="stretch")
        for kapsam, ad in (("tam", "tam alan OPEX'i (Furnas)"), ("sarf_guc", "yalnızca sarf + güç (Enchi)")):
            t = ox["toplam"][kapsam]
            if t["kapsanan"] == 0:
                continue
            etiket = f"Toplam, {ad}: {t['kapsanan']}/{t['secili']} alan"
            if t["tam_kapsam"]:
                st.metric(etiket, f"${t['alt_usd_yil']:,.0f} - ${t['ust_usd_yil']:,.0f} / yıl")
            else:
                st.caption(_md(f"{etiket} için veri var; toplam kısmidir: {_usd(t['alt_usd_yil'])} - {_usd(t['ust_usd_yil'])} / yıl "
                               "(veri olmayan alanlar dahil değil, toplam olarak kullanma)."))
        st.caption("İşçilik, bakım ve genel giderler yalnızca 'tam' kapsamda vardır. Kapsamlar toplanmaz. Birim maliyetler aşamanın "
                   "besleme miktarına uygulanır ve ölçekle değişmediği varsayılır.")

    # ---- Veri kapsamı ----
    with st.expander("Referans veri kapsamı (hangi alan için hangi rapor var)"):
        vk = pd.DataFrame(veri_kapsami())[["alan", "n_capex", "capex_kapasite", "capex_projeler", "n_opex"]]
        vk.columns = ["Alan", "CAPEX referans sayısı", "Referans kapasiteleri (t/gün)", "Projeler", "OPEX referans sayısı"]
        st.dataframe(vk, hide_index=True, width="stretch")
        st.caption("Tek referanslı alanlarda min-maks aralığı yoktur; sonuç tek bir raporun ölçeklenmiş değeridir.")
