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

Wartości q i p nie pochodzą z `MILESTONES.md` (p ustalono w `feat/agents-random`, q w `feat/aco`). Pozostałe są z tego dokumentu.

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

Pomiar z 5 listopada 2026 na mapie testowej: wartości domyślne oprócz wskazanych, 20 agentów, 270 puszek, T = 3000, ziarna 0–29. Skrypt był jednorazowy i nie ma go w repozytorium, więc liczby są poglądowe. Właściwe porównanie przyjdzie z `feat/metrics-experiments`.

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
