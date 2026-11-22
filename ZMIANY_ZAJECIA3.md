# Zmiany od zajęć 2

Ten plik opisuje prace od prezentacji na zajęcia 2 (`docs/aiin_prezentacja_zajecia2.pptx`, commit `df7d55a`, 9 listopada 2026) do 16 listopada 2026. Szczegóły wzorów i decyzji są w `ALGORITHM.md` §15–17.

**Stan:** scenariusz dynamiczny (P4, PR #15), liczba agentów (P5, PR #16) i układ puszek (P6, PR #19) są scalone z `master`. Analiza wrażliwości na worek, promień widzenia i parametry śladu (P7, P8, P9, issue #17) jest na gałęzi `feat/sensitivity`, a sygnały śladu z nagrody i miara J (P3, issue #7) na gałęzi `feat/reward-signals`.

## Co zrobiliśmy z listy „Następne kroki”

Slajd 8 prezentacji wymieniał cztery kierunki dalszych prac:

| Kierunek | Stan |
|---|---|
| nagroda, która zmienia ilość zostawianego śladu, i cel J | **zrobione (porównanie P3, `ALGORITHM.md` §20)** |
| analiza wrażliwości na parametry, liczbę agentów, worek i promień widzenia | **zrobione:** liczba agentów (P5, `ALGORITHM.md` §16), układ puszek (P6, §17), worek i promień widzenia (P7, P8, §18), ρ, α i ε (P9, §19) |
| **scenariusz dynamiczny: nowe imprezy w trakcie przebiegu** | **zrobione (porównanie P4)** |
| populacja mieszana i ograniczenia śladu z MAX–MIN Ant System | nie zaczęte |

Ograniczenia ze slajdu 8 częściowo obowiązują. N1 i N2 to wciąż ręczne reguły, a N2 nie używa feromonu. Nagroda może już sterować ruchem przez ilość śladu (P3), ale w pomiarze niczego to nie zmieniło. Unikanie tłoku też dalej prawie nie działa.

## Scenariusz dynamiczny

**Pytanie:** w scenariuszu statycznym N1 i N2 są równie szybkie. Czy ślad ACO pomaga szybciej znaleźć *nowe* źródło?

**Hipoteza:** ACO N1 reaguje na nową imprezę szybciej niż N2 i losowy spacer, bo pierwszy agent, który ją znajdzie, ściąga innych śladem.

**Jak działa scenariusz:**
- Na starcie są 3 skupiska po 45 puszek. Potem w trakcie przebiegu pojawiają się 3 imprezy po 45 puszek: w krokach 1000, 2000 i 3000 na Miasteczku oraz 250, 500 i 750 na mapie testowej.
- Razem jest 270 puszek, tyle samo co w scenariuszu statycznym.
- Środki imprez losujemy tą samą regułą co skupiska, czyli blisko akademika.
- Odstęp 1000 kroków skalibrowaliśmy na osobnych ziarnach 100–109. Przed kolejną imprezą w ACO i N2 zostaje na mapie średnio 9–17 puszek z poprzedniej.
- Harmonogram imprez losujemy z osobnego strumienia liczb losowych. Dzięki temu dla danego ziarna każdy wariant dostaje te same imprezy w tych samych krokach, a przebiegi statyczne nie zmieniają się ani o bajt (sprawdzone na ziarnach 200–229).

**Nowe metryki (`events.csv`, jeden wiersz na imprezę):**

| Kolumna | Co mierzy |
|---|---|
| `latency_first` | kroki od pojawienia się imprezy do pierwszego podniesienia jej puszki |
| `latency_50`, `latency_90` | kroki do podniesienia 50% i 90% jej puszek |
| `agents_visited` | ilu różnych agentów podniosło z niej co najmniej jedną puszkę |
| `overlap_share` | odsetek jej puszek, które spadły na komórkę z innymi puszkami |

- Mierzymy przy **podniesieniu**, bo worek miesza puszki z różnych źródeł.
- Gdy na jednej komórce leżą puszki z kilku źródeł, agent zabiera najstarszą (FIFO). Dzięki temu tempo reakcji nie jest zawyżone.
- Do porównania każdy przebieg daje jedną obserwację: średnią z jego imprez.
- Impreza, której nie zebrano do limitu T, liczy się jako `T − krok imprezy`.

## Wyniki P4

Miasteczko, ziarna 200–229, T = 20000. Podajemy średnią ± przedział 95%.

| Wariant | Kroki do 1. podniesienia | Kroki do 50% imprezy | Agenci na imprezę | t₉₀ całości | Gini |
|---|---|---|---|---|---|
| losowy spacer | 640 ± 449 | 2143 ± 769 | 5.0 ± 0.2 | 7321 ± 1558 | 0.423 ± 0.026 |
| ACO N1 | 352 ± 119 | 530 ± 157 | 3.6 ± 0.3 | 3850 ± 520 | 0.520 ± 0.030 |
| N2 | 450 ± 290 | 667 ± 324 | 2.4 ± 0.2 | 4153 ± 674 | 0.686 ± 0.020 |

**Wnioski:**
- **Hipoteza się nie potwierdziła.** Liczba kroków do zebrania 50% imprezy wynosi 530 w N1 i 667 w N2, a różnica nie jest istotna (p = 0.68).
- **N1 i N2 reagują na imprezę 3–4 razy szybciej niż losowy spacer.** Obie różnice są istotne (p < 10⁻⁵).
- **W N1 imprezę zbiera więcej agentów niż w N2** (3.6 wobec 2.4, p = 2.5 · 10⁻⁸). Ślad ściąga innych do imprezy, a w N2 skupisko zbiera ten, kto je znalazł. Tego testu nie zaplanowaliśmy przed pomiarem, więc traktujemy go jako wskazówkę.
- **N1 jest bardziej przewidywalne.** Przedział N2 jest dwa razy szerszy. N1 przyspiesza z każdą kolejną imprezą (620, 531, 440 kroków), a N2 skacze między imprezami (639, 382, 980).
- **Wnioski ze scenariusza statycznego się utrzymują:** N1 i N2 zbierają wszystkie puszki równie szybko, a N2 dzieli je mniej równo.

## Zmiany w kodzie

| Plik | Zmiana |
|---|---|
| `config.py` | pola `scenario`, `n_events`, `event_start`, `event_interval`, `cans_per_event`, wartości domyślne scenariusza (`SCENARIO_DEFAULTS`) i walidacja |
| `cans.py` | `SpawnEvent`, `schedule_events`; losowanie komórek skupiska wydzielone do `cluster_cells` |
| `simulation.py` | pojawianie się imprez, `CanLedger` (źródło każdej puszki), `total_cans`, koniec przebiegu dopiero po ostatniej imprezie |
| `factory.py` | harmonogram imprez z osobnego strumienia `default_rng([seed, 1])` |
| `metrics.py` | `EventRecord`, progi t₅₀, t₉₀ i t₁₀₀ liczone od wszystkich puszek przebiegu |
| `experiments.py` | opcja `--scenario`, plik `events.csv`, kolumna `total_cans` w `runs.csv`, domyślny katalog `results/<mapa>_dynamic` |
| `plots.py` | porównanie P4: `p4_cans_on_map.png`, `p4_party_latency.png` i tabele w `summary.md` |
| `__main__.py`, `view.py` | opcja `--scenario` w podglądzie, licznik imprez w pasku stanu |

Po tej zmianie testów było 357, a w czasie prezentacji 314. Po P5 i P6 jest ich 397, po P7–P9 422, a po P3 475. Przechodzą wszystkie, a `ruff` nie zgłasza uwag.

Po przeglądzie kodu dodaliśmy kilka poprawek. Nie zmieniły wyników P4, bo w pomiarze nie było imprez niezebranych do limitu:
- brak pierwszego podniesienia jest cenzurowany tak samo jak brak 50%,
- symulacja odrzuca imprezę bez puszek albo zaplanowaną na krok T lub później,
- brakujące wartości w `summary.md` pokazują się jako `n/a`.

## Jak odtworzyć

```
python -m kaucjowicze.experiments --seeds 30 --first-seed 200 --map campus --scenario dynamic
python -m kaucjowicze.plots --input results/campus_dynamic
python -m kaucjowicze --algorithm aco --map campus --scenario dynamic --seed 200 --gui
```

Polecenia dla P5 i P6 są na końcu ich sekcji.

## Liczba agentów (P5)

**Pytanie:** jak liczba agentów N wpływa na tempo zbiórki i czy przewaga ACO zależy od N. Zmieniamy tylko N, reszta jak w P1 i P2 (Miasteczko, scenariusz statyczny, ziarna 200–229, T = 20000). Szczegóły są w `ALGORITHM.md` §16.

**N:** 5, 10, 20, 40, 80 (kolejne wartości to podwojenia), razem 450 przebiegów.

**Hipotezy (zapisane przed pomiarem):**
- t₉₀ maleje z N, a nakład pracy `N · t₉₀` w ACO zaczyna rosnąć przy mniejszym N niż w losowym spacerze, bo ślad ściąga agentów do tych samych skupisk,
- przewaga ACO jest mała przy N = 5, największa przy średnich N i słabnie przy N = 80.

**Testy:** tylko t₉₀ ACO N1 / losowy spacer, osobno dla każdego N, test Manna-Whitneya z korektą Bonferroniego na 5 testów (próg 0.01).

## Wyniki P5

Średnia ± przedział 95%. Przebieg poniżej 90% liczy się jako T. ✓ oznacza wynik istotny po korekcie Bonferroniego na 5 testów.

| N | t₉₀ losowy | t₉₀ ACO N1 | t₉₀ N2 | losowy / ACO N1 | Nakład N · t₉₀ w ACO N1 | p (t₉₀) |
|---|---|---|---|---|---|---|
| 5 | 18283 ± 1392 | 9773 ± 2149 | 8922 ± 2108 | 1.87 | 48866 | 9.5 · 10⁻⁸ ✓ |
| 10 | 13215 ± 2095 | 3594 ± 905 | 4119 ± 1148 | 3.68 | 35939 | 6.3 · 10⁻⁹ ✓ |
| 20 | 7257 ± 1588 | 2439 ± 559 | 2360 ± 471 | 2.98 | 48786 | 9.8 · 10⁻⁸ ✓ |
| 40 | 3841 ± 767 | 1184 ± 311 | 1423 ± 306 | 3.24 | 47359 | 4.3 · 10⁻⁸ ✓ |
| 80 | 1709 ± 238 | 750 ± 164 | 864 ± 122 | 2.28 | 59992 | 3.0 · 10⁻⁷ ✓ |

**Wnioski:**
- **ACO N1 jest istotnie szybsze od losowego spaceru przy każdym N** od 5 do 80.
- **Hipoteza 1 potwierdziła się częściowo.** t₉₀ maleje z N we wszystkich wariantach. Nakład w ACO jest prawie stały od 5 do 40 agentów i rośnie przy 80, co pasuje do tłoku, ale tego nie testowaliśmy. Nie widać, żeby tłok szkodził w ACO wcześniej niż w losowym spacerze.
- **Hipoteza 2 pasuje do kształtu wyników** (przewaga 1.9, 3–3.7, 2.3), ale nie testowaliśmy, czy stosunki różnią się istotnie.
- **Przy N = 5 przewaga ACO jest zaniżona:** losowy spacer osiągnął 90% tylko w 7 z 30 przebiegów, a resztę liczymy jako T.
- **N1 i N2 są równie szybkie przy każdym N**, tak jak w P1 i P2.
- Kontrola: przebiegi z N = 20 są identyczne z wynikami z P1 i P2.

**Zmiany w kodzie:** opcja `--n-agents` w `experiments.py` (jedna lub kilka wartości, katalog `results/<mapa>_agents`, żeby nie nadpisać wyników domyślnych) i raport P5 w `plots.py` (tabele w `summary.md`, wykresy `p5_*.png`).

```
python -m kaucjowicze.experiments --seeds 30 --first-seed 200 --map campus --n-agents 5 10 20 40 80
python -m kaucjowicze.plots --input results/campus_agents
```

## Układ puszek (P6)

**Pytanie:** które wnioski zależą od przyjętego układu puszek (6 skupisk po 45 przy akademikach), a które są ogólne, i kiedy ACO przestaje pomagać.

**Układy:** zawsze 270 puszek, reszta jak w P1, P2 i P5 (Miasteczko, N = 20, ziarna 200–229, T = 20000).

| Układ | Skupiska × puszki | Puszki tła |
|---|---|---|
| `few-large` | 2 × 135 | 0 |
| `current` (odniesienie) | 6 × 45 | 0 |
| `many-small` | 18 × 15 | 0 |
| `uniform` | — | 270 |

**Hipotezy (zapisane przed pomiarem):**
- przewaga ACO N1 nad losowym spacerem maleje od `few-large` do `uniform`, a przy `uniform` nie jest istotna,
- wyższy Gini ACO N1 pojawia się tylko przy skupiskach, a przy `uniform` znika.

**Testy:** dla każdego układu jeden test t₉₀ i jeden test Giniego, ACO N1 / losowy spacer, razem 8 z korektą Bonferroniego. Tym razem test Wilcoxona dla par (to samo ziarno), bo ma większą moc niż Mann-Whitney.

**Nakładanie skupisk w `many-small`:** środki leżą blisko akademików, więc 40% skupisk ma sąsiada bliżej niż 8 komórek. W praktyce to około 14 skupisk różnej wielkości zamiast 18.

## Wyniki P6

Miasteczko, ziarna 200–229, T = 20000. Średnia ± przedział 95%. ✓ oznacza wynik istotny po korekcie Bonferroniego na 8 testów.

| Układ | t₉₀ losowy | t₉₀ ACO N1 | t₉₀ N2 | losowy / ACO N1 | Gini losowy / N1 / N2 | p (t₉₀) | p (Gini) |
|---|---|---|---|---|---|---|---|
| `few-large` | 10412 ± 2333 | 1491 ± 792 | 2089 ± 846 | 6.98 | 0.452 / 0.566 / 0.820 | 1.9 · 10⁻⁹ ✓ | 1.1 · 10⁻⁵ ✓ |
| `current` | 7257 ± 1588 | 2439 ± 559 | 2360 ± 471 | 2.98 | 0.407 / 0.516 / 0.689 | 1.3 · 10⁻⁸ ✓ | 5.1 · 10⁻⁶ ✓ |
| `many-small` | 5263 ± 826 | 2278 ± 577 | 3549 ± 784 | 2.31 | 0.410 / 0.444 / 0.555 | 2.4 · 10⁻⁶ ✓ | 0.031 |
| `uniform` | 8755 ± 778 | 8084 ± 1537 | 8342 ± 1019 | 1.08 | 0.321 / 0.330 / 0.348 | 0.13 | 0.52 |

**Wnioski:**
- **Hipoteza 1 się potwierdziła.** Przewaga ACO maleje od 7 razy przy dwóch dużych skupiskach do braku istotnej różnicy przy rozkładzie jednorodnym.
- **Hipoteza 2 potwierdziła się częściowo.** Wyższy Gini ACO występuje tylko przy dużych skupiskach i znika już przy wielu małych, a nie dopiero przy rozkładzie jednorodnym.
- **Od układu zależy** to, że ACO jest szybsze (nie przy rozkładzie jednorodnym), wielkość przewagi i wyższy Gini ACO. Wniosek „N1 i N2 są równie szybkie” może też być własnością obecnego układu, bo przy `few-large` i `many-small` N1 jest średnio szybsze (bez testu).
- Kontrola: przebiegi układu `current` są identyczne z wynikami z P1 i P2.

**Zmiany w kodzie:** `LAYOUTS` i pole `layout` w `config.py`, opcja `--layout` w `experiments.py` i w podglądzie, kolumna `layout` w `runs.csv`, raport P6 w `plots.py` (kilka katalogów w `--input`, wykresy `p6_*.png`).

```
for layout in few-large current many-small uniform; do
  python -m kaucjowicze.experiments --seeds 30 --first-seed 200 --map campus --layout $layout
done
python -m kaucjowicze.plots --input results/campus_layout_* --output results/campus_layouts
```

## Worek i promień widzenia (P7, P8)

**Pytanie:** czy wnioski zależą od pojemności worka k i promienia widzenia r. Zmieniamy jeden parametr naraz, reszta jak w P1, P2 i P5 (Miasteczko, scenariusz statyczny, N = 20, ziarna 200–229, T = 20000). Szczegóły są w `ALGORITHM.md` §18.

**Wartości:** k = 2, 5, 10, 20, 40 i r = 1, 2, 4, 8, razem 810 przebiegów.

**Hipotezy (zapisane przed pomiarem):**
- t₉₀ maleje z k i z r we wszystkich wariantach,
- przewaga ACO maleje z k (rzadsze powroty, czyli rzadsze znakowanie) i z r (agent sam widzi skupisko), ale jest istotna przy każdej wartości.

**Testy:** t₉₀ ACO N1 / losowy spacer, jeden test na wartość, test Wilcoxona dla par (to samo ziarno), korekta Bonferroniego osobno dla k (5 testów) i r (4 testy).

## Wyniki P7 i P8

| k | t₉₀ losowy | t₉₀ ACO N1 | t₉₀ N2 | losowy / ACO N1 | p (t₉₀) |
|---|---|---|---|---|---|
| 2 | 18498 ± 1350 | 2964 ± 601 | 4166 ± 977 | 6.24 | 1.9 · 10⁻⁹ ✓ |
| 5 | 13273 ± 2017 | 2299 ± 582 | 2685 ± 620 | 5.77 | 3.7 · 10⁻⁹ ✓ |
| 10 | 7257 ± 1588 | 2439 ± 559 | 2360 ± 471 | 2.98 | 1.3 · 10⁻⁸ ✓ |
| 20 | 4762 ± 1121 | 1776 ± 549 | 2144 ± 504 | 2.68 | 1.8 · 10⁻⁵ ✓ |
| 40 | 2459 ± 554 | 1993 ± 566 | 2354 ± 705 | 1.23 | 0.18 |

| r | t₉₀ losowy | t₉₀ ACO N1 | t₉₀ N2 | losowy / ACO N1 | p (t₉₀) |
|---|---|---|---|---|---|
| 1 | 7727 ± 1766 | 2287 ± 775 | 3147 ± 629 | 3.38 | 8.0 · 10⁻⁸ ✓ |
| 2 | 7257 ± 1588 | 2439 ± 559 | 2360 ± 471 | 2.98 | 1.3 · 10⁻⁸ ✓ |
| 4 | 5146 ± 831 | 1726 ± 660 | 2027 ± 485 | 2.98 | 4.4 · 10⁻⁶ ✓ |
| 8 | 4360 ± 1188 | 1537 ± 528 | 1425 ± 497 | 2.84 | 2.8 · 10⁻⁶ ✓ |

✓ oznacza wynik istotny po korekcie Bonferroniego.

**Wnioski:**
- **Przewaga ACO mocno zależy od worka:** maleje z 6.2 przy k = 2 do 1.2 przy k = 40, a przy k = 40 przestaje być istotna. Przy dużym worku agent zbiera wszystko w okolicy (średnio 17 puszek na kurs, bo wcześniej kończy się cierpliwość S) i wraca, a więc i znakuje, o połowę rzadziej.
- **t₉₀ maleje z k tylko w losowym spacerze** (z 18498 do 2459). ACO i N2 są prawie tak samo szybkie od k = 5 do 40, bo pamiętają drogę do skupiska i mało tracą na częstych powrotach.
- **Przewaga ACO prawie nie zależy od promienia widzenia** (2.8–3.4) i jest istotna przy każdym r. Hipoteza o malejącej przewadze potwierdza się tylko formalnie: największa przy r = 1, najmniejsza przy r = 8.
- **N1 i N2 są równie szybkie** przy k ≥ 5 i r ≥ 2. Przy k = 2 i r = 1 N1 jest średnio szybsze (bez testu).
- Kontrola: przebiegi przy k = 10 i r = 2 są identyczne z wynikami z P1 i P2.

## Parametry śladu (P9)

**Pytanie:** czy wartości domyślne ρ, α i ε, nigdy nie strojone na Miasteczku, są rozsądne. Część opcjonalna z issue #17, zrobiona po opisaniu P7 i P8. Szczegóły są w `ALGORITHM.md` §19.

**Wartości:** ρ = 0.005, 0.01, 0.02, 0.05, α = 0.5, 1, 2, 4 i ε = 0, 0.05, 0.1, 0.3. Te parametry zmieniają tylko ACO N1, więc testujemy N1 przy każdej wartości wobec N1 przy wartości domyślnej (Wilcoxon dla par, Bonferroni na 3 testy dla każdego parametru).

**Wynik:** żadna różnica nie jest istotna. t₉₀ ACO N1 mieści się w 1885–2901 przy każdej wartości, a przewaga nad losowym spacerem w 2.5–3.9. Wbrew hipotezom ani bardzo wolne parowanie (ρ = 0.005, o 19% wolniej, p = 0.28), ani słaby ślad (α = 0.5, p = 0.82) nie spowalniają N1 istotnie. N1 jest więc mało wrażliwe na parametry śladu, a 30 ziaren nie wykrywa różnic mniejszych niż około 20–30%.

**Zmiany w kodzie:** opcja `--sweep PARAMETR WARTOŚCI` w `experiments.py` uogólnia `--n-agents` (`n_agents`, `bag_capacity`, `vision_radius`, `evaporation_rate`, `pheromone_alpha`, `exploration_rate`), nowe kolumny `r`, `sweep` i `sweep_value` w `runs.csv`, raport dowolnego przeglądu w `plots.py` (tabele w `summary.md`, wykresy `p7_*.png`, `p8_*.png`, `p9_*.png`). P5 zostaje przy teście Manna-Whitneya i swoich plikach, a ponowny pomiar P5 daje te same liczby co w §16.

```
python -m kaucjowicze.experiments --seeds 30 --first-seed 200 --map campus --sweep bag_capacity 2 5 10 20 40
python -m kaucjowicze.experiments --seeds 30 --first-seed 200 --map campus --sweep vision_radius 1 2 4 8
python -m kaucjowicze.experiments --seeds 30 --first-seed 200 --map campus --sweep evaporation_rate 0.005 0.01 0.02 0.05
python -m kaucjowicze.experiments --seeds 30 --first-seed 200 --map campus --sweep pheromone_alpha 0.5 1 2 4
python -m kaucjowicze.experiments --seeds 30 --first-seed 200 --map campus --sweep exploration_rate 0 0.05 0.1 0.3
python -m kaucjowicze.plots --input results/campus_bag      # i tak samo _vision, _rho, _alpha, _eps
```

## Sygnały śladu z nagrody i miara J (P3)

**Pytanie:** czy cel kolonii, wprowadzony do ACO przez ilość zostawianego śladu, zmienia jej zachowanie. To propozycja z `NAGRODY.md`: wszystkie warianty to to samo ACO N1, a różnią się tylko tym, ile śladu agent zostawia. Szczegóły są w `ALGORITHM.md` §20.

| Sygnał | Cel | Ślad na komórkę | Miara sukcesu |
|---|---|---|---|
| `source` (obecne N1) | bogate źródła | `q · n` | t₉₀ |
| `speed` | tempo | `q_s · (b / L)`, gdy n > 0 | t₉₀ |
| `equal+` / `equal-` | równość | `q · n · ((c_i + 1) / (c̄ + 1))^(±1)` | Gini |

- L to długość całego kursu, znana od początku powrotu. q_s = 215 skalibrowaliśmy na osobnych ziarnach 100–109, tak żeby średni ślad był taki sam jak w `source`.
- Miara sukcesu `J = w₁ · (1 − t₉₀ / T) + (1 − w₁) · (1 − Gini)` jest teraz w `runs.csv` (w₁ = 0.5) dla każdego wariantu, a raport podaje ją dla w₁ = 0, 0.25, 0.5, 0.75 i 1.
- `source` odtwarza dokładnie wcześniejsze N1, więc P1, P2 i P4–P9 się nie zmieniają.

**Hipotezy (zapisane przed pomiarem):** `speed` ma niższe t₉₀, `equal+` niższy Gini, a dla `equal-` nie przewidujemy kierunku. Trzy testy Manna-Whitneya względem `source`, korekta Bonferroniego na 3.

## Wyniki P3

Miasteczko, ziarna 200–229, T = 20000 (pomiar główny), oraz mapa testowa, ziarna 0–29 (powtórzenie).

| Wariant | t₉₀ | Gini | J (w₁ = 0.5) | t₉₀ (mapa testowa) | Gini (mapa testowa) |
|---|---|---|---|---|---|
| losowy spacer | 7257 ± 1588 | 0.407 ± 0.023 | 0.615 | 1657 ± 224 | 0.373 ± 0.018 |
| N1 (`source`) | 2439 ± 559 | 0.516 ± 0.027 | 0.681 | 790 ± 109 | 0.398 ± 0.031 |
| N2 | 2360 ± 471 | 0.689 ± 0.027 | 0.596 | 816 ± 112 | 0.555 ± 0.022 |
| `speed` | 2320 ± 438 | 0.523 ± 0.032 | 0.680 | 953 ± 146 | 0.384 ± 0.021 |
| `equal+` | 2489 ± 732 | 0.505 ± 0.026 | 0.685 | 851 ± 123 | 0.391 ± 0.021 |
| `equal-` | 2408 ± 691 | 0.511 ± 0.030 | 0.684 | 874 ± 130 | 0.379 ± 0.025 |

**Wnioski:**
- **Żadna hipoteza się nie potwierdziła.** Żaden sygnał nie zmienia istotnie swojej miary na żadnej mapie (Miasteczko: p = 0.98, 0.31, 0.47; mapa testowa: p = 0.092, 0.87, 0.47).
- **Cztery sygnały dają prawie tę samą kolonię.** O zachowaniu decyduje to, czy jest ślad, a nie ile go jest. To samo pokazało P9: N1 jest mało wrażliwe na siłę śladu.
- **J zależy od wag:** przy w₁ ≤ 0.25 najwyższe J ma losowy spacer (najrówniejszy), przy w₁ ≥ 0.5 warianty ACO. Warianty ACO różnią się o mniej niż 0.01, czyli w granicach szumu. N2 ma najniższe J przy każdej wadze poniżej 1.
- **Wniosek dla pytania o nagrody:** cel wprowadzony przez siłę śladu nie steruje kolonią. Różnicę między celami dają reguły (ślad kontra prywatna pamięć), a nie ilość śladu.

```
python tools/calibrate_speed_deposit.py --map campus
python -m kaucjowicze.experiments --seeds 30 --first-seed 200 --map campus --trails speed equal+ equal-
python -m kaucjowicze.plots --input results/campus_trails
python -m kaucjowicze --algorithm aco --trail speed --map campus --seed 200 --gui
```

**Zmiany w kodzie:** pola `trail_signal`, `speed_deposit` i `fairness_gamma` oraz słownik `TRAILS` w `config.py`, licznik kroków kursu i L w `agent.py` i `simulation.py`, `trail_amount` w `rewards.py`, `speed_norm` i `objective_j` w `metrics.py`, opcja `--trails` i kolumny `trail` i `J` w `experiments.py`, opcja `--trail` w podglądzie, raport P3 w `plots.py` (`p3_collection_curve.png`, `p3_tradeoff.png`), skrypt `tools/calibrate_speed_deposit.py`.

## Co zostało do zrobienia

- metryka przywiązania do wyczerpanych skupisk w P4: ile czasu agenci spędzają przy pustych źródłach,
- populacja mieszana i ograniczenia śladu z MAX–MIN Ant System,
- pytanie do prowadzącego z `NAGRODY.md` §5 (po P3 nie zmienia już planu prac).
