# Kaucjowicze — plan projektu

**Przedmiot:** Algorytmy Inteligentne Inspirowane Naturą
**Temat:** Symulacja kaucjowiczy zbierających puszki na mapie Miasteczka Studenckiego AGH algorytmem ACO

---

## 1. Temat i cel

| Element | Opis |
|---|---|
| **Agenci** | Mrówki-kaucjowicze |
| **Cel** | Puszki rozmieszczone w klastrach |
| **Baza** | Punkt skupu |
| **Komunikacja** | Ślad feromonowy wskazujący miejsca z dużą liczbą puszek |

**Cel projektu:** pokazać na danych, że agenci komunikujący się śladem feromonowym zbierają puszki szybciej niż agenci poruszający się losowo.

## 2. Uzasadnienie

- **Problem na kampusie.** Po imprezach, np. w piątkowe wieczory pod akademikami, puszki rozsypują się po Miasteczku, a kaucja sprawia, że opłaca się je zbierać. Nikt nie wie, gdzie jest ich najwięcej, więc zbieranie jest chaotyczne i wolne.
- **Ten sam problem poza kampusem.** Szukanie rozproszonych zasobów bez centralnego sterowania to zadanie m.in. dla rojów robotów i zbiórki odpadów. Kampus jest naszym modelem testowym.
- **Mierzalny efekt.** Mierzymy liczbę puszek zebranych w czasie oraz długość tras. ACO porównujemy z losowym spacerem na tych samych mapach.

## 3. Model symulacji

### 3.1 Środowisko
- Siatka 2D odwzorowująca Miasteczko Studenckie AGH. Akademiki i inne budynki są przeszkodami.
- Punkt skupu jest bazą: jeden lub kilka punktów (parametr).
- Puszki rozmieszczone są w klastrach, najczęściej pod akademikami, oraz pojedynczo jako szum tła.

### 3.2 Scenariusze rozmieszczenia puszek
1. **Statyczny (podstawowy).** Wszystkie puszki generujemy na starcie. Symulacja trwa do zebrania wszystkich puszek albo do upływu czasu T.
2. **Dynamiczny (rozszerzenie).** W trakcie symulacji pojawiają się nowe klastry, czyli „imprezy” w losowych akademikach. Parametry: częstotliwość, wielkość i miejsce klastrów. Ten scenariusz sprawdza, czy kolonia potrafi porzucić wyczerpane źródła i znaleźć nowe (rola parowania feromonu).

### 3.3 Agent (kaucjowicz)
- **Worek o pojemności k puszek** (parametr, np. k = 10).
- Maszyna stanów:
  ```
  SEARCHING ──(bag full or no cans nearby)──► CARRYING ──(reached base, dropped cans)──► SEARCHING
  ```
- **Po oddaniu puszek agent wraca na mapę** i zbiera dalej, aż skończą się puszki albo minie czas T.
- W stanie `CARRYING` agent wraca do bazy najkrótszą drogą (lub za śladem „do bazy”) i zostawia ślad ścieżki.

### 3.4 Feromony
- **Ślad „do puszek”:** zostawiany w drodze powrotnej z puszkami. Jego intensywność rośnie z liczbą zebranych puszek, czyli z jakością źródła.
- **Ślad „do bazy”** (opcjonalnie): zostawiany podczas szukania i ułatwiający powrót.
- **Parowanie** ze współczynnikiem ρ, opcjonalnie z dyfuzją na sąsiednie komórki.
- **Wybór kierunku:** prawdopodobieństwo ∝ τ^α · η^β. τ to feromon, a η to heurystyka, np. odległość lub kierunek. Dodatkowo ε-eksploracja, czyli losowy ruch z prawdopodobieństwem ε.
- Opcjonalnie ograniczenia τ_min / τ_max według MAX–MIN Ant System, żeby kolonia nie utknęła na jednym źródle.

### 3.5 Baseline
- **Losowy spacer:** te same reguły worka, powrotu do bazy i ponownego wyjścia na mapę, ale bez feromonu.

## 4. Ocena algorytmu

### 4.1 Metryki zbierane w każdym przebiegu
- krzywa liczby puszek zebranych w czasie,
- czas do zebrania 50% / 90% / 100% puszek,
- łączna długość tras wszystkich agentów oraz długość trasy na zebraną puszkę,
- liczba kursów do bazy,
- liczba puszek zebranych przez każdego agenta.

### 4.2 Warianty funkcji celu
Porównujemy trzy podejścia do oceny jakości algorytmu:

| Wariant | Co optymalizujemy | Miara |
|---|---|---|
| **A: szybkość** | tempo zbierania przez całą kolonię | czas do zebrania X% puszek / liczba puszek zebranych w czasie T |
| **B: równomierność** | sprawiedliwy podział puszek między zbieraczy | współczynnik Giniego (lub odchylenie standardowe) liczby puszek na agenta |
| **C: kombinacja** | kompromis między A i B | `J = w1 · szybkość_norm + w2 · (1 − Gini)`, z analizą wpływu wag w1, w2 |

**Kolejność prac:**
1. Zaczynamy od wariantu **A**, bo bezpośrednio odpowiada celowi projektu (ACO kontra losowy spacer).
2. Wariant **B** początkowo tylko raportujemy jako metrykę, bez optymalizowania.
3. Następnie wprowadzamy wariant **C** i ewentualnie mechanizm wpływający na równomierność, np. odpychanie agentów od zatłoczonych klastrów. Porównujemy, jak wybór funkcji celu zmienia zachowanie kolonii.

> Funkcje **nagrody** agentów (wspólna kontra indywidualna), które kształtują ich zachowanie, oraz plan pierwszych porównań opisuje [`MILESTONES.md`](MILESTONES.md). Miary A/B/C powyżej służą do oceny każdego wariantu.

### 4.3 Protokół eksperymentów
- ACO i baseline uruchamiamy na tych samych mapach i z tymi samymi ziarnami losowania.
- Wykonujemy N powtórzeń dla każdej konfiguracji (np. N = 30).
- Wyniki podajemy jako średnią ± przedział ufności 95%.
- Istotność różnic sprawdzamy testem statystycznym, np. Manna-Whitneya.

## 5. Eksperymenty

1. **ACO kontra losowy spacer** w scenariuszu statycznym (eksperyment główny).
2. **Analiza wrażliwości** na:
   - współczynnik parowania ρ,
   - wagi α / β oraz ε,
   - pojemność worka k,
   - liczbę agentów.
3. **Scenariusz statyczny kontra dynamiczny**: adaptacja śladów do nowych źródeł.
4. **Porównanie funkcji celu A / B / C.**

## 6. Zakres prac i etapy

Stan na 22 listopada 2026. Szczegóły zmian od zajęć 2 opisuje [`ZMIANY_ZAJECIA3.md`](ZMIANY_ZAJECIA3.md).

### Etap 1: Inicjalizacja
- [x] Siatka z akademikami jako przeszkodami (mapa MS AGH, `ALGORITHM.md` §13)
- [x] Generator puszek w klastrach (scenariusz statyczny)
- [x] Agenci z losowym ruchem, workiem k i powrotem do bazy (baseline)
- [x] Podstawowa wizualizacja

### Etap 2: Wdrożenie ACO
- [x] Pole feromonowe (NumPy)
- [x] Powrót do bazy najkrótszą drogą i zostawianie śladu
- [x] Wybór kierunku na podstawie feromonu (α, ε; bez η i β, zob. `ALGORITHM.md` §4)

### Etap 3: Optymalizacja i dane
- [x] Parowanie śladów (dyfuzji nie wdrożyliśmy)
- [ ] Balans eksploracji i eksploatacji (ε jest w kodzie, analiza wrażliwości na ρ, α i ε nie jest zaczęta)
- [x] Zapis wyników do CSV
- [x] Metryki wariantów A i B
- [ ] Metryka wariantu C (`J`): kolumna jest pusta, propozycja w [`NAGRODY.md`](NAGRODY.md)
- [x] Scenariusz dynamiczny (porównanie P4, `ALGORITHM.md` §15)

### Etap 4: Finalizacja i raport
- [x] Demo symulacji (okno Pygame, `--gui`)
- [x] Skrypty generujące wykresy z CSV (`kaucjowicze.plots`)
- [ ] Sprawozdanie

**Cel końcowy:** wykazać na wykresach, że zbieranie z ACO jest szybsze niż losowy spacer.

## 7. Format danych (CSV)

**Plik przebiegów (`runs.csv`):** jeden wiersz na przebieg
`run_id, seed, algorithm (aco/random), reward, scenario, map, n_agents, k, rho, alpha, beta, eps, max_steps, initial_cans, steps, t_50, t_90, t_100, cans_at_T, total_path_length, path_per_can, trips, gini, cans_min, cans_max, J, total_cans, layout`

Kolumny spoza pierwotnego planu i kolumny, które zostają puste (`beta`, `J`), opisuje `ALGORITHM.md` §11. `layout` jest pusta, gdy przebieg nie używa nazwanego układu puszek (§17).

**Plik szeregu czasowego (`timeline.csv`):** jeden wiersz na krok czasu
`run_id, step, cans_collected, cans_on_map, agents_searching, agents_carrying`

**Plik agentów (`agents.csv`):** jeden wiersz na agenta w przebiegu
`run_id, agent_id, cans, path_length, trips`

**Plik imprez (`events.csv`):** jeden wiersz na imprezę w przebiegu scenariusza dynamicznego (w statycznym sam nagłówek)
`run_id, event_id, spawn_step, x, y, cans, overlap_share, latency_first, latency_50, latency_90, picked_up, agents_visited`

W `runs.csv` kolumna `total_cans` to puszki z całego przebiegu (startowe i z imprez), a `initial_cans` tylko te ze startu. Progi t₅₀, t₉₀ i t₁₀₀ liczymy od `total_cans`.

## 8. Narzędzia

| Narzędzie | Zastosowanie |
|---|---|
| Python + NumPy | symulacja agentów i pola feromonowego na siatce |
| Pygame | okno wizualizacji z ortofotomapą MS AGH albo zwykłą mapą jako tłem (opcjonalna zależność `[gui]`) |
| CSV + pandas, matplotlib, SciPy | zapis przebiegów, wykresy i testy statystyczne do sprawozdania (opcjonalna zależność `[analysis]`) |
| Git i GitHub | wersjonowanie kodu, skryptów i raportu |

**Sprzęt:** wystarczą zwykłe laptopy, bez karty graficznej i dodatkowego sprzętu. Całość piszemy w jednym języku.

**Język aplikacji: angielski.** Po angielsku piszemy:
- kod, czyli nazwy zmiennych, funkcji, klas, modułów i plików,
- komentarze i docstringi,
- komunikaty w aplikacji: interfejs wizualizacji, logi, komunikaty błędów i wyjście w konsoli,
- nazwy kolumn w plikach CSV oraz etykiety i legendy wykresów,
- commity i README repozytorium.

Po polsku zostają tylko dokumenty projektowe (ten plan) i sprawozdanie.

## 9. Otwarte kwestie

Kwestie rozstrzygnięte mają odnośnik do miejsca, w którym zapisano decyzję.

- ~~Skala siatki i sposób przeniesienia mapy MS AGH (rozdzielczość, które budynki uwzględnić)~~: komórka 3 m, mapa 100 × 91 z OpenStreetMap (`ALGORITHM.md` §13)
- ~~Liczba i rozmieszczenie punktów skupu~~: jeden punkt w środku mapy, położenie umowne (`MILESTONES.md` 1, `ALGORITHM.md` §13). Porównanie kilku punktów skupu nie jest zaczęte (`MILESTONES.md`, Część II)
- ~~Liczba agentów i domyślne wartości parametrów (k, ρ, α, β, ε, T)~~: `MILESTONES.md` 1 i tabela oznaczeń w `ALGORITHM.md`. Bez β (§4), T = 20000 na Miasteczku (§13). Wpływ liczby agentów: porównanie P5 (§16)
- ~~Definicja „braku puszek w okolicy” (promień widzenia agenta)~~: r = 2 oraz powrót po S = 50 krokach bez nowej puszki (`MILESTONES.md` 1)
- Wagi w1, w2 w wariancie C: nadal otwarte, propozycja w [`NAGRODY.md`](NAGRODY.md)
- Podział zadań w zespole

## 10. Literatura

### Podstawowe źródła

| Autorzy | Rok | Praca | Wkład |
|---|---|---|---|
| Goss, Aron, Deneubourg, Pasteels | 1989 | Self-organized shortcuts in the Argentine ant. *Naturwissenschaften* 76: 579–581 | Eksperyment z podwójnym mostem |
| Dorigo, Maniezzo, Colorni | 1996 | Ant System: Optimization by a colony of cooperating agents. *IEEE Trans. SMC-B* 26(1): 29–41 | Pierwszy algorytm ACO |
| Dorigo, Gambardella | 1997 | Ant Colony System: A cooperative learning approach to the TSP. *IEEE Trans. Evol. Comput.* 1(1): 53–66 | ACS: eksploracja i eksploatacja |
| Stützle, Hoos | 2000 | MAX–MIN Ant System. *Future Generation Computer Systems* 16(8): 889–914 | Ograniczone ślady feromonu |
| Dorigo, Stützle | 2004 | *Ant Colony Optimization*. MIT Press | Monografia |
| Dorigo, Birattari, Stützle | 2006 | Ant colony optimization: artificial ants as a computational intelligence technique. *IEEE Comput. Intell. Mag.* 1(4): 28–39 | Przegląd wariantów i zastosowań |

### Nowsze i podobne prace

| Autorzy | Rok | Praca | Związek z projektem |
|---|---|---|---|
| Talamali, Bose, Haire, Xu, Marshall, Reina | 2019 | Sophisticated collective foraging with minimalist agents: a swarm robotics test. *Swarm Intelligence* 14 | Zbieranie z wirtualnymi feromonami, symulacje i do 200 robotów |
| Font Llenas, Talamali, Xu, Marshall, Reina | 2018 | Quality-sensitive foraging by a robot swarm through virtual pheromone trails. *ANTS 2018* | Wybór źródeł o różnej jakości za pomocą feromonu |
| Reed, Evering | 2012 | An ant colony algorithm for recycling waste collection. *BIOMA 2012*: 221–230 | Podobna motywacja (surowce wtórne), ale to routing pojazdów |
| Akhtar | 2019 | Evolution of Ant Colony Optimization Algorithm: A Brief Literature Review. arXiv:1908.08007 | Przegląd po 2010: problemy dynamiczne, hybrydy, równoległość |

### Wnioski z literatury dla projektu
- **Podwójny most (1989):** prawie cała kolonia wybiera krótszą gałąź, ale niewielki odsetek nadal używa dłuższej. Dlatego potrzebujemy ε-eksploracji.
- **Rola parowania:** zbyt silne parowanie zabija eksplorację, a zbyt słabe sprawia, że kolonia przestaje szukać nowych źródeł. Ma to szczególne znaczenie w scenariuszu dynamicznym.
