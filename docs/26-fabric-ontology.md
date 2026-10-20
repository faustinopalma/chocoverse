# 26. Fabric IQ ontology: enterprise context and explicit relationships

The implementation publishes a native Fabric IQ ontology over the existing enterprise snapshot.
Cloud publication verifies all eight registered Delta sources and exact readback of eight entity types,
eight property bindings, eight relationships and eight contextualizations. The browser renders the entity
types, their source mappings and the relationship canvas. Product and SellOut instance browsing resolves
the bound OneLake data; SellOut retains its four identifying columns and the sold-quantity property.
The tenant must enable **Users can create Ontology (preview) items** before creation; a disabled setting
returns `403 FeatureNotAvailable`. Local schema, key, relationship and Delta replay tests alone do not
prove cloud availability: successful publication also requires verified source files, table registration
and definition readback.
The [runbook](../infra/demo/README.md#fabric-iq-ontology-preview) owns prerequisites and publication commands.

## Why this is different from the Power BI model

The [Power BI semantic model](./23-semantic-model-showcase.md) owns analytical calculations, filter context,
time intelligence and semi-additive balances. An ontology names business entities, their identifying
properties, relationships and bindings to actual data. It makes the meaning and paths between concepts
explicit for supported exploration and agent experiences.

The two are complementary, not interchangeable. This increment does not recreate DAX as ontology
properties, claim that a relationship computes a KPI, replace the semantic model, or silently switch the
[existing Data Agent](./24-data-agent-showcase.md) to another source.

## Entity grains and teaching value

| Entity | Unique key | Meaning |
|---|---|---|
| Product | Product | The three recorded product categories; not individual batches |
| Channel | Channel | A route to market; not a named customer |
| Territory | Territory | An aggregate sales area; not a factory location |
| VirtualDay | Date | One date on the continuous virtual Rome calendar |
| SellOut | Date, Channel, Product, Territory | Daily customer purchases in kilograms at the source fact grain |
| ProductionFlow | Date, Product | Daily starts, releases and shipments; distinct flows |
| FinanceDay | Date | Company-level postings in integer euro cents; not product profitability |
| CompanyObservation | Date | Sampled finished stock, backlog, WIP and financial balances |

There are eight directed relationship types: SellOut relates to Product, Channel, Territory and VirtualDay;
ProductionFlow relates to Product and VirtualDay; FinanceDay and CompanyObservation relate to VirtualDay.
Each relationship has a real contextualization table and exact source/target key mappings.
For example, a SellOut-to-Product edge carries the full four-column source identifier and the product key.
This avoids incorrectly merging different days, territories or channels into one sales entity.

No factory, machine, individual order, customer or supplier entity is invented from aggregate facts.
The reduced-detail runtime does not provide the governed instance data needed to bind those concepts.
The same restriction applies to OEE, first-pass quality, profit and cost-of-goods-sold: this ontology
does not make unmeasured quantities appear measured.

## Data bindings and virtual time

The public definition contract used here supports Lakehouse-backed entity instances and relationship
contextualizations. A dedicated context Lakehouse holds immutable Delta copies of the already reconciled
enterprise snapshot, not unrestricted simulator state or hidden truth.
The published items are `ont_giandoria` and `lh_giandoria_context`; runtime identities stay in ignored state.

Date keys are ISO strings, because ontology entity identifiers support strings and integers.
They represent virtual Rome calendar dates, not ingestion timestamps, UTC instants or the host clock.
All dates come from the saved virtual snapshot, including the full calendar; no `now`, `ago`, `TODAY`
or wall-clock cutoff is used. Ordinary entity bindings need no synthetic midnight timestamps or
timestamp-specific Delta protocol features.

Daily facts are ordinary entities rather than misleading time-series properties on one undifferentiated
company instance. Each property's ontology name is prefixed by its entity name to maintain global uniqueness;
its binding still points to the original source-column name.

The source tables are versioned by schema version and snapshot digest. Replaying the same publication
verifies existing Delta content instead of appending duplicate rows or overwriting files.
A newer snapshot creates different table names; old data is retained until an explicitly scoped cleanup.
No scheduled refresh or live replication is installed. The ontology's snapshot must not be described as
tracking the running simulator simply because ontology supports real-time sources in other configurations.

## Implementation and verification

* [ontology.py](../src/giandoria/ontology.py) validates source grains and relationship referential integrity,
  creates deterministic positive 64-bit ontology IDs, generates definitions and binds every property.
* Local Delta tables use typed Arrow columns and a single initial transaction. Reuse requires exact logical
  data equality and version zero.
* Only the two explicitly named items can be created or updated through the existing guarded transport.
  An existing unregistered or differently owned item is not adopted.
  Fabric's same-named SQL endpoint is accepted only when its ID matches the companion recorded by the
  exact owned, registered Lakehouse.
* Ontology availability is checked before creating the Lakehouse or copying data. On a later run, an existing
  registered ontology is not cleared while preparing replacement sources.
* Upload uses Entra Storage tokens and the Sweden Central OneLake endpoint, with create-only writes.
  Data files precede Delta commits. Each uploaded file is read back and compared byte-for-byte.
* Publication requires registered Delta source tables and exact ontology-definition readback before recording
  success. Definitions explicitly include the service's schema references, empty collections and nullable
  defaults; comparison does not broadly ignore extra fields or differences.
* [test_ontology.py](../tests/test_ontology.py) covers exact source grains, supported key types, global property
  names, orphan/duplicate rejection, composite relationship keys, immutable Delta replay and registration guards.

No Spark job, graph materialization, autonomous action or new model inference is part of this increment.
The intended additional paid footprint is retained OneLake data and existing Fabric capacity/query activity.
It is not zero-cost merely because no Azure resource is provisioned.

## Exploring the ontology

The public definition contract used by this publisher currently opens in Fabric's old ontology experience.
The portal announces its retirement on **January 31, 2027** and offers **Create copy** into the new experience.
Do not treat that migration as a cosmetic rename: export the new contract, preserve ownership tracking and
reverify keys, source mappings, relationships and consumer answers before replacing the published item.

Open `ont_giandoria` in the existing workspace. Select an entity type to see its relationship neighborhood,
then **View Entity Type details** to inspect **Configure** and **Instances**. Configure shows the key,
property-to-table mappings and related types; Instances reads the actual bound source rows.
After changing the snapshot or contract, recheck that Product resolves the expected categories and SellOut
retains its complete composite identity. A bounded aggregate comparison with the semantic model is an
additional analytical-consumer check, not something proved by schema publication alone.

Useful educational questions include:

* Which product/channel/territory combinations are represented by recorded sell-out?
* What is the relationship between a daily production flow and its product/calendar date?
* Why is a sampled stock balance not additive across calendar dates?
* Which concepts are not available at product or customer grain?

An ontology agent or a Data Agent connection is a separate consumer configuration and needs its own
source-access, supported-feature and answer-quality verification. Publication alone does not prove
natural-language querying, source permissions for the isolated manager identity or live decision integration.

## Official contracts

* [Ontology overview and preview scope](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview)
* [Required tenant settings](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview-tenant-settings)
* [Data binding and supported key types](https://learn.microsoft.com/en-us/fabric/iq/ontology/how-to-bind-data)
* [Public ontology definition](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/ontology-definition)
* [OneLake API access and regional endpoints](https://learn.microsoft.com/en-us/fabric/onelake/onelake-access-api)
