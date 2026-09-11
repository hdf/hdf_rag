# Belső dokumentumkereső – FastAPI + Qdrant

Lokálisan futó Python prototípus: szöveges dokumentumokat fogad, átfedő részletekre bontja őket, majd magyar és angol kérdésekre szemantikusan releváns forrásrészleteket keres. Nem generál LLM-es válaszokat. A dokumentumrészletek, metaadatok és vektorok a beágyazott Qdrant lemezes tárolójába kerülnek, így újraindítás után is megmaradnak.

## Gyors indítás

Python 3.11–3.14 szükséges; a tesztelt környezet Python 3.14.4, Linux x86_64. Docker, GPU, API-kulcs és Azure-előfizetés nem szükséges. Az első indítás internetkapcsolatot igényel az embedding modell letöltéséhez; a BGE-M3 modellsúlyai körülbelül 2,3 GB méretűek, ezért a letöltés és betöltés több percig is tarthat. A Python-függőségek további lemezterületet igényelnek. CPU-n fut; a modellsúlyokon felül a futtatáshoz és a kötegelt feldolgozáshoz is szabad memória szükséges; a memóriaigény a szöveghosszal és a batch méretével nő.

A repository gyökerében Linux/macOS alatt:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e '.[dev]'
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

A külön PyTorch-lépés a CPU-s csomagot telepíti. macOS-en, ha a CPU-index nem kínál megfelelő csomagot, használd a `python -m pip install torch` parancsot.

Windows PowerShell alatt az első két parancs: `py -m venv .venv`, majd `.venv\Scripts\Activate.ps1`; a további parancsok megegyeznek. Debian/Ubuntu rendszeren, ha a venv létrehozása `ensurepip` hibát ad, a Python-verzióhoz tartozó `python3-venv` rendszerkomponens szükséges.

Várd meg az `Application startup complete` üzenetet. A modell a Hugging Face helyi cache-ébe kerül, és a következő indítások újra felhasználják. Előzetes letöltés után `HF_HUB_OFFLINE=1` környezeti változóval offline indítható. A dokumentumok feldolgozása és az embedding számítása helyben történik.

- Interaktív API és kipróbálás: <http://127.0.0.1:8000/docs>
- OpenAPI: <http://127.0.0.1:8000/openapi.json>
- Állapot: <http://127.0.0.1:8000/health>

Egyetlen Uvicorn workerrel indítsd: a beágyazott Qdrant könyvtárát egyszerre egy folyamat használhatja. Leállítás: Ctrl+C.

## Kipróbálás

Másik terminálban, aktivált virtuális környezetből:

A betöltőscript egy már futó API-hoz kapcsolódik, nem indítja el a szervert. Az első terminálban hagyd futni az Uvicornt, és várd meg az `Application startup complete` üzenetet. `Cannot reach the API` / `Connection refused` esetén ellenőrizd, hogy az API fut-e a megadott porton. Eltérő címhez: `python scripts/load_examples.py --url http://HOST:PORT`. VS Code Remote SSH esetén mindkét terminált az Ubuntu szerveren nyisd meg; a böngészőhöz használt porttovábbítás ettől független.

```bash
python scripts/load_examples.py
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"Hogyan indul el egy új projekt?","top_k":3}'
```

Windows alatt a Swagger felület vagy a `curl.exe` használható. A betöltő script ismételt futtatásakor a már létező mintadokumentumokat kihagyja. A példakérdésnél a projektindítási útmutatót várjuk első helyen; a tesztekben is szerepel ez az elvárás.

Saját dokumentum feltöltése:

```bash
curl -i http://127.0.0.1:8000/documents \
  -H 'Content-Type: application/json' \
  -d '{"id":"DOC-004","title":"Költségjóváhagyás","text":"A projekt költségkeretét a szponzor hagyja jóvá."}'
```

Sikeres válasz, HTTP 201:

```json
{"document_id":"DOC-004","chunks":1}
```

Keresési válasz alakja (a pontszám szemléltető érték):

```json
{
  "results": [
    {
      "document_id": "DOC-004",
      "title": "Költségjóváhagyás",
      "chunk": "A projekt költségkeretét a szponzor hagyja jóvá.",
      "chunk_index": 0,
      "score": 0.87
    }
  ]
}
```

## API-szerződés és hibák

| Végpont | Működés | Válasz |
| --- | --- | --- |
| `GET /health` | Ellenőrzi a Qdrant collection elérhetőségét; a modell induláskor töltődik be | 200, hiba esetén 503 |
| `POST /documents` | Kötelező `id`, `title`, `text` JSON-mezők | 201; létező ID esetén 409 |
| `POST /search` | Kötelező `query`; `top_k` alapértéke 3 | 200, `results` tömb |

A `/health` sikeres válasza például:

```json
{
  "status": "ok",
  "qdrant": {
    "status": "ok",
    "reachable": true,
    "mode": "embedded",
    "collection": "documents_bge_m3_256_v1",
    "collection_status": "green",
    "points_count": 3,
    "check_duration_ms": 0.12,
    "detail": null
  }
}
```

Az ellenőrzés minden kérésnél ténylegesen lekéri a konfigurált collection adatait. A `points_count` a Qdrant által jelentett pontok (chunkok), nem a dokumentumok száma; szerveres módban közelítő érték lehet. Az `embedded` helyi, folyamaton belüli tárolót, a `server` külön Qdrant szervert jelent. A `green` és az optimalizálás alatti `yellow` állapot 200-at ad, más collection-állapot 503-at. Sikertelen lekérdezéskor `status: degraded`, `qdrant.status: unavailable`, `reachable: false` és általános hibaüzenet érkezik 503-mal; ez a collection hiányát is jelentheti, nem kizárólag hálózati hibát. A lekérdezési idő a folyamaton belüli lockra várást is tartalmazza. Nem végez próbaírást vagy embedding-számítást.

Az ID legfeljebb 128, a cím 300, a dokumentum 100 000, a kérdés 2000 karakter. A csak whitespace tartalmú mezők, hiányzó vagy ismeretlen mezők és hibás típusok 422 választ eredményeznek. A `top_k` szigorúan egész szám 1–20 között. A modell tokenkorlátját túllépő kérdés szintén 422; nincs csendes levágás. A szélső whitespace-eket levágjuk a bemeneti szövegről. Üres indexben a keresés üres listát ad. Az ismételt ID 409 választ ad, és a meglévő dokumentumot megőrzi; frissítő és törlő API nem része a prototípusnak.

A keresés chunkokat rangsorol, így egy dokumentum több találattal is megjelenhet. A koszinusz-hasonlósági pontszám nem valószínűség és nem megbízhatósági százalék. Nincs kalibrált relevanciaküszöb: nem üres indexben egy témán kívüli kérdésre is érkezhetnek találatok.

Az infrastruktúrahibák általános 503 választ adnak, belső kapcsolati adatok nélkül. A naplózás indulást, feltöltött chunkszámot, találatszámot és hibatípust rögzít; dokumentumtartalmat és kérdést nem naplózunk. Indulási hiba esetén a folyamat nem válik használatra késszé.

## Felépítés és döntések

```text
POST /documents → validálás → tokenalapú chunkolás → helyi embedding → Qdrant
POST /search    → validálás → kérdés embedding     → Qdrant top-k → forrásrészletek
```

- **FastAPI:** Pydantic-validálás, automatikus OpenAPI és közvetlenül használható tesztfelület kevés kóddal.
- **Qdrant:** vektoros keresés és payload-perzisztencia egy tárolóban. Külön SQLite itt felesleges kettős adatkezelést és szinkronizálási feladatot jelentene. A [Qdrant kliens](https://github.com/qdrant/qdrant-client) azonos API-val kínál beágyazott és szerveres módot.
- **Helyi `BAAI/bge-m3`:** többnyelvű modell, fizetős szolgáltatás nélkül. A [modellkártya](https://huggingface.co/BAAI/bge-m3) szerinti dense embeddinget használjuk Sentence Transformers segítségével, query/passage prefix nélkül, normalizálással és koszinusz-hasonlósággal. A vektorméret 1024, a modell bemeneti korlátja 8192 token. Sparse és ColBERT reprezentációt ez a prototípus nem számít. CPU-n a kisebb E5-smallnál nagyobb erőforrásigénnyel kell számolni; a választás minőségét saját kérdésekkel kell mérni.
- **Chunkolás:** 256 modelltokent tartalmazó ablakok 40 token átfedéssel. Az átfedés a határon átnyúló összefüggések egy részét megőrzi. A BGE-M3 saját tokenizere adja a tokenhatárokat, így ugyanaz a szöveg a korábbi E5-modellhez képest eltérően tagolódhat. A 8192 tokenes modellkorlát ellenére rövid, célzottan visszaadható részleteket használunk. Tokenizer-offsetekkel az eredeti szöveg részleteit tároljuk, nem visszadekódolt tokeneket. Ez egyszerű és kiszámítható; kompromisszumként mondatot is kettévághat. Később bekezdés- és mondathatárokat követő chunkolást értékelnék.
- **Metaadatok:** dokumentumazonosító, cím, chunksorszám és karakterpozíció kerül a payloadba. A cím metaadat, az embedding a törzsszövegből készül. A karakterpozíciók a validált, szélein levágott szövegre vonatkoznak.
- **Szinkron ingestion:** a 201 csak a Qdrant írás befejezése után érkezik. A modell és a lokális tároló elérését folyamaton belüli lock védi. Ez a kis demóhoz egyszerű; nagyobb terhelésnél külön feldolgozó és szerveres Qdrant szükséges.

A [fejlesztés előtti öt ügyfélkérdés és feltételezések](docs/discovery.md) külön dokumentumban szerepelnek. A megbeszélt választások: helyi többnyelvű modell, elsődlegesen Python venv és beágyazott Qdrant, magyar README, valamint ismételt ID esetén 409.

Alternatíva lenne BM25: gyorsabb, egyszerűbb, és dokumentumkódokra vagy pontos kifejezésekre gyakran jó, de gyengébb lehet átfogalmazásnál. Nagyobb megoldásban hibrid BM25 + vektoros keresést, majd szükség szerint rerankert mérnék össze ezzel az alappal. A Qdrant kiválasztása ehhez a vektoros prototípushoz indokolt; kizárólag kulcsszavas kereséshez túlzás lenne.

## Konfiguráció és adatok

A fő függőségeknél a fejlesztéskor elérhető legújabb stabil kiadásokat rögzítettük: FastAPI 0.141.1, Qdrant kliens 1.19.0, Sentence Transformers 6.0.1, Uvicorn 0.52.4 és Pydantic Settings 2.15.0. A közvetett függőségek a csomagok kompatibilitási korlátait követik: például a Qdrant kliens `portalocker<4`, a SymPy `mpmath<1.4` verziót kér, a Pydantic pedig meghatározott `pydantic-core` kiadáshoz kötött.

A teljes tesztelt Linux/Python 3.14 CPU-s környezet a `requirements-lock.txt` fájlban szerepel. Ugyanilyen platformon az aktivált venv-ben `python -m pip install -r requirements-lock.txt`, majd `python -m pip install -e '.[dev]'` állítja elő. Ez környezetpillanatkép, nem minden operációs rendszerre érvényes lockfile; más platformon a gyors indítás lépéseit használd. Függőségfrissítés után a teljes tesztcsomagot újra kell futtatni.

Az `.env.example` opcionálisan `.env` néven másolható. Minden parancsot a projekt gyökeréből futtass.

| Változó | Alapérték | Szerep |
| --- | --- | --- |
| `HDF_QDRANT_PATH` | `data/qdrant` | Beágyazott tároló könyvtára |
| `HDF_QDRANT_URL` | nincs | Ha megadod, szerveres Qdrantot használ |
| `HDF_COLLECTION` | `documents_bge_m3_256_v1` | Collection neve |

A szerveres mód opcionális: indíts külön Qdrantot a [hivatalos útmutató](https://qdrant.tech/documentation/quick-start/) szerint perzisztens kötettel, majd állítsd be a `HDF_QDRANT_URL=http://localhost:6333` értéket. A lokális index nem költözik át automatikusan; töltsd fel újra a dokumentumokat. A prototípus szerveres módban is egy API-folyamatot feltételez, mert a duplikációellenőrzés nem több folyamatra kiterjedő tranzakció.

A korábbi E5 collection megmarad, de az alkalmazás alapértelmezetten már az új BGE-M3 collectionben keres. Az átállás után indítsd újra az API-t, majd futtasd újra a `python scripts/load_examples.py` parancsot, és töltsd fel újra a saját dokumentumaidat. Ha a `.env` fájlban korábban megadtál `HDF_COLLECTION` értéket, állítsd át `documents_bge_m3_256_v1`-re.

Leállított alkalmazás mellett a `data/qdrant` könyvtárról készíthetsz másolatot. Új, üres indexhez másik tárolóútvonalat állíts be. Modell- vagy chunkolásváltozáskor új collection és újraindexelés szükséges; az alkalmazás a vektorméretet és távolságmértéket ellenőrzi, a modellazonosságot nem tudja pusztán ezekből megállapítani.

Korlátok: nincs autentikáció, dokumentumszintű ACL, feltöltött fájlok feldolgozása, háttérsor vagy többfolyamatos írási koordináció. A Qdrant-írás hibája vagy folyamatösszeomlás esetén nincs alkalmazásszintű tranzakciós helyreállítás; egy bizonytalan kimenetelű feltöltést ellenőrizni kell. A mintákhoz és megbízható lokális használathoz készül, nem nyilvános telepítéshez.

## Tesztelés

```bash
pytest -q
ruff check .
```

Az alaptesztek valódi, ideiglenes könyvtárba mentő Qdranttal és determinisztikus embedding tesztdublőzzel futnak, modellletöltés nélkül. Ellenőrzik az API-t, validálást, duplikációt, rangsorolási adatfolyamot, újranyitás utáni perzisztenciát, chunkátfedést, forráspozíciókat és a hibaválaszok tisztítását. Ezek önmagukban nem mérik a valódi modell szemantikai minőségét.

A tényleges modell integrációs tesztje három magyar/angol példakérdés első találatát ellenőrzi:

```bash
HDF_TEST_MODEL=1 pytest -q -m model
```

PowerShell alatt előbb `$env:HDF_TEST_MODEL="1"`, majd `pytest -q -m model`. Ez első alkalommal letölti a modellt. A három kérdés smoke teszt; érdemi minőségméréshez ügyfélkérdésekkel címkézett adathalmaz és például Recall@k/MRR szükséges.

Ellenőrzött eredmény a fenti környezetben: **18 sikeres alapteszt** a health-bővítés után; a valódi BGE-M3 modellteszt a modellváltáskor külön sikeresen lefutott; a `ruff check .` és a `pip check` is sikeres. A Starlette tesztkliens egy belső AnyIO API elavulásáról figyelmeztet; ez a teszteket nem akadályozza. A modellteszt a BGE-M3 1024 dimenziós kimenetét és hosszabb magyar szöveg több chunkra bontását is ellenőrzi.

## Azure / vállalati továbbfejlesztés

Az API-t **Azure Container Apps** környezetbe vinném, mert a konténeres FastAPI és a hosszabb modellbetöltés jól illeszkedik hozzá. Az eredeti fájlokat és verzióikat **Blob Storage** őrizné; eseményvezérelt, rövid előfeldolgozáshoz **Azure Functions**, a nehezebb parsing/OCR/embedding feladatokhoz sorból dolgozó konténeres worker lenne célszerű. **Azure AI Search** akkor váltaná a Qdrantot, ha a menedzselt üzemeltetés és a beépített hibrid keresés előnye megéri a költséget; nem használnám párhuzamosan mindkettőt azonos célra. A dokumentumverziókhoz, feldolgozási állapotokhoz és jogosultsági kapcsolatokhoz **Azure SQL** elegendő lehet; Cosmos DB-t csak indokolt dokumentumos adatmodell vagy globális elosztás esetén választanék.

A felhasználókat **Microsoft Entra ID** hitelesítené, az API ellenőrizné a tokeneket, és a felhasználó/csoport ACL-szűrőjét még a retrieval során alkalmazná. **Managed Identity** biztosítaná a szolgáltatások közti hozzáférést; a megmaradó titkokat **Key Vault** tárolná. **Application Insights** és OpenTelemetry mérné a késleltetést, hibákat, feldolgozási sorhosszt és keresési minőséget, érzékeny tartalom naplózása nélkül. Nagyobb állománynál aszinkron ingestion, idempotens verziókezelés, retry/dead-letter sor, batch embedding, indexkapacitás-tervezés és terhelésalapú workerskálázás kellene. Mentési, törlési és adatmegőrzési szabályokat az ügyfél elvárásaiból vezetnék le.

## Mi hiányzik a valódi RAG-hoz?

Ez a prototípus a retrieval réteget valósítja meg, válaszgenerálás nélkül.
Teljes ingestion során az eredeti fájlokat tartósan, verziózottan tárolnánk.
A formátumfüggő parsingot szükség szerint OCR, tisztítás és szerkezetfelismerés követné.
A chunkokhoz dokumentumverziót, oldalszámot, forráshivatkozást és hozzáférési metaadatokat társítanánk.
Az embeddingeket és keresési indexeket újrafeldolgozható, idempotens folyamat építené.
Felhasználói kérdéskor először azonosítanánk a felhasználót és meghatároznánk a látható dokumentumokat.
A retrieval ezekből választaná ki a releváns kontextust, opcionálisan hibrid kereséssel és rerankinggel.
A kiválasztott részletekből tokenkeretbe illeszkedő, egyértelmű forrásazonosítókat tartalmazó prompt készülne.
Az LLM ebből fogalmazna választ, és elégtelen bizonyíték esetén ezt jelezné.
A dokumentumtartalmat nem megbízható utasításként, hanem forrásadatként kezelnénk a prompt injection kockázatának csökkentésére.
A válasz állításaihoz chunk- és dokumentumverzióra mutató hivatkozások kapcsolódnának, amelyeket a felhasználó megnyithat.
A retrieval minőségét, a válasz forráshűségét, a jogosultsági szűrést és a visszautasítás helyességét külön tesztelnénk és monitoroznánk.

## Repository tartalma

```text
app/                   API, konfiguráció, embedding/chunkolás, keresési szolgáltatás
docs/discovery.md      Öt ügyfélkérdés és feltételezések
examples/documents.json Magyar és angol mintadokumentumok
scripts/load_examples.py Minták feltöltése
tests/                 API-, perzisztencia- és opcionális modelltesztek
pyproject.toml         Csomagdefiníció és függőségek
requirements-lock.txt  Tesztelt Linux/Python 3.14 CPU-s verziók
task.md                Eredeti feladatkiírás
```

A `.gitignore` kizárja az adatokat, a virtuális környezetet, cache-eket és a `.env` fájlt. GitHubra feltöltés előtt a feladatkiírás megoszthatóságáról a repository tulajdonosa dönthet.

## AI-eszközök használata

A megvalósításhoz OpenAI Codexet használtunk a feladat elemzésére, a kód és a dokumentáció elkészítésére, valamint a tesztek megírására és futtatására. A FastAPI és Qdrant választása a felhasználótól származik; a helyi többnyelvű embeddinget, a venv-alapú indítást, a magyar README-t és a duplikált ID-k 409-es kezelését a felhasználó külön megerősítette. Az automatizált ellenőrzések eredménye nem helyettesíti a beadó saját kódáttekintését. A beadás előtt ezt a megjegyzést egészítsd ki az általad ténylegesen ellenőrzött és módosított részekkel; jelenleg nem állítunk elvégzett emberi kódellenőrzést.
