import { BrowserRouter, NavLink, Route, Routes } from "react-router";
import BitcoinLogo from "./components/BitcoinLogo";
import MarketPage from "./pages/MarketPage";
import PortfolioPage from "./pages/PortfolioPage";
import "./App.css";

// The app shell: header with the Portfolio / Market tabs, and whichever page the address points to.
export default function App() {
  return (
    <BrowserRouter>
      <main className="app">
        <header className="app-header">
          <BitcoinLogo size={36} />
          <div>
            <h1>Trading</h1>
            <p className="subtitle">paper trading · live prices via Alpaca</p>
          </div>
          <nav className="tabs" aria-label="Main">
            <NavLink to="/" end className={({ isActive }) => `tab ${isActive ? "active" : ""}`}>Portfolio</NavLink>
            <NavLink to="/market" className={({ isActive }) => `tab ${isActive ? "active" : ""}`}>Market</NavLink>
          </nav>
        </header>

        <Routes>
          <Route path="/" element={<PortfolioPage />} />
          <Route path="/market" element={<MarketPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
