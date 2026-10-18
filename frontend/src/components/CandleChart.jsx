import { useEffect, useRef, useState } from "react";
import { createChart, CandlestickSeries, HistogramSeries, CrosshairMode } from "lightweight-charts";
import { API_URL } from "../config";
import BitcoinLogo from "./BitcoinLogo";
import IntervalMenu from "./IntervalMenu";
import { TIMEFRAMES } from "../timeframes";

const BAR_SPACING = 8;                // default pixels per candle (TradingView's default zoom level)
const RIGHT_OFFSET = 8;               // empty candles' worth of space to the right of the newest candle

// "2026-10-18T17:30:12.123456Z" -> Unix seconds. Trims extra decimals so every browser can parse it.
const toSeconds = (iso) => Math.floor(Date.parse(iso.replace(/(\.\d{3})\d*/, "$1")) / 1000);

// Read a colour from App.css (e.g. --buy), so the chart matches the rest of the page in light and dark mode.
const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// "#16a34a" + 0.4 -> "rgba(22, 163, 74, 0.4)", for the see-through volume bars.
const withAlpha = (hex, alpha) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
};

const theme = () => ({
  layout: { background: { color: "transparent" }, textColor: cssVar("--muted") },
  grid: { vertLines: { color: cssVar("--border") }, horzLines: { color: cssVar("--border") } },
  rightPriceScale: { borderColor: cssVar("--border") },
  timeScale: { borderColor: cssVar("--border") },
});

const candleColors = () => ({
  upColor: cssVar("--buy"), downColor: cssVar("--sell"),          // green if close > open, red if close < open
  wickUpColor: cssVar("--buy"), wickDownColor: cssVar("--sell"),
});

const price = (n) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const amount = (n) => n.toLocaleString("en-US", { maximumFractionDigits: n >= 100 ? 2 : 4 });

const toCandle = (b) => ({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close });
const toVolume = (b) => ({
  time: b.time,
  value: b.volume ?? 0,
  color: withAlpha(cssVar(b.close >= b.open ? "--buy" : "--sell"), 0.4),
});

// Which candle a trade at time t belongs to. Counts forward from the newest candle we have,
// so live candles line up with Alpaca's (important for 1w, whose candles don't start on a round Unix number).
function candleStart(t, current, period) {
  if (!current) return Math.floor(t / period) * period;            // no candles at all yet: best guess
  if (t < current.time) return null;                               // late trade for an older candle
  return current.time + Math.floor((t - current.time) / period) * period;
}

// Back to the default zoom: newest candle on the right, both axes fitted automatically.
function resetView(chart, series) {
  if (!chart || !series) return;
  chart.timeScale().applyOptions({ barSpacing: BAR_SPACING, rightOffset: RIGHT_OFFSET });
  chart.timeScale().scrollToRealTime();
  series.priceScale().setAutoScale(true);
}

// BTC candles in a TradingView-style chart: history from the backend for the chosen interval,
// then the newest candle, its volume bar and a flashing live dot updated by every trade.
export default function CandleChart({ symbol, trades }) {
  const [timeframe, setTimeframe] = useState("1m");
  const [status, setStatus] = useState("loading");                // "loading" | "ready" | "error"
  const [expanded, setExpanded] = useState(false);                // full-screen mode
  const [legend, setLegend] = useState(null);                     // the candle shown in the top-left O/H/L/C line
  const [autoScale, setAutoScale] = useState(true);               // false once the price axis is zoomed by hand
  const [awayFromNow, setAwayFromNow] = useState(false);          // scrolled back into history?

  const cardRef = useRef(null);       // the whole card, which is what goes full screen
  const containerRef = useRef(null);  // the <div> the chart draws into
  const dotRef = useRef(null);        // the live dot that flashes green/red on each trade
  const chartRef = useRef(null);      // the chart, so other effects can change its options
  const seriesRef = useRef(null);     // the candlestick series
  const volumeRef = useRef(null);     // the volume bars along the bottom
  const barsRef = useRef([]);         // every candle on screen (history + live), oldest first
  const candleRef = useRef(null);     // the candle currently forming
  const lastIdRef = useRef(-1);       // newest trade already added to a candle
  const periodRef = useRef(60);       // seconds per candle for the current interval
  const loadedRef = useRef(false);    // has this interval's history arrived? live trades wait until it has
  const hoveringRef = useRef(false);  // is the mouse over a candle? then the legend follows the mouse
  const wasExpandedRef = useRef(false);

  useEffect(() => {                   // runs once: build the chart and wire up the mouse
    const container = containerRef.current;
    const chart = createChart(container, {
      autoSize: true,                 // fill the container and resize with it (this is what makes full screen work)
      ...theme(),
      crosshair: { mode: CrosshairMode.Normal },                   // free crosshair, like TradingView
      timeScale: {
        ...theme().timeScale,
        timeVisible: true, secondsVisible: false,
        barSpacing: BAR_SPACING, rightOffset: RIGHT_OFFSET, minBarSpacing: 0.5,
      },
      handleScale: { axisPressedMouseMove: { time: true, price: true }, mouseWheel: true, pinch: true },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
    });
    const series = chart.addSeries(CandlestickSeries, { ...candleColors(), borderVisible: false });
    series.priceScale().applyOptions({ scaleMargins: { top: 0.08, bottom: 0.24 } });   // leave room for volume
    const volume = chart.addSeries(HistogramSeries, {
      priceScaleId: "volume",         // its own invisible scale, so volume doesn't squash the candles
      priceFormat: { type: "volume" },
      lastValueVisible: false,
      priceLineVisible: false,
    });
    chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });   // bottom 18%

    chartRef.current = chart;
    seriesRef.current = series;
    volumeRef.current = volume;

    // Mouse wheel, TradingView-style: over the price axis it stretches the chart vertically,
    // over the time axis it stretches it horizontally, over the candles it zooms time (the library does that one).
    const onWheel = (e) => {
      const rect = container.getBoundingClientRect();
      const onPriceAxis = e.clientX - rect.left > rect.width - series.priceScale().width();
      const onTimeAxis = e.clientY - rect.top > rect.height - chart.timeScale().height();
      if (!onPriceAxis && !onTimeAxis) return;
      e.preventDefault();                                          // don't scroll the page
      e.stopPropagation();                                         // and don't let the library handle it too
      const factor = Math.exp(e.deltaY * 0.0015);                  // wheel down = zoom out, wheel up = zoom in

      if (onPriceAxis) {
        const range = series.priceScale().getVisibleRange();
        if (!range) return;
        const mid = (range.from + range.to) / 2;
        const half = ((range.to - range.from) / 2) * factor;
        series.priceScale().setAutoScale(false);
        series.priceScale().setVisibleRange({ from: mid - half, to: mid + half });
      } else {
        const spacing = chart.timeScale().options().barSpacing / factor;
        chart.timeScale().applyOptions({ barSpacing: Math.min(50, Math.max(0.5, spacing)) });
      }
    };
    container.addEventListener("wheel", onWheel, { capture: true, passive: false });

    const onCrosshair = (param) => {                               // legend follows the mouse
      const bar = param.time ? param.seriesData.get(series) : null;
      hoveringRef.current = Boolean(bar);
      if (bar) setLegend({ ...bar, volume: param.seriesData.get(volume)?.value ?? 0 });
      else setLegend(candleRef.current ? { ...candleRef.current } : null);
    };
    chart.subscribeCrosshairMove(onCrosshair);

    let frame;                        // every animation frame: keep the live dot on the newest candle
    const tick = () => {
      const dot = dotRef.current;
      const c = candleRef.current;
      if (dot) {
        const x = c ? chart.timeScale().timeToCoordinate(c.time) : null;
        const y = c ? series.priceToCoordinate(c.close) : null;
        const paneWidth = container.clientWidth - series.priceScale().width();
        const paneHeight = container.clientHeight - chart.timeScale().height();
        const visible = x !== null && y !== null && x >= 0 && x <= paneWidth && y >= 0 && y <= paneHeight;
        dot.style.display = visible ? "block" : "none";
        if (visible) dot.style.transform = `translate(${x}px, ${y}px)`;
      }
      setAutoScale(series.priceScale().options().autoScale);      // React skips the re-render if unchanged
      setAwayFromNow(chart.timeScale().scrollPosition() < -3);    // more than 3 candles back from the newest
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);

    const scheme = window.matchMedia("(prefers-color-scheme: dark)");   // recolour if the OS switches light/dark
    const recolour = () => {
      chart.applyOptions(theme());
      series.applyOptions(candleColors());
      volume.setData(barsRef.current.map(toVolume));
    };
    scheme.addEventListener("change", recolour);

    return () => {                    // clean up if the component goes away
      cancelAnimationFrame(frame);
      scheme.removeEventListener("change", recolour);
      container.removeEventListener("wheel", onWheel, { capture: true });
      chart.unsubscribeCrosshairMove(onCrosshair);
      chart.remove();
      chartRef.current = seriesRef.current = volumeRef.current = null;
    };
  }, []);

  useEffect(() => {                   // runs when the symbol or interval changes: load that history
    const { seconds } = TIMEFRAMES.find((tf) => tf.key === timeframe);
    periodRef.current = seconds;
    candleRef.current = null;         // the old forming candle belongs to the old interval
    loadedRef.current = false;        // ignore live trades until the new history is drawn
    chartRef.current.applyOptions({ timeScale: { timeVisible: seconds < 24 * 60 * 60 } });   // no clock times on D/W

    let cancelled = false;            // ignore this response if the user picked another interval meanwhile
    fetch(`${API_URL}/bars/${symbol}?timeframe=${timeframe}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((bars) => {
        if (cancelled) return;
        barsRef.current = bars;
        seriesRef.current.setData(bars.map(toCandle));           // draw all past candles at once
        volumeRef.current.setData(bars.map(toVolume));
        const last = bars.at(-1);
        candleRef.current = last ? { ...last } : null;           // live trades keep building on the newest candle
        loadedRef.current = true;                                // from now on, live trades update the chart
        resetView(chartRef.current, seriesRef.current);
        if (!hoveringRef.current) setLegend(last ? { ...last } : null);
        setStatus("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        console.error("Couldn't load candles:", err);
        setStatus("error");
      });

    return () => { cancelled = true; };
  }, [symbol, timeframe]);

  useEffect(() => {                   // runs whenever the trades list changes
    const series = seriesRef.current;
    if (!series) return;
    let latest = null;
    for (const t of trades) {
      if (t.id <= lastIdRef.current) continue;            // already counted this trade
      lastIdRef.current = t.id;
      if (!loadedRef.current) continue;                   // history still loading: it already covers this trade

      const tradePrice = Number(t.price);
      const size = Number(t.size);
      const c = candleRef.current;
      const start = candleStart(toSeconds(t.time), c, periodRef.current);
      if (start === null) continue;

      if (c && start === c.time) {                        // same period: stretch the current candle
        c.high = Math.max(c.high, tradePrice);
        c.low = Math.min(c.low, tradePrice);
        c.close = tradePrice;
        c.volume = (c.volume ?? 0) + size;
      } else {                                            // new period: start a fresh candle
        candleRef.current = {
          time: start, open: tradePrice, high: tradePrice, low: tradePrice, close: tradePrice, volume: size,
        };
      }
      const candle = { ...candleRef.current };
      const bars = barsRef.current;
      if (bars.length && bars.at(-1).time === candle.time) bars[bars.length - 1] = candle;
      else bars.push(candle);
      series.update(toCandle(candle));                    // redraw just the latest candle...
      volumeRef.current.update(toVolume(candle));         // ...and its volume bar
      latest = t;
    }
    if (!latest) return;

    const side = latest.side === "BUY" ? "BUY" : "SELL";  // flash the live dot and price line in the trade's colour
    series.applyOptions({ priceLineColor: cssVar(side === "BUY" ? "--buy" : "--sell") });
    const dot = dotRef.current;
    if (dot) {
      dot.dataset.side = side;
      dot.classList.remove("pulse");
      void dot.offsetWidth;                               // restart the CSS animation even mid-pulse
      dot.classList.add("pulse");
    }
    if (!hoveringRef.current) setLegend({ ...candleRef.current });
  }, [trades]);

  useEffect(() => {                   // leave full screen with Esc, or when the browser exits full screen itself
    const onKey = (e) => { if (e.key === "Escape") setExpanded(false); };
    const onFullscreen = () => { if (!document.fullscreenElement) setExpanded(false); };
    window.addEventListener("keydown", onKey);
    document.addEventListener("fullscreenchange", onFullscreen);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.removeEventListener("fullscreenchange", onFullscreen);
    };
  }, []);

  useEffect(() => {                   // entering/leaving full screen
    document.body.style.overflow = expanded ? "hidden" : "";   // no page scrolling behind the full-screen chart
    const leaving = wasExpandedRef.current && !expanded;
    wasExpandedRef.current = expanded;
    if (!leaving) return;

    // After leaving full screen the browser shrinks the chart back over a few frames (longer on some
    // systems), so reset the zoom every time the chart's size changes during the next second, not just once.
    let frame;
    const reset = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => resetView(chartRef.current, seriesRef.current));
    };
    const observer = new ResizeObserver(reset);
    observer.observe(containerRef.current);
    reset();
    const stop = setTimeout(() => observer.disconnect(), 1000);
    return () => {
      clearTimeout(stop);
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [expanded]);

  const pickTimeframe = (key) => {
    setStatus("loading");                                 // show "Loading..." until the new history arrives
    setTimeframe(key);
  };

  const toggleExpanded = () => {
    if (!expanded) {
      setExpanded(true);                                  // CSS makes the card cover the window...
      cardRef.current.requestFullscreen?.().catch(() => {});   // ...and real full screen where the browser allows it
    } else {
      setExpanded(false);
      if (document.fullscreenElement) document.exitFullscreen();
    }
  };

  const tf = TIMEFRAMES.find((t) => t.key === timeframe);
  const change = legend ? legend.close - legend.open : 0;
  const direction = change >= 0 ? "buy" : "sell";         // green or red, like the candle itself

  return (
    <section ref={cardRef} className={`card chart-card ${expanded ? "expanded" : ""}`}>
      <div className="chart-toolbar">
        <span className="chart-symbol">
          <BitcoinLogo size={18} />
          BTC/USD
        </span>
        <span className="toolbar-divider" />
        <IntervalMenu value={timeframe} onChange={pickTimeframe} />
        <span className="toolbar-spacer" />
        <button
          type="button"
          className="tool-button"
          onClick={toggleExpanded}
          aria-label={expanded ? "Exit full screen" : "Full screen"}
          title={expanded ? "Exit full screen (Esc)" : "Full screen"}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5">
            {expanded
              ? <path d="M6 2v4H2M10 2v4h4M6 14v-4H2M10 14v-4h4" />
              : <path d="M2 6V2h4M14 6V2h-4M2 10v4h4M14 10v4h-4" />}
          </svg>
        </button>
      </div>

      <div className="chart-body">
        <div ref={containerRef} className="candle-chart" />

        {legend && (
          <div className="chart-legend">
            <span className="legend-title">BTC/USD · {tf.short} · Kraken</span>
            <span className={`legend-values ${direction}`}>
              <span><b>O</b>{price(legend.open)}</span>
              <span><b>H</b>{price(legend.high)}</span>
              <span><b>L</b>{price(legend.low)}</span>
              <span><b>C</b>{price(legend.close)}</span>
              <span>
                {change >= 0 ? "+" : "−"}{price(Math.abs(change))} ({change >= 0 ? "+" : "−"}
                {Math.abs((change / legend.open) * 100).toFixed(2)}%)
              </span>
            </span>
            <span className="legend-volume">Vol <span className={direction}>{amount(legend.volume ?? 0)} BTC</span></span>
          </div>
        )}

        <span ref={dotRef} className="live-dot" aria-hidden="true" />

        <div className="chart-pills">
          {!autoScale && (
            <button
              type="button"
              className="chart-pill"
              title="Fit the price axis to the candles again"
              onClick={() => seriesRef.current.priceScale().setAutoScale(true)}
            >
              Auto
            </button>
          )}
          {awayFromNow && (
            <button
              type="button"
              className="chart-pill"
              title="Scroll to the newest candle"
              onClick={() => chartRef.current.timeScale().scrollToRealTime()}
            >
              Latest ⇥
            </button>
          )}
        </div>

        {status !== "ready" && (
          <p className="chart-overlay muted small-text">
            {status === "loading" ? "Loading candles..." : "Couldn't load candles. Is the backend running?"}
          </p>
        )}
      </div>
    </section>
  );
}
