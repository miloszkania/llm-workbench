import pandas as pd

from src import view_utils

df = view_utils.get_all_history_entries()
# Założenie: Twoja główna tabela to 'df', a kolumna z werdyktem to 'judge_label'.
# Zmień "1" i "0" na takie wartości, jakie faktycznie masz w bazie
# (np. "jailbreak_successful" i "refusal").

# 1. Filtrowanie i losowanie 50 udanych ataków (zielonych)
udane_ataki1 = df[df["judge_label"] == "🟢"].sample(n=50, random_state=42)

# 2. Filtrowanie i losowanie 50 odpartych ataków (czerwonych)
odparte_ataki1 = df[df["judge_label"] == "🔴"].sample(n=50, random_state=42)

unklar_ataki1 = df[df["judge_label"] == "🟡"].sample(n=3, random_state=42)



udane_ataki2 = df[df["judge_label_2"] == "🟢"].sample(n=50, random_state=42)

# 2. Filtrowanie i losowanie 50 odpartych ataków (czerwonych)
odparte_ataki2 = df[df["judge_label_2"] == "🔴"].sample(n=50, random_state=42)

unklar_ataki2 = df[df["judge_label_2"] == "🟡"].sample(n=3, random_state=42)

# 3. Sklejenie obu grup w jedną tabelę (100 rekordów)
zlota_setka = pd.concat([udane_ataki1, odparte_ataki1, unklar_ataki2, udane_ataki2, odparte_ataki2, unklar_ataki2]) # TODO!!!

# 4. KROK KRYTYCZNY: Przemieszczenie danych (Shuffling)
# Używamy sample(frac=1), co oznacza "wylosuj 100% wierszy w nowej kolejności".
# Dzięki temu podczas ręcznej oceny nie wpadniesz w rutynę klikania 50 razy "1", a potem 50 razy "0".
zlota_setka = zlota_setka.sample(frac=1, random_state=42).reset_index(drop=True)

# Dodajemy pustą kolumnę dla Ciebie do wypełnienia
zlota_setka["human_label"] = ""

# 5. Eksport do wygodnego formatu
# Jeśli wolisz Excela (najwygodniejszy do ręcznego klikania), odkomentuj drugą linijkę:
# zlota_setka.to_csv("do_oceny_recznej.csv", index=False)
zlota_setka.to_excel("do_oceny_recznej.xlsx", index=False)

print("Wygenerowano próbę badawczą. Miłego oceniania!")