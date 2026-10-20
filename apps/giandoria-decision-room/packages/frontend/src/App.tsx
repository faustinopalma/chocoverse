import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { AlertDialog, Badge, Button, Callout, Card, Flex, IconButton, Progress, Spinner, TextArea, Theme, Tooltip } from '@radix-ui/themes';
import { ArrowRight, ArrowUpRight, BookOpen, CalendarDays, CheckCircle2, ChevronRight, CircleHelp, Database, FlaskConical, Layers3, Lightbulb, LockKeyhole, MessageSquareText, Moon, Package, RefreshCw, ShieldCheck, Sparkles, Sun, TrendingUp, Wallet } from 'lucide-react';
import { sourceContext, type DecisionReviewRecord } from '@rayfin-app/shared';
import evidenceQuery from '../../shared/src/evidence-query.json';
import { useAuth } from './hooks/auth.context';
import { useAppTheme } from './hooks/use-theme';
import { useSemanticModelQuery } from './hooks/use-semantic-model-query';
import { getRayfinClient } from './lib/rayfin-client';
import { decisionCases, parseEvidence, stockScenario, type DecisionCase, type Evidence } from './lib/decisions';
import { normalizeReview } from './lib/reviews';
import './DecisionRoom.css';

type PageName = 'Decision inbox' | 'Business explorer' | 'Scenario workbench' | 'Review journal';
const pages: PageName[] = ['Decision inbox', 'Business explorer', 'Scenario workbench', 'Review journal'];
const format = (value: number | null, unit = '') => value === null ? 'Not measured' :
  new Intl.NumberFormat('en-GB', { maximumFractionDigits: 1 }).format(value) + unit;
const message = (error: unknown) => error instanceof Error ? error.message : 'The operation failed. Check app configuration and permissions.';

function Metric({ label, value, detail, icon, delta }: {
  label: string; value: string; detail: string; icon?: ReactNode; delta?: string;
}) {
  return <Card className="metric" variant="surface" size="3">
    <div className="metric-heading"><span>{label}</span>{icon && <span className="metric-icon">{icon}</span>}</div>
    <strong>{value}</strong><div className="metric-footer"><small>{detail}</small>
      {delta && <Badge variant="soft">{delta}</Badge>}</div>
  </Card>;
}

function CoverComparison({ evidence, days }: { evidence: Evidence; days: number }) {
  const scenario = stockScenario(evidence.Stock, evidence.DailySales, days);
  return <Card className="cover-card" variant="surface" size="3">
    <div className="section-title"><div className="flex items-center gap-200"><Package size={18} /><h3>Stock against an illustrative policy</h3></div>
      <Tooltip content="Average sell-out over 30 virtual days multiplied by the selected cover days. Not a production plan."><IconButton variant="ghost" aria-label="Explain stock-cover comparison"><CircleHelp size={17} /></IconButton></Tooltip>
    </div>
    {scenario && evidence.Stock !== null ? <>
      <div className="cover-values"><span><b>{format(evidence.Stock, ' kg')}</b> observed</span><span><b>{format(scenario.target, ' kg')}</b> target</span></div>
      {scenario.target > 0 && <Progress size="2" value={Math.min(100, Math.max(0, evidence.Stock / scenario.target * 100))} aria-label="Observed stock as a percentage of illustrative target" />}
      <p className="muted">{days} virtual days of cover · Arithmetic sensitivity only, not a forecast.</p>
    </> : <p className="muted">Not measured: a stock or daily sell-out observation is missing.</p>}
  </Card>;
}

function App() {
  const [page, setPage] = useState<PageName>('Decision inbox');
  const [working, setWorking] = useState(false);
  const [selected, setSelected] = useState('backlog');
  const [cover, setCover] = useState(3);
  const { isDark, toggleTheme } = useAppTheme();
  const query = useSemanticModelQuery({ connection: 'enterprise', query: evidenceQuery.query });
  const loading = query.isLoading;
  let evidence: Evidence | undefined;
  let error = query.error ? message(query.error) : '';
  if (query.data?.status === 'success') {
    try {
      evidence = parseEvidence(query.data.table.rows, query.data.table.columns, sourceContext);
    } catch (err) {
      error = message(err);
    }
  } else if (query.data?.status === 'error') error = query.data.error.message;
  const cases = evidence ? decisionCases(evidence) : [];
  const active = cases.find(item => item.id === selected);
  return <Theme appearance={isDark ? 'dark' : 'light'} accentColor="crimson" grayColor="sand" radius="large"><div className="decision-room">
    <aside className="sidebar">
      <a className="wordmark" href={sourceContext.commercialUrl} target="_blank" rel="noreferrer"><span className="brand-icon">G<span /></span><span>GIANDORIA<small>DECISION INTELLIGENCE</small></span></a>
      <div className="workspace-label">YOUR WORKSPACE</div>
      <nav aria-label="Decision Room">
        {pages.map((name, i) => <Button variant="soft" key={name} aria-current={page === name ? 'page' : undefined}
          disabled={working} onClick={() => setPage(name)}>{[<Layers3 size={19} />, <BookOpen size={19} />, <FlaskConical size={19} />, <CheckCircle2 size={19} />][i]}{name}{page === name && <ChevronRight className="nav-chevron" size={15} />}</Button>)}
      </nav>
      <div className="sidebar-bottom"><div className="trust-mark"><ShieldCheck size={19} /> Governed by Fabric</div><span className="status-dot" /> Enterprise data only
        <p>No live production commands.<br />Your reviews remain private to you.</p>
        <a href={sourceContext.ontologyUrl} target="_blank" rel="noreferrer">Explore Fabric ontology <ArrowUpRight size={14} /></a>
      </div>
    </aside>
    <main>
      <header className="topbar"><div className="flex items-center gap-200"><span>WORKSPACE</span><ChevronRight size={13} /><b>Decision Room</b></div><div className="flex items-center gap-400"><Badge variant="surface" size="2"><Database size={12} /> SNAPSHOT · NOT LIVE</Badge><Tooltip content={isDark ? 'Switch to light appearance' : 'Switch to dark appearance'}><IconButton variant="ghost" aria-label={isDark ? 'Use light theme' : 'Use dark theme'} onClick={toggleTheme}>{isDark ? <Sun size={18} /> : <Moon size={18} />}</IconButton></Tooltip></div></header>
      <section className="page-heading">
        <div><p className="eyebrow">FROM EVIDENCE TO JUDGEMENT</p><h1>{page}</h1><p>Understand the signals. Challenge the proposal.<br className="mobile-break" /> Record your reasoning.</p></div>
        <Button variant="surface" size="3" className="secondary" onClick={() => void query.refetch()} disabled={loading || working}><RefreshCw size={16} /> Refresh evidence</Button>
      </section>
      <div className="provenance"><span><CalendarDays size={15} /><b>Virtual data through</b> {sourceContext.throughDate}</span><span><b>Calendar</b> Europe/Rome</span><span><b>Run</b> {sourceContext.run}</span><Tooltip content={sourceContext.snapshotDigest}><span className="version"><LockKeyhole size={13} /><b>Version</b> {sourceContext.snapshotDigest.slice(0, 12)}</span></Tooltip></div>
      {error && <div className="error" role="alert"><strong>Evidence unavailable</strong><p>{error}</p><p>No sample values have been substituted. Refresh after resolving access or configuration.</p></div>}
      {loading && <div className="loading" role="status"><Spinner size="2" />Reading the governed semantic snapshot...</div>}
      {evidence && !loading && <>
        <section className="metrics" aria-label="Enterprise observations">
          <Metric icon={<Package size={19} />} label="FINISHED STOCK" value={format(evidence.Stock, ' kg')} detail={`Last observation: ${evidence.Observation}`} />
          <Metric icon={<Layers3 size={19} />} label="BACKLOG" value={format(evidence.Backlog, ' kg')} detail={`Earlier observation: ${format(evidence.PreviousBacklog, ' kg')}`} delta={evidence.Backlog !== null && evidence.PreviousBacklog !== null && evidence.PreviousBacklog > 0 ? `${format((evidence.Backlog / evidence.PreviousBacklog - 1) * 100, '%')} change` : undefined} />
          <Metric icon={<TrendingUp size={19} />} label="DAILY SELL-OUT" value={format(evidence.DailySales, ' kg')} detail="Average over final 30 virtual days" />
          <Metric icon={<Wallet size={19} />} label="OBSERVED CASH" value={format(evidence.Cash, ' EUR')} detail="Last balance, not a sum over time" />
        </section>
        {page === 'Decision inbox' && <div className="overview-strip"><Card className="signal-summary" variant="surface" size="3"><span className="summary-icon"><Lightbulb size={22} /></span><div><p className="eyebrow">RULE-BASED SCREENING</p><h2>{cases.filter(item => item.triggered).length} signals deserve a closer look.</h2><p>Start with the evidence, then ask the Data Agent.<br />You remain in control of the decision.</p></div></Card><CoverComparison evidence={evidence} days={cover} /></div>}
        {page === 'Decision inbox' && <div className="inbox-grid">
          <section className="case-list"><div className="section-title"><h2>Signals to examine</h2><Badge variant="soft" radius="full">{cases.filter(item => item.triggered).length} active</Badge></div>
            {cases.map((item, index) => <Card asChild key={item.id} variant="surface" size="3"><button disabled={working} aria-pressed={selected === item.id} className="case-card" onClick={() => setSelected(item.id)}>
              <div className="case-topline"><span className="case-number">0{index + 1}</span><Badge variant={item.triggered ? 'soft' : 'surface'} color={item.triggered ? 'crimson' : 'gray'}>{item.triggered ? 'Review signal' : 'Rule not triggered'}</Badge></div>
              <h3>{item.title}</h3><p>{item.condition}</p><span className="card-link">Examine evidence <ArrowRight size={15} /></span>
            </button></Card>)}
          </section>
          {active && <Investigation key={active.id} item={active} evidence={evidence} cover={cover} onWorking={setWorking} />}
        </div>}
        {page === 'Business explorer' && <Explorer />}
        {page === 'Scenario workbench' && <Card asChild variant="surface" size="4"><section className="panel">
          <p className="eyebrow"><FlaskConical size={15} /> ISOLATED WHAT-IF · NO LIVE WRITEBACK</p><h2>Stock-cover policy laboratory</h2>
          <p>Compare a hypothetical stock target with the last enterprise observation. This is arithmetic sensitivity, not a causal simulation or a capacity-feasible production plan.</p>
          <label className="field-label">Target cover in virtual days<select value={cover} onChange={event => setCover(Number(event.target.value))}>{[2, 3, 4, 5, 7].map(days => <option key={days} value={days}>{days} days</option>)}</select></label>
          <CoverComparison evidence={evidence} days={cover} />
          <table><thead><tr><th>Cover</th><th>Target stock</th><th>Target minus observed stock</th></tr></thead>
            <tbody>{[2, 3, 4, 5, 7].map(days => {
              const result = stockScenario(evidence.Stock, evidence.DailySales, days);
              return <tr key={days} className={days === cover ? 'highlight' : ''}><td>{days} virtual days {days === cover ? '(selected)' : ''}</td><td>{format(result?.target ?? null, ' kg')}</td><td>{format(result?.gap ?? null, ' kg')}</td></tr>;
            })}</tbody></table>
          <div className="method"><b>Method</b><p>Target = average daily sell-out over 30 virtual days x cover days. Gap = target - last observed finished stock. A positive gap indicates stock below the illustrative target, not an order to produce that amount.</p></div>
          <Button size="3" className="primary" onClick={() => { setSelected('stock'); setPage('Decision inbox'); }}>Investigate and review this policy <ArrowUpRight size={15} /></Button>
        </section></Card>}
      </>}
      {page === 'Review journal' && <Journal />}
      <footer><b>Reading guide</b><p>Sell-out is what consumers bought; shipments are dispatches; releases are completed production made available. Backlog is recorded unfulfilled demand, not hidden lost sales. Cash and stock are sampled balances. Rule-based proposals and AI answers are advisory, not approved actions or measured outcomes.</p>
        <a href={sourceContext.operationsUrl} target="_blank" rel="noreferrer">Open Operations report <ArrowUpRight size={14} /></a></footer>
    </main>
  </div></Theme>;
}

function Investigation({ item, evidence, cover, onWorking }: {
  item: DecisionCase; evidence: Evidence; cover: number; onWorking: (working: boolean) => void;
}) {
  const { session } = useAuth();
  const [question, setQuestion] = useState(item.question);
  const [answer, setAnswer] = useState('');
  const [askedQuestion, setAskedQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [verdict, setVerdict] = useState('Revisit');
  const [rationale, setRationale] = useState('');
  const [submissionId] = useState(() => crypto.randomUUID());
  const [recordCreated, setRecordCreated] = useState(false);
  async function investigate() {
    setBusy(true); onWorking(true); setError(''); setAnswer(''); setSaved(false);
    const submitted = question.trim();
    try {
      const client = await getRayfinClient();
      const result = await client.functions.investigate.invoke({ question: submitted });
      if (result.snapshotDigest !== sourceContext.snapshotDigest || result.virtualDate !== evidence.Through) {
        throw new Error('Agent evidence belongs to a different virtual snapshot.');
      }
      setAskedQuestion(submitted); setAnswer(result.answer);
    } catch (err) { setError(message(err)); }
    finally { setBusy(false); onWorking(false); }
  }
  async function save() {
    setSaving(true); onWorking(true); setError('');
    try {
      if (!session?.user?.id) throw new Error('Your authenticated user identity is unavailable. Sign in again.');
      const client = await getRayfinClient();
      const payload = {
        id: submissionId, owner_id: session.user.id, title: item.title,
        verdict, virtualDate: evidence.Through, snapshotDigest: sourceContext.snapshotDigest,
        evidence: JSON.stringify({ evidence, rule: item.condition, triggered: item.triggered,
          proposal: item.proposal, scenario: stockScenario(evidence.Stock, evidence.DailySales, cover),
          scenarioType: 'illustrative-stock-cover-not-causal-simulation' }),
        question: askedQuestion, answer, rationale: rationale.trim(), createdAt: new Date(),
      };
      if (recordCreated) await client.data.DecisionReview.update({ id: submissionId }, payload);
      else await client.data.DecisionReview.create(payload);
      setRecordCreated(true);
      setSaved(true);
    } catch (err) { setError(message(err)); }
    finally { setSaving(false); onWorking(false); }
  }
  return <Card asChild variant="surface" size="4"><section className="panel investigation">
    <div className="panel-heading"><div><p className="eyebrow">PLANNER DESK</p><h2>{item.title}</h2></div><Badge variant="surface"><ShieldCheck size={12} /> Read-only</Badge></div>
    <div className="workflow-guide" aria-label="Review workflow"><span>01 Evidence</span><ChevronRight size={13} /><span>02 Investigation</span><ChevronRight size={13} /><span>03 Judgement</span></div>
    <Callout.Root className="proposal"><Callout.Icon><Lightbulb size={18} /></Callout.Icon><Callout.Text><span className="signal">RULE-BASED PROPOSAL</span><span className="block">{item.proposal}</span></Callout.Text></Callout.Root>
    {item.id === 'stock' && <p className="muted">Selected illustrative policy: {cover} virtual days. The saved review includes this arithmetic scenario, not a simulated production outcome.</p>}
    <h3><Sparkles size={18} /> Ask the Fabric Data Agent</h3>
    <p className="muted">One bounded analytical request per click. Source definitions are checked before and after the answer; there are no automatic inference retries.</p>
    <label className="field-label">Question<TextArea size="3" value={question} maxLength={1500} rows={5} onChange={event => setQuestion(event.target.value)} disabled={busy} /></label>
    <Button size="3" className="primary" loading={busy} onClick={() => void investigate()} disabled={busy || saving || !question.trim()}>{busy ? 'Investigating...' : 'Investigate with Data Agent'} <ArrowUpRight size={15} /></Button>
    {busy && <p role="status">The Data Agent may take several minutes. Do not resubmit while this request is running.</p>}
    {answer && <div className="answer"><div className="flex items-center gap-200"><MessageSquareText size={17} /><span className="signal">AI-GENERATED · VERIFY AGAINST THE SOURCE</span></div><p>{answer}</p></div>}
    <div className="review-section"><h3><CheckCircle2 size={18} />Your judgement</h3><p>Approval records your opinion only. It does not change production, cash, the manager or the live simulation.</p>
      <label className="field-label">Verdict<select value={verdict} onChange={event => { setVerdict(event.target.value); setSaved(false); }}><option>Approve</option><option>Reject</option><option>Revisit</option></select></label>
      <label className="field-label">Reasoning<TextArea size="3" placeholder="What convinced you? What evidence is still missing?" value={rationale} maxLength={2000} rows={3} onChange={event => { setRationale(event.target.value); setSaved(false); }} /></label>
      <Button size="3" variant="surface" className="secondary" loading={saving} disabled={busy || saving || saved || !rationale.trim()} onClick={() => void save()}><LockKeyhole size={15} />{saving ? 'Saving...' : saved ? 'Saved to your journal' : 'Save private review'}</Button>
      {saved && <p className="success" role="status">Saved in the Fabric App database with snapshot, rule, evidence and selected cover policy.</p>}
    </div>
    {error && <div className="error" role="alert">{error}</div>}
  </section></Card>;
}

function Explorer() {
  const [product, setProduct] = useState('');
  const [channel, setChannel] = useState('');
  const [territory, setTerritory] = useState('');
  const [result, setResult] = useState<{ name: string; value: string }[]>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function explore() {
    setBusy(true); setError(''); setResult(undefined);
    try {
      const filters = [
        { value: product, allowed: sourceContext.products, column: "'Product'[Product]" },
        { value: channel, allowed: sourceContext.channels, column: "'Channel'[Channel]" },
        { value: territory, allowed: sourceContext.territories, column: "'Territory'[Territory]" },
      ].filter(filter => filter.value).map(filter => {
        if (!filter.allowed.some(value => value === filter.value)) throw new Error('Unsupported business dimension.');
        return `TREATAS({"${filter.value.replaceAll('"', '""')}"}, ${filter.column})`;
      });
      const query = `EVALUATE CALCULATETABLE(ROW("Sell-out kg", [Sold kg], "Released kg", [Released kg], "Cash EUR", [Cash as observed EUR])${filters.length ? ', ' + filters.join(', ') : ''})`;
      const response = await (await getRayfinClient()).connectors.enterprise.executeQuery({ query });
      if (response.status !== 'success') throw new Error(response.error.message);
      if (response.table.rows.length !== 1) throw new Error('Expected one scoped analytical row.');
      setResult(response.table.columns.map((column, index) => {
        const value = response.table.rows[0][index];
        if (value !== null && (typeof value !== 'number' || !Number.isFinite(value))) throw new Error('Unexpected analytical value.');
        return { name: column.name.replace(/^\[|\]$/g, ''), value: format(value) };
      }));
    } catch (err) { setError(message(err)); }
    finally { setBusy(false); }
  }
  return <Card asChild variant="surface" size="4"><section className="panel explorer-panel">
    <p className="eyebrow"><BookOpen size={15} /> ONE VOCABULARY · EXPLICIT GRAINS</p><h2>Explore the business, not just the numbers</h2>
    <p>Choose aggregate concepts represented by the ontology. Queries below use the semantic model; the ontology link opens the native entity and relationship explorer.</p>
    <div className="filters">{[
      { label: 'Product', value: product, set: setProduct, values: sourceContext.products },
      { label: 'Channel', value: channel, set: setChannel, values: sourceContext.channels },
      { label: 'Territory', value: territory, set: setTerritory, values: sourceContext.territories },
    ].map(filter => <label className="field-label" key={filter.label}>{filter.label}<select value={filter.value} onChange={event => { filter.set(event.target.value); setResult(undefined); }}><option value="">All</option>{filter.values.map(value => <option key={value}>{value}</option>)}</select></label>)}</div>
    <Button size="3" className="primary" loading={busy} disabled={busy} onClick={() => void explore()}>{busy ? 'Reading...' : 'Read this business slice'}<ArrowRight size={15} /></Button>
    {error && <div className="error" role="alert">{error}</div>}
    {result && <div className="metrics">{result.map(metric => <Metric key={metric.name} label={metric.name} value={metric.value} detail="Whole snapshot, selected business slice" />)}</div>}
    <div className="method"><b>Why some numbers are not measured</b><p>Production has date x product grain, not channel x territory grain. Financial balances are company-level. Unsupported slices return blank; they are never allocated or replaced with zero. Product categories are not batches, channels are not individual customers, and territories are not factory locations.</p></div>
    <div className="link-row"><a href={sourceContext.ontologyUrl} target="_blank" rel="noreferrer">Open native ontology <ArrowUpRight size={15} /></a><a href={sourceContext.commercialUrl} target="_blank" rel="noreferrer">Open Commercial report <ArrowUpRight size={15} /></a></div>
  </section></Card>;
}

function Journal() {
  const [records, setRecords] = useState<DecisionReviewRecord[]>([]);
  const [cursor, setCursor] = useState<string>();
  const [hasMore, setHasMore] = useState(false);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback((after?: string) => {
    return getRayfinClient().then(async client => {
      let query = client.data.DecisionReview.select(['id', 'owner_id', 'title', 'verdict', 'virtualDate',
        'snapshotDigest', 'evidence', 'question', 'answer', 'rationale', 'createdAt'])
        .orderBy({ createdAt: 'desc', id: 'asc' }).first(20);
      if (after) query = query.after(after);
      return query.executePaginated();
    }).then(result => {
      if (result.hasNextPage && !result.endCursor) throw new Error('Review pagination omitted its continuation cursor.');
      const items = result.items.map(normalizeReview);
      setRecords(old => after ? [...old, ...items] : items);
      setCursor(result.endCursor ?? undefined); setHasMore(result.hasNextPage);
    }).catch(err => { setError(message(err)); })
      .finally(() => { setBusy(false); });
  }, []);
  useEffect(() => { void load(); }, [load]);
  async function change(record: DecisionReviewRecord, remove: boolean) {
    setBusy(true); setError('');
    try {
      const client = await getRayfinClient();
      if (remove) await client.data.DecisionReview.delete({ id: record.id });
      else await client.data.DecisionReview.update({ id: record.id }, { verdict: 'Revisit' });
      await load();
    } catch (err) { setError(message(err)); }
    finally { setBusy(false); }
  }
  return <Card asChild variant="surface" size="4"><section className="panel">
    <div className="section-title"><div><p className="eyebrow">PERSISTED IN FABRIC SQL</p><h2>Your private review journal</h2></div><Button size="3" className="secondary" variant="surface" disabled={busy} onClick={() => { setBusy(true); setError(''); void load(); }}><RefreshCw size={15} />Reload reviews</Button></div>
    <p>Server-side owner policies restrict these records to your signed-in identity. Reviews are mutable working notes, not an immutable compliance ledger or proof of a live outcome.</p>
    {busy && <div className="loading" role="status"><Spinner />Reading your review records...</div>}
    {error && <div className="error" role="alert">{error}</div>}
    {!busy && !error && records.length === 0 && <p className="empty">No reviews yet. Examine a signal, record your reasoning and save a private review.</p>}
    {records.map(record => <Card asChild variant="surface" size="3" key={record.id}><article className="journal-card"><div className="section-title"><h3>{record.title}</h3><Badge variant="soft">{record.verdict}</Badge></div>
      <p className="muted">Virtual cutoff {record.virtualDate} · Snapshot {record.snapshotDigest.slice(0, 12)}</p><p>{record.rationale}</p>
      <details><summary>Evidence, question and answer</summary><pre>{record.evidence}</pre><p><b>Question:</b> {record.question || 'No Data Agent request recorded.'}</p><p className="preserve">{record.answer}</p></details>
      <div className="link-row"><Button disabled={busy} className="secondary" variant="surface" onClick={() => void change(record, false)}>Mark for revisit</Button>
        <AlertDialog.Root><AlertDialog.Trigger><Button disabled={busy} variant="ghost" color="gray">Delete review</Button></AlertDialog.Trigger>
          <AlertDialog.Content maxWidth="440px"><AlertDialog.Title>Delete this private review?</AlertDialog.Title><AlertDialog.Description>The saved evidence and your reasoning will be deleted. The live company is not affected. This cannot be undone.</AlertDialog.Description>
            <Flex gap="3" mt="5" justify="end"><AlertDialog.Cancel><Button variant="soft" color="gray">Keep review</Button></AlertDialog.Cancel><AlertDialog.Action><Button onClick={() => void change(record, true)}>Delete review permanently</Button></AlertDialog.Action></Flex>
          </AlertDialog.Content></AlertDialog.Root>
      </div>
    </article></Card>)}
    {hasMore && <Button className="secondary" variant="surface" disabled={busy} onClick={() => { setBusy(true); setError(''); void load(cursor); }}>Load more reviews</Button>}
  </section></Card>;
}

export default App;
