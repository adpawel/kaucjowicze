# Kaucjowicze: plan na kolejne zajęcia

Ten dokument rozpisuje, co pokazujemy na najbliższych zajęciach i co zostaje na później. Ogólny model i literatura są w [`PLAN.md`](PLAN.md). Tutaj doprecyzowujemy założenia i funkcje nagrody. Wzory i decyzje podjęte przy implementacji zbiera [`ALGORITHM.md`](ALGORITHM.md).

**Stan obecny (`master`):** siatka z przeszkodami, punkt skupu, generator puszek w skupiskach, tymczasowa mapa testowa, podgląd w konsoli, testy i CI.
**Brakuje:** agentów, ACO, wizualizacji, funkcji nagrody, metryk i porównań.

---

## Część I: najbliższe zajęcia

Prowadzący oczekuje:
1. działającej wizualizacji,
2. działającego algorytmu,
3. ustalonych funkcji nagrody,
4. zapisanych założeń,
5. pierwszych porównań: ACO kontra losowy spacer oraz nagroda wspólna kontra indywidualna.

### 1. Założenia modelu

Wartości liczbowe to punkt startowy, będziemy je stroić. Każda jest parametrem w `SimulationConfig`.

**Świat**
| Założenie | Wartość startowa |
|---|---|
| Mapa | testowa 100×60 (prostokątne akademiki). Prawdziwa mapa MS AGH później |
| Czas | dyskretne kroki. Symulacja trwa do zebrania wszystkich puszek albo do limitu T = 3000 kroków |
| Ruch | jedna komórka na krok, 8 sąsiadów. Wejście na przeszkodę jest zabronione |
| Puszki | scenariusz statyczny: 6 skupisk po 40 puszek oraz 30 pojedynczych (razem 270) |
| Baza | jeden punkt skupu na środku mapy |
| Losowość | każde porównanie ma wspólną listę ziaren, więc warianty dostają te same mapy |

**Agent (kaucjowicz)**
| Założenie | Wartość startowa |
|---|---|
| Liczba agentów | N = 20, wszyscy startują z bazy |
| Pojemność worka | k = 10 puszek |
| Podnoszenie | jedna puszka na krok, z komórki, na której stoi agent |
| Widzenie | promień r = 2. Agent widzi puszki w okolicy i idzie do najbliższej |
| Powrót do bazy | gdy worek jest pełny albo gdy agent ma puszki i przez S = 50 kroków nie zobaczył nowej |
| Droga do bazy | najkrótsza ścieżka. Mapę odległości od bazy liczymy raz, przeszukiwaniem wszerz z uwzględnieniem przeszkód, a agent schodzi po jej gradiencie |
| Po oddaniu | agent od razu wraca na mapę (stan `SEARCHING`) |
| Stany | `SEARCHING` → `CARRYING` → oddanie puszek w bazie → `SEARCHING` |

**Feromon (ACO)**
| Założenie | Wartość startowa |
|---|---|
| Rodzaj śladu | jeden ślad „do puszek”, zostawiany przez agenta w stanie `CARRYING` w drodze do bazy |
| Ilość śladu | `q · (puszki pozostałe w okolicy źródła)`. Bogate skupisko daje mocny ślad, a wyczerpane przestaje go zostawiać |
| Parowanie | ρ = 0.02 na krok, czyli `τ ← (1 − ρ) · τ` |
| Podążanie za śladem | agent w stanie `SEARCHING` wybiera sąsiada z prawdopodobieństwem ∝ (τ + τ₀)^α. Preferuje ruch „od bazy” (rosnąca odległość na mapie odległości), żeby szedł po śladzie w stronę puszek, a nie z powrotem |
| Eksploracja | z prawdopodobieństwem ε = 0.1 losowy ruch |
| Parametry | α = 1, τ₀ = 0.01 |

**Losowy spacer (punkt odniesienia):** te same reguły worka, widzenia, powrotu i ponownego wyjścia na mapę, ale bez feromonu. Gdy agent nie widzi puszki, wykonuje losowy ruch, z niewielką skłonnością do utrzymania kierunku, żeby nie kręcił się w miejscu.

### 2. Funkcje nagrody

**Nagroda** to to, co agent stara się zmaksymalizować i co kształtuje jego zachowanie. **Metryki** (rozdział 4) mierzymy zawsze, niezależnie od nagrody. W ACO agent się nie uczy, więc nagroda decyduje o regułach: czy agent zostawia ślad i jak wybiera skupisko.

#### N1: nagroda wspólna (kooperacyjna)
- **Definicja:** `R_i = (wszystkie zebrane puszki) / N`. Zarobek jest dzielony równo, więc każdemu agentowi zależy na tempie całej grupy.
- **Zachowanie:**
  - zostawia ślad do znalezionych puszek, żeby ściągnąć do nich innych,
  - unika przepełnionych skupisk. Gdy w okolicy skupiska jest więcej agentów niż puszek do zebrania, wybór tego kierunku dostaje karę i agent szuka gdzie indziej,
  - sam też korzysta ze śladów.
- **Hipoteza:** najszybsze zbieranie całości, równy zarobek z definicji.

#### N2: nagroda indywidualna (egoistyczna)
- **Definicja:** `R_i = (puszki zebrane przez agenta i)`. Każdy zbiera jak najwięcej dla siebie.
- **Zachowanie:**
  - **nie zostawia śladu**, bo ściągałby konkurencję do swojego skupiska,
  - pamięta swoje najlepsze skupisko (pamięć prywatna) i po oddaniu puszek wraca tam najkrótszą drogą, dopóki skupisko się nie wyczerpie,
  - nie zważa na tłok, bo jeśli jest dużo puszek, to idzie tam niezależnie od innych.
- **Hipoteza:** wolniejsze zbieranie całości (brak komunikacji), ale nierówny podział. Agenci, którzy wcześnie trafili na duże skupisko, zarabiają dużo, a pozostali mało.

**Co sprawdzamy w porównaniu N1 i N2:** czy komunikacja i dzielenie się zyskiem przyspieszają zbieranie oraz ile kosztuje to najlepszych zbieraczy. Na późniejsze zajęcia zostają: mieszana populacja (część egoistów, którzy tylko korzystają z cudzych śladów) i nagroda ważona (Część II).

### 3. Pierwsze porównania (na te zajęcia)

| # | Porównanie | Warianty | Co pokazujemy |
|---|---|---|---|
| P1 | **ACO kontra losowy spacer** | ACO z nagrodą N1 / losowy spacer | krzywa zebranych puszek w czasie, czas do 50/90% puszek, długość trasy na puszkę |
| P2 | **Nagroda wspólna kontra indywidualna** | ACO N1 / agenci N2 / losowy spacer jako odniesienie | to samo co w P1 oraz rozkład puszek na agenta (wykres pudełkowy) i współczynnik Giniego |

- Każdy wariant uruchamiamy na tych samych 30 ziarnach (30 map).
- Wyniki podajemy jako średnią ± przedział ufności 95% (pasmo na krzywej).
- Istotność sprawdzamy testem Manna-Whitneya dla czasu do 90% puszek.

### 4. Metryki (dla każdego przebiegu)

- liczba puszek zebranych w każdym kroku (krzywa),
- `t_50`, `t_90`, `t_100`: kroki do zebrania 50/90/100% puszek (pusta wartość, jeśli w czasie T nie zebrano tylu),
- łączna długość tras i długość trasy na jedną puszkę,
- liczba kursów do bazy,
- puszki na agenta, z których liczymy współczynnik Giniego, minimum i maksimum.

Format CSV opisuje `PLAN.md`, rozdział 7. Dochodzi jedna kolumna `reward` (`shared` / `individual`) w `runs.csv`.

### 5. Wizualizacja (Pygame)

Wymagania na zajęcia:
- mapa: przeszkody, baza, puszki (kolor zależny od liczby),
- feromon jako mapa cieplna pod spodem, z możliwością włączenia i wyłączenia,
- agenci w kolorze zależnym od stanu: `SEARCHING` lub `CARRYING`,
- licznik kroku i zebranych puszek, nazwa wariantu,
- sterowanie: pauza (spacja), szybkość (+/−), restart z tym samym ziarnem (R),
- uruchomienie: `python -m kaucjowicze --algorithm aco --reward shared --seed 0 --gui`.

Wizualizacja **tylko czyta stan symulacji**. Symulacja musi działać bez okna (CI, eksperymenty). Pygame dodajemy jako opcjonalną zależność `[gui]`, żeby CI go nie instalowało.

### 6. Do zrobienia: podział na branche

| Branch | Zakres | Zależy od |
|---|---|---|
| `feat/agents-random` | klasa agenta, stany, worek, widzenie, mapa odległości od bazy i powrót, pętla symulacji bez okna, losowy spacer | — |
| `feat/visualization` | okno Pygame według punktu 5. Na start może rysować samą mapę z puszkami | — (agentów podpina po scaleniu `feat/agents-random`) |
| `feat/aco` | pole feromonu, zostawianie śladu, parowanie, podążanie za śladem, ε | `feat/agents-random` |
| `feat/rewards` | warianty N1 i N2: tłok w N1, pamięć prywatna i brak śladu w N2 | `feat/aco` |
| `feat/metrics-experiments` | zbieranie metryk, zapis CSV, skrypt `experiments.py` (N ziaren × warianty), skrypt wykresów (matplotlib) | `feat/agents-random` (format można przygotować wcześniej) |

Pierwsze dwa i ostatni branch mogą ruszyć równolegle od razu.

### 7. Co pokazujemy na zajęciach (scenariusz)

1. **Założenia:** krótko z tego dokumentu (punkty 1 i 2).
2. **Wizualizacja na żywo:** losowy spacer, potem ACO z włączoną mapą feromonu. Widać, jak ślady prowadzą do skupisk i znikają po ich wyczerpaniu.
3. **Nagroda N2 na żywo:** brak śladów, agenci wracają do „swoich” skupisk.
4. **Wykresy z P1 i P2:** krzywe zbierania z pasmem ufności, wykres pudełkowy puszek na agenta, tabela `t_90` i Gini z p-wartościami.
5. **Wnioski i plan dalszych prac** (Część II).

### 8. Gotowe, gdy

- [ ] `python -m kaucjowicze ... --gui` pokazuje działającą symulację dla wszystkich trzech wariantów: losowy spacer, ACO z N1, agenci N2
- [ ] symulacja bez okna przechodzi w CI, są testy agenta, feromonu i metryk
- [ ] `experiments.py` generuje CSV dla P1 i P2 (30 ziaren)
- [ ] wykresy z P1 i P2 są wygenerowane i zapisane, np. w `results/figures/` (poza repozytorium), a wybrane trafiają do prezentacji
- [ ] założenia z tego dokumentu są zgodne z kodem (wartości domyślne w `SimulationConfig`)

---

## Część II: dalsze zajęcia

Kolejności i podziału na zajęcia jeszcze nie ustalamy.

### Kolejne porównania

| Porównanie | Pytanie |
|---|---|
| **Populacja mieszana** (0/25/50/75/100% egoistów) | Czy egoiści korzystający z cudzych śladów zarabiają więcej kosztem grupy? Od jakiego odsetka współpraca się załamuje? |
| **Nagroda ważona** `R_i = w · (własne) + (1 − w) · (wspólne / N)` dla w ∈ {0, 0.25, 0.5, 0.75, 1} | Jak płynnie przejść od współpracy do egoizmu? Gdzie jest kompromis między tempem a równością (`J` z `PLAN.md` 4.2)? |
| **Wrażliwość na ρ** | Za szybkie parowanie oznacza brak pamięci, za wolne powoduje, że agenci trzymają się wyczerpanych skupisk |
| **Wrażliwość na α i ε** | Balans eksploatacji śladów i eksploracji |
| **Liczba agentów N** | Skalowanie i moment, od którego tłok szkodzi |
| **Pojemność worka k** | Mało dużych kursów kontra dużo małych |
| **Promień widzenia r** | Ile daje feromon, gdy agenci dobrze widzą |
| **Scenariusz dynamiczny** („imprezy” w trakcie) | Czy kolonia porzuca wyczerpane skupiska i znajduje nowe? |
| **Liczba i położenie punktów skupu** | Jeden centralny kontra kilka na obrzeżach |
| **Rozkład puszek** | Mało dużych skupisk, dużo małych skupisk, rozkład jednorodny (kiedy ACO przestaje pomagać) |
| **MAX–MIN** (τ_min/τ_max) kontra zwykłe parowanie | Czy ograniczenia śladu zapobiegają zbyt szybkiemu skupieniu się na jednym skupisku? |
| **Mapa testowa kontra prawdziwa mapa MS AGH** | Czy wnioski przenoszą się na realny układ budynków? |

### Pozostałe prace
- przeniesienie prawdziwej mapy MS AGH (budynki, ścieżki, położenie punktu skupu) i mapa jako tło wizualizacji,
- scenariusz dynamiczny,
- skrypt uruchamiający wszystkie eksperymenty jednym poleceniem i odtwarzający wykresy do sprawozdania,
- dopracowanie demo,
- sprawozdanie: założenia, metodologia, wyniki, wnioski, ograniczenia modelu.
