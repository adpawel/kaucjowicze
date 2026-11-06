# Kaucjowicze: problem z nagrodami i warianty śladu

Ten dokument opisuje, dlaczego obecne funkcje nagrody nie określają tego, do czego dążą agenci, oraz proponuje warianty, które to zmieniają. Ogólny model jest w [`PLAN.md`](PLAN.md), obecne N1 i N2 w [`MILESTONES.md`](MILESTONES.md), a wzory i pomiary w [`ALGORITHM.md`](ALGORITHM.md).

**Status: propozycja.** Nic z sekcji 3 i 4 nie jest zaimplementowane ani zmierzone.

---

## 1. Co jest nie tak

1. **Nagroda nie steruje zachowaniem.** `agent_rewards` (`rewards.py`) wywołuje tylko `__main__.py`, po przebiegu, żeby wypisać wynik. Zmiana wzoru nie zmienia żadnego ruchu agenta. Zachowania N1 i N2 są napisane ręcznie.
2. **„Dzielenie się” w N1 istnieje tylko na papierze.** Każdy agent nosi własny worek, a `cans_collected` rośnie o to, co sam oddał (`simulation.py`, `_deposit`).
3. **P2 nie porównuje dwóch celów tego samego algorytmu.** N2 nie ma feromonu, więc nie jest ACO. P2 mierzy głównie ślad kontra prywatna pamięć (`ALGORITHM.md`, punkt 10).
4. **Unikanie tłoku, jedyna reguła odróżniająca N1 od zwykłego ACO, prawie nie działa.** Włącza się przy 0,44% decyzji o śladzie (`ALGORITHM.md`, punkt 10).
5. **Sukces nie jest zdefiniowany jednoznacznie.** Warianty A i B z `PLAN.md` 4.2 są mierzone, ale `J` (wariant C) nie jest policzone: kolumna jest pusta, nie ma wag ani definicji `szybkość_norm`.
6. **Hipoteza o szybszym N1 się nie potwierdziła.** t₉₀ wynosi 790 ± 109 wobec 816 ± 112 w N2, p = 0.70 (`ALGORITHM.md`, punkt 12).

**Zastrzeżenie:** wstępny opis projektu (PDF) nie wspomina o nagrodach, a `MILESTONES.md` ma tylko „ustalone funkcje nagrody”, bez cytatu. Nie wiemy, co dokładnie miał na myśli prowadzący, dlatego sekcja 5 zawiera pytanie do niego. Obecne N1 i N2 oraz wyniki P1 i P2 pozostają poprawne jako pomiary niezależnie od odpowiedzi.

## 2. Pomysł

Nagroda ma wchodzić do algorytmu tam, gdzie w ACO robi to naturalnie: przez ilość śladu. W klasycznym Ant System `Δτ = Q / L`, czyli lepsze rozwiązanie daje więcej feromonu. Agent nadal się nie uczy, ale definicja sukcesu realnie kieruje kolonią.

Wszystkie warianty używają tego samego `AcoPolicy`, a różnią się tylko sygnałem w `_lay_trail` (`simulation.py`). Porównanie mierzy więc wyłącznie wpływ celu.

## 3. Warianty

| Wariant | Cel | Ślad na komórkę Δτ | Hipoteza | Miara sukcesu |
|---|---|---|---|---|
| `source` (obecny N1) | bogate źródła | `q · n` | punkt odniesienia | t₉₀ |
| `speed` | tempo | `q_s · (b / L) · [n > 0]` | kolonia woli bliskie i bogate źródła, t₉₀ niższe | t₉₀ |
| `equal+` | równość | `q · n · w_i`, γ = +1 | bogaci mocniej ściągają innych do swoich źródeł, Gini niższy | Gini |
| `equal−` | równość | `q · n · w_i`, γ = −1 | bogaci słabiej znakują, więc rzadziej skupiają na sobie kolonię; może jednak pogorszyć Gini | Gini |

**Oznaczenia**

- `n`: puszki widziane przy źródle po ostatnim podniesieniu (`agent.source_cans`).
- `b`: puszki w worku.
- `L`: pełna długość kursu, czyli kroki od wyjścia z bazy + `d(c)` w chwili rozpoczęcia powrotu. Odległość `d` agent zna z mapy odległości, więc `L` jest znane już przy pierwszym znakowaniu i pozostaje stałe przez cały powrót.
- `w_i = ((c_i + 1) / (c̄ + 1))^γ`: `c_i` to puszki oddane przez agenta, a `c̄` to średnia kolonii. Na starcie `w_i = 1`.

**Czemu równość ma dwa warianty.** Intuicja mówi, że bogaty agent powinien zostawiać słabszy ślad (`equal−`), ale ślad to także informacja dla biedniejszych. Słabszy ślad może więc pogorszyć podział, a mocniejszy (`equal+`) go poprawić. Nie umiemy tego rozstrzygnąć bez pomiaru, a oba kierunki opisuje jeden parametr γ.

**Pułapki**

- **Czynnik `[n > 0]` w `speed`.** Bez niego agent, który zabrał ostatnią puszkę, znakowałby wyczerpane źródło. Obecnie `n = 0` samo wygasza ślad (`ALGORITHM.md`, punkt 2).
- **Skala `q_s`.** Szacunkowo `b / L` to rząd 0.1, a `n` to rząd 10, przy progu τ₀ = 0.01. Z tym samym `q` ślad `speed` byłby około 100 razy słabszy, a porównanie mierzyłoby siłę śladu, a nie cel. `q_s` kalibrujemy tak, by średnie Δτ było równe temu z `source`, na osobnych ziarnach (100–109), a nie na ziarnach testowych 0–29.
- **Szum w `L`.** Długość kursu zawiera przypadkowe błądzenie, więc `L` mierzy też szczęście w szukaniu, a nie tylko odległość źródła. Wyniki `speed` trzeba czytać z tym zastrzeżeniem.

**Uproszczenie modelu:** `c̄` to wiedza globalna, której pojedynczy agent w rzeczywistości by nie miał. Dopuszczamy ją, bo nagroda wspólna i tak zakłada znajomość puli.

### Definicja sukcesu (wariant C)

```
szybkość_norm = 1 − t₉₀ / T      (przebieg poniżej progu: t₉₀ = T, więc 0)
J = w₁ · szybkość_norm + w₂ · (1 − Gini),   w₂ = 1 − w₁
```

Kolumna `J` w `runs.csv` przyjmuje w₁ = 0.5, a analiza obejmuje w₁ ∈ {0, 0.25, 0.5, 0.75, 1}. `J` liczymy dla wszystkich wariantów, także losowego spaceru i N2. To, który wariant jest „najlepszy”, zależy więc jawnie od przyjętych wag.

N2 i losowy spacer zostają bez zmian jako odniesienie.

## 4. Plan wdrożenia

Osobna gałąź `adpawel/feat/reward-signals`, po scaleniu `feat/metrics-experiments`. Najpierw testy czerwone, potem implementacja. Decyzje i pomiary trafiają do `ALGORITHM.md` na tej samej gałęzi.

1. `config.py`: `trail_signal` (domyślnie `source`), `speed_deposit` (q_s), `fairness_gamma`.
2. `agent.py`: licznik kroków kursu i zapamiętane `L`, zerowane w `_deposit`. Licznik rośnie niezależnie od sygnału i nie losuje liczb, więc nie zmienia przebiegów `source`.
3. `simulation.py`: `_lay_trail` bierze Δτ z nowej funkcji `trail_amount(agent, config, mean_cans)` w `rewards.py`. `L` zapamiętujemy w jednym miejscu dla obu przejść do `CARRYING` w `_search`: pełny worek i koniec cierpliwości.
4. `factory.py`, `__main__.py`: przekazanie sygnału w konfiguracji, opcja `--trail`.
5. `metrics.py`: `J` i `szybkość_norm`. `experiments.py`: nowe warianty, kolumna `trail` w `runs.csv`.
6. `plots.py`: porównanie P3 (cztery warianty): krzywe, wykres kompromisu t₉₀ kontra Gini, tabela `J` dla wag, testy Manna-Whitneya względem `source`. Istniejące warianty zachowują kolory, a nowe sprawdzamy `validate_palette.js`.

**Testy:** znane wartości Δτ dla każdego sygnału, brak śladu przy `n = 0` we wszystkich wariantach, poprawne `L` na korytarzu z `tests/test_metrics.py`, znane wartości `J` oraz przebieg poniżej progu.

**Weryfikacja:** `source` musi odtworzyć dokładnie N1 z `ALGORITHM.md`, punkt 12 (t₅₀ 308, t₉₀ 790, Gini 0.398, pełna zbiórka 29/30). Inny wynik oznacza, że zmiana naruszyła bazowy przebieg. Następnie pełny eksperiment na ziarnach 0–29, `pytest` i `ruff`.

Wynik negatywny też jest wynikiem: jeśli sygnały nie zmienią istotnie t₉₀ ani Giniego, zapisujemy to wprost.

## 5. Pytanie do prowadzącego

> Czy nagroda ma być kryterium oceny kolonii, czy ma wpływać na zachowanie agentów?

- **Tylko kryterium:** wystarczy policzyć `J` i jasno opisać sukces. Warianty śladu są opcjonalne.
- **Wpływ na zachowanie:** wdrażamy sekcję 4. Warto też dopytać, czy N2 ma zostać jako porównanie, skoro nie jest ACO.

**Co mówimy na zajęciach do czasu odpowiedzi:** cel kolonii to jak najszybsze zebranie puszek, sukces mierzymy przez t₉₀, a N1 i N2 to ręcznie napisane reguły inspirowane tymi nagrodami.
