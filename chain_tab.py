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
    CEVHER, ASAMA_TURLERI, AYIRMA_TURLERI, LIC_TURLERI, TUR_ALANLARI, SABLONLAR,
    Asama, akim_adlari, akim_etiketi, varsayilan_alanlar, dogrula, akis_hesapla, asama_capex,
)

_OZEL = "(Özel, boş akış)"
_AKIM_CINS = {"kons": "konsantre", "atik": "atık", "cikis": "çıkış"}


def _usd(x):
    return f"${x:,.0f}".replace("$", "\\$")


def _sablon_yukle(ad):
    if ad == _OZEL:
        asamalar = [Asama(uid="s1", ad="Kırma", tur="kirma")]
    else:
        asamalar = SABLONLAR[ad]()
    st.session_state["kz_gen"] = st.session_state.get("kz_gen", 0) + 1
    st.session_state["kz_liste"] = [
        {"uid": a.uid, "ad": a.ad, "tur": a.tur, "besleme": a.besleme,
         "agirlik": a.agirlik_verimi_pct, "metal": a.metal_verimi_pct} for a in asamalar
    ]
    st.session_state["kz_sayac"] = 10
    st.session_state["kz_sablon_yuklu"] = ad


def _asama_ekle(tur_anahtari):
    liste = st.session_state["kz_liste"]
    st.session_state["kz_sayac"] += 1
    uid = f"s{st.session_state['kz_sayac']}"
    onceki = liste[-1] if liste else None
    besleme = CEVHER
    if onceki:
        cikislar = akim_adlari(Asama(uid=onceki["uid"], ad=onceki["ad"], tur=onceki["tur"]))
        besleme = cikislar[0]
    liste.append({"uid": uid, "ad": ASAMA_TURLERI[tur_anahtari], "tur": tur_anahtari, "besleme": besleme,
                  "agirlik": 10.0 if tur_anahtari in AYIRMA_TURLERI else 100.0,
                  "metal": 85.0 if tur_anahtari in AYIRMA_TURLERI else (90.0 if tur_anahtari in LIC_TURLERI else 100.0)})


def _asama_sil(uid):
    st.session_state["kz_liste"] = [a for a in st.session_state["kz_liste"] if a["uid"] != uid]


def _lic_aktar(deger):
    st.session_state["lic_tpd"] = float(min(max(deger, 100.0), 200_000.0))


def _dot(cevher_tpd, tenor, birim, asamalar, sonuc):
    """Akış şeması (Graphviz DOT)."""
    ten = lambda v: f"{v:,.2f} {birim}"
    satir = {s["uid"]: s for s in sonuc["asamalar"]}
    tuketilen = {a.besleme for a in asamalar}
    d = ["digraph G {", "rankdir=LR;", 'node [shape=box, style="rounded,filled", fillcolor="#eef2f7", fontname="Helvetica"];',
         'edge [fontname="Helvetica", fontsize=10];',
         f'cevher [label="Cevher\\n{cevher_tpd:,.0f} t/gün\\n{ten(tenor)}", fillcolor="#fdf3d6"];']
    for a in asamalar:
        s = satir[a.uid]
        tur_ad = ASAMA_TURLERI[a.tur]
        d.append(f'{a.uid} [label="{a.ad}' + ("" if a.ad == tur_ad else f"\\n{tur_ad}") + '"];')
        kaynak = "cevher" if a.besleme == CEVHER else a.besleme.split(":")[0]
        akim = sonuc["akimlar"][a.besleme]
        cins = _AKIM_CINS.get(a.besleme.partition(":")[2], "")
        on_ek = f"{cins}\\n" if cins in ("konsantre", "atık") else ""
        d.append(f'{kaynak} -> {a.uid} [label="{on_ek}{akim["tpd"]:,.0f} t/gün\\n{ten(akim["tenor"])}"];')
    for a in asamalar:
        s = satir[a.uid]
        if a.tur in AYIRMA_TURLERI and f"{a.uid}:kons" not in tuketilen:
            d.append(f'{a.uid}_urun [label="Konsantre (ürün)\\n{s["kons_tpd"]:,.0f} t/gün\\n{ten(s["kons_tenor"])}\\n'
                     f'ürüne giden metal %{s["urun_metal_pct"]:.1f}", fillcolor="#d9efd9"];')
            d.append(f'{a.uid} -> {a.uid}_urun;')
        if a.tur in LIC_TURLERI:
            d.append(f'{a.uid}_urun [label="Çözelti (ürün)\\nürüne giden metal %{s["urun_metal_pct"]:.1f}", fillcolor="#d9efd9"];')
            d.append(f'{a.uid} -> {a.uid}_urun;')
        if a.tur in AYIRMA_TURLERI or a.tur in LIC_TURLERI:
            if f"{a.uid}:atik" not in tuketilen:
                d.append(f'{a.uid}_atik [label="Atık\\n{s["atik_tpd"]:,.0f} t/gün\\n{ten(s["atik_tenor"])}", fillcolor="#f3dada"];')
                d.append(f'{a.uid} -> {a.uid}_atik;')
    d.append("}")
    return "\n".join(d)


def render():
    st.header("Kombine Akış: kütle/metal dengesi ve aşama bazlı CAPEX")
    st.markdown(
        "Flotasyon + liç, gravite + liç gibi çok aşamalı akışlar için. Aşamaları sırayla kurarsın; her aşama "
        "önceki bir aşamanın çıkışını (konsantre ya da atık) alır. Uygulama **aşamalar arası kütle ve metal "
        "dengesini** kurar, toplam verimi hesaplar ve her CAPEX alanını **o aşamanın gerçek besleme miktarına** göre "
        "ölçekler (örneğin konsantre liçi, tesis beslemesine göre değil konsantre miktarına göre)."
    )
    with st.expander("Kapsam ve sınırlar", expanded=False):
        st.markdown(
            "- Tek metal izlenir (ör. Au g/t ya da Cu %). Cu-Au gibi çok metalli akışlar bu sürümde yok.\n"
            "- Ayırma aşamalarında (flotasyon, gravite, DMS, manyetik) **ağırlık verimi** ve **metal verimi** girilir; "
            "konsantre ve atık tenörleri bunlardan hesaplanır. Liç aşamasında **ekstraksiyon (%)** girilir; çözünen metal "
            "ürün sayılır.\n"
            "- Hiçbir aşamaya beslenmeyen konsantre ürün (satılan konsantre) sayılır; hiçbir aşamaya beslenmeyen atıktaki "
            "metal kayıptır.\n"
            "- Şablonlardaki verim ve tenör değerleri **yer tutucudur**, veri değildir. Kendi test sonuçlarınla değiştir.\n"
            "- CAPEX referansları tek rotalı tesislerden gelir (Altar, Furnas, Cerro Blanco: flotasyon; Enchi: CIL; "
            "Cactus, Santa Fe: yığın liçi). Kombine bir tesis raporu henüz eklenmedi. Gravite, DMS, manyetik ve SX-EW "
            "gibi alanlar için rapor verisi yok; toplama girmez.\n"
            "- Referans kapasitesinden çok uzak ölçeklerde (0,25 kat altı, 4 kat üstü) tablo uyarı verir. Küçük bir "
            "konsantre liç devresi için tam cevher CIL referansı (Enchi) güvenilir bir alt sınır değildir: ince öğütme, "
            "uzun bekleme süresi ve yoğun siyanürleme gerekebilir.\n"
            "- İşletme gideri (OPEX) aşama bazında hesaplanmıyor."
        )

    # ---- Şablon ve girişler ----
    sablon = st.selectbox("Başlangıç şablonu", [_OZEL] + list(SABLONLAR), key="kz_sablon",
                          help="Yalnızca akış yapısını getirir. Verim ve tenör değerleri yer tutucudur.")
    if st.session_state.get("kz_sablon_yuklu") != sablon or "kz_liste" not in st.session_state:
        _sablon_yukle(sablon)
    gen = st.session_state["kz_gen"]
    if sablon != _OZEL:
        st.warning("Şablondaki verim değerleri örnek yer tutucudur, veri değildir. Kendi testlerinden gir.")

    g1, g2, g3, g4 = st.columns(4)
    metal_adi = g1.text_input("İzlenen metal", value="Au", key="kz_metal")
    birim = g2.selectbox("Tenör birimi", ["g/t", "%"], key="kz_birim")
    cevher_tpd = g3.number_input("Cevher besleme miktarı (kuru t/gün)", min_value=100.0, max_value=300_000.0,
                                 value=10_000.0, step=500.0, key="kz_tpd")
    tenor = g4.number_input(f"Besleme tenörü ({birim})", min_value=0.0001, max_value=99.0,
                            value=2.0 if birim == "g/t" else 1.0, step=0.1, format="%.4f", key=f"kz_tenor_{birim}")

    # ---- Aşamalar ----
    st.subheader("Aşamalar")
    asamalar = []
    gecerli_akimlar = [CEVHER]
    liste = st.session_state["kz_liste"]
    for i, d in enumerate(liste):
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
            besleme = c3.selectbox("Besleme akımı", gecerli_akimlar, index=gecerli_akimlar.index(varsayilan_bes),
                                   format_func=lambda k: akim_etiketi(k, _onceki(liste, asamalar)), key=besleme_key)
            c4.button("Sil", key=f"{kp}_sil", on_click=_asama_sil, args=(uid,), help="Bu aşamayı sil")
            agirlik, metal = 100.0, 100.0
            if tur in AYIRMA_TURLERI:
                p1, p2 = st.columns(2)
                agirlik = p1.number_input("Konsantreye giden ağırlık verimi (%)", min_value=0.0, max_value=100.0,
                                          value=float(d["agirlik"]) if d["tur"] == tur else 10.0, step=0.5,
                                          key=f"{kp}_{tur}_w")
                metal = p2.number_input(f"Konsantreye giden metal verimi (%)", min_value=0.0, max_value=100.0,
                                        value=float(d["metal"]) if d["tur"] == tur else 85.0, step=0.5,
                                        key=f"{kp}_{tur}_m")
            elif tur in LIC_TURLERI:
                metal = st.number_input("Metal ekstraksiyonu (%)", min_value=0.0, max_value=100.0,
                                        value=float(d["metal"]) if d["tur"] == tur else 90.0, step=0.5,
                                        key=f"{kp}_{tur}_m",
                                        help="Liç kinetiği sekmesindeki deney verisinden okuyabilirsin.")
        a = Asama(uid=uid, ad=ad.strip() or uid, tur=tur, besleme=besleme,
                  agirlik_verimi_pct=agirlik, metal_verimi_pct=metal)
        asamalar.append(a)
        gecerli_akimlar = gecerli_akimlar + akim_adlari(a)

    e1, e2 = st.columns([3, 1])
    yeni_tur = e1.selectbox("Eklenecek aşama türü", list(ASAMA_TURLERI), format_func=ASAMA_TURLERI.get,
                            key="kz_yeni_tur", label_visibility="collapsed")
    e2.button("Aşama ekle", key="kz_ekle", on_click=_asama_ekle, args=(yeni_tur,))

    if not asamalar:
        st.info("Akışta aşama yok. Yukarıdan bir aşama ekle.")
        return
    hatalar = dogrula(cevher_tpd, tenor, birim, asamalar)
    if hatalar:
        st.error("Akış hesaplanamadı:\n\n" + "\n".join(f"- {h}" for h in hatalar))
        return
    sonuc = akis_hesapla(cevher_tpd, tenor, birim, asamalar)

    # ---- Sonuçlar ----
    st.subheader("Kütle ve metal dengesi")
    m1, m2, m3 = st.columns(3)
    m1.metric(f"Toplam {metal_adi} verimi (ürüne)", f"%{sonuc['toplam_verim_pct']:.1f}")
    m2.metric("Atıkta kalan metal", f"%{sonuc['kayip_metal_pct']:.1f}")
    m3.metric("Aşama sayısı", f"{len(asamalar)}")
    if not any(a.tur in AYIRMA_TURLERI or a.tur in LIC_TURLERI for a in asamalar):
        st.info("Akışta henüz ürün veren aşama (ayırma ya da liç) yok; verim hesaplanması için en az birini ekle.")
    for u in sonuc["uyarilar"]:
        st.warning(u)
    f2 = lambda v, n=2: "-" if v is None else f"{v:,.{n}f}"
    tablo = []
    for s in sonuc["asamalar"]:
        tablo.append({
            "Aşama": s["ad"], "Tür": ASAMA_TURLERI[s["tur"]], "Besleme akımı": akim_etiketi(s["besleme"], asamalar),
            "Besleme (t/gün)": f2(s["besleme_tpd"], 0), f"Besleme tenörü ({birim})": f2(s["besleme_tenor"]),
            "Konsantre (t/gün)": f2(s["kons_tpd"], 0), f"Konsantre tenörü ({birim})": f2(s["kons_tenor"]),
            "Atık (t/gün)": f2(s["atik_tpd"], 0), f"Atık tenörü ({birim})": f2(s["atik_tenor"]),
            "Ürüne giden metal (%)": f2(s["urun_metal_pct"], 1) if s["urun_metal_pct"] else "-",
        })
    st.dataframe(pd.DataFrame(tablo), hide_index=True, width="stretch")
    try:
        st.graphviz_chart(_dot(cevher_tpd, tenor, birim, asamalar, sonuc))
    except Exception:
        st.caption("Akış şeması çizilemedi; tablo geçerlidir.")

    lic_asamalar = [s for a, s in zip(asamalar, sonuc["asamalar"]) if a.tur == "lic_cil"]
    if lic_asamalar:
        s0 = lic_asamalar[0]
        st.button(f"'{s0['ad']}' besleme miktarını ({s0['besleme_tpd']:,.0f} t/gün) Liç Kinetiği sekmesindeki CIL boyutlandırmaya aktar",
                  key="kz_aktar", on_click=_lic_aktar, args=(s0["besleme_tpd"],))

    # ---- Aşama bazlı CAPEX ----
    st.subheader("Aşama bazlı CAPEX tahmini (doğrudan maliyet)")
    st.caption("Her alan, kendi aşamasının besleme (ya da konsantre/atık) miktarında, raporlardaki doğrudan maliyetten "
               "ayrı ayrı ölçeklenir. Dolaylı maliyet ve gider payı sana bırakılır.")
    tuketilen = {a.besleme for a in asamalar}
    for a in asamalar:
        secenek = TUR_ALANLARI[a.tur]
        kons_tuk = f"{a.uid}:kons" in tuketilen
        a.alanlar = st.multiselect(
            f"{a.ad}: CAPEX alanları", options=secenek, default=varsayilan_alanlar(a, kons_tuk),
            format_func=lambda k: ALAN_TURLERI[k], key=f"kz{gen}_{a.uid}_{a.tur}_{int(kons_tuk)}_alan")
    n1, n2, n3, n4 = st.columns(4)
    alan_n = n1.number_input("Ölçekleme üsteli (n)", min_value=0.3, max_value=1.0, value=LITERATUR_USTEL, step=0.01,
                             key="kz_n", help="Genel literatür değeri (veri değil).")
    duzeltme = n2.number_input("Maliyet düzeltme çarpanı", min_value=0.1, max_value=5.0, value=1.0, step=0.01,
                               key="kz_duzeltme", help="Enflasyon ve piyasa için senin gireceğin çarpan; uygulama endeks varsaymaz.")
    dolayli = n3.number_input("Dolaylı maliyet (% doğrudan)", min_value=0.0, max_value=100.0, value=0.0, step=1.0, key="kz_dol")
    gider = n4.number_input("Gider payı (% doğrudan+dolaylı)", min_value=0.0, max_value=100.0, value=0.0, step=1.0, key="kz_gid")

    c = asama_capex(asamalar, sonuc, alan_n, duzeltme)
    satirlar = []
    for r in c["satirlar"]:
        satirlar.append({
            "Aşama": r["asama"], "Alan": r["alan"],
            "Kapasite (t/gün)": f"{r['kapasite_tpd']:,.0f} ({r['taban']})",
            "En düşük": "veri yok" if r["min_usd"] is None else f"${r['min_usd']:,.0f}",
            "En yüksek": "veri yok" if r["max_usd"] is None else f"${r['max_usd']:,.0f}",
            "Referans kapasitesine oran": r["oran"] or "-", "Referans(lar)": r["referanslar"],
        })
    if satirlar:
        st.dataframe(pd.DataFrame(satirlar), hide_index=True, width="stretch")
        carp = (1 + dolayli / 100.0) * (1 + gider / 100.0)
        t1, t2 = st.columns(2)
        t1.metric("Toplam doğrudan (en düşük referans)", f"${c['alt_usd']:,.0f}")
        t2.metric("Toplam doğrudan (en yüksek referans)", f"${c['ust_usd']:,.0f}")
        if dolayli or gider:
            st.caption(f"Dolaylı maliyet ve gider payı eklenmiş toplam: {_usd(c['alt_usd'] * carp)} - {_usd(c['ust_usd'] * carp)}")
        if c["eksik"]:
            st.warning("Bu alanlar için doğrulanmış rapor verisi yok, toplama girmedi; gerçek toplam daha yüksektir: "
                       + "; ".join(c["eksik"]))
        if c["ekstrapolasyon"]:
            with st.expander(f"Ölçek uyarısı: {len(c['ekstrapolasyon'])} alan referans kapasitesinden çok uzakta"):
                st.markdown("\n".join(f"- {u}" for u in c["ekstrapolasyon"]))
                st.caption("Güç yasası bu aralıkların dışında güvenilmez. Bu satırları kesin sayı değil, kaba büyüklük olarak oku.")
        st.caption("Referanslar farklı kapsam, bölge ve çalışma sınıfı taşır; iki uç arasındaki fark ölçek etkisi değildir. "
                   "Altar yalnızca ekipman satın alma + montajdır; Furnas, Cerro Blanco, Enchi, Cactus ve Santa Fe "
                   "raporların doğrudan maliyetidir.")


def _onceki(liste, asamalar):
    """Besleme etiketleri için o ana kadar kurulmuş aşama listesi (ad çözümlemesi)."""
    return asamalar
