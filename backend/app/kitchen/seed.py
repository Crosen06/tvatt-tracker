"""Common Swedish groceries the household starts from. All start as "not at home".

Each entry: (name, category, staple, counted, match_words).
"""

SEED_ITEMS = [
    # Kyl
    ("Mjölk", "Kyl", False, False, ["mellanmjölk", "standardmjölk", "lättmjölk"]),
    ("Fil", "Kyl", False, False, ["filmjölk"]),
    ("Yoghurt", "Kyl", False, False, ["turkisk yoghurt", "grekisk yoghurt"]),
    ("Smör", "Kyl", False, False, ["smör eller margarin", "margarin"]),
    ("Ägg", "Kyl", False, True, []),
    ("Ost", "Kyl", False, False, ["riven ost", "hårdost", "lagrad ost"]),
    ("Parmesan", "Kyl", False, False, ["parmesanost", "parmigiano"]),
    ("Grädde", "Kyl", False, False, ["vispgrädde", "matlagningsgrädde"]),
    ("Crème fraiche", "Kyl", False, False, ["creme fraiche", "crème fraîche"]),
    ("Kvarg", "Kyl", False, False, []),
    ("Fetaost", "Kyl", False, False, ["feta", "salladsost"]),
    ("Mozzarella", "Kyl", False, False, []),
    ("Bacon", "Kyl", False, False, []),
    ("Skinka", "Kyl", False, False, ["kokt skinka"]),
    ("Korv", "Kyl", False, False, ["falukorv", "prinskorv"]),
    ("Köttfärs", "Kyl", False, False, ["nötfärs", "blandfärs"]),
    ("Kyckling", "Kyl", False, False, ["kycklingfilé", "kycklinglårfilé", "kycklingbröst"]),
    ("Juice", "Kyl", False, False, ["apelsinjuice"]),
    # Frys
    ("Fryst fisk", "Frys", False, False, ["torskfilé", "laxfilé", "fiskfilé"]),
    ("Frysta ärtor", "Frys", False, False, ["ärtor", "gröna ärtor"]),
    ("Frysta grönsaker", "Frys", False, False, ["wokgrönsaker"]),
    ("Frysta bär", "Frys", False, False, ["blåbär", "hallon"]),
    ("Glass", "Frys", False, False, []),
    # Skafferi
    ("Pasta", "Skafferi", False, False, ["spaghetti", "makaroner", "penne", "tagliatelle"]),
    ("Ris", "Skafferi", False, False, ["jasminris", "basmatiris"]),
    ("Krossade tomater", "Skafferi", False, True, ["krossade tomater på burk"]),
    ("Tomatpuré", "Skafferi", False, False, []),
    ("Kokosmjölk", "Skafferi", False, True, []),
    ("Buljong", "Skafferi", False, False, ["buljongtärning", "hönsbuljong", "grönsaksbuljong", "kalvfond", "fond"]),
    ("Vetemjöl", "Skafferi", True, False, ["mjöl"]),
    ("Strösocker", "Skafferi", True, False, ["socker"]),
    ("Havregryn", "Skafferi", False, False, []),
    ("Müsli", "Skafferi", False, False, ["flingor"]),
    ("Matolja", "Skafferi", True, False, ["rapsolja", "neutral olja", "olja"]),
    ("Olivolja", "Skafferi", True, False, []),
    ("Tonfisk", "Skafferi", False, True, []),
    ("Bönor", "Skafferi", False, True, ["kidneybönor", "svarta bönor", "vita bönor"]),
    ("Kikärtor", "Skafferi", False, True, []),
    ("Linser", "Skafferi", False, False, ["röda linser"]),
    ("Kaffe", "Skafferi", False, False, []),
    ("Te", "Skafferi", False, False, []),
    # Frukt & grönt
    ("Lök", "Frukt & grönt", False, False, ["gul lök", "rödlök", "schalottenlök"]),
    ("Vitlök", "Frukt & grönt", False, False, ["vitlöksklyfta"]),
    ("Potatis", "Frukt & grönt", False, False, []),
    ("Morot", "Frukt & grönt", False, False, ["morötter"]),
    ("Tomat", "Frukt & grönt", False, False, ["körsbärstomater", "cocktailtomater"]),
    ("Gurka", "Frukt & grönt", False, False, []),
    ("Paprika", "Frukt & grönt", False, False, []),
    ("Sallad", "Frukt & grönt", False, False, ["isbergssallad", "romansallad", "salladsblad"]),
    ("Citron", "Frukt & grönt", False, False, ["citronsaft"]),
    ("Banan", "Frukt & grönt", False, False, []),
    ("Äpple", "Frukt & grönt", False, False, ["äpplen"]),
    ("Purjolök", "Frukt & grönt", False, False, ["purjo"]),
    ("Broccoli", "Frukt & grönt", False, False, []),
    # Bröd
    ("Bröd", "Bröd", False, False, ["limpa", "formbröd"]),
    ("Knäckebröd", "Bröd", False, False, []),
    ("Tortillabröd", "Bröd", False, False, ["tortillas"]),
    # Kryddor
    ("Salt", "Kryddor", True, False, ["flingsalt"]),
    ("Svartpeppar", "Kryddor", True, False, ["peppar", "nymalen svartpeppar"]),
    ("Paprikapulver", "Kryddor", False, False, []),
    ("Curry", "Kryddor", False, False, ["currypulver"]),
    ("Oregano", "Kryddor", False, False, []),
    ("Soja", "Kryddor", False, False, ["japansk soja", "sojasås"]),
    ("Ketchup", "Kryddor", False, False, []),
    ("Senap", "Kryddor", False, False, []),
    # Dryck
    ("Mineralvatten", "Dryck", False, False, ["kolsyrat vatten"]),
    # Hushåll
    ("Toalettpapper", "Hushåll", False, False, []),
    ("Hushållspapper", "Hushåll", False, False, []),
    ("Diskmedel", "Hushåll", False, False, []),
    ("Tvättmedel", "Hushåll", False, False, []),
]

SEED_IGNORE = ["vatten", "kallt vatten", "ljummet vatten", "kokande vatten"]
