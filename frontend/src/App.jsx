import { useEffect, useMemo, useState } from "react";
import axios from "axios";

const API_BASE = "http://127.0.0.1:8000/api/v1";

const formatRupees = (paise) => `Rs ${(paise / 100).toLocaleString("en-IN")}`;
const makeIdempotencyKey = () => {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  // Fallback for browsers/environments without randomUUID support.
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

export default function App() {
  const [merchantId, setMerchantId] = useState(1);
  const [dashboard, setDashboard] = useState(null);
  const [amountRupees, setAmountRupees] = useState("");
  const [bankAccountId, setBankAccountId] = useState("bank-demo-001");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const fetchDashboard = async () => {
    const response = await axios.get(`${API_BASE}/merchants/${merchantId}/dashboard`);
    setDashboard(response.data);
  };

  useEffect(() => {
    fetchDashboard();
    const timer = setInterval(fetchDashboard, 3000);
    return () => clearInterval(timer);
  }, [merchantId]);

  const onSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await axios.post(
        `${API_BASE}/payouts`,
        {
          amount_paise: Math.round(Number(amountRupees) * 100),
          bank_account_id: bankAccountId
        },
        {
          headers: {
            "X-Merchant-Id": String(merchantId),
            "Idempotency-Key": makeIdempotencyKey()
          }
        }
      );
      setAmountRupees("");
      fetchDashboard();
    } catch (err) {
      console.error("Payout request error:", err);
      const apiDetail = err?.response?.data?.detail;
      const status = err?.response?.status;
      if (apiDetail) {
        setError(`${apiDetail}${status ? ` (HTTP ${status})` : ""}`);
      } else {
        setError(`Failed to request payout. ${err?.message || "Check backend at http://127.0.0.1:8000."}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const merchant = dashboard?.merchant;

  return (
    <div className="page">
      <header className="header">
        <h1>Merchant Ledger Dashboard</h1>
        <select value={merchantId} onChange={(e) => setMerchantId(Number(e.target.value))}>
          <option value={1}>Merchant 1</option>
          <option value={2}>Merchant 2</option>
          <option value={3}>Merchant 3</option>
        </select>
      </header>

      {merchant && (
        <section className="cards">
          <div className="card">
            <p>Available Balance</p>
            <h2>{formatRupees(merchant.available_balance_paise)}</h2>
          </div>
          <div className="card">
            <p>Held Balance</p>
            <h2>{formatRupees(merchant.held_balance_paise)}</h2>
          </div>
          <div className="card">
            <p>Ledger Balance</p>
            <h2>{formatRupees(merchant.balance_paise)}</h2>
          </div>
        </section>
      )}

      <section className="panel">
        <h3>Request Payout</h3>
        <form onSubmit={onSubmit} className="form">
          <input
            type="number"
            min="1"
            step="1"
            placeholder="Amount in rupees"
            value={amountRupees}
            onChange={(e) => setAmountRupees(e.target.value)}
            required
          />
          <input
            value={bankAccountId}
            onChange={(e) => setBankAccountId(e.target.value)}
            placeholder="Bank account id"
            required
          />
          <button disabled={loading}>{loading ? "Submitting..." : "Create Payout"}</button>
        </form>
        {error && <p className="error">{error}</p>}
      </section>

      <section className="grid">
        <div className="panel">
          <h3>Recent Credits / Debits</h3>
          <table>
            <thead>
              <tr>
                <th>Type</th>
                <th>Amount</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {dashboard?.recent_entries?.map((entry) => (
                <tr key={entry.id}>
                  <td>{entry.entry_type}</td>
                  <td>{formatRupees(entry.amount_paise)}</td>
                  <td>{entry.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="panel">
          <h3>Payout History</h3>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Attempts</th>
              </tr>
            </thead>
            <tbody>
              {dashboard?.payouts?.map((payout) => (
                <tr key={payout.id}>
                  <td>{payout.id}</td>
                  <td>{formatRupees(payout.amount_paise)}</td>
                  <td className={`status ${payout.status}`}>{payout.status}</td>
                  <td>{payout.attempts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
