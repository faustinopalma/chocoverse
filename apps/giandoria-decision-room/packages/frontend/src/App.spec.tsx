import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { sourceContext } from '@rayfin-app/shared';
import { deserializeDabResponse } from '@microsoft/rayfin-data';
import App from './App';

const api = vi.hoisted(() => ({
  query: vi.fn(), create: vi.fn(), update: vi.fn(), investigate: vi.fn(),
  select: vi.fn(), orderBy: vi.fn(), first: vi.fn(), after: vi.fn(),
  executePaginated: vi.fn(), delete: vi.fn(),
}));
vi.mock('./hooks/auth.context', () => ({
  useAuth: () => ({ session: { user: { id: 'test-owner' } } }),
}));
vi.mock('./lib/rayfin-client', () => ({
  getRayfinClient: async () => ({
    connectors: { enterprise: { executeQuery: api.query } },
    data: { DecisionReview: { create: api.create, update: api.update, select: api.select, delete: api.delete } },
    functions: { investigate: { invoke: api.investigate } },
  }),
}));

const columns = ['Through', 'Sequence', 'Observation', 'Stock', 'Backlog', 'PreviousBacklog',
  'DailySales', 'Cash', 'Revenue30', 'CashMovement30', 'Sold30'].map(name => ({ name: `[${name}]` }));

beforeEach(() => {
  vi.clearAllMocks();
  api.query.mockResolvedValue({ status: 'success', table: { columns, rows: [[
    sourceContext.throughDate, sourceContext.sequence, sourceContext.throughDate,
    0, 37, 18, 417.56666666666666, 3441661.55, 144187.5, 62537.87, 12527,
  ]] } });
  api.create.mockResolvedValue({});
  api.update.mockResolvedValue({});
  api.delete.mockResolvedValue({});
  api.select.mockReturnValue(api);
  api.orderBy.mockReturnValue(api);
  api.first.mockReturnValue(api);
  api.after.mockReturnValue(api);
  api.executePaginated.mockResolvedValue({ items: [], hasNextPage: false });
  document.documentElement.removeAttribute('data-theme');
  document.documentElement.classList.remove('dark');
});

describe('Decision Room', () => {
  it('renders source-derived figures with virtual provenance, not wall time', async () => {
    render(<App />);
    expect(await screen.findByText('3,441,661.6 EUR')).toBeVisible();
    expect(screen.getAllByText(sourceContext.throughDate, { exact: false }).length).toBeGreaterThan(0);
    expect(screen.getByText('2 active')).toBeVisible();
    expect(screen.getByText('SNAPSHOT · NOT LIVE')).toBeVisible();
    expect(api.query).toHaveBeenCalledTimes(1);
    const backlog = screen.getByRole('button', { name: /01\s*Review signal Backlog pressure/ });
    const stock = screen.getByRole('button', { name: /02\s*Review signal Stock-cover gap/ });
    expect(backlog).toHaveAttribute('aria-pressed', 'true');
    expect(stock).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(stock);
    expect(stock).toHaveAttribute('aria-pressed', 'true');
    expect(backlog).toHaveAttribute('aria-pressed', 'false');
  });

  it('surfaces connector errors without substituting business values', async () => {
    api.query.mockResolvedValue({ status: 'error', error: { message: 'Source access denied.' } });
    render(<App />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Source access denied.');
    expect(screen.queryByText('3,441,661.6 EUR')).toBeNull();
    expect(screen.queryByText('Reading the governed semantic snapshot...')).toBeNull();
  });

  it('compares cover policies as arithmetic, never as a simulation result', async () => {
    render(<App />);
    await screen.findByText('3,441,661.6 EUR');
    fireEvent.click(screen.getByRole('button', { name: 'Scenario workbench' }));
    expect(screen.getByText(/not a causal simulation/)).toBeVisible();
    expect(screen.getByRole('row', { name: /3 virtual days/ })).toHaveTextContent('1,252.7 kg');
    fireEvent.change(screen.getByLabelText('Target cover in virtual days'), { target: { value: '4' } });
    fireEvent.click(screen.getByRole('button', { name: 'Investigate and review this policy' }));
    expect(screen.getByText(/Selected illustrative policy: 4 virtual days/)).toBeVisible();
  });

  it('saves only the authenticated owner and preserves the submitted agent question', async () => {
    api.investigate.mockResolvedValue({ answer: 'Observed backlog rose. Capacity is not measured.',
      virtualDate: sourceContext.throughDate, snapshotDigest: sourceContext.snapshotDigest });
    render(<App />);
    await screen.findByText('3,441,661.6 EUR');
    fireEvent.change(screen.getByLabelText('Question'), { target: { value: 'Explain backlog.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Investigate with Data Agent' }));
    expect(await screen.findByText('Observed backlog rose. Capacity is not measured.')).toBeVisible();
    fireEvent.change(screen.getByLabelText('Question'), { target: { value: 'An unsent edit.' } });
    fireEvent.change(screen.getByLabelText('Reasoning'), { target: { value: 'Need capacity evidence before approval.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save private review' }));
    await screen.findByRole('button', { name: 'Saved to your journal' });
    expect(api.create).toHaveBeenCalledWith(expect.objectContaining({
      owner_id: 'test-owner', question: 'Explain backlog.', verdict: 'Revisit',
      snapshotDigest: sourceContext.snapshotDigest, virtualDate: sourceContext.throughDate,
    }));
    fireEvent.change(screen.getByLabelText('Verdict'), { target: { value: 'Reject' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save private review' }));
    await waitFor(() => expect(api.update).toHaveBeenCalledTimes(1));
    expect(api.update.mock.calls[0][0].id).toBe(api.create.mock.calls[0][0].id);
  });

  it('rejects an agent answer stamped with another snapshot', async () => {
    api.investigate.mockResolvedValue({ answer: 'An untrusted answer.', virtualDate: sourceContext.throughDate,
      snapshotDigest: 'different' });
    render(<App />);
    await screen.findByText('3,441,661.6 EUR');
    fireEvent.click(screen.getByRole('button', { name: 'Investigate with Data Agent' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('different virtual snapshot');
    expect(screen.queryByText('An untrusted answer.')).toBeNull();
  });

  it('renders SDK-hydrated review text and persists revisit and confirmed deletion', async () => {
    const record = deserializeDabResponse({
      id: 'test-review', owner_id: 'test-owner', title: 'Temporary validation review',
      verdict: 'Approve', virtualDate: sourceContext.throughDate,
      snapshotDigest: sourceContext.snapshotDigest, evidence: '{}',
      question: '2034-09-01', answer: 'false', rationale: 'Test note.',
      createdAt: '2026-10-20T12:00:00Z',
    });
    expect(record.virtualDate).toBeInstanceOf(Date);
    api.executePaginated.mockResolvedValueOnce({ items: [record], hasNextPage: false })
      .mockResolvedValueOnce({ items: [{ ...record, verdict: 'Revisit' }], hasNextPage: false })
      .mockResolvedValueOnce({ items: [], hasNextPage: false });
    render(<App />);
    await screen.findByText('3,441,661.6 EUR');
    fireEvent.click(screen.getByRole('button', { name: 'Review journal' }));
    expect(await screen.findByText('Temporary validation review')).toBeVisible();
    expect(screen.getByText(/Virtual cutoff 2034-09-03/)).toBeVisible();
    expect(screen.getByText('2034-09-01', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('false')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Mark for revisit' }));
    expect(await screen.findByText('Revisit')).toBeVisible();
    expect(api.update).toHaveBeenCalledWith({ id: 'test-review' }, { verdict: 'Revisit' });
    fireEvent.click(screen.getByRole('button', { name: 'Delete review' }));
    expect(await screen.findByRole('alertdialog')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Delete review permanently' }));
    expect(await screen.findByText(/No reviews yet/)).toBeVisible();
    expect(api.delete).toHaveBeenCalledWith({ id: 'test-review' });
  });

  it('surfaces an invalid persisted review date before it can crash rendering', async () => {
    api.executePaginated.mockResolvedValueOnce({
      items: [{ virtualDate: new Date('invalid') }], hasNextPage: false,
    });
    render(<App />);
    await screen.findByText('3,441,661.6 EUR');
    fireEvent.click(screen.getByRole('button', { name: 'Review journal' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('invalid virtual cutoff');
  });
});
