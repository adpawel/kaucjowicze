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

**Uproszczenie:** n to zwykła suma w oknie, więc liczy też puszki za cienką ścianą, których agent nie zobaczyłby przy szukaniu (`first_step_to_nearest_can`). Na mapie testowej nie ma to znaczenia, bo budynki są grubsze niż r = 2. Trzeba do tego wrócić przy prawdziwej mapie MS AGH.

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

W oknie liczymy puszki C oraz agentów w stanie `SEARCHING` S. Kierunek jest zatłoczony, gdy `C > 0` i `S > C`. Wtedy w punkcie 4 zamiast τ_out(n) używamy:

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

**Uproszczenie:** tak jak w punkcie 2 okno nie uwzględnia ścian, a agent „widzi” tłok dalej niż puszki (do 2R + 1 = 7 komórek przy r = 2). Tłum widać z większej odległości niż puszkę, ale przy prawdziwej mapie MS AGH trzeba do tego wrócić.

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

- `max_steps` jest potrzebne do przebiegów poniżej progu, a `initial_cans` i `steps` opisują przebieg,
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
