// Every interval the chart offers, grouped like TradingView's interval menu.
// "key" is what the backend expects (TIMEFRAMES in main.py), "short" is what the toolbar shows.
export const TIMEFRAMES = [
  { key: "1m", short: "1m", label: "1 minute", group: "Minutes", seconds: 60 },
  { key: "5m", short: "5m", label: "5 minutes", group: "Minutes", seconds: 5 * 60 },
  { key: "10m", short: "10m", label: "10 minutes", group: "Minutes", seconds: 10 * 60 },
  { key: "30m", short: "30m", label: "30 minutes", group: "Minutes", seconds: 30 * 60 },
  { key: "1h", short: "1h", label: "1 hour", group: "Hours", seconds: 60 * 60 },
  { key: "4h", short: "4h", label: "4 hours", group: "Hours", seconds: 4 * 60 * 60 },
  { key: "1d", short: "D", label: "1 day", group: "Days", seconds: 24 * 60 * 60 },
  { key: "1w", short: "W", label: "1 week", group: "Days", seconds: 7 * 24 * 60 * 60 },
];
