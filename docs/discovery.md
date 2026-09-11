# Ügyfélkérdések és kiinduló feltételezések

## A fejlesztés előtt feltett öt kérdés

1. Milyen formátumú, nyelvű és méretű dokumentumok érkeznek, és milyen gyakran változnak?
2. Mekkora dokumentumállományra, párhuzamos használatra és válaszidőre kell tervezni?
3. Minden felhasználó minden dokumentumot láthat, vagy szükséges felhasználói, csoportos és szervezeti hozzáférés-szabályozás?
4. Dokumentumrészleteket várnak, vagy forrásokkal alátámasztott, megfogalmazott válaszokat; milyen példakérdésekkel mérhető a találatok minősége?
5. Elhagyhatják-e az adatok a vállalati környezetet, és milyen telepítési, megőrzési és törlési előírásokat kell teljesíteni?

## A prototípushoz rögzített feltételezések

- JSON-ban érkező, elsősorban magyar és angol egyszerű szöveget dolgozunk fel; PDF, OCR és fájlkonverzió nincs a kezdeti körben.
- Kis dokumentumállományra és kevés párhuzamos kérésre készül a lokális bemutató; nincs vállalt rendelkezésre állás vagy válaszidő.
- A lokális demót egy megbízható felhasználó használja. Nyilvános szolgáltatásként további hozzáférés-védelem szükséges.
- A keresés forrásrészleteket ad vissza. Az LLM-es válaszgenerálás későbbi továbbfejlesztés.
- A dokumentumok és keresési adatok helyben maradnak, és újraindítás után is rendelkezésre állnak.

A modell és az indítási mód végleges választását a README rögzíti.
