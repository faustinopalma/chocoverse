# 16 — References

Sources for the design are grouped as **M** (market), **P** (production, supply and planning) and **F** (platform,
Azure and cost), and cited in the chapters as [M#], [P#] and [F#]. This chapter records source details, known gaps
and rules for keeping references current.

---

## 16.1 How to read this chapter

| Family | Topic | Entries | Cited | Not cited |
|---|---|---:|---:|---|
| **M** | Italian chocolate market, seasons, campaigns, calendar, territory | 35 | 32 | M12, M22, M25 |
| **P** | Processes, machines, quality, raw materials, suppliers, regulation, planning methods | 49 | 49 | — |
| **F** | Microsoft Fabric, Azure, Foundry, prices, billing and tenant governance | 93 | 86 | F6, F8, F24, F25, F34, F41, F59 |

* **Columns.** *Used for* names the facts taken from the source. *Cited in* lists the chapters that cite it.
* **Not cited.** Unused entries remain numbered so existing citations keep their meaning.
* **Site-level entries.** For some production sources the research notes recorded only the website. These are
  marked *(site)*; the link points to the site, and *Used for* says which facts came from it.
* **Values are for parametrization.** Trade and vendor figures describe typical ranges, not one plant or one
  company. The chapters mark values without a source as *(estimate)*, *(assumption)* or *(derivation)*, and claims
  still to confirm as *(verify)*.
* **No chocolate brands.** The universe and its companies are fictional (chapter 02). The descriptions name
  publishers, equipment vendors and ingredient suppliers, but no chocolate brand. When a source is a chocolate
  maker's own page, or discusses one, it is described in general terms; only the link shows the site.
* **Prices change.** Azure, Fabric and model prices were checked in October 2026, in USD. They must be checked
  again before phase 0 (§16.6).

---

## 16.2 Market and seasonality (M)

| ID | Source | Used for | Cited in | Link |
|---|---|---|---|---|
| M1 | Great Italian Food Trade: Italian chocolate exports 2025, with industry-association data | Italian production for final consumption in 2024 (372,665 t, €6.607 bn); exports in 2024 (€2.88 bn, 414,940 t) and their main markets | 02, 03 | <https://www.greatitalianfoodtrade.it/cioccolato/cioccolato-italiano-export-2025-nutraceutica-sostenibilita/> |
| M2 | Italia Insights: the chocolate market in Italy | Cross-check of the export figures; leading regions and provinces; higher demand in the North, festival peaks in the South | 02, 03 | <https://italiainsights.it/ricerche-di-mercato/agroalimentare-alimenti/il-mercato-del-cioccolato-in-italia/> |
| M3 | Mordor Intelligence: Italy chocolate market | Retail market size and growth (≈ $2.89 bn in 2025, ≈ 5.3% a year); mix by type, form, price tier and channel (supermarkets and hypermarkets ≈ 65% of spend); dark as the fastest-growing segment; visitors at large chocolate festivals | 02, 03 | <https://www.mordorintelligence.com/industry-reports/italy-chocolate-market> |
| M4 | Manageritalia: five trends in Italian chocolate consumption | Per-capita consumption (≈ 3–4.5 kg per year) | 03 | <https://www.manageritalia.it/economia/italiani-pazzi-per-il-cioccolato-5-trend-sui-consumi/> |
| M5 | Wikipedia: Cocoa crisis (2020s) | Cocoa price history: about $2,500 per tonne for decades, then the London peak of $11,530 per tonne in June 2024; the model for the cocoa-spike scenario | 03, 05, 09 | <https://en.wikipedia.org/wiki/Cocoa_crisis_(2020s)> |
| M6 | Vespertool: chocolate demand more price-sensitive than expected | Cocoa butter, mass and powder prices in 2025; chocolate price rises in Europe in 2025 (+15% to +32%); European price elasticity of 0.7–0.8 instead of the 0.4–0.5 assumed before | 03, 05 | <https://vespertool.com/news/chocolate-demand-proves-more-price-sensitive-than-expected/> |
| M7 | Teleborsa: Halloween in Italy, October sales | Halloween as a minor peak: October sweet sales 13% above the monthly average (2024) | 03 | <https://www.teleborsa.it/News/2025/10/27/halloween-in-italia-boom-di-caramelle-e-vendite-in-crescita-del-13percent-nel-mese-di-ottobre-127.html> |
| M8 | ItalyPost: planning supplier holidays, maintenance and flows in summer | Praline shipments to the trade stop from mid-June to mid-September | 03, 05, 06 | <https://www.italypost.it/news/monitor/9333/ferie-fornitori-manutenzione-e-flussi-lestate-si-pianifica-non-si-subisce.html> |
| M9 | TCT: summer closures 2025 | Collective factory closure of 2–3 weeks around 15 August, typically about 10–22 August | 03, 04, 06 | <https://www.tct-srl.it/chiusure-estive-metalmeccanica-2025/> |
| M10 | MDPI *Businesses* 3(3):30, 2023 | Confectionery among the retail categories most affected by heat | 03 | <https://www.mdpi.com/2673-7116/3/3/30> |
| M11 | Tuttogratis: the Easter-egg business in 2025 | Easter-egg market size (single source); price points of industrial and artisan eggs | 03 | <https://attualita.tuttogratis.it/2025/04/20/il-business-delle-uova-di-pasqua-nel-2025-tra-artigianato-e-grande-distribuzione/> |
| M12 | Teleborsa: Easter 2024 and hen eggs | A warning only: its "300 million eggs" are hen eggs, not chocolate eggs | Not cited | <https://www.teleborsa.it/News/2024/03/28/pasqua-300-milioni-di-uova-nel-piatto-colomba-al-top-113.html> |
| M13 | Bakeit: optimising Easter-egg production | Industrial Easter calendar: bulk production from November and storage; eggs on the shelf from early February; most eggs bought in the last 2–3 weeks | 03, 04 | <https://www.bakeit.it/blogs/news/come-ottimizzare-la-produzione-delle-uova-di-pasqua-e-aumentare-la-redditivita> |
| M14 | Anteprima Volantino: retail flyer, Easter 2024 | Easter promotion mechanics in large retail (vouchers, second item at a discount) | 03 | <https://www.anteprimavolantino.it/17920/volantino-ipercoop-dal-21-marzo-al-1-aprile-2024/> |
| M15 | QuiFinanza: value of panettone and pandoro, Christmas 2024 | Panettone and pandoro, which compete with chocolate for the Christmas budget and shelf; Italy ≈ 40% of European consumption | 03 | <https://quifinanza.it/economia/panettoni-pandori-valore-natale-2024/866895/> |
| M16 | Dai Colli Fiorentini: advent-calendar searches in Italy, 2024 | Online interest in advent calendars (+22% in 2024); a weak proxy, since no sales figures exist | 03 | <https://daicollifiorentini.it/calendario-dellavvento-boom-di-ricerche-in-italia-22-nel-2024/> |
| M17 | An artisan chocolatier's page on Christmas gift boxes | Corporate-gift timeline: quotes from September, orders October to mid-November, delivery by mid-December | 02, 03, 05 | <https://www.bramardicioccolato.it/confezioni-natalizie.php> |
| M18 | University of Bari: a cancer-research charity's chocolate day, 8 November 2025 | Charity campaign: 200 g dark-chocolate pack, €15 minimum donation, ≈ 2,400 squares | 02, 03 | <https://www.uniba.it/it/notizieuniba/anno-2025/cioccolatini-della-ricerca-airc-8-novembre-2025> |
| M19 | Il Reporter: a leukaemia charity's Easter eggs, 2025 | Charity Easter egg: €15 minimum, ≈ 4,900 squares, a weekend before Easter; more than 16.7 million eggs in over 30 years | 02, 03 | <https://ilreporter.it/sezioni/cronaca-e-politica/uova-di-pasqua-ail-2025-dove-trovarle-il-costo-e-le-piazze/> |
| M20 | Events page of the same charity | Dates of the 2026 Easter campaign weekend | 03 | <https://www.ail.it/ail-eventi-e-news/ail-manifestazioni/map-test> |
| M21 | Nordest News: chocolate hearts of a rare-disease charity, 20–21 December 2025 | Christmas charity box: 220 g of heart pralines, more than 3,000 collection points | 02, 03 | <https://www.nordestnews.it/2025/11/10/il-20-e-21-dicembre-arrivano-nelle-piazze-italiane-i-cuori-di-cioccolato-di-fondazione-telethon-2/> |
| M22 | Lagardère Travel Retail Italy: duty free | Chocolate in airport travel retail | Not cited | <https://www.lagardere-tr.it/it/competenze/duty-free-luxury> |
| M23 | *BMJ Open* 8(4):e019788 | UK study of 32,249 households: chocolate and confectionery are price-sensitive, most of all in low-income households | 03 | <https://bmjopen.bmj.com/content/8/4/e019788> |
| M24 | TrenderHQ: Easter dates 2026–2045 | Easter Sundays, including 13 April 2031 | 03, 14 | <https://trenderhq.com/easter-dates-for-the-next-20-years-2026-2045/> |
| M25 | Calendario 365: Shrove Tuesday | Carnival dates | Not cited | <https://www.calendario-365.it/giorni-festivi/marted%C3%AC-grasso.html> |
| M26 | Festività IT: Italian holidays 2026 | National public holidays | 03, 14 | <https://festivita-it.it/2026> |
| M27 | SCF Group: Black Friday 2026 | Black Friday and Black Week dates | 03 | <https://www.scfgroup.it/black-friday-2026-date-numeri-e-commerce/> |
| M28 | PMI.it: winter sales 2026 by region | Winter sales calendar | 03 | <https://www.pmi.it/economia/mercati/484489/saldi-invernali-2026-calendario-regioni.html> |
| M29 | Everyeye: summer sales 2026 by region | Summer sales calendar | 03 | <https://lifestyle.everyeye.it/notizie/saldi-estivi-2026-date-ufficiali-regione-regione-884484.html> |
| M30 | Scuola.net: school calendar 2025–2026 by region | School terms and holidays | 03, 14 | <https://www.scuola.net/news/1084/calendario-scolastico-2025-2026-festivita-regione-per-regione> |
| M31 | CNA: chocolate in Italy, 2022 report | Regional pattern: consumption higher in the North than in the Centre and South | 02, 03 | <https://www.cna.it/wp-content/uploads/2022/11/il-cioccolato-in-Italia2022.pdf> |
| M32 | ISTAT: tourism statistics | Tourism seasonality by city, used for flagship-store footfall | 02, 03, 14 | <https://www.istat.it/en/archivio/tourism> |
| M33 | ISTAT: tourism tables by municipality | Tourist arrivals and nights by municipality | 02, 03, 14 | <https://contact.istat.it/s/article/Turismo-tavole-a-livello-comunale> |
| M34 | Open Data Sicilia: Italian municipalities | Municipalities with population and coordinates, derived from ISTAT, for the territory master data | 02, 14 | <https://github.com/opendatasicilia/comuni-italiani> |
| M35 | ISTAT: open data portal | Official open data for the territory | 02, 14 | <https://www.istat.it/it/archivio/opendata> |

---

## 16.3 Production, supply and planning methods (P)

| ID | Source | Used for | Cited in | Link |
|---|---|---|---|---|
| P1 | CacaoCraft *(site)* | Cleaning; roasting temperatures and times; conching durations | 04 | <https://cacaocraft.co> |
| P2 | Scientific review on chocolate particle size (ScienceDirect) | Particle size after grinding and refining; finished-product limits | 04 | <https://www.sciencedirect.com/science/article/pii/S092422441930305X> |
| P3 | Huanda Cocoa: Dutch-process cocoa explained | Alkalising (pH change) and pressing (fat left in the press cake) | 04 | <https://huandacocoa.com/dutch-process-cocoa-explained.html> |
| P4 | Bühler: conching | Industrial conche batch sizes | 04 | <https://www.buhlergroup.com/global/en/process-technologies/Conching.html> |
| P5 | Probat: refiner-conche | Conche batch sizes, from pilot to 1–6 t | 04 | <https://www.probat.com/products/machines/conching-flavour-treatment/refiner-conche/> |
| P6 | D Baker Aid *(site)* | Tempering curves for dark, milk and white chocolate | 04 | <https://dbakeraid.com> |
| P7 | Chocolate conche machine supplier *(site)* | Holding tanks: temperature and maximum holding time | 04 | <https://chocolateconchemachine.com> |
| P8 | Kurt Makina *(site)* | Five-roll refiner throughput | 04 | <https://kurtmakina.com> |
| P9 | Alpy Group *(site)* | Throughput of tempering machines and moulding lines | 04 | <https://alpygroup.com> |
| P10 | Top Choco Machine *(site)* | Cooling tunnels: dwell time, zone temperatures, humidity | 04 | <https://topchocomachine.com> |
| P11 | Aasted *(site)* | Easter-egg shells (spinning, cold stamping), joining, surprise insertion, wrapping | 04 | <https://aasted.eu> |
| P12 | Made-in-China *(site)* | Egg-wrapping speeds; robotic egg lines (≈ 16–17 large eggs per minute) | 04 | <https://www.made-in-china.com> |
| P13 | Selmi Group *(site)* | Praline technologies (shell moulding, one-shot, enrobing) and gianduja extrusion | 04 | <https://selmi-group.com> |
| P14 | Atlas Hazelnuts *(site)* | Hazelnut roasting and skin removal | 04 | <https://atlashazelnuts.com> |
| P15 | Nutalia *(site)* | Hazelnut paste: milling temperature and fineness | 04 | <https://nutalia.it> |
| P16 | Choc Machines *(site)* | Wrapping speeds for pralines and bars | 04 | <https://chocmachines.com> |
| P17 | PT Chronos: palletizing robot | Palletizing pick rates | 04 | <https://ptchronos.com/products/palletizing/palletizing-robots/high-performant-palletizing-robot> |
| P18 | Oxmaint: changeover time reduction in food plants | Allergen changeover durations and phases; swab verification; common failure modes | 04 | <https://oxmaint.com/industries/food-manufacturing/food-plant-changeover-time-reduction-smed-cmms-guide> |
| P19 | iFactory: MTBF and MTTR benchmarks in FMCG | MTBF and MTTR ranges, used as a proxy | 04 | <https://ifactoryapp.com/industries/fmcg/mtbf-mttr-fmcg-calculation-benchmarks> |
| P20 | Bytes: changeover sequencing for chocolate | Sequence dark → milk → nut-containing | 04 | <https://mybytes.com/en/use-cases/chocolate/changeover-sequencing> |
| P21 | TA Instruments *(site)* | Viscosity of chocolate measured with the Casson model (yield value and plastic viscosity) | 04 | <https://www.tainstruments.com> |
| P22 | Domson *(site)* | Causes of fat bloom and sugar bloom | 04 | <https://domson.co.uk> |
| P23 | I Need Me Some Chocolate *(site)* | Shelf life and storage conditions by product type | 02, 04 | <https://ineedmesomechocolate.com> |
| P24 | Fabrico *(site)* | OEE of confectionery lines (≈ 55–70%; world class 75–85%) | 04 | <https://fabrico.io> |
| P25 | Study on energy use in cocoa processing (PubMed Central) | Energy intensity, ≈ 500–660 kWh per tonne (not Italy-specific) | 04 | <https://pmc.ncbi.nlm.nih.gov/articles/PMC10969383/> |
| P26 | Origin Direct *(site)* | Cocoa origins, shares and crop calendars | 02, 05 | <https://origindirectgroup.com> |
| P27 | Trading Economics: cocoa | Cocoa futures: all-time high of $12,906 per tonne (New York, December 2024); about $5,700 per tonne in October 2026 | 03, 05 | <https://tradingeconomics.com/commodity/cocoa> |
| P28 | GoComet *(site)* | Ocean transit times from West Africa to Italian ports | 02, 05 | <https://www.gocomet.com> |
| P29 | Omas Commodities: storing cocoa beans | Bean storage: moisture, humidity, temperature, FIFO | 04, 05 | <https://omascommodities.com/how-to-store-cocoa-beans-properly-to-maintain-quality/> |
| P30 | Agrion: Tonda Gentile 2025–2027 | Piedmont hazelnuts (Tonda Gentile): area, harvest and production | 02, 05 | <https://agrion.it/tonda-gentile-e-produttiva-2025-2027/> |
| P31 | RAI News Piemonte: hazelnut harvest, September 2026 | Piedmont crop collapse in 2024 and partial recovery in 2025 | 02, 05 | <https://www.rainews.it/tgr/piemonte/articoli/2026/09/titolo-nocciola-dee6353d-5965-4cd7-9414-571d28e3b1b2.html> |
| P32 | CLAL: skim milk powder prices | Skim milk powder price level | 02, 05 | <https://www.clal.it/en/?section=skim_west> |
| P33 | Alibaba *(site)* | Toy surprises: minimum orders, unit prices, 9–15 weeks door to port, air-freight option | 02, 03, 04, 05, 06 | <https://www.alibaba.com> |
| P34 | Ready Set Italia *(site)* | Ferragosto closures; seasonal hiring peaks | 04 | <https://readysetitalia.com> |
| P35 | Regulation (EU) 2024/3234 amending the EU deforestation regulation | The deforestation regulation as amended: due-diligence statement filed once by the first operator, plot geolocation, application dates | 05 | <https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex:32024R3234> |
| P36 | Council of the EU: targeted revision of the deforestation regulation, 18 December 2025 | Postponement to 30 December 2026 (30 June 2027 for micro and small operators) and simplification; this is why the rule set is a scenario parameter | 05 | <https://www.consilium.europa.eu/en/press/press-releases/2025/12/18/deforestation-council-signs-off-targeted-revision-to-simplify-and-postpone-the-regulation/> |
| P37 | Akaygam: chillers | Glycol and water chillers; cocoa-butter melting range (≈ 30–34 °C) | 04, 05 | <https://akaygam.com/chiller.html> |
| P38 | Directive 2000/36/EC on cocoa and chocolate products | Definition of gianduja nut chocolate: 20–40 g of hazelnuts per 100 g | 02 | <https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32000L0036> |
| P39 | Jain, Barber and Osterfeld: Expert simulation for on-line scheduling. Winter Simulation Conference, 1989 | The earliest use of backward simulation for scheduling named by the review [P47] | 17 | <https://doi.org/10.1145/76738.76857> |
| P40 | Watson, Medeiros and Sadowski: Generating component release plans with backward simulation. Winter Simulation Conference, 1993 | Release plans for components, by simulating backwards from the due dates | 17 | <https://doi.org/10.1145/256563.256886> |
| P41 | Watson, Medeiros and Sadowski: A simulation-based backward planning approach for order release. Winter Simulation Conference, 1997 | Backward planning with simulation for order release; capacity-aware release and need dates | 17 | <https://repository.lsu.edu/infosys_pubs/259/> |
| P42 | Ying and Clark: Order release planning in a job shop using a bidirectional simulation algorithm. Winter Simulation Conference, 1994 | Order release with a simulation that runs forwards or backwards | 17 | <https://doi.org/10.1109/wsc.1994.717481> |
| P43 | Jain and Chan: Experiences with backward simulation based approach for lot release planning. Winter Simulation Conference, 1997 | Backward simulation for lot release planning, and its practical limits | 17 | <https://doi.org/10.1145/268437.268622> |
| P44 | Dori and Borrmann: Determination of float time for individual construction tasks using constraint-based discrete-event simulation. Winter Simulation Conference, 2012 | The float of each task from a forward and a backward simulation | 17 | <https://doi.org/10.1109/wsc.2012.6465193> |
| P45 | Laroque, Leißau, Scholl and Schneider: Backward simulation for production planning – recent advances in a real-world use-case. Winter Simulation Conference, 2021 | Backward simulation for production planning in an industrial case, a semiconductor plant | 17 | <https://informs-sim.org/wsc21papers/158.pdf> |
| P46 | Leißau and Laroque: Reverse engineering the future – an automated backward simulation approach to on-time production in the semiconductor industry. Winter Simulation Conference, 2023 | Automated reversal of a forward model on commercial simulation software; a forward check of the backward result; rules, such as the critical ratio, with no backward counterpart | 17 | <https://informs-sim.org/wsc23papers/170.pdf> |
| P47 | Leißau and Laroque: Backward-oriented decision and planning approaches in production scenarios: a systematic literature review and potential solution approach. SNE Simulation Notes Europe 34(3), 2024, pp. 111–122 | The literature on backward simulation from 1989 to 2022, and its earliest work | 17 | <https://www.sne-journal.org/fileadmin/user_upload_sne/SNE_Issues_OA/SNE_34_3/articles/sne.34.3.10691.tn.OA.pdf> |
| P48 | Li and Willis: An iterative scheduling technique for resource-constrained project scheduling. European Journal of Operational Research 56(3), 1992, pp. 370–379 | Forward and backward passes, iterated, to improve resource-constrained schedules | 17 | <https://doi.org/10.1016/0377-2217(92)90320-9> |
| P49 | Hanzálek and Šůcha: Time symmetry of resource constrained project scheduling with general temporal constraints and take-give resources. Annals of Operations Research 248, 2017, pp. 209–237 | Time symmetry: a scheduling problem and its mirror image are equivalent | 17 | <https://doi.org/10.1007/s10479-016-2184-6> |

---

## 16.4 Platform, Azure and cost (F)

| ID | Source | Used for | Cited in | Link |
|---|---|---|---|---|
| F1 | Fabric licenses | Power BI Pro licence needed to open content on capacities below F64 | 12, 13 | <https://learn.microsoft.com/en-us/fabric/enterprise/licenses> |
| F2 | Microsoft Fabric pricing | Capacity billed per second while active; price per CU-hour | 13, 15 | <https://azure.microsoft.com/en-us/pricing/details/microsoft-fabric/> |
| F3 | Azure Retail Prices API | Region prices for capacity units, OneLake and other meters; source of the price card | 11, 13, 15, 18 | <https://prices.azure.com/api/retail/prices> |
| F4 | Fabric capacities REST API: Suspend | Suspending a capacity from code | 12 | <https://learn.microsoft.com/en-us/rest/api/microsoftfabric/fabric-capacities/suspend> |
| F5 | Fabric capacities REST API: Resume | Resuming a capacity from code | 12 | <https://learn.microsoft.com/en-us/rest/api/microsoftfabric/fabric-capacities/resume> |
| F6 | Azure CLI: `az fabric capacity` | Command-line alternative to F4 and F5 | Not cited | <https://learn.microsoft.com/en-us/cli/azure/fabric/capacity> |
| F7 | Pause and resume your capacity | Suspending stops all items and bills the smoothed usage at once; `write` permission prerequisite; Microsoft's gallery runbook for pause and resume | 11, 12, 13 | <https://learn.microsoft.com/en-us/fabric/enterprise/pause-resume> |
| F8 | Warehouse pause and resume behaviour | Background on paused capacities | Not cited | <https://learn.microsoft.com/en-us/fabric/data-warehouse/pause-resume> |
| F9 | Throttling | Smoothing, carry-forward and throttling stages | 11, 13 | <https://learn.microsoft.com/en-us/fabric/enterprise/throttling> |
| F10 | Fabric trial | Trial capacity: limits; it can only be started from the user interface | 11, 12, 15 | <https://learn.microsoft.com/en-us/fabric/fundamentals/fabric-trial> |
| F11 | Create and manage budgets | Budgets, thresholds and action groups; delay of cost data | 11, 12, 13 | <https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets> |
| F12 | Action groups | Actions that budgets can trigger, including runbooks | 11, 12 | <https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/action-groups> |
| F13 | Eventstream capacity consumption | Eventstream meters (per hour, traffic, processor) | 12, 13 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-streams/monitor-capacity-consumption> |
| F14 | Eventstream settings | Throughput tiers | 10, 12, 14 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-streams/configure-settings> |
| F15 | Custom endpoint with Microsoft Entra ID authentication | Emitter authentication without keys | 10, 11, 12 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-streams/custom-endpoint-entra-id-auth> |
| F16 | Custom endpoint source | Event Hubs and Kafka protocols of the custom endpoint | 10 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-streams/add-source-custom-app> |
| F17 | Eventstream topology REST API | Reading source connections after deployment; pausing and resuming sources | 11, 12 | <https://learn.microsoft.com/en-us/rest/api/fabric/eventstream/topology> |
| F18 | Stream Analytics time management | Event-time policies that would drop or reorder accelerated events | 10 | <https://learn.microsoft.com/en-us/stream-analytics-query/time-management-azure-stream-analytics> |
| F19 | Eventstream SQL code editor | Stream processing with SQL and its time semantics | 10 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-streams/process-events-using-sql-code-editor> |
| F20 | Activator trigger model | Rules on objects and properties; conditions on state, thresholds and wall-time windows | 11, 12 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/data-activator/activator-trigger-model> |
| F21 | Activator latency | Rule evaluation delays | 11, 12 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/data-activator/activator-latency> |
| F22 | Activator rule actions | Email, Teams, Power Automate, Fabric items | 11, 12 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/data-activator/rule-actions> |
| F23 | Activator limitations | Limits and general availability | 11, 12 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/data-activator/data-activator-limitations> |
| F24 | Reflex (Activator) items REST API | Activator as code | Not cited | <https://learn.microsoft.com/en-us/rest/api/fabric/reflex/items> |
| F25 | Activator Git integration | Activator in source control | Not cited | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/git-activator> |
| F26 | Real-Time Intelligence consumption | Eventhouse uptime billing (vCores × active seconds) | 11, 12, 13, 15 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/real-time-intelligence-consumption> |
| F27 | Eventhouse smart capacity control | Auto-suspend and wake-up; minimum consumption ("always on") | 11, 12, 13, 15 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/eventhouse-smart-capacity-control> |
| F28 | Eventhouse OneLake availability | Delta copy of KQL tables in OneLake, with no extra storage cost | 10, 12 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-house-onelake-availability> |
| F29 | Eventhouse destination of an Eventstream | Direct ingestion into Eventhouse tables | 10 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-streams/add-destination-kql-database> |
| F30 | Kusto batching policy | Default batching of up to 5 minutes; tuning to seconds | 10, 12, 15 | <https://learn.microsoft.com/en-us/kusto/management/batching-policy?view=microsoft-fabric> |
| F31 | Kusto retention policy | Retention based on ingestion time | 10, 12, 14 | <https://learn.microsoft.com/en-us/kusto/management/retention-policy?view=microsoft-fabric> |
| F32 | Digital twin builder | Optional digital-twin item | 11, 12 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/digital-twin-builder/overview> |
| F33 | Fabric Maps | Map of the territory | 11, 12 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/map/about-fabric-maps> |
| F34 | Fabric IQ overview | Background on Fabric IQ | Not cited | <https://learn.microsoft.com/en-us/fabric/iq/overview> |
| F35 | Fabric IQ ontology | Optional ontology of the universe | 11, 12 | <https://learn.microsoft.com/en-us/fabric/iq/ontology/overview> |
| F36 | Fabric data agent | Natural-language questions over the data; prerequisites | 09, 11, 12, 15 | <https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent> |
| F37 | Foundry Agent Service: Fabric data-agent tool | The classic Fabric data-agent tool of Foundry, which is being replaced | 09, 12, 15 | <https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/fabric> |
| F38 | Foundry Agent Service: Fabric IQ tool | Agents that reach a Fabric data agent (preview) | 09, 15 | <https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/fabric-iq> |
| F39 | SQL database in Fabric: compute usage | Optional relational store and its billing | 10, 12, 15 | <https://learn.microsoft.com/en-us/fabric/database/sql/control-compute-usage> |
| F40 | Real-Time Dashboard Git integration | Dashboards as code | 11 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/git-real-time-dashboard> |
| F41 | Real-Time hub business events | Background on business events | Not cited | <https://learn.microsoft.com/en-us/fabric/real-time-hub/business-events/business-events-overview> |
| F42 | Terraform provider `microsoft/fabric` | Fabric items as code | 11, 12, 15 | <https://github.com/microsoft/terraform-provider-fabric> |
| F43 | Fabric CLI (`fab`) | Admin and wiring calls from scripts | 11, 12, 15 | <https://github.com/microsoft/fabric-cli> |
| F44 | fabric-cicd | Selected item-definition publisher; walking skeleton pins 1.4.0 | 11, 12, 15, 20 | <https://microsoft.github.io/fabric-cicd/latest/> |
| F45 | Bicep and ARM: `Microsoft.Fabric/capacities` | Capacity as code; no overage property in the schema | 11, 12, 13, 15 | <https://learn.microsoft.com/en-us/azure/templates/microsoft.fabric/capacities> |
| F46 | Tenant settings: developer settings | Service principals and the Fabric APIs | 11, 12, 15 | <https://learn.microsoft.com/en-us/fabric/admin/service-admin-portal-developer> |
| F47 | Admin REST API: list tenant settings | Reading tenant settings from code | 11, 12, 15 | <https://learn.microsoft.com/en-us/rest/api/fabric/admin/tenants/list-tenant-settings> |
| F48 | Tenant settings: admin API settings | Service principals and admin APIs (off by default) | 11 | <https://learn.microsoft.com/en-us/fabric/admin/service-admin-portal-admin-api-settings> |
| F49 | Foundry Agent Service overview | Foundry resource, project and model deployments (Global Standard) | 09, 11, 12 | <https://learn.microsoft.com/en-us/azure/foundry/agents/overview> |
| F50 | Foundry blog: Agent Service generally available | Service status | 09, 11, 15 | <https://devblogs.microsoft.com/foundry/foundry-agent-service-ga/> |
| F51 | Microsoft Agent Framework overview | Agent runtime inside our own containers | 09, 11, 15 | <https://learn.microsoft.com/en-us/agent-framework/overview/> |
| F52 | Azure OpenAI pricing | Model token prices (the page is rendered by script; see F63) | 09, 13, 15 | <https://azure.microsoft.com/en-us/pricing/details/azure-openai/> |
| F53 | Batch processing with Azure OpenAI in Foundry | 50% discount and 24-hour turnaround | 09, 13 | <https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/batch> |
| F54 | Structured outputs | Schema-bound agent answers; not supported together with parallel tool calls | 09 | <https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs> |
| F55 | Azure Container Apps overview | Hosting of the simulators and Lab Control | 11 | <https://learn.microsoft.com/en-us/azure/container-apps/overview> |
| F56 | Container Apps jobs | Genesis, archive and batch jobs | 11 | <https://learn.microsoft.com/en-us/azure/container-apps/jobs> |
| F57 | Container Apps pricing | vCPU and memory rates; scale to zero | 11, 12, 13 | <https://azure.microsoft.com/en-us/pricing/details/container-apps/> |
| F58 | Event Hubs pricing | Throughput-unit rate for ingestion option B | 10, 12, 13, 15 | <https://azure.microsoft.com/en-us/pricing/details/event-hubs/> |
| F59 | Service Bus pricing | Background for a control queue | Not cited | <https://azure.microsoft.com/en-us/pricing/details/service-bus/> |
| F60 | Container Registry pricing | Basic tier per day | 13 | <https://azure.microsoft.com/en-us/pricing/details/container-registry/> |
| F61 | Azure Monitor pricing | Log Analytics and Application Insights per GB | 13, 18 | <https://azure.microsoft.com/en-us/pricing/details/monitor/> |
| F62 | Fabric item definitions overview | Items deployed from definitions stored in Git | 11, 12, 15 | <https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/item-definition-overview> |
| F63 | Third-party summaries of Azure OpenAI prices | Token prices of gpt-5-mini, gpt-5-nano, gpt-4.1-mini and gpt-4.1, to be checked against F52 | 09 | <https://pricepertoken.com/endpoints/azure>, <https://redresscompliance.com/azure-openai-enterprise-pricing-guide> and <https://www.wrvishnu.com/azure-ai-foundry-pricing-2026/> |
| F64 | Admin REST API: update tenant setting | Changing tenant settings from code | 11, 12, 15 | <https://learn.microsoft.com/en-us/rest/api/fabric/admin/tenants/update-tenant-setting> |
| F65 | Planning in Fabric IQ: writeback to Fabric SQL (preview) | Plan item with planning sheets, scenarios and writeback | 06, 11, 12, 14, 15 | <https://learn.microsoft.com/en-us/fabric/iq/plan/planning-concept-writeback> |
| F66 | Operations agents | Optional agent that watches the lab and recommends actions | 09, 11, 12 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/operations-agent> |
| F67 | Kusto update policy (Fabric) | Streaming ingestion on by default for Eventhouse tables; an update policy with a `join` needs it turned off upstream | 10, 12, 15 | <https://learn.microsoft.com/en-us/kusto/management/update-policy?view=microsoft-fabric> |
| F68 | Eventstream with an Eventhouse direct-ingestion destination, through the API | Properties of the destination; silent *Warning* state when they are wrong | 12 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-streams/api-kusto-pull-destination> |
| F69 | Eventstream REST API | Creating Eventstreams and reading source connections | 11, 12 | <https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-streams/eventstream-rest-api> |
| F70 | Azure permissions for analytics | `Microsoft.Fabric/capacities` actions for the custom role | 12 | <https://learn.microsoft.com/en-us/azure/role-based-access-control/permissions/analytics> |
| F71 | Kusto mirroring policy | OneLake availability per table; blocked renames and purges; write delay | 10, 12 | <https://learn.microsoft.com/en-us/kusto/management/mirroring-policy?view=microsoft-fabric> |
| F72 | Scale your capacity | Changing the SKU in place | 13 | <https://learn.microsoft.com/en-us/fabric/enterprise/scale-capacity> |
| F73 | Surge protection | Limit on background work set by the administrator | 12, 13, 15 | <https://learn.microsoft.com/en-us/fabric/enterprise/surge-protection> |
| F74 | Azure billing for a Fabric capacity | Meters on the bill, including OneLake storage and OneLake Cache | 13 | <https://learn.microsoft.com/en-us/fabric/enterprise/azure-billing> |
| F75 | Monitor a paused capacity | Spike in the Capacity Metrics app at suspend | 13 | <https://learn.microsoft.com/en-us/fabric/enterprise/monitor-paused-capacity> |
| F76 | Capacity overage | Opt-in overage billed at 3× the CU price, with an administrator limit | 12, 13, 15 | <https://learn.microsoft.com/en-us/fabric/enterprise/capacity-overage-overview> |
| F77 | Fabric operations | Interactive and background operations | 13 | <https://learn.microsoft.com/en-us/fabric/enterprise/fabric-operations> |
| F78 | Fabric capacity overview events in the Real-Time hub | `Capacity.Summary` events every 30 seconds and `Capacity.State` events | 12, 13, 15 | <https://learn.microsoft.com/en-us/fabric/real-time-hub/explore-fabric-capacity-overview-events> |
| F79 | Cost Management Query API | Daily reconciliation of billed cost | 13 | <https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage> |
| F80 | Power BI blog: important update to Power BI pricing | Power BI Pro at $14 per user per month from April 2025. The page blocks automated reading; it was confirmed through search | 13, 14 | <https://community.fabric.microsoft.com/blog/fbc_pbiupdatesblog/important-update-to-microsoft-power-bi-pricing/5174341> |
| F81 | Configure streaming ingestion (Azure Data Explorer) | Queued ingestion suggested above about 4 GB per hour per table; update-policy limits with streaming | 10, 15 | <https://learn.microsoft.com/en-us/azure/data-explorer/ingest-data-streaming> |
| F82 | Bicep deployment stacks | Subscription-scope stacks that delete the resources that leave the template | 18 | <https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/deployment-stacks> |
| F83 | Deployment stacks: known issues | Limits of stacks to plan around | 18 | <https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/deployment-stacks-known-issues> |
| F84 | Foundry quota management | Quota per model, region and subscription; units of tokens and requests per minute; quota requests | 15, 18 | <https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/quota> |
| F85 | Role-based access control for Foundry | The Foundry User role for calling models; roles whose names start with "Cognitive Services" are not for Foundry | 09, 11, 12, 18 | <https://learn.microsoft.com/en-us/azure/foundry/concepts/rbac-foundry> |
| F86 | Azure OpenAI API version lifecycle | The v1 API and the token scope for Microsoft Entra ID | 18 | <https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle> |
| F87 | Recover or purge deleted Foundry resources | Soft delete keeps a deleted account's name for 48 hours; purge frees it | 18 | <https://learn.microsoft.com/en-us/azure/ai-services/recover-purge-resources> |
| F88 | Threat protection for AI services | Defender for AI scans text tokens, not image or audio; prompt evidence | 18 | <https://learn.microsoft.com/en-us/azure/defender-for-cloud/ai-threat-protection> |
| F89 | Defender for Cloud free trial | 30-day trials of the Defender plans | 18 | <https://learn.microsoft.com/en-us/azure/defender-for-cloud/free-trial> |
| F90 | Network security perimeter concepts | `SecuredByPerimeter` access; inbound rules by subscription and IP address; transition and enforced modes | 12, 15, 18 | <https://learn.microsoft.com/en-us/azure/private-link/network-security-perimeter-concepts> |
| F91 | Azure Verified Module for Cognitive Services accounts | The Bicep module of the shared Foundry resource | 18 | <https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/cognitive-services/account> |
| F92 | Azure Policy effects: DeployIfNotExists and Modify | How tenant policies add resources and change requests | 18 | <https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-deploy-if-not-exists>, <https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-modify> |
| F93 | Defender Cloud Security Posture Management | The resources that the CSPM plan bills, including Container Apps since 1 July 2026; Foundry resources are not among them | 18 | <https://learn.microsoft.com/en-us/azure/defender-for-cloud/concept-cloud-security-posture-management> |
| F94 | Container Apps billing | Consumption replicas at zero incur no resource consumption charge; jobs bill while executing; Dedicated/optional-feature fees are separate | 13 | <https://learn.microsoft.com/en-us/azure/container-apps/billing> |
| F95 | Container Apps private endpoints | Private ingress adds Dedicated Plan Management charges even for Consumption; distinct from accessing a Storage private endpoint | 13 | <https://learn.microsoft.com/en-us/azure/container-apps/private-endpoints-with-dns> |
| F96 | Container Registry SKU features | Base registry includes storage in its daily rate; Private Link requires Premium | 13 | <https://learn.microsoft.com/en-us/azure/container-registry/container-registry-skus> |
| F97 | Azure Policy exemption structure | Resource-scoped Waiver, initiative member selection, optional expiresOn and required exemption/assignment permissions | 18, 19 | <https://learn.microsoft.com/en-us/azure/governance/policy/concepts/exemption-structure> |
| F98 | Eventhouse definition | Source properties and supported item definition format | 20 | <https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/eventhouse-definition> |
| F99 | KQL Database definition | Parent Eventhouse and database/schema definition files | 20 | <https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/kql-database-definition> |
| F100 | Fabric long-running operations | Accepted requests, polling operation status and fetching results | 20 | <https://learn.microsoft.com/en-us/rest/api/fabric/articles/long-running-operation> |
| F101 | Kusto dynamic type | Strongly typed values and JSON normalization; raw text retained separately | 20 | <https://learn.microsoft.com/en-us/kusto/query/scalar-data-types/dynamic?view=microsoft-fabric> |
| F102 | Radix Themes | React component authoring, theme configuration and accessible interface primitives | 27 | <https://www.radix-ui.com/themes/docs/overview/getting-started> |

---

## 16.5 Known gaps

The research could not close the gaps below. None of them blocks the design, because each one becomes an estimate, a
scenario parameter or a phase-0 check.

### Market

| Gap | How the design handles it | Where |
|---|---|---|
| No official split of Italian chocolate sales by month, channel or region | Seasonal shapes are design assumptions, marked as such and easy to change | Chapter 03 |
| Channels other than supermarkets and hypermarkets (≈ 65% [M3]) are not broken down | Giandoria's channel mix is an assumption | Chapter 02 |
| Only a range for per-capita consumption (≈ 3–4.5 kg [M4]) | Calibration uses market value instead (≈ $3.9 bn at the epoch); ≈ 4 kg is a cross-check | Chapter 03 |
| No official table of chocolate consumption by region | Base demand is built per province from ISTAT population; a North–South gradient follows the qualitative sources [M2][M31] | Chapter 03 |
| No euro figures for Valentine's Day, advent calendars or post-Easter markdowns and returns | Estimates; the post-Easter return rate is a scenario parameter, marked [GAP] | Chapter 03; chapter 05 |
| The Easter-egg market size [M11] and the charity's cumulative egg count [M19] each rest on a single source | Used only as orders of magnitude | Chapter 03 |

### Production and supply

| Gap | How the design handles it | Where |
|---|---|---|
| No chocolate-specific MTBF and MTTR | A general food and packaging proxy [P19] | Chapter 04 |
| No firm figure for the microbiology release hold, and no source for the microbiology limits | 24–72 hours *(estimate)*; limits marked *(verify)* | Chapter 04 §4.7 |
| No share of seasonal staff in the workforce | Hiring peaks follow [P34]; crew sizes are estimates | Chapter 04 §4.8 |
| No public prices for vanilla and lecithin; no sourced price for sugar | Sugar ≈ €600–750 per tonne *(estimate)*; vanilla and lecithin are small volumes, priced as tunable parameters | Chapter 05 §5.2 |
| No single threshold for refrigerated summer transport | Temperature-controlled trucks above ≈ 25–27 °C *(estimate)* | Chapter 05 |
| Energy intensity is not Italy-specific [P25] | Order of magnitude only | Chapter 04 |
| The search for open-source implementations of backward simulation, and for work outside the simulation literature, was limited | No priority is claimed: the method introduced in chapter 17 is credited as an independent invention, not as the first one | Chapter 17 §17.10 |
| Eight of the eleven sources on planning methods (P39–P44, P48, P49) were read through their abstracts, their metadata and the review [P47], not in full | They support only the history of the method and general statements; no parameter depends on them | Chapter 17 §17.2, §17.5, §17.10 |

### Platform and cost

| Gap | How the design handles it | Where |
|---|---|---|
| The official model price page is rendered by script, so token prices come from secondary sources [F63] | Checked before phase 0 and written into the price card (RT-02) | Chapter 09 §9.7; chapter 13 §13.6 |
| Whether Eventstreams consume capacity with no traffic | Check 16 and measurement CM-03 | Chapter 12 §12.16; chapter 13 §13.12 |
| When an idle Eventhouse suspends itself | Measurement CM-02 | Chapter 13 §13.12 |
| The rate at which the settlement at suspend is billed | Measurement CM-01 | Chapter 13 §13.12 |
| Defaults of overage and surge protection, and whether an API sets them | Check 27 and measurement CM-04 | Chapter 12 §12.16; chapter 13 §13.12 |
| Ingestion latency with streaming and with batching at Profile M | Check 4 and decision D10 | Chapter 10 §10.7; chapter 15 §15.5 |
| General availability of some features (Fabric Maps, SQL database, Real-Time Dashboard, business events, Agent Framework) was inferred, not stated | Marked *(inferred)* or *(verify)*, and checked again before the phase that uses them | Chapter 11 §11.3; chapter 14 §14.3 |
| For Italy North and Sweden Central only the capacity-unit price was checked; the other meters use list prices that can differ by region | The price card reads the Retail Prices API for the chosen region [F3] | Chapter 13 §13.6 |
| Which callers a network security perimeter admits through a subscription rule | Check 29 | Chapter 12 §12.16; chapter 18 §18.10 |
| Defender cost after the free trials, and how CSPM counts apps scaled to zero and jobs | The first invoice and the daily reconciliation | Chapter 13 §13.6; chapter 18 §18.6 |

---

## 16.6 Keeping the references current

* **Prices.** F2, F3, F52, F57, F58, F60, F61, F63 and F80 are checked again before phase 0 and at the start of each
  phase. The price card in RT-02 holds the values that the cost meter uses (chapter 13 §13.6).
* **Preview and *(verify)* features.** Sources for features marked preview, *(inferred)* or *(verify)*, such as the
  Plan item [F65], the operations agent [F66] and the data agent [F36], are checked again before the phase that needs
  them (chapter 14 §14.3).
* **Numbering.** A new source takes the next free number in its family. Numbers are never reused or renumbered. A
  source that no longer supports a claim stays in the list, marked *withdrawn*, and the chapters that cite it are
  updated in the same change.
* **Decisions.** When a decision of chapter 15 is closed with new evidence, the evidence is added here with its own
  number.
