import { useMemo, useState } from "react";
import {
  useAccountBalances,
  useAccounts,
  useAllEntries,
  useCreateEntry,
  useCreateSimpleEntry,
  useEntries,
  usePayees,
  useVoidEntry,
} from "@/api/queries";
import { Money } from "@/components/Money";
import { exportLedgerUrl } from "@/lib/api";
import { entryDate, formatTime, localISODateTime, money } from "@/lib/format";
import { useFilters } from "@/store/filters";
import type { Account, EntryKind, JournalEntry, JournalLineInput } from "@/lib/types";

const now = () => localISODateTime(new Date());

/** What each quick-entry kind needs from the two account pickers. Keeping the
 * copy here (rather than in JSX) makes the accounting visible in one place:
 * money always lands in or leaves a balance-sheet account. */
const KINDS: Record<EntryKind, { label: string; moneyLabel: string; counterLabel: string; counterTypes: string[]; hint: string }> = {
  expense: {
    label: "Money out",
    moneyLabel: "Paid from",
    counterLabel: "Category",
    counterTypes: ["expense"],
    hint: "Debits the expense, credits the account it came from.",
  },
  income: {
    label: "Money in",
    moneyLabel: "Received into",
    counterLabel: "Source",
    counterTypes: ["income"],
    hint: "Debits where it landed, credits the income source.",
  },
  transfer: {
    label: "Transfer",
    moneyLabel: "To",
    counterLabel: "From",
    counterTypes: ["asset", "liability"],
    hint: "Between your own accounts — never counted as income or spending.",
  },
};

function QuickEntry({ accounts }: { accounts: Account[] }) {
  const create = useCreateSimpleEntry();
  const { data: payees } = usePayees();

  const [kind, setKind] = useState<EntryKind>("expense");
  const [amount, setAmount] = useState("");
  const [accountId, setAccountId] = useState<number | "">("");
  const [counterId, setCounterId] = useState<number | "">("");
  const [occurredAt, setOccurredAt] = useState(now());
  const [memo, setMemo] = useState("");
  const [payeeId, setPayeeId] = useState<number | "">("");

  const spec = KINDS[kind];
  const moneyAccounts = accounts.filter((a) => a.type === "asset" || a.type === "liability");
  const counterAccounts = accounts.filter((a) => spec.counterTypes.includes(a.type));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (accountId === "" || counterId === "" || !amount) return;
    await create.mutateAsync({
      kind,
      amount,
      account_id: Number(accountId),
      counter_account_id: Number(counterId),
      occurred_at: occurredAt,
      memo: memo || undefined,
      payee_id: payeeId === "" ? undefined : Number(payeeId),
    });
    setAmount("");
    setMemo("");
  };

  return (
    <section className="card">
      <div className="card__head">
        <h3>New entry</h3>
        <span className="eyebrow">{spec.hint}</span>
      </div>
      <div className="card__body">
        <div className="filterbar__segment kind-toggle" role="group" aria-label="Entry kind">
          {(Object.keys(KINDS) as EntryKind[]).map((k) => (
            <button
              key={k}
              type="button"
              className={`seg ${kind === k ? "seg--on" : ""}`}
              onClick={() => {
                setKind(k);
                setCounterId("");
              }}
              aria-pressed={kind === k}
            >
              {KINDS[k].label}
            </button>
          ))}
        </div>

        <form className="entry-form" onSubmit={submit}>
          <label className="field">
            <span className="eyebrow">Amount</span>
            <input
              type="number"
              step="0.01"
              min="0"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              required
            />
          </label>

          <label className="field">
            <span className="eyebrow">{spec.moneyLabel}</span>
            <select
              value={accountId}
              onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : "")}
              required
            >
              <option value="">Select…</option>
              {moneyAccounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.code} · {a.name}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="eyebrow">{spec.counterLabel}</span>
            <select
              value={counterId}
              onChange={(e) => setCounterId(e.target.value ? Number(e.target.value) : "")}
              required
            >
              <option value="">Select…</option>
              {counterAccounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.code} · {a.name}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="eyebrow">When</span>
            <input
              type="datetime-local"
              value={occurredAt}
              onChange={(e) => setOccurredAt(e.target.value)}
            />
          </label>

          {kind !== "transfer" && (
            <label className="field">
              <span className="eyebrow">Payee</span>
              <select
                value={payeeId}
                onChange={(e) => setPayeeId(e.target.value ? Number(e.target.value) : "")}
              >
                <option value="">—</option>
                {payees?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
          )}

          <label className="field field--wide">
            <span className="eyebrow">Note</span>
            <input value={memo} onChange={(e) => setMemo(e.target.value)} placeholder="Optional" />
          </label>

          <button className="btn btn--primary" disabled={create.isPending}>
            {create.isPending ? "Posting…" : "Post entry"}
          </button>
        </form>
        {create.isError && <div className="empty empty--error">{String(create.error)}</div>}
      </div>
    </section>
  );
}

interface DraftLine {
  account_id: number | "";
  side: "debit" | "credit";
  amount: string;
  memo: string;
}

const emptyLine = (): DraftLine => ({ account_id: "", side: "debit", amount: "", memo: "" });

function JournalGrid({ accounts }: { accounts: Account[] }) {
  const create = useCreateEntry();
  const [open, setOpen] = useState(false);
  const [lines, setLines] = useState<DraftLine[]>([emptyLine(), emptyLine()]);
  const [occurredAt, setOccurredAt] = useState(now());
  const [memo, setMemo] = useState("");

  const totals = useMemo(() => {
    let debits = 0;
    let credits = 0;
    for (const line of lines) {
      const value = Number(line.amount) || 0;
      if (line.side === "debit") debits += value;
      else credits += value;
    }
    return { debits, credits, balanced: debits > 0 && Math.abs(debits - credits) < 0.005 };
  }, [lines]);

  const update = (i: number, patch: Partial<DraftLine>) =>
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!totals.balanced) return;
    const payload: JournalLineInput[] = lines
      .filter((l) => l.account_id !== "" && Number(l.amount) > 0)
      .map((l) => ({
        account_id: Number(l.account_id),
        [l.side]: Number(l.amount).toFixed(2),
        memo: l.memo || undefined,
      }));
    await create.mutateAsync({ occurred_at: occurredAt, lines: payload, memo: memo || undefined });
    setLines([emptyLine(), emptyLine()]);
    setMemo("");
  };

  return (
    <section className="card">
      <button className="disclosure" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span aria-hidden>{open ? "▾" : "▸"}</span>
        <span>Advanced · journal entry</span>
        <span className="eyebrow">
          more than two lines — a payslip, a split bill, a part-payment
        </span>
      </button>

      {open && (
        <div className="card__body">
          <form onSubmit={submit}>
            <div className="form-row" style={{ marginBottom: 12 }}>
              <label className="field">
                <span className="eyebrow">When</span>
                <input
                  type="datetime-local"
                  value={occurredAt}
                  onChange={(e) => setOccurredAt(e.target.value)}
                />
              </label>
              <label className="field field--wide">
                <span className="eyebrow">Description</span>
                <input
                  value={memo}
                  onChange={(e) => setMemo(e.target.value)}
                  placeholder="What happened"
                />
              </label>
            </div>

            <table className="ledger journal-grid">
              <thead>
                <tr>
                  <th>Account</th>
                  <th className="col-side">Side</th>
                  <th className="num">Amount</th>
                  <th>Line note</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {lines.map((line, i) => (
                  <tr key={i}>
                    <td>
                      <select
                        value={line.account_id}
                        onChange={(e) =>
                          update(i, { account_id: e.target.value ? Number(e.target.value) : "" })
                        }
                      >
                        <option value="">Select…</option>
                        {accounts.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.code} · {a.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <select
                        value={line.side}
                        onChange={(e) =>
                          update(i, { side: e.target.value as "debit" | "credit" })
                        }
                      >
                        <option value="debit">Debit</option>
                        <option value="credit">Credit</option>
                      </select>
                    </td>
                    <td className="num">
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        className="num"
                        value={line.amount}
                        onChange={(e) => update(i, { amount: e.target.value })}
                        placeholder="0.00"
                      />
                    </td>
                    <td>
                      <input
                        value={line.memo}
                        onChange={(e) => update(i, { memo: e.target.value })}
                        placeholder="Optional"
                      />
                    </td>
                    <td className="num">
                      {lines.length > 2 && (
                        <button
                          type="button"
                          className="btn btn--ghost btn--sm"
                          onClick={() => setLines((prev) => prev.filter((_, idx) => idx !== i))}
                        >
                          ×
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="journal-foot">
              <button
                type="button"
                className="btn"
                onClick={() => setLines((prev) => [...prev, emptyLine()])}
              >
                + Add line
              </button>

              {/* The invariant, live: you cannot post until the two sides agree. */}
              <div className={`balance-meter ${totals.balanced ? "balance-meter--ok" : ""}`}>
                <span>
                  Debits <span className="fig">{money(totals.debits)}</span>
                </span>
                <span className="balance-meter__sep">·</span>
                <span>
                  Credits <span className="fig">{money(totals.credits)}</span>
                </span>
                <span className="balance-meter__verdict">
                  {totals.balanced
                    ? "✓ balanced"
                    : `off by ${money(Math.abs(totals.debits - totals.credits))}`}
                </span>
              </div>

              <button className="btn btn--primary" disabled={!totals.balanced || create.isPending}>
                Post entry
              </button>
            </div>
            {create.isError && <div className="empty empty--error">{String(create.error)}</div>}
          </form>
        </div>
      )}
    </section>
  );
}

function EntryRow({
  entry,
  accountName,
  balance,
}: {
  entry: JournalEntry;
  accountName: (id: number) => string;
  balance?: string;
}) {
  const [open, setOpen] = useState(false);
  const voidEntry = useVoidEntry();
  const total = entry.lines.reduce((sum, l) => sum + Number(l.debit), 0);

  // A two-line entry has an obvious "what/where"; anything longer is genuinely
  // multi-sided and only its expansion tells the truth.
  const simple = entry.lines.length === 2;
  const debitLine = entry.lines.find((l) => Number(l.debit) > 0);
  const creditLine = entry.lines.find((l) => Number(l.credit) > 0);

  return (
    <>
      <tr className={entry.voided_at ? "row--voided" : undefined}>
        <td className="col-date">
          <div>{entryDate(entry.occurred_at)}</div>
          <div className="muted fig col-time">{formatTime(entry.occurred_at)}</div>
        </td>
        <td>
          <button className="linkish" onClick={() => setOpen((v) => !v)}>
            {entry.memo || (simple && debitLine ? accountName(debitLine.account_id) : "Journal entry")}
          </button>
          <div className="muted entry-sub">
            {simple && debitLine && creditLine
              ? `${accountName(debitLine.account_id)} ← ${accountName(creditLine.account_id)}`
              : `${entry.lines.length} lines`}
            {entry.source !== "manual" && <span className="pill pill--sm">{entry.source}</span>}
          </div>
        </td>
        <td className="num">
          <Money value={total.toFixed(2)} />
        </td>
        <td className="num muted fig">{balance ? money(balance) : "—"}</td>
        <td className="num">
          {!entry.voided_at && (
            <button
              className="btn btn--ghost btn--sm"
              title="Void this entry"
              onClick={() => {
                if (confirm("Void this entry? It stays in the books, marked void.")) {
                  voidEntry.mutate(entry.id);
                }
              }}
            >
              ×
            </button>
          )}
        </td>
      </tr>
      {open && (
        <tr className="row--lines">
          <td />
          <td colSpan={4}>
            <table className="ledger ledger--nested">
              <tbody>
                {entry.lines.map((line) => (
                  <tr key={line.id}>
                    <td className="fig col-code">{line.line_no}</td>
                    <td>
                      {accountName(line.account_id)}
                      {line.memo && <span className="muted"> · {line.memo}</span>}
                    </td>
                    <td className="num">
                      {Number(line.debit) > 0 ? <Money value={line.debit} sign="debit" /> : ""}
                    </td>
                    <td className="num">
                      {Number(line.credit) > 0 ? <Money value={line.credit} sign="credit" /> : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </td>
        </tr>
      )}
    </>
  );
}

export function Ledger() {
  const accountId = useFilters((s) => s.accountId);
  const { data: accounts } = useAccounts();
  const { data: entries, isLoading } = useEntries();
  const { data: allEntries } = useAllEntries();
  const { data: balances } = useAccountBalances();

  const accountName = useMemo(() => {
    const map = new Map<number, string>();
    accounts?.forEach((a) => map.set(a.id, a.name));
    return (id: number) => map.get(id) ?? `Account ${id}`;
  }, [accounts]);

  /**
   * Running cash balance per entry, computed across the *whole* history rather
   * than the filtered window — a balance that reset at an arbitrary range
   * start would not be a balance.
   */
  const runningByEntry = useMemo(() => {
    const cashIds = new Set(
      (accounts ?? []).filter((a) => a.type === "asset").map((a) => a.id),
    );
    const ordered = [...(allEntries ?? [])].sort((a, b) =>
      a.occurred_at === b.occurred_at ? a.id - b.id : a.occurred_at.localeCompare(b.occurred_at),
    );
    const out = new Map<number, string>();
    let running = 0;
    for (const entry of ordered) {
      for (const line of entry.lines) {
        if (!cashIds.has(line.account_id)) continue;
        running += Number(line.debit) - Number(line.credit);
      }
      out.set(entry.id, running.toFixed(2));
    }
    return out;
  }, [allEntries, accounts]);

  const cashOnHand = Number(balances?.totals_by_type.asset ?? 0);
  const periodTotal = (entries ?? []).reduce(
    (sum, e) => sum + e.lines.reduce((s, l) => s + Number(l.debit), 0),
    0,
  );

  return (
    <div>
      <div className="page-head">
        <span className="eyebrow">04 · Ledger</span>
        <h1>Every entry, dated and dressed</h1>
        <p>
          Each line of this ledger is a balanced journal entry — debits on one side, credits on
          the other, always equal. Record it the quick way and the app writes both sides for you;
          open the advanced grid when an entry genuinely has more than two.
        </p>
      </div>

      <section className="stat-grid" style={{ marginBottom: 20 }}>
        <div className="card stat">
          <span className="eyebrow">Cash across all assets</span>
          <div className="stat__value">
            <Money value={cashOnHand.toFixed(2)} sign={cashOnHand >= 0 ? "credit" : "debit"} />
          </div>
          <span className="stat__sub muted">every asset account, right now</span>
        </div>
        <div className="card stat">
          <span className="eyebrow">Posted this period</span>
          <div className="stat__value">
            <Money value={periodTotal.toFixed(2)} />
          </div>
          <span className="stat__sub muted">{entries?.length ?? 0} entries in range</span>
        </div>
        <div className="card stat">
          <span className="eyebrow">Export</span>
          <div className="stat__value" style={{ fontSize: 15 }}>
            <a className="btn" href={exportLedgerUrl({ account_id: accountId ?? undefined })}>
              ↓ Ledger CSV
            </a>
          </div>
          <span className="stat__sub muted">one row per journal line</span>
        </div>
      </section>

      <div className="grid" style={{ gap: 20 }}>
        {accounts && <QuickEntry accounts={accounts} />}
        {accounts && <JournalGrid accounts={accounts} />}

        <section className="card">
          <div className="card__head">
            <h3>Entries</h3>
            <span className="eyebrow">click a row to see both sides</span>
          </div>
          <div className="card__body">
            {isLoading && <div className="empty">Reading the ledger…</div>}
            {!isLoading && !entries?.length && (
              <div className="empty">Nothing recorded in this range yet.</div>
            )}
            {!!entries?.length && (
              <table className="ledger">
                <thead>
                  <tr>
                    <th className="col-date">Date</th>
                    <th>Entry</th>
                    <th className="num">Amount</th>
                    <th className="num">Cash balance</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <EntryRow
                      key={entry.id}
                      entry={entry}
                      accountName={accountName}
                      balance={runningByEntry.get(entry.id)}
                    />
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
