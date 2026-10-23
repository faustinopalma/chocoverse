# La ripresa delle forniture di Giandoria, analizzata con un Fabric Data Agent

## Giandoria nel Chocoverse

Giandoria è un'azienda italiana del cioccolato che rifornisce negozi di proprietà, supermercati e canali export.
**Chocoverse** è il suo mondo di business interconnesso: fornitori, pianificatori, reparti produttivi,
partner logistici e clienti.

Ordini dei clienti, previsioni condivise e informazioni sulle vendite alimentano la pianificazione della domanda.
La finanza segue costi e liquidità lungo la filiera; Microsoft Fabric riunisce i dati aziendali.

## Questa analisi della ripresa

A settembre 2047 Giandoria amplia i canali della grande distribuzione e dell'export. A fine ottobre un guasto
imprevisto richiede una manutenzione non programmata sulla linea di stampaggio, che dà forma al cioccolato,
riducendone la capacità. A fine dicembre Giandoria aggiunge turni di lavoro.

A fine febbraio Operations si chiede: **Giandoria è tornata a rifornire i clienti?**
Come sono andate le vendite durante l'interruzione? Le spedizioni si sono riprese?
Ci sono ancora ordini in attesa di spedizione?

Chiediamolo a un Fabric Data Agent, partendo dalle vendite. Confrontiamo settembre, prima della manutenzione,
novembre, durante la riduzione di capacità, e febbraio, dopo l'aggiunta dei turni.

Le domande originali, gli screenshot delle risposte e il grafico di Fabric restano in inglese.
Il racconto e i commenti ai risultati sono tradotti in italiano.

## 1. Misurare il cambiamento nelle vendite

Operations deve prima individuare quali prodotti hanno subito un calo delle vendite durante il problema
di fornitura e quanto hanno recuperato. Confrontiamo il *sell-out*, il cioccolato effettivamente venduto
ai clienti, nei tre mesi. Sono vendite realizzate, non una misura della domanda potenziale:
la disponibilità può limitare ciò che i clienti riescono ad acquistare.
Il confronto individua i prodotti da seguire poi in fabbrica.
Le medie per giorno di calendario rendono confrontabili mesi di durata diversa.

**Domanda registrata — vendite per prodotto:**

> How did daily sales change across September 2047, November 2047 and February 2048? Use our semantic-model
> sell-out measures. Give one table with each product's average kg per calendar day in the three months,
> rounded to one decimal. Identify the products behind the change.

![Risposta di Fabric: sell-out per prodotto e giorno di calendario nei tre mesi del confronto.][recovery-sales]

Il fondente passa da **211,5 a 147,6 a 227,2 kg/giorno**; il cioccolato al latte da
**190,4 a 106,9 a 169,9 kg/giorno**. Il gianduja stagionale segue un percorso diverso, con un picco a novembre.
L'analisi prosegue quindi su fondente e latte, che condividono la linea di stampaggio.

## 2. Seguire il fenomeno in fabbrica

Operations deve ora verificare se la fabbrica sta rifornendo i prodotti all'origine del cambiamento nelle vendite.
Il *throughput* è il volume che attraversa la produzione nel tempo.
Confrontiamo quantità avviate, rilasciate e spedite. Il Lakehouse contiene questi dati produttivi per prodotto.

**Domanda registrata — flusso produttivo:**

> Does the sales pattern also appear in supply? Use Lakehouse SQL to compare September 2047, November 2047
> and February 2048. Combine dark70 and milk and return one row per month with started, released and shipped
> kg per calendar day, rounded to one decimal. Keep production flows distinct from sell-out.

![Risposta di Fabric: quantità avviate, rilasciate e spedite di fondente e latte
per giorno di calendario.][recovery-flow]

Le spedizioni complessive passano da **397,2 a 253,1 a 404,9 kg/giorno**.
Avvii e rilasci mostrano lo stesso calo a novembre e la ripresa a febbraio.
L'andamento è coerente con la minore capacità di stampaggio durante la manutenzione e il successivo aumento.
Il solo confronto mensile non permette di separare gli effetti della capacità da quelli della domanda.

Il flusso produttivo è tornato al ritmo di settembre. La prossima domanda è come questa ripresa raggiunga
gli ordini ancora da evadere.

## 3. Verificare gli ordini arretrati

Il ritmo recuperato dalla fabbrica solleva un'altra domanda: che cosa è successo agli ordini ancora in attesa
di spedizione? Questo volume è il *backlog*, cioè gli ordini arretrati dell'azienda.
Operations deve conoscerne l'andamento giornaliero e il saldo di fine mese per capire se la ripresa
sta raggiungendo anche quegli ordini.

**Domanda registrata — recupero del backlog:**

> Has the company also reduced its backlog? Use the Lakehouse's observed company balances from 2047-11-01
> through 2048-02-29. Plot daily backlog and finished stock as a native line chart. For November and February,
> report average observed backlog, last observed backlog and the number of observed dates.
> Use every available observation.

![Risposta di Fabric: backlog aziendale di novembre e febbraio e numero di date osservate.][recovery-backlog]

Il grafico appartiene alla **stessa domanda riportata sopra** e usa tutte le **121 date osservate** per serie.

![Grafico nativo di Fabric: backlog in blu e scorte di prodotto finito in magenta,
con 121 date osservate per linea.][recovery-history]

Il backlog medio osservato scende da **983,0 kg a novembre a 533,3 kg a febbraio**.
L'ultima osservazione di febbraio è **0 kg**, contro **1.119 kg** alla chiusura di novembre.
La media rivela anche il carico di lavoro gestito durante febbraio.
Il confronto usa 30 osservazioni di novembre e 29 di febbraio.

## 4. Che cosa ci dice l'analisi

La ripresa di Giandoria emerge da tutte e tre le risposte. Le vendite di fondente superano il ritmo di settembre,
mentre quelle di cioccolato al latte recuperano solo parte del calo.
Le spedizioni complessive di fondente e latte raggiungono **404,9 kg/giorno**,
poco sopra i **397,2 kg/giorno** di settembre.

Il flusso recuperato raggiunge anche gli ordini arretrati: il backlog medio scende da
**983,0 kg a novembre a 533,3 kg a febbraio**, e febbraio si chiude a **zero**.
Il saldo finale segnala l'azzeramento del backlog; la media mensile mostra che Giandoria stava ancora
smaltendo l'arretrato nel corso di febbraio.

L'analisi parte dai segnali commerciali, verifica le spedizioni della fabbrica e segue gli ordini in attesa.
Con domande in linguaggio naturale, l'analista percorre questo filo tra misure del modello semantico,
SQL sul Lakehouse e un grafico giornaliero. Le risposte mostrano una ripresa delle forniture e dell'evasione
degli ordini, con un recupero non uniforme delle vendite dei prodotti.

---

## Fonti

L'analisi usa i dati di settembre e novembre 2047 e febbraio 2048, disponibili fino al **3 marzo 2048**.
Le [risposte complete e i valori verificati][evidence] supportano i risultati presentati.
La [guida tecnica][companion] spiega come riprodurre l'analisi e ne documenta i limiti di verifica.
Questa è la traduzione della [versione inglese di riferimento](./data-agent-story.md).

## Nota finale — seguire Giandoria nel Chocoverse

Questa analisi è un episodio di **Chocoverse**, l'universo di business di Giandoria in evoluzione.
La prossima analisi potrà seguire come Giandoria trasforma la ripresa in forniture affidabili nei diversi canali.

Fabric offre prospettive complementari: Eventhouse e Real-Time Dashboards seguono gli eventi operativi;
Lakehouse, modello semantico e Power BI organizzano viste analitiche e misure di business.
Ontology collega le entità, il Data Agent risponde alle domande sulle fonti configurate e la Decision Room
supporta indagini soggette a governance.

Il [percorso introduttivo del progetto](../README.md) presenta il Chocoverse nel suo insieme.
Il [repository originale](https://github.com/faustinopalma/chocoverse) e la [guida tecnica][companion]
forniscono istruzioni di implementazione e riproduzione.

[recovery-sales]: ./images/data-agent-story/recovery-sales.png
[recovery-flow]: ./images/data-agent-story/recovery-flow.png
[recovery-backlog]: ./images/data-agent-story/recovery-backlog.png
[recovery-history]: ./images/data-agent-story/recovery-history.svg
[evidence]: ./data-agent-recovery-evidence.json
[companion]: ./29-data-agent-companion.md
