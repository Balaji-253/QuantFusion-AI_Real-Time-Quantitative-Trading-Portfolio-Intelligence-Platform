import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type Tick = {
  event_id: string;
  symbol: string;
  price: number;
  volume: number;
  source: string;
  event_time: string;
  received_time?: string;
};

type Metric = {
  symbol?: string;
  observations?: number;
  latest_price?: number | null;
  window_return?: number | null;
  volatility?: number | null;
  max_drawdown?: number | null;
  latest_timestamp?: string | null;
  source?: string;
  volatility_unit?: string;
  window_size?: number;
  lookback_minutes?: number;
};

type Signal = {
  symbol?: string;
  signal?: string;
  score?: number | null;
  reason?: string;
  observations?: number;
  price?: number | null;
  window_return?: number | null;
  threshold?: number;
  source?: string;
  mode?: string;
};

type Position = {
  quantity: number;
  last_price: number;
  market_value: number;
};

type Portfolio = {
  cash: number;
  positions: Record<string, Position>;
  market_value: number;
  equity: number;
  mode: string;
};

type PaperOrder = {
  order_id: string;
  symbol: string;
  side: string;
  quantity: number;
  requested_price?: number;
  filled_price: number;
  notional: number;
  status: string;
  created_at: string;
};

function fmt(value: number | null | undefined, digits = 2) {
  return value == null || !Number.isFinite(value)
    ? "—"
    : value.toLocaleString(undefined, {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });
}

function normalizeBySymbol<T>(data: unknown): Record<string, T> {
  if (Array.isArray(data)) {
    return Object.fromEntries(
      data
        .filter(
          (item): item is T & { symbol: string } =>
            item !== null &&
            typeof item === "object" &&
            typeof (item as { symbol?: unknown }).symbol === "string",
        )
        .map((item) => [item.symbol, item]),
    );
  }

  if (data && typeof data === "object") {
    return data as Record<string, T>;
  }

  return {};
}

async function readJson(response: Response): Promise<any> {
  const data = await response.json();

  if (!response.ok) {
    const detail =
      data && typeof data.detail === "string"
        ? data.detail
        : `HTTP ${response.status}`;

    throw new Error(detail);
  }

  return data;
}

export default function App() {
  const [ticks, setTicks] = useState<Tick[]>([]);
  const [metrics, setMetrics] = useState<Record<string, Metric>>({});
  const [signals, setSignals] = useState<Record<string, Signal>>({});
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [portfolioError, setPortfolioError] = useState("");
  const [selected, setSelected] = useState("SPY");
  const [connection, setConnection] = useState("Connecting");
  const [lastUpdate, setLastUpdate] = useState("—");
  const [orderSubmitting, setOrderSubmitting] = useState(false);

  async function refresh() {
    const results = await Promise.allSettled([
      fetch(`${API}/api/v1/market/latest`),
      fetch(`${API}/api/v1/analytics/metrics`),
      fetch(`${API}/api/v1/analytics/signals`),
      fetch(`${API}/api/v1/portfolio`),
      fetch(`${API}/api/v1/orders`),
    ]);

    try {
      const result = results[0];

      if (result.status === "rejected") {
        throw result.reason;
      }

      const latest = await readJson(result.value);
      setTicks(Array.isArray(latest.items) ? latest.items : []);
      setLastUpdate(new Date().toLocaleTimeString());
      setConnection("REST connected");
    } catch {
      setConnection("API unavailable");
      return;
    }

    try {
      const result = results[1];

      if (result.status === "fulfilled") {
        const data = await readJson(result.value);
        setMetrics(normalizeBySymbol<Metric>(data.items));
      }
    } catch {
      setMetrics({});
    }

    try {
      const result = results[2];

      if (result.status === "fulfilled") {
        const data = await readJson(result.value);
        setSignals(normalizeBySymbol<Signal>(data.items));
      }
    } catch {
      setSignals({});
    }

    try {
      const result = results[3];

      if (result.status === "fulfilled") {
        const data = await readJson(result.value);
        setPortfolio(data as Portfolio);
        setPortfolioError("");
      } else {
        throw result.reason;
      }
    } catch {
      setPortfolioError("Portfolio endpoint is temporarily unavailable.");
    }

    try {
      const result = results[4];

      if (result.status === "fulfilled") {
        const data = await readJson(result.value);
        setOrders(Array.isArray(data.items) ? data.items : []);
      }
    } catch {
      // Keep the previously loaded order history.
    }
  }

  useEffect(() => {
    let disposed = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | undefined;
    let refreshTimer: number | undefined;

    const safeRefresh = async () => {
      if (!disposed) {
        await refresh();
      }
    };

    void safeRefresh();

    refreshTimer = window.setInterval(() => {
      void safeRefresh();
    }, 5000);

    const connect = () => {
      if (disposed) return;

      try {
        socket = new WebSocket(
          `${API.replace(/^http/, "ws")}/ws/market`,
        );

        socket.onopen = () => {
          if (!disposed) {
            setConnection("Live WebSocket");
          }
        };

        socket.onmessage = (message) => {
          if (disposed) return;

          try {
            const payload = JSON.parse(message.data);

            if (payload.type === "market_event" && payload.data) {
              const incoming = payload.data as Tick;

              setTicks((current) =>
                [
                  incoming,
                  ...current.filter(
                    (tick) => tick.symbol !== incoming.symbol,
                  ),
                ].slice(0, 20),
              );

              setLastUpdate(new Date().toLocaleTimeString());
            } else if (Array.isArray(payload.items)) {
              setTicks(payload.items);
              setLastUpdate(new Date().toLocaleTimeString());
            }
          } catch {
            // Ignore malformed WebSocket messages.
          }
        };

        socket.onerror = () => {
          if (!disposed) {
            setConnection("REST connected · WebSocket reconnecting");
          }
        };

        socket.onclose = () => {
          if (!disposed) {
            reconnectTimer = window.setTimeout(connect, 3000);
          }
        };
      } catch {
        if (!disposed) {
          reconnectTimer = window.setTimeout(connect, 3000);
        }
      }
    };

    connect();

    return () => {
      disposed = true;

      if (refreshTimer !== undefined) {
        window.clearInterval(refreshTimer);
      }

      if (reconnectTimer !== undefined) {
        window.clearTimeout(reconnectTimer);
      }

      socket?.close();
    };
  }, []);

  const selectedMetric = metrics[selected];
  const selectedSignal = signals[selected];
  const selectedTick = ticks.find(
    (tick) => tick.symbol === selected,
  );

  const chartData = useMemo(
    () =>
      ticks
        .filter((tick) => tick.symbol === selected)
        .map((tick) => ({
          time: new Date(tick.event_time).toLocaleTimeString(),
          price: tick.price,
        })),
    [ticks, selected],
  );

  async function submitPaperOrder(side: "BUY" | "SELL") {
    if (orderSubmitting) return;

    setOrderSubmitting(true);

    try {
      const response = await fetch(`${API}/api/v1/orders/paper`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          symbol: selected,
          side,
          quantity: 1,
          idempotency_key: crypto.randomUUID().replace(/-/g, ""),
        }),
      });

      const body = await readJson(response);

      window.alert(
        `Paper order filled: ${body.side} ${body.quantity} ${body.symbol} @ ${fmt(body.filled_price)}. This is a simulation.`,
      );

      await refresh();
    } catch (error) {
      window.alert(
        error instanceof Error
          ? error.message
          : "Could not submit paper order.",
      );
    } finally {
      setOrderSubmitting(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">Q</div>
          <div>
            <strong>
              QuantFusion <span>AI</span>
            </strong>
            <small>QUANTITATIVE MARKET INTELLIGENCE</small>
          </div>
        </div>

        <div className="status">
          <i
            className={
              connection.includes("connected") ||
              connection.includes("WebSocket")
                ? "dot live"
                : "dot"
            }
          />
          {connection}
          <span className="divider">·</span>
          Updated {lastUpdate}
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">
            MARKET OVERVIEW / RESEARCH ENVIRONMENT
          </p>
          <h1>
            Quantitative intelligence, <em>in real time.</em>
          </h1>
          <p className="sub">
            Streaming market events, statistical analytics and
            risk-aware paper execution.
          </p>
        </div>

        <div className="paper-badge">
          <span>●</span> PAPER TRADING ONLY
        </div>
      </section>

      <section className="notice">
        Synthetic market simulator is enabled by default. Displayed
        prices are generated test data, not live exchange quotes or
        investment recommendations.
      </section>

      <section className="symbol-grid">
        {["SPY", "QQQ", "AAPL", "MSFT"].map((symbol) => {
          const tick = ticks.find((item) => item.symbol === symbol);
          const metric = metrics[symbol];

          return (
            <button
              className={
                selected === symbol
                  ? "symbol-card active"
                  : "symbol-card"
              }
              key={symbol}
              onClick={() => setSelected(symbol)}
            >
              <div className="symbol-head">
                <span>{symbol}</span>
                <span className="tiny-dot" />
              </div>

              <strong className="price">${fmt(tick?.price)}</strong>

              <div className="symbol-foot">
                <span>Window return</span>
                <b
                  className={
                    (metric?.window_return ?? 0) >= 0
                      ? "positive"
                      : "negative"
                  }
                >
                  {metric?.window_return == null
                    ? "—"
                    : `${metric.window_return >= 0 ? "+" : ""}${fmt(metric.window_return * 100)}%`}
                </b>
              </div>
            </button>
          );
        })}
      </section>

      <section className="main-grid">
        <article className="panel chart-panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">MARKET MONITOR</p>
              <h2>
                {selected} <span>· latest observation</span>
              </h2>
            </div>

            <select
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
            >
              <option>SPY</option>
              <option>QQQ</option>
              <option>AAPL</option>
              <option>MSFT</option>
            </select>
          </div>

          <div className="chart-stat">
            <strong>
              ${fmt(selectedMetric?.latest_price ?? selectedTick?.price)}
            </strong>
            <span>Latest observation · synthetic sample</span>
          </div>

          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chartData}
                margin={{ top: 12, right: 12, bottom: 0, left: 0 }}
              >
                <defs>
                  <linearGradient
                    id="fillPrice"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="0%"
                      stopColor="#42d6b0"
                      stopOpacity={0.28}
                    />
                    <stop
                      offset="95%"
                      stopColor="#42d6b0"
                      stopOpacity={0}
                    />
                  </linearGradient>
                </defs>

                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#253348"
                />

                <XAxis
                  dataKey="time"
                  tick={{ fill: "#7f91aa", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />

                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fill: "#7f91aa", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={65}
                />

                <Tooltip
                  contentStyle={{
                    background: "#111d2d",
                    border: "1px solid #2b3a50",
                    borderRadius: 8,
                  }}
                />

                <Area
                  type="monotone"
                  dataKey="price"
                  stroke="#42d6b0"
                  fill="url(#fillPrice)"
                  strokeWidth={2}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <p className="chart-foot">
            Live latest-value stream. The chart shows received observations;
            it is not a full historical price series.
          </p>
        </article>

        <article className="panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">MODEL OUTPUT</p>
              <h2>Research signal</h2>
            </div>
            <span className="tag">BASELINE</span>
          </div>

          <div className="signal-box">
            <span className="signal-label">CURRENT BIAS</span>
            <strong>{selectedSignal?.signal ?? "UNAVAILABLE"}</strong>
            <small>
              {selectedSignal?.reason ??
                "Waiting for research signal data."}
            </small>
          </div>

          <div className="metric-list">
            <div>
              <span>Signal strength (-1 to +1)</span>
              <b>
                {selectedSignal?.score == null
                  ? "—"
                  : selectedSignal.score.toFixed(3)}
              </b>
            </div>

            <div>
              <span>Observations</span>
              <b>{selectedSignal?.observations ?? selectedMetric?.observations ?? "—"}</b>
            </div>

            <div>
              <span>Window volatility</span>
              <b>
                {selectedMetric?.volatility == null
                  ? "—"
                  : `${fmt(selectedMetric.volatility * 100)}%`}
              </b>
            </div>

            <div>
              <span>Maximum drawdown</span>
              <b>
                {selectedMetric?.max_drawdown == null
                  ? "—"
                  : `${fmt(selectedMetric.max_drawdown * 100)}%`}
              </b>
            </div>
          </div>

          <p className="chart-foot">
            Missing analytics are shown as unavailable. Signals are not
            trained or validated trading predictions.
          </p>
        </article>
      </section>

      <section className="bottom-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">EXECUTION SANDBOX</p>
              <h2>Paper order ticket</h2>
            </div>
            <span className="tag safe">SIMULATED</span>
          </div>

          <p className="muted">
            Submit a one-unit simulated order at the latest observed
            price. Backend risk limits remain authoritative.
          </p>

          <div className="order-ticket">
            <div>
              <span>Instrument</span>
              <strong>{selected}</strong>
            </div>
            <div>
              <span>Quantity</span>
              <strong>1 unit</strong>
            </div>
            <div>
              <span>Estimated notional</span>
              <strong>${fmt(selectedTick?.price)}</strong>
            </div>
          </div>

          <div className="order-actions">
            <button
              className="buy"
              disabled={orderSubmitting}
              onClick={() => void submitPaperOrder("BUY")}
            >
              {orderSubmitting ? "Submitting…" : "Submit paper buy"}
            </button>
            <button
              className="sell"
              disabled={orderSubmitting}
              onClick={() => void submitPaperOrder("SELL")}
            >
              {orderSubmitting ? "Submitting…" : "Submit paper sell"}
            </button>
          </div>

          <p className="chart-foot">
            No brokerage integration. No real orders are sent.
          </p>
        </article>

        <article className="panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">EVENT PIPELINE</p>
              <h2>Latest market events</h2>
            </div>
            <span className="tag">{ticks.length} symbols</span>
          </div>

          <div className="event-table">
            <div className="event-row table-head">
              <span>Symbol</span>
              <span>Last price</span>
              <span>Source</span>
            </div>

            {ticks.map((tick) => (
              <button
                className="event-row"
                key={tick.symbol}
                onClick={() => setSelected(tick.symbol)}
              >
                <span className="event-symbol">{tick.symbol}</span>
                <b>${fmt(tick.price)}</b>
                <span className="source">{tick.source}</span>
              </button>
            ))}

            {ticks.length === 0 && (
              <p className="muted">Waiting for first market event…</p>
            )}
          </div>
        </article>
      </section>

      <section className="bottom-grid account-grid">
        <article className="panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">ACCOUNT / PAPER MODE</p>
              <h2>Portfolio overview</h2>
            </div>
            <span className="tag safe">
              {portfolio?.mode ?? "UNAVAILABLE"}
            </span>
          </div>

          {portfolioError && (
            <p className="muted">{portfolioError}</p>
          )}

          <div className="metric-list portfolio-metrics">
            <div>
              <span>Total equity</span>
              <b>{portfolio ? `$${fmt(portfolio.equity)}` : "—"}</b>
            </div>
            <div>
              <span>Available cash</span>
              <b>{portfolio ? `$${fmt(portfolio.cash)}` : "—"}</b>
            </div>
            <div>
              <span>Positions market value</span>
              <b>
                {portfolio ? `$${fmt(portfolio.market_value)}` : "—"}
              </b>
            </div>
          </div>

          <div className="event-table">
            <div className="event-row position-row table-head">
              <span>Position</span>
              <span>Quantity / Price</span>
              <span>Market value</span>
            </div>

            {Object.entries(portfolio?.positions ?? {}).map(
              ([symbol, position]) => (
                <button
                  className="event-row position-row"
                  key={symbol}
                  onClick={() => setSelected(symbol)}
                >
                  <span className="event-symbol">{symbol}</span>
                  <span>
                    {fmt(position.quantity, 4)} @ $
                    {fmt(position.last_price)}
                  </span>
                  <b>${fmt(position.market_value)}</b>
                </button>
              ),
            )}

            {portfolio &&
              Object.keys(portfolio.positions ?? {}).length === 0 && (
                <p className="muted">
                  No open positions in the paper portfolio.
                </p>
              )}
          </div>
        </article>

        <article className="panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">EXECUTION RECORD</p>
              <h2>Paper order history</h2>
            </div>
            <span className="tag">{orders.length} orders</span>
          </div>

          <div className="event-table">
            <div className="event-row order-history-row table-head">
              <span>Order</span>
              <span>Quantity / Fill</span>
              <span>Status</span>
            </div>

            {orders.map((order) => (
              <div
                className="event-row order-history-row"
                key={order.order_id}
              >
                <span>
                  <b className="event-symbol">
                    {order.side} {order.symbol}
                  </b>
                  <small className="order-date">
                    {new Date(order.created_at).toLocaleString()}
                  </small>
                </span>

                <span>
                  {fmt(order.quantity, 4)} @ ${fmt(order.filled_price)}
                </span>

                <span
                  className={
                    order.status === "FILLED"
                      ? "positive source"
                      : "source"
                  }
                >
                  {order.status}
                </span>
              </div>
            ))}

            {orders.length === 0 && (
              <p className="muted">No paper orders recorded yet.</p>
            )}
          </div>

          <p className="chart-foot">
            Order records are retrieved from the backend. All
            executions shown here are simulated.
          </p>
        </article>
      </section>

      <footer>
        <span>QUANTFUSION AI · DEVELOPMENT FOUNDATION</span>
        <span>
          Health and API docs:{" "}
          <a href={`${API}/docs`} target="_blank" rel="noreferrer">
            OpenAPI
          </a>
        </span>
        <span>Paper trading only · No financial advice</span>
      </footer>
    </main>
  );
}