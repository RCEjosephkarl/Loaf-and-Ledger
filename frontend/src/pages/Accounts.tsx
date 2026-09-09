import { useMemo, useState } from "react";
import {
  useAccountBalances,
  useAccounts,
  useArchiveAccount,
  useCreateAccount,
} from "@/api/queries";
import { Money } from "@/components/Money";
import { exportTrialBalanceUrl } from "@/lib/api";
import { ACCOUNT_TYPE_LABEL, ACCOUNT_TYPE_ORDER, money } from "@/lib/format";
import type { AccountBalance, AccountType } from "@/lib/types";
import { InfoNote } from "@/components/InfoNote";

/** What each type's balance means in plain words — a chart of accounts is
 * only useful if you can read it without knowing the accounting. */
const TYPE_BLURB: Record<string, string> = {
  asset: "What you have — cash, bank, wallets, investments.",
  liability: "What you owe. A positive balance here is debt outstanding.",
  equity: "The opening position your books started from.",
  income: "What you've earned, cumulative since records began.",
  expense: "What you've spent, cumulative since records began.",
};

function TypeGroup({ type, rows }: { type: AccountType; rows: AccountBalance[] }) {
  const archive = useArchiveAccount();
  const total = rows.reduce((sum, r) => sum + Number(r.balance), 0);
  if (!rows.length) return null;

  return (
    <section className="card">
      <div className="card__head">
        <h3>
          {ACCOUNT_TYPE_LABEL[type]}
          <InfoNote label={`About ${ACCOUNT_TYPE_LABEL[type].toLowerCase()}`}>
            <p>{TYPE_BLURB[type]}</p>
          </InfoNote>
        </h3>
        <span className="eyebrow">{rows.length} accounts</span>
      </div>
      <div className="card__body">
        <table className="ledger">
          <thead>
            <tr>
              <th className="col-code">Code</th>
              <th>Account</th>
              <th className="num">Debits</th>
              <th className="num">Credits</th>
              <th className="num">Balance</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.account_id}>
                <td className="fig col-code">{r.code}</td>
                <td>{r.name}</td>
                <td className="num muted fig">{money(r.debits)}</td>
                <td className="num muted fig">{money(r.credits)}</td>
                <td className="num">
                  <Money value={r.balance} sign={Number(r.balance) >= 0 ? "credit" : "debit"} />
                </td>
                <td className="num">
                  <button
                    className="btn btn--ghost btn--sm"
                    title="Archive this account"
                    onClick={() => {
                      if (confirm(`Archive ${r.code} ${r.name}? Past entries keep it.`)) {
                        archive.mutate(r.account_id);
                      }
                    }}
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="total">
              <td colSpan={4}>Total {ACCOUNT_TYPE_LABEL[type].toLowerCase()}</td>
              <td className="num">
                <Money value={total.toFixed(2)} sign={total >= 0 ? "credit" : "debit"} />
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}

function NewAccountForm() {
  const create = useCreateAccount();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState<AccountType>("expense");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code || !name) return;
    try {
      await create.mutateAsync({ code, name, type });
      setCode("");
      setName("");
    } catch {
      /* surfaced below */
    }
  };

  return (
    <section className="card">
      <div className="card__head">
        <h3>
          Add an account
          <InfoNote label="About account codes">
            <p>
              The leading digit is the convention, not a rule the app enforces: assets 1xxx,
              liabilities 2xxx, equity 3xxx, income 4xxx, spending 5xxx, statutory 6xxx.
            </p>
          </InfoNote>
        </h3>
      </div>
      <div className="card__body">
        <form className="form-row" onSubmit={submit}>
          <label className="field field--code">
            <span className="eyebrow">Code</span>
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="5200" />
          </label>
          <label className="field">
            <span className="eyebrow">Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Pet care" />
          </label>
          <label className="field">
            <span className="eyebrow">Type</span>
            <select value={type} onChange={(e) => setType(e.target.value as AccountType)}>
              {ACCOUNT_TYPE_ORDER.map((t) => (
                <option key={t} value={t}>
                  {ACCOUNT_TYPE_LABEL[t]}
                </option>
              ))}
            </select>
          </label>
          <button className="btn btn--primary" disabled={create.isPending}>
            {create.isPending ? "Adding…" : "Add"}
          </button>
        </form>
        {create.isError && <div className="empty empty--error">{String(create.error)}</div>}
      </div>
    </section>
  );
}

export function Accounts() {
  const { data: balances, isLoading } = useAccountBalances();
  const { data: accounts } = useAccounts();

  const byType = useMemo(() => {
    const map = new Map<AccountType, AccountBalance[]>();
    balances?.accounts.forEach((a) => {
      const list = map.get(a.type) ?? [];
      list.push(a);
      map.set(a.type, list);
    });
    return map;
  }, [balances]);

  const assets = Number(balances?.totals_by_type.asset ?? 0);
  const liabilities = Number(balances?.totals_by_type.liability ?? 0);

  return (
    <div>
      <div className="page-head">
        <h1>
          Accounts
          <InfoNote label="About accounts" lead="Every pocket, named.">
            <p>
              The chart of accounts every entry posts against. Each balance below is derived from
              the journal alone — nothing is stored as a running total, so the books can always be
              reproduced from their entries.
            </p>
          </InfoNote>
        </h1>
      </div>

      {isLoading && <div className="empty">Reading the books…</div>}

      {balances && (
        <>
          <section className="stat-grid" style={{ marginBottom: 20 }}>
            <div className="card stat">
              <span className="eyebrow">Net worth</span>
              <div className="stat__value">
                <Money
                  value={balances.net_worth}
                  sign={Number(balances.net_worth) >= 0 ? "credit" : "debit"}
                />
              </div>
              <span className="stat__sub muted">Assets less liabilities</span>
            </div>
            <div className="card stat">
              <span className="eyebrow">Assets</span>
              <div className="stat__value">
                <Money value={assets.toFixed(2)} sign="credit" />
              </div>
              <span className="stat__sub muted">{byType.get("asset")?.length ?? 0} accounts</span>
            </div>
            <div className="card stat">
              <span className="eyebrow">Liabilities</span>
              <div className="stat__value">
                <Money value={liabilities.toFixed(2)} sign={liabilities > 0 ? "debit" : "credit"} />
              </div>
              <span className="stat__sub muted">What you owe</span>
            </div>
            <div className="card stat">
              <span className="eyebrow">Open accounts</span>
              <div className="stat__value fig">{accounts?.length ?? "—"}</div>
              <span className="stat__sub muted">
                <a href={exportTrialBalanceUrl()}>↓ Trial balance CSV</a>
              </span>
            </div>
          </section>

          <div className="grid" style={{ gap: 20 }}>
            {ACCOUNT_TYPE_ORDER.map((type) => (
              <TypeGroup key={type} type={type} rows={byType.get(type) ?? []} />
            ))}
            <NewAccountForm />
          </div>
        </>
      )}
    </div>
  );
}
