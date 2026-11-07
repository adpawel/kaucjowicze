# Kaucjowicze: decyzje algorytmiczne

Ten dokument zbiera wzory i decyzje matematyczne, które zapadły przy implementacji, razem z uzasadnieniem. [`PLAN.md`](PLAN.md) opisuje ogólny model, a [`MILESTONES.md`](MILESTONES.md) założenia i wartości startowe. Tutaj trafia to, co te dokumenty zostawiły otwarte, oraz miejsca, w których kod od nich odchodzi.

Nową decyzję dopisujemy w tej samej gałęzi, która ją wprowadza.

**Oznaczenia**

| Symbol | Parametr w `SimulationConfig` | Wartość | Znaczenie |
|---|---|---|---|
| τ(c) | — | — | feromon na komórce c |
| d(c) | — | — | liczba kroków z c do najbliższej bazy (przeszukiwanie wszerz) |
| q | `trail_deposit` | 1.0 | siła śladu na jedną puszkę |
| ρ | `evaporation_rate` | 0.02 | parowanie na krok |
| α | `pheromone_alpha` | 1.0 | wykładnik wagi śladu |
| τ₀ | `pheromone_base` | 0.01 | waga komórki bez śladu |
| ε | `exploration_rate` | 0.1 | prawdopodobieństwo losowego ruchu |
| r | `vision_radius` | 2 | promień widzenia (odległość Czebyszewa) |
| p | `direction_persistence` | 0.5 | skłonność do utrzymania kierunku |
| R | `crowd_radius` | 3 | połowa szerokości okna, w którym agent sprawdza tłok |
| λ | `crowd_penalty` | 0.0 | mnożnik śladu przed tłokiem (1 wyłącza unikanie tłoku) |

Wartości q, p, R i λ nie pochodzą z `MILESTONES.md` (p ustalono w `feat/agents-random`, q w `feat/aco`, R i λ w `feat/rewards`). Pozostałe są z tego dokumentu.

---

## 1. Ruch i odległość

Ruch odbywa się w 8-sąsiedztwie, a każdy ruch, także po skosie, kosztuje jeden krok. Odległość na otwartej mapie to więc odległość Czebyszewa, a nie euklidesowa: przejście po skosie nie jest droższe.

Mapę d liczymy raz, bo przeszkody się nie zmieniają. Agent w stanie `CARRYING` idzie na sąsiada o najmniejszym d, a remisy rozstrzyga stała kolejność `NEIGHBOURS`. Kierunek powrotu jest przez to deterministyczny, z czego korzysta punkt 4.

## 2. Zostawianie śladu

Agent w stanie `CARRYING`, opuszczając komórkę c:

```
τ(c) ← τ(c) + q · n
```

gdzie n (`source_cans`) to liczba puszek w oknie o promieniu r wokół agenta, policzona **zaraz po ostatnim podniesieniu puszki**.

| Decyzja | Uzasadnienie |
|---|---|
| n liczymy po podniesieniu, więc zabrana puszka się nie liczy | Kto zabrał ostatnią puszkę, ma n = 0 i nie zostawia śladu. Wyczerpane źródło samo przestaje wabić, a pojedyncze puszki tła nie tworzą ścieżek |
| n to zapamiętana wartość, nieaktualizowana w drodze | Agent wie tylko to, co widział. Ślad nie korzysta z wiedzy o stanie źródła, którego agent już nie widzi |
| Znakujemy komórkę opuszczaną, a nie tę, na którą agent wchodzi | Ślad obejmuje samo źródło i nie obejmuje bazy, na której jest niepotrzebny |
| n zerujemy po oddaniu puszek | Następny kurs nie dziedziczy siły śladu z poprzedniego |

n liczy tylko puszki, do których da się dojść bez wychodzenia poza okno (`seen_cans`), czyli te same, które agent widzi przy szukaniu (`first_step_to_nearest_can`). Pierwotnie była to zwykła suma w oknie, licząca też puszki za cienką ścianą. Na mapie testowej obie wersje dają identyczne przebiegi, a na mapie kampusu różnią się przy około 3% podniesień (punkt 13).

## 3. Parowanie

Po ruchu wszystkich agentów, raz na krok, na całej mapie:

```
τ ← (1 − ρ) · τ
```

Parowanie następuje po zostawieniu śladu, więc świeży ślad paruje już w tym samym kroku.

Przy ρ = 0.02 okres połowicznego zaniku to ln 2 / −ln(1 − ρ) ≈ 34 kroki. Ślad o sile 5 spada do τ₀ po około 308 krokach. Na mapie testowej najdalsza komórka jest 50 kroków od bazy, więc ślad spokojnie przeżywa drogę tam i z powrotem.

## 4. Wybór kierunku

Agent w stanie `SEARCHING`, który nie widzi puszki, wybiera ruch tak (dla komórki c i jej wolnych sąsiadów n):

1. Liczymy ślad prowadzący od bazy:
   ```
   τ_out(n) = τ(n)   jeśli d(n) > d(c)
   τ_out(n) = 0      w przeciwnym razie
   ```
2. Jeśli max τ_out(n) ≤ τ₀: ruch jak w losowym spacerze (punkt 5). ε nie ma tu zastosowania.
3. W przeciwnym razie z prawdopodobieństwem ε: jednostajnie losowy sąsiad.
4. W pozostałych przypadkach sąsiad n z prawdopodobieństwem:
   ```
   P(n) ∝ (τ_out(n) + τ₀)^α
   ```

W kodzie podstawy dzielimy przed potęgowaniem przez największą z nich: b(n) = τ_out(n) + τ₀, a waga to (b(n) / max b)^α. Prawdopodobieństwa są te same, bo wspólny czynnik się skraca, ale największa waga wynosi zawsze 1. Bez tego przy dużym α (np. α = 300, τ₀ = 0.01, τ = 0.02) wszystkie wagi spadają do zera w arytmetyce zmiennoprzecinkowej, a przy dużym τ rosną do nieskończoności. W obu przypadkach normalizacja daje NaN.

**Odejście od `PLAN.md`:** rozdział 3.4 podaje wzór τ^α · η^β. Korzystamy z prostszego wzoru z `MILESTONES.md`, bez heurystyki η i parametru β.

### „Preferuje ruch od bazy”

`MILESTONES.md` nie określa, jak silna jest ta preferencja. Feromon na komórkach, które nie prowadzą od bazy, po prostu się nie liczy, a komórki te dostają samą wagę τ₀^α. Warunek d(n) > d(c) jest ostry, więc ślad na komórkach o tej samej odległości także nie przyciąga.

- **Czemu to działa:** ślad powstaje przy powrocie najkrótszą drogą, więc kolejne komórki śladu mają d mniejsze dokładnie o 1. Idąc w drugą stronę, d zawsze rośnie, czyli warunek ostry nie gubi żadnej komórki śladu.
- **Czemu nie osobny mnożnik:** nie trzeba dodatkowego parametru, a agent nie zawraca po śladzie.
- **Czemu nie zawężamy samego wyboru sąsiadów do d(n) > d(c):** przy braku śladu agenci spływaliby na brzegi mapy, bo ruch miałby stałe odchylenie od bazy.

### Znaczenie τ₀

Dla jednej komórki ze śladem wśród 8 sąsiadów, przy α = 1 i τ₀ = 0.01, udział tej komórki w losowaniu (przed uwzględnieniem ε) to (τ + τ₀) / (τ + 8τ₀):

| τ | 0.01 | 0.1 | 1 | 5 |
|---|---|---|---|---|
| Udział | 22% | 61% | 94% | 99% |

Słaby ślad tylko sugeruje kierunek, a mocny praktycznie go wyznacza. Próg z kroku 2 tworzy skok: tuż poniżej τ₀ agent ignoruje ślad, tuż powyżej ma na niego około 22% szans.

## 5. Eksploracja bez śladu

Odejście od dosłownego wzoru: przy braku śladu `MILESTONES.md` dawałby równe wagi τ₀, czyli ruch bez pamięci kierunku. Zamiast tego agent porusza się **tak samo jak w losowym spacerze**: z prawdopodobieństwem p utrzymuje kierunek, jeśli komórka przed nim jest wolna, a inaczej losuje sąsiada jednostajnie.

**Uzasadnienie:** ACO i punkt odniesienia mają się różnić tylko korzystaniem ze śladów. Gdyby ACO eksplorowało gorzej od losowego spaceru, porównanie P1 mierzyłoby też różnicę w eksploracji.

Dlatego brak śladu sprawdzamy **przed** losowaniem ε. ε oznacza tu odejście od śladu, więc bez śladu nie ma od czego odchodzić. Gdyby ε działało także bez śladu, przy p = 0.5, ε = 0.1 i 8 wolnych sąsiadach szansa utrzymania kierunku spadłaby z 0.5 + 0.5/8 = 56,25% do 0.9 · 56,25% + 0.1/8 = 51,875%, czyli eksploracja różniłaby się od punktu odniesienia. Pierwsza wersja kodu miała ten błąd. Wyniki w punkcie 7 pochodzą już z wersji poprawionej.

Ruch ε pozostaje jednostajny, bez utrzymywania kierunku. Agent idący śladem i tak ma kierunek zgodny ze śladem, więc utrzymywanie go osłabiłoby wychodzenie ze ścieżki.

## 6. Mapa cieplna

Wizualizacja normalizuje feromon liniowo do bieżącego maksimum: τ / max τ. Jasność na ekranie nie jest więc porównywalna między krokami. Gdy przy bazie zbiega się wiele śladów, dalsze odcinki są blade. Nie wpływa to na symulację.

## 7. Wyniki kontrolne

Pomiar z 5 listopada 2026 na mapie testowej: wartości domyślne oprócz wskazanych, 20 agentów, 270 puszek, T = 3000, ziarna 0–29. Skrypt był jednorazowy i nie ma go w repozytorium, więc liczby są poglądowe. Właściwe porównanie jest w punkcie 12.

Pomiar pochodzi sprzed `feat/rewards`, więc „ACO (domyślne)” oznacza tu ACO bez unikania tłoku. Obecnie odpowiada to λ = 1, co daje te same wyniki (punkt 10).

| Wariant | t₅₀ | t₉₀ (± 95%) | Trasa na puszkę | Lepsze t₉₀ niż losowy spacer |
|---|---|---|---|---|
| losowy spacer | 474 | 1657 ± 214 | 197 | — |
| **ACO (domyślne)** | **307** | **822 ± 179** | **109** | **28/30** |
| ACO, q = 0.1 | 296 | 804 ± 126 | 116 | 28/30 |
| ACO, q = 0.3 | 295 | 717 ± 113 | 121 | 28/30 |
| ACO, q = 3 | 302 | 913 ± 191 | 122 | 27/30 |
| ACO, ε = 0.3 | 303 | 848 ± 132 | 123 | 28/30 |
| ACO, ρ = 0.005 | 313 | 1011 ± 239 | 128 | 25/30 |
| ACO, ρ = 0.01 | 309 | 885 ± 151 | 125 | 26/30 |
| ACO, ρ = 0.05 | 293 | 901 ± 159 | 125 | 26/30 |

Przebieg, który nie osiągnął 90% puszek, liczymy jako t₉₀ = T. Dotyczy to 2 ziaren losowego spaceru i 1 ziarna ACO. Przedziały ufności wariantów ACO się nakładają, więc te dane nie pozwalają wybierać między nimi. Nie wykonano testu istotności.

Wszystkie puszki zebrano na 22/30 ziaren w losowym spacerze i na 28/30 w ACO z wartościami domyślnymi.

**Mapy, na których ACO wypadło gorzej.** Na ziarnach 5 i 9 t₉₀ było gorsze niż w losowym spacerze, a na ziarnach 0 i 9 ACO nie zebrało wszystkich puszek. Na każdej z tych map puściliśmy po 20 nowych przebiegów każdego algorytmu (ta sama mapa, inne losowanie ruchów):

| Ziarno | t₉₀ losowy | t₉₀ ACO | Lepsze t₉₀ ACO | Pełna zbiórka: losowy | Pełna zbiórka: ACO |
|---|---|---|---|---|---|
| 0 | 1581 ± 218 | 841 ± 73 | 20/20 | 13/20 | 20/20 |
| 5 | 1668 ± 178 | 1152 ± 276 | 16/20 | 4/20 | 19/20 |
| 9 | 2171 ± 249 | 1113 ± 247 | 18/20 | 7/20 | 20/20 |

Te wyniki to głównie zmienność między przebiegami, a nie słabość ACO na tych mapach.

**Znane ograniczenie: późne odkrywanie skupisk.** W przebiegu na ziarnie 9 zostało 41 puszek w rogu mapy, czyli niemal całe jedno skupisko. Agenci nie utknęli: spędzili w pobliżu tych puszek tylko 5 z 60 000 kroków agentów, a przez większość czasu byli w zachodniej połowie mapy. Feromon pomaga wracać do znalezionych skupisk, ale nie pomaga znaleźć nowych. Eksploracja bez śladu to nadal błądzenie, więc nieodkryte skupisko może przetrwać do T.

## 8. Nagroda wspólna N1: unikanie tłoku

`MILESTONES.md` mówi: „gdy w okolicy skupiska jest więcej agentów niż puszek do zebrania, wybór tego kierunku dostaje karę”. Nie określa, czym jest okolica ani jak duża jest kara. Przyjęliśmy, że dla ruchu z komórki c na sąsiada n w kierunku v = n − c okolicą jest kwadratowe okno o środku i promieniu (odległość Czebyszewa):

```
a = c + (R + 1) · v      promień R
```

W oknie liczymy puszki C oraz agentów w stanie `SEARCHING` S, ale tylko na komórkach, do których da się dojść od n bez wychodzenia poza okno (n zawsze leży na jego brzegu). Kierunek jest zatłoczony, gdy `C > 0` i `S > C`. Wtedy w punkcie 4 zamiast τ_out(n) używamy:

```
τ_out(n) ← λ · τ_out(n)
```

Kara działa przed progiem z kroku 2, więc przy λ = 0 agent, któremu zostały same zatłoczone kierunki, porusza się jak w losowym spacerze, czyli „szuka gdzie indziej”.

| Decyzja | Uzasadnienie |
|---|---|
| Okno leży przed agentem, a nie wokół sąsiada | Okna wokół sąsiednich komórek prawie się pokrywają, więc kara dotykałaby wszystkich kierunków po równo i niczego by nie zmieniała. Przesunięte okno odpowiada za konkretny kierunek. Komórka c nie należy do żadnego okna, więc agent nie liczy sam siebie |
| Warunek C > 0 | Bez niego agenci idący jeden za drugim po śladzie do dalekiego skupiska zniechęcaliby się nawzajem, bo w połowie drogi puszek nie ma. Takie okno nie jest okolicą skupiska |
| Liczymy tylko agentów `SEARCHING` | Agent `CARRYING` właśnie odchodzi i nie zabierze już żadnej puszki |
| S > C, bez uwzględniania wolnego miejsca w workach | Dosłownie według `MILESTONES.md`: więcej agentów niż puszek |
| Kara dotyczy tylko śladu | Bez śladu agent ma się poruszać jak w losowym spacerze (punkt 5). Waga τ₀ zostaje, więc kierunek nie jest zabroniony |
| Widoczna puszka nadal wygrywa | Agent, który widzi puszkę, idzie po nią bez pytania polityki. Omijanie puszki w zasięgu niczego by nie przyspieszyło |
| R = 3 | Równe `cluster_spread`, czyli odchyleniu standardowemu skupiska. Wartość dobrana ad hoc: pomiar w punkcie 10 nie odróżnia R = 2, 3 i 5 |
| λ = 0 | Ślady sięgają kilkudziesięciu jednostek (szczyt 11–29 na ziarnach 0–9), a τ₀ = 0.01, więc umiarkowana kara prawie nie zmienia wyboru. Przy τ = 20 i λ = 0.1 kierunek nadal dostaje około 97% wagi wśród 8 sąsiadów. Wartość też ad hoc: pomiar nie odróżnia λ = 0, 0.1 i 0.5 |

**Uproszczenie:** agent „widzi” tłok dalej niż puszki (do 2R + 1 = 7 komórek przy r = 2). Tłum widać z większej odległości niż puszkę. Ściana zasłania to, co jest za nią (punkt 13).

## 9. Nagroda indywidualna N2: pamięć prywatna

Agent N2 nie zostawia śladu, dlatego symulacja w tym wariancie w ogóle nie ma pola feromonu. Gdy nic nie pamięta, porusza się jak w losowym spacerze. Gdy pamięta źródło, idzie do niego najkrótszą drogą, bez ε i bez sprawdzania tłoku.

`MILESTONES.md` nie definiuje „najlepszego skupiska”. Pamięć to para (komórka m, liczba puszek n_m). Po każdym podniesieniu puszki na komórce c, gdy w oknie o promieniu r zostało n puszek (ta sama wartość co w punkcie 2):

```
jeśli nic nie pamięta  lub  n ≥ n_m  lub  odległość(c, m) ≤ r:
    m ← c, n_m ← n      (a przy n = 0: agent zapomina)
```

Agent zapomina źródło także wtedy, gdy na nie dojdzie i nie widzi tam żadnej puszki.

| Decyzja | Uzasadnienie |
|---|---|
| Jakość źródła to liczba puszek w zasięgu wzroku | Agent nie zna rozmiaru całego skupiska. To ta sama miara, która w N1 ustala siłę śladu |
| n ≥ n_m, a nie n > n_m | Przy remisie nowsza informacja jest lepsza |
| Warunek odległość(c, m) ≤ r | Agent jest na miejscu, więc to, co widzi, zastępuje starą liczbę, także gdy jest mniejsza. Inaczej liczba z pierwszej wizyty blokowałaby zmianę źródła na lepsze, gdy pamiętane jest już prawie puste |
| Pojedyncza puszka daleko od źródła (n = 0) nie kasuje pamięci | Mówi coś tylko o tamtym miejscu |
| Agent idzie po widoczną puszkę także w drodze do źródła | Ta sama reguła widzenia co u pozostałych. Później wraca na trasę do źródła |

Trasa korzysta z mapy odległości od m (przeszukiwanie wszerz jak w punkcie 1), liczonej przy pierwszym użyciu danej komórki i zapamiętywanej. Przebieg N2 trwa około 3,2 s, a losowego spaceru około 1,9 s.

**Nagrody liczone po przebiegu:** N1 to `R_i = (wszystkie oddane puszki) / N`, a N2 to `R_i = (puszki oddane przez i)`. Puszki w worku jeszcze się nie liczą.

## 10. Porównanie nagród (pomiar kontrolny)

Pomiar z 5 listopada 2026 w tych samych warunkach co w punkcie 7 (30 ziaren, t₉₀ = T, jeśli nie osiągnięto 90%). Skrypt był jednorazowy, a liczby są poglądowe. Nie wykonano testu istotności.

| Wariant | t₅₀ | t₉₀ (± 95%) | Trasa na puszkę | Gini | Min / max puszek na agenta | Pełna zbiórka | Lepsze t₉₀ niż losowy spacer |
|---|---|---|---|---|---|---|---|
| losowy spacer | 474 | 1657 ± 214 | 197 | 0.37 | 0.7 / 31.5 | 22/30 | — |
| **N2 (indywidualna)** | **326** | **816 ± 107** | **133** | **0.56** | **0.2 / 48.4** | **28/30** | **28/30** |
| ACO bez unikania tłoku (λ = 1) | 307 | 822 ± 179 | 109 | 0.38 | 0.6 / 33.9 | 28/30 | 28/30 |
| **N1 (wspólna, R = 3, λ = 0)** | **308** | **790 ± 104** | **110** | **0.40** | **0.7 / 36.6** | **29/30** | **29/30** |
| N1, R = 3, λ = 0.1 | 299 | 897 ± 187 | 121 | 0.40 | 0.5 / 36.1 | 29/30 | 27/30 |
| N1, R = 3, λ = 0.5 | 303 | 826 ± 186 | 108 | 0.38 | 0.6 / 33.8 | 29/30 | 28/30 |
| N1, R = 2, λ = 0 | 301 | 812 ± 108 | 120 | 0.39 | 0.5 / 36.2 | 30/30 | 28/30 |
| N1, R = 5, λ = 0 | 303 | 742 ± 97 | 116 | 0.40 | 0.6 / 36.0 | 28/30 | 29/30 |

Średnie min i max liczymy po przebiegach. Gini liczymy z puszek oddanych przez agentów, także w N1, gdzie nagroda jest z definicji równa, bo mierzy on, kto faktycznie zbierał.

**Wnioski z tego pomiaru:**

- **Hipoteza o nierówności N2 się potwierdza:** Gini 0.56 wobec 0.40 w N1.
- **Hipoteza o wolniejszym N2 się nie potwierdza.** t₉₀ jest takie samo w granicach przedziałów ufności (816 ± 107 wobec 790 ± 104). Prawdopodobnie pamięć prywatna daje wiele z tego, co ślad, bo agent też wraca do znanego skupiska. Różnicę widać w trasie na puszkę (133 wobec 110) i w t₅₀ (326 wobec 308), ale to nadal bez testu istotności.
- **Unikanie tłoku prawie nie działa przy obecnych parametrach.** Na tych 30 ziarnach kierunek był zatłoczony średnio 9,6 razy na przebieg, czyli przy 0,44% z około 2180 decyzji o śladzie. Skupiska mają po 40 puszek, a agentów jest 20, więc warunek S > C zachodzi prawdopodobnie dopiero przy końcu skupiska. Różnice między wariantami N1 mieszczą się w szumie, więc nie ma podstaw do twierdzenia, że kara pomaga ani że szkodzi. Porównanie P2 mierzy więc głównie ślad kontra pamięć, a nie tłok. Można to sprawdzić przy większej liczbie agentów (Część II w `MILESTONES.md`).

## 11. Metryki i metoda porównań

Metryki liczy `metrics.py`, a testy i przedziały ufności `plots.py`. Zapis metryk tylko czyta stan symulacji, więc nie zmienia przebiegu.

| Metryka | Definicja | Uzasadnienie |
|---|---|---|
| Zebrane puszki | Puszki oddane w bazie. Puszki w worku się nie liczą | Tak samo działa warunek końca symulacji i nagrody (punkt 9) |
| t₅₀, t₉₀, t₁₀₀ | Pierwszy krok, po którym oddano co najmniej ⌈X% · puszki⌉. Pusta wartość, jeśli nie nastąpiło to do T | Próg liczymy na liczbach całkowitych, żeby błąd zaokrąglenia nie przesunął dokładnego progu, np. 243 z 270 |
| Trasa na puszkę | Wszystkie ruchy wszystkich agentów / oddane puszki, liczone dla przebiegu, a potem uśredniane. Pusta wartość, jeśli nie oddano żadnej puszki | Liczymy też ruchy po ostatnim oddaniu, bo agent i tak je wykonał |
| Gini | `G = Σᵢ Σⱼ abs(xᵢ − xⱼ) / (2 n Σ x)` z puszek oddanych przez agentów. G = 0, gdy nikt nic nie oddał | Wersja bez korekty n / (n − 1), więc maksimum to (n − 1) / n, czyli 0.95 przy 20 agentach |

**Przebiegi poniżej progu.** Do średniej, przedziału ufności i testu przebieg, który nie osiągnął progu, wchodzi jako t = T (jak w punkcie 7). Średnia jest przez to zaniżona dla wariantów, które często nie osiągają progu, dlatego raportujemy też liczbę przebiegów, które go osiągnęły. Test rangowy jest na to mniej wrażliwy: taki przebieg dostaje po prostu najgorszą rangę.

**Przedział ufności 95%:** `x̄ ± t₀.₉₇₅,ₙ₋₁ · s / √n`, czyli z rozkładu t-Studenta. Przy n = 30 kwantyl wynosi 2.045. Przedziały w punktach 7 i 10 są o około 4% węższe, co odpowiada kwantylowi 1.96. To wniosek z samych liczb, bo tamtego skryptu nie ma w repozytorium.

**Krzywa zbierania.** Przebieg, który skończył się przed T, zostaje do końca wykresu na swojej końcowej wartości. Bez tego najszybsze przebiegi wypadałyby ze średniej, a krzywa pod koniec by spadała. Pasmo liczymy osobno dla każdego kroku tym samym wzorem. Nie przycinamy go do liczby puszek, więc pod koniec może nieznacznie ją przekraczać.

**Test istotności.** Dwustronny test Manna-Whitneya, jak w `MILESTONES.md`, dla t₉₀ oraz Giniego. Test nie korzysta z tego, że warianty mają te same mapy. Test parami (np. Wilcoxona) mógłby mieć większą moc, ale zostajemy przy ustalonym planie. Nie stosujemy korekty na wielokrotne porównania, więc p-wartości trzeba czytać z tym zastrzeżeniem. Gdy wszystkie wartości obu wariantów są równe (np. żaden przebieg nie osiągnął progu), przyjmujemy p = 1, bo nie ma różnicy do wykrycia. Robimy to jawnie, ponieważ scipy zwraca w tym przypadku 1 albo NaN, zależnie od wersji (1.15.3 i 1.18.1).

**Rozkład puszek na agenta.** Wykres pudełkowy łączy agentów ze wszystkich przebiegów wariantu (600 wartości). Agenci jednego przebiegu nie są niezależni, więc wykres jest tylko opisowy, a test wykonujemy na Ginim liczonym dla przebiegu.

**Format CSV.** Kolumny są zgodne z `PLAN.md`, rozdział 7, z kolumną `reward` z `MILESTONES.md`. Dodatkowo:

- `max_steps` jest potrzebne do przebiegów poniżej progu, a `map`, `initial_cans` i `steps` opisują przebieg,
- `path_per_can`, `cans_min` i `cans_max` to metryki z `MILESTONES.md`, rozdział 4.

Pozostają puste: `beta`, bo wybór kierunku nie ma heurystyki η (punkt 4), oraz `J`, bo wagi w₁, w₂ wariantu C nie są ustalone. `rho`, `alpha` i `eps` wypełniamy tylko dla N1, bo pozostałe warianty z nich nie korzystają. N2 ma w `algorithm` wartość `aco`, tak jak w `--algorithm aco --reward individual`, choć nie używa feromonu.

## 12. Porównania P1 i P2

Pomiar z 6 listopada 2026: `python -m kaucjowicze.experiments --seeds 30`, wartości domyślne, ziarna 0–29, mapa testowa. Średnia ± 95%.

| Wariant | t₅₀ | t₉₀ | Trasa na puszkę | Kursy | Gini | Min / max puszek na agenta | Osiągnęło 90% | Pełna zbiórka |
|---|---|---|---|---|---|---|---|---|
| losowy spacer | 474 ± 83 | 1657 ± 224 | 196.8 ± 16.4 | 45 ± 2 | 0.373 ± 0.018 | 0.7 / 31.5 | 28/30 | 22/30 |
| ACO N1 | 308 ± 42 | 790 ± 109 | 110.2 ± 16.7 | 46 ± 1 | 0.398 ± 0.031 | 0.7 / 36.6 | 30/30 | 29/30 |
| N2 | 326 ± 44 | 816 ± 112 | 132.7 ± 14.4 | 47 ± 2 | 0.555 ± 0.022 | 0.2 / 48.4 | 30/30 | 28/30 |

| Porównanie | p dla t₉₀ | p dla Giniego |
|---|---|---|
| ACO N1 / losowy spacer | 7.8 · 10⁻⁹ | 0.26 |
| ACO N1 / N2 | 0.70 | 6.0 · 10⁻⁹ |
| N2 / losowy spacer | 8.1 · 10⁻⁹ | 5.5 · 10⁻¹¹ |

Średnie t₅₀ i t₉₀, trasa na puszkę, Gini, min / max i liczby przebiegów zgadzają się z pomiarami kontrolnymi z punktów 7 i 10 (z dokładnością do ich zaokrągleń), co potwierdza, że nowy kod mierzy to samo.

**Wnioski:**

- **P1: ACO jest szybsze od losowego spaceru.** t₉₀ jest około dwa razy krótsze, a różnica istotna. Nierówność podziału nie różni się istotnie (p = 0.26).
- **P2: nie ma dowodu, że N1 jest szybsze od N2** (p = 0.70). Hipoteza o wolniejszym N2 z `MILESTONES.md` nie znajduje potwierdzenia w tym pomiarze. Brak istotnej różnicy nie oznacza, że warianty są równe: 30 ziaren może nie wystarczyć, by wykryć małą różnicę.
- **P2: N2 dzieli puszki wyraźnie mniej równo** (Gini 0.555 wobec 0.398, różnica istotna). Ta hipoteza się potwierdza.
- Sześć wykonanych testów nie zmienia tych wniosków: po korekcie Bonferroniego (próg 0.05 / 6 ≈ 0.0083) wyniki po obu stronach progu pozostają te same.
- Trasa na puszkę jest w N1 średnio krótsza niż w N2 (110.2 ± 16.7 wobec 132.7 ± 14.4), ale przedziały się nakładają, a tej metryki nie testowaliśmy, więc to tylko wskazówka.

## 13. Mapa Miasteczka

Maskę `src/kaucjowicze/data/ms_agh_map.png` generuje z danych OpenStreetMap skrypt `tools/build_campus_map.py`. Jeden piksel to jedna komórka. Symulacja czyta tylko ten plik, więc maskę można poprawiać ręcznie, a dane OSM pobrane 7 listopada 2026 leżą w `data/ms_agh_osm.json`.

**Obszar:** prostokąt 300 × 273 m, czyli 100 × 91 komórek po 3 m. Zakres wybrał zespół: strona Budryka z akademikami, wschodnia granica na linii Smoka Studenta, a pozostałe proste, z fragmentem ulicy na brzegach.

| Decyzja | Uzasadnienie |
|---|---|
| Komórka 3 m | Szerokość mapy pozostaje taka jak na mapie testowej, a przejścia na Autostradzie MS AGH i między akademikami mają co najmniej jedną komórkę. Węższe przejścia mogły zniknąć. Wartość dobrana ad hoc |
| Obrót o 13° względem północy | Tyle wynosi kierunek ścian akademików zmierzony z obrysów. Ściany leżą wzdłuż siatki, więc nie mają schodków, a prostokąt nie obejmuje budynków po drugiej stronie Reymonta |
| Przeszkody: budynki oprócz `building=roof` i `building=bridge`, płoty, mury, mury oporowe, żywopłoty | Pod dachem i mostem można przejść. Pozostałe `barrier` (krawężniki, słupki) nie zatrzymują pieszego |
| Można chodzić wszędzie poza przeszkodami, także po trawie | Tak zachowują się ludzie, a wyniki nie zależą od kompletności sieci chodników |
| Budynek zajmuje komórkę pokrytą w co najmniej 50% | Obrysy nie są sztucznie pogrubiane, więc wąskie przejścia nie znikają |
| Przeszkody liniowe rysujemy bez kroków po skosie | Agent może przejść po skosie między komórkami stykającymi się rogami (`free_neighbours`), więc linia po skosie byłaby dziurawa |
| Chodnik przecinający płot lub żywopłot oraz brama z OSM tworzą przejście | Bramy często nie ma w danych, a chodnik przez płot oznacza, że da się tamtędy przejść. Czyścimy jedną komórkę wokół przecięcia wzdłuż chodnika. Brama z `locked=yes` albo `access=private` lub `no` nie tworzy przejścia, chyba że ma `foot=yes`, `designated` lub `permissive` |
| Chodnik z `tunnel=building_passage` lub `tunnel=yes` przechodzi przez budynek, o ile nie ma ujemnego `layer` | Tak OSM opisuje przejścia, m.in. na Autostradzie MS AGH. Droga z ujemnym `layer` biegnie pod ziemią, więc nie otwiera tego, co nad nią. Jedyny taki chodnik w danych przecinał blok, którego dach na zdjęciu jest ciągły. Nie sprawdzaliśmy tego w terenie |
| Obszary odcięte od głównej części mapy stają się przeszkodami (160 komórek) | Puszki w takim miejscu nigdy nie zostałyby zebrane. `load_mask` zgłasza błąd, gdy taki obszar powstanie po ręcznej poprawce |
| Baza: komórka Autostrady MS AGH najbliższa środka mapy, (49, 36) | Odpowiada centralnej bazie z mapy testowej. Położenie jest umowne, bo nie ma tam prawdziwego punktu skupu |

**Tło okna:** ortofotomapa z Geoportalu (usługa WMS GUGiK), obrócona i przycięta do tego samego prostokąta (`ms_agh_photo.jpg`). Jest tylko warstwą w oknie, więc nie wpływa na wyniki. Zdjęcie pokazuje dachy, a maska obrysy z OSM, więc mogą się nieznacznie rozjeżdżać.

**Znane ograniczenia:** mapa odtwarza to, co jest w OSM, i nie była sprawdzana w terenie. Ogrodzone boiska i ogród przedszkola są dostępne, bo ich ogrodzenia mają przerwy lub bramy, więc puszki mogą pojawić się także tam.

**Ściany a okna widzenia.** Przy cienkich przeszkodach zwykła suma w oknie liczyłaby to, co za nimi, dlatego n (punkt 2) i tłok (punkt 8) liczymy po komórkach połączonych wewnątrz okna. Na ziarnach 0–29 mapy kampusu n różni się od zwykłej sumy przy 3,2% podniesień w N1. Na mapie testowej wszystkie 90 przebiegów pozostaje bez zmian względem punktu 12, co sprawdziliśmy, porównując `runs.csv`.

**Pozostałe parametry bez zmian.** Liczba agentów, puszek, skupisk, r, S, ρ, ε i α (poza układem puszek opisanym niżej) są takie same jak na mapie testowej, żeby wyniki dało się porównać. Mapa ma podobny udział wolnych komórek (77%), ale jest większa: 7019 wolnych komórek wobec 4600, a najdalsza komórka jest 80 kroków od bazy wobec 50. Ślad o sile 5 nadal spokojnie przeżywa drogę tam i z powrotem: po 160 krokach ma około 0.19, a τ₀ = 0.01. Nie stroiliśmy tych parametrów pod nową mapę. Dotyczy to też R = 3 i λ = 0: uzasadnienie R z punktu 8 („równe σ”) nie przenosi się na kampus, gdzie σ = 2, więc R = 1,5 σ, a wartości nie kalibrowaliśmy ponownie.

**Układ puszek na kampusie.** Mapa testowa zachowuje układ z `MILESTONES.md`. Na kampusie 270 puszek tworzy 6 skupisk po 45, z σ = 2 komórki (6 m), a środek skupiska leży najwyżej 4 komórki (12 m, odległość Czebyszewa, parametr `cluster_dorm_distance`) od akademika, czyli budynku z `building=dormitory`. Akademiki mają w masce osobny, szary kolor.

| Decyzja | Uzasadnienie |
|---|---|
| Środki przy akademikach | `PLAN.md`, 3.1, zakłada puszki głównie pod akademikami. Wcześniej środek mógł wypaść np. na środku boiska. Odległość 4 dobrana ad hoc |
| σ = 2 zamiast 3 | Przy σ = 3 aż 67% puszek leżało pojedynczo w komórce, a skupisko wyglądało jak rozrzucone puszki. Przy σ = 2 około 80% skupiska mieści się w promieniu 11 m zamiast 16 m. Wybór oceniony wizualnie |
| Bez puszek tła | **Odejście od `PLAN.md`, 3.1.** Pojedyncze puszki wydłużały koniec zbiórki, co na ziarnach kalibracyjnych 100–119 (N1, 20 przebiegów na układ) wyglądało tak: t₁₀₀ wynosi średnio 5530 przy 6×42 z 18 puszkami tła i 2751 przy 6×45 bez tła, a t₉₀ odpowiednio 2063 i 1907 |
| Nadal 270 puszek i 6 skupisk | Mniejsze skupiska nie skróciły zbiórki (6×30: t₁₀₀ = 2907). Mniej skupisk skraca ją bardziej (4×45: 1629), ale zmniejsza też liczbę miejsc do odkrycia. To pomiar kalibracyjny bez testu istotności |

Te wartości to założenia dobrane na podstawie wyglądu mapy i czasu trwania, a nie danych o prawdziwych puszkach.

**Korekta: ziarna 0–29 nie były nietknięte.** Wcześniejsza wersja tego punktu twierdziła, że nie używaliśmy ich przy wyborze układu. To nieprawda: przed zmianą układu dwa razy policzyliśmy na nich P1 i P2, tabelę porównującą σ i puszki tła, a podgląd rozmieszczenia oglądaliśmy na ziarnach 0–3. Tylko ostatnie porównanie układów (powyżej) było na ziarnach 100–119. Dlatego główne wyniki w punkcie 14 pochodzą z ziaren 200–229, których wcześniej nie używaliśmy.

**Limit T = 20000 na kampusie.** Przy T = 3000 i poprzednim układzie puszek żaden przebieg losowego spaceru nie osiągnął 90% puszek (0/30), a ACO tylko 11/30, więc t₉₀ opisywałoby głównie limit. Limit dobraliśmy na osobnych ziarnach 100–109 przy T = 20000. Przy obecnym układzie zostawiamy go bez zmian: ACO kończy się znacznie wcześniej, a losowy spacer wciąż go czasem osiąga (punkt 14). Mapa testowa zachowuje T = 3000.

## 14. Porównania P1 i P2 na mapie Miasteczka

Pomiar z 7 listopada 2026: `python -m kaucjowicze.experiments --seeds 30 --first-seed 200 --map campus`, ziarna 200–229, T = 20000, układ puszek z punktu 13. Te ziarna nie brały udziału w żadnej wcześniejszej decyzji. Średnia ± 95%.

| Wariant | t₅₀ | t₉₀ | Trasa na puszkę | Kursy | Gini | Min / max puszek na agenta | Osiągnęło 90% | Pełna zbiórka |
|---|---|---|---|---|---|---|---|---|
| losowy spacer | 1267 ± 221 | 7257 ± 1588 | 921.0 ± 154.7 | 33 ± 2 | 0.407 ± 0.023 | 0.1 / 35.6 | 29/30 | 25/30 |
| ACO N1 | 468 ± 85 | 2439 ± 559 | 214.3 ± 40.4 | 34 ± 1 | 0.516 ± 0.027 | 0.1 / 46.2 | 30/30 | 30/30 |
| N2 | 538 ± 95 | 2360 ± 471 | 258.9 ± 42.3 | 33 ± 2 | 0.689 ± 0.027 | 0.1 / 69.2 | 30/30 | 30/30 |

| Porównanie | p dla t₉₀ | p dla Giniego |
|---|---|---|
| ACO N1 / losowy spacer | 9.8 · 10⁻⁸ | 3.3 · 10⁻⁷ |
| ACO N1 / N2 | 1.0 | 7.4 · 10⁻¹⁰ |
| N2 / losowy spacer | 5.8 · 10⁻⁸ | 3.0 · 10⁻¹¹ |

**Wnioski:**

- **P1 potwierdza się na układzie budynków Miasteczka.** t₉₀ ACO jest około 3 razy krótsze niż w losowym spacerze, a różnica jest istotna także po korekcie Bonferroniego (próg 0.0083). ACO wygrało na 28 z 30 map.
- **ACO dzieli puszki mniej równo niż losowy spacer** (Gini 0.516 wobec 0.407, różnica istotna także po korekcie). Na mapie testowej tej różnicy nie było (p = 0.26). Szybsza zbiórka idzie więc w parze z tym, że część agentów zbiera wyraźnie więcej.
- **P2: nie ma dowodu, że N1 jest szybsze od N2** (p ≈ 1, t₉₀ 2439 wobec 2360, N1 szybsze na 17 z 30 map). Brak istotnej różnicy nie oznacza, że warianty są równe. N2 dzieli puszki wyraźnie mniej równo (Gini 0.689 wobec 0.516).
- **Trasa na puszkę jest w N1 średnio krótsza niż w N2** (214.3 ± 40.4 wobec 258.9 ± 42.3), ale przedziały się nakładają, a tej metryki nie testowaliśmy, więc to tylko wskazówka.
- **Trasy na puszkę nie należy porównywać między mapami.** Liczy ona też ruchy po ostatnim oddaniu, a przebiegi mają różną długość i inny limit T.

### Kontrola: te same wnioski na innych ziarnach i układach

| Pomiar | t₉₀ losowy / N1 / N2 | p dla t₉₀: N1 / losowy | p dla t₉₀: N1 / N2 | Gini losowy / N1 / N2 | p dla Giniego: N1 / losowy |
|---|---|---|---|---|---|
| ziarna 200–229 (wyniki główne) | 7257 / 2439 / 2360 | 9.8 · 10⁻⁸ | 1.0 | 0.407 / 0.516 / 0.689 | 3.3 · 10⁻⁷ |
| ziarna 0–29, ta sama maska | 6133 / 2204 / 2785 | 3.3 · 10⁻⁷ | 0.26 | 0.404 / 0.482 / 0.690 | 0.0003 |
| ziarna 0–29, maska przed usunięciem podziemnego przejścia | 5672 / 2455 / 2088 | 2.7 · 10⁻⁶ | 0.47 | 0.416 / 0.484 / 0.682 | 0.0024 |
| ziarna 0–29, poprzedni układ puszek (6 × 40 + 30 puszek tła, σ = 3, środki w dowolnym miejscu) | 8928 / 3859 / 4513 | 4.8 · 10⁻⁷ | 0.65 | 0.404 / 0.438 / 0.614 | 0.064 |

- **Wnioski o szybkości nie zależą od tych zmian.** We wszystkich pomiarach ACO i N2 są istotnie szybsze od losowego spaceru, a między N1 i N2 nie ma istotnej różnicy.
- **Pojedynczy przebieg jest bardzo czuły na drobne zmiany.** Otwarcie lub zamknięcie 5 komórek zmieniło średnie t₉₀ N1 na tych samych ziarnach z 2455 na 2204, bo ruchy agentów rozchodzą się już od pierwszych kroków. To rozrzut tej samej wielkości co przedział ufności, więc różnic tego rzędu nie należy interpretować.
- **Wniosek o Ginim N1 względem losowego spaceru zależy od układu puszek.** Przy skupiskach przy akademikach różnica jest istotna, a przy poprzednim, bardziej rozproszonym układzie nie była. Mierzymy go więc dla przyjętego założenia, a nie jako ogólną własność ACO.
