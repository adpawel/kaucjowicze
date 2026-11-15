# Zmiany od zajęć 2

Ten plik opisuje prace od prezentacji na zajęcia 2 (`aiin_prezentacja_zajecia2.pptx`, commit `df7d55a`, 9 listopada 2026) do 15 listopada 2026. Szczegóły wzorów i decyzji są w `ALGORITHM.md` §15.

**Stan:** zmiany są na gałęzi `adpawel/feat/dynamic-scenario` (PR #15) i nie są jeszcze scalone z `master`.

## Co zrobiliśmy z listy „Następne kroki”

Slajd 8 prezentacji wymieniał cztery kierunki dalszych prac:

| Kierunek | Stan |
|---|---|
| nagroda, która zmienia ilość zostawianego śladu, i cel J | nie zaczęte (plan w `NAGRODY.md`, porównanie P3) |
| analiza wrażliwości na parametry, liczbę agentów, worek i promień widzenia | nie zaczęte |
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

Testów jest teraz 357, a w czasie prezentacji było ich 314. Przechodzą wszystkie, a `ruff` nie zgłasza uwag.

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

## Co zostało do zrobienia

- metryka przywiązania do wyczerpanych skupisk w P4: ile czasu agenci spędzają przy pustych źródłach,
- pozostałe trzy kierunki z tabeli na początku pliku.
