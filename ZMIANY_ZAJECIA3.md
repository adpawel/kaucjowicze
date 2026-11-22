# Zmiany od zajęć 2

Ten plik opisuje prace od prezentacji na zajęcia 2 (`aiin_prezentacja_zajecia2.pptx`, commit `df7d55a`, 9 listopada 2026) do 16 listopada 2026. Szczegóły wzorów i decyzji są w `ALGORITHM.md` §15–17.

**Stan:** wszystko z tego pliku jest scalone z `master`: scenariusz dynamiczny (P4, PR #15), liczba agentów (P5, PR #16) i układ puszek (P6, PR #19).

## Co zrobiliśmy z listy „Następne kroki”

Slajd 8 prezentacji wymieniał cztery kierunki dalszych prac:

| Kierunek | Stan |
|---|---|
| nagroda, która zmienia ilość zostawianego śladu, i cel J | nie zaczęte (plan w `NAGRODY.md`, porównanie P3) |
| analiza wrażliwości na parametry, liczbę agentów, worek i promień widzenia | **liczba agentów zrobiona (porównanie P5, `ALGORITHM.md` §16)**, **układ puszek zrobiony (porównanie P6, §17)**, pozostałe parametry nie zaczęte |
| **scenariusz dynamiczny: nowe imprezy w trakcie przebiegu** | **zrobione (porównanie P4)** |
| populacja mieszana i ograniczenia śladu z MAX–MIN Ant System | nie zaczęte |

Ograniczenia ze slajdu 8 nadal obowiązują. N1 i N2 to wciąż ręczne reguły: nagroda nie steruje ruchem, a N2 nie używa feromonu. Unikanie tłoku też dalej prawie nie działa.

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

Po tej zmianie testów było 357, a w czasie prezentacji 314. Po P5 i P6 jest ich 397. Przechodzą wszystkie, a `ruff` nie zgłasza uwag.

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

## Co zostało do zrobienia

- metryka przywiązania do wyczerpanych skupisk w P4: ile czasu agenci spędzają przy pustych źródłach,
- analiza wrażliwości na ρ, α, ε, worek i promień widzenia,
- pozostałe dwa kierunki z tabeli na początku pliku.
