import { useState } from "react";
import "./App.css";
import { API_BASE_URL } from "./api";
import {
  ChatPanel,
  DailyAssistantPanel,
  ImageAnalysisPanel,
  ProjectPlanPanel,
  PropertyValuationPanel,
  WeatherPanel,
} from "./Workflows";

const features = [
  {
    number: "01",
    title: "Site Safety Analysis",
    description: "Inspect construction images for visible safety hazards.",
    icon: "🦺",
    color: "blue",
    tab: "Site Analysis",
  },
  {
    number: "02",
    title: "Crack Detection",
    description: "Review visible crack characteristics and limitations.",
    icon: "🔎",
    color: "orange",
    tab: "Crack Detection",
  },
  {
    number: "03",
    title: "Project Planning",
    description: "Estimate conceptual phases, materials and costs.",
    icon: "🧱",
    color: "green",
    tab: "Project Planning",
  },
  {
    number: "04",
    title: "Property Valuation",
    description: "Calculate an indicative INR range using a local reference rate.",
    icon: "₹",
    color: "purple",
    tab: "Property Valuation",
  },
  {
    number: "05",
    title: "Construction Assistant",
    description: "Ask construction and real-estate questions.",
    icon: "✧",
    color: "pink",
    tab: "AI Assistant",
  },
  {
    number: "06",
    title: "Daily Site Assistant",
    description: "Organize a site report into proposed next actions and risks.",
    icon: "✓",
    color: "green",
    tab: "Daily Site Assistant",
  },
  {
    number: "07",
    title: "Weather Advisory",
    description: "Review user-provided conditions without fabricated forecasts.",
    icon: "🌦️",
    color: "cyan",
    tab: "Weather Advisory",
  },
];

const navigation = [
  ["Overview", "▦"],
  ["Site Analysis", "⌕"],
  ["Crack Detection", "◌"],
  ["Project Planning", "▤"],
  ["Property Valuation", "₹"],
  ["AI Assistant", "✧"],
  ["Daily Site Assistant", "✓"],
  ["Weather Advisory", "☼"],
];

function Overview({ setActiveTab }) {
  return (
    <>
      <section className="welcome-section">
        <div>
          <span className="eyebrow">SMART CONSTRUCTION MANAGEMENT</span>
          <h2>Build smarter. Plan better.</h2>
          <p>
            Analyze site images, estimate materials, plan costs and make
            informed construction decisions.
          </p>
          <button className="primary-button" onClick={() => setActiveTab("Site Analysis")}>
            Start Site Analysis <span>→</span>
          </button>
        </div>
        <div className="welcome-art" aria-hidden="true">
          <div className="art-circle circle-one" />
          <div className="art-circle circle-two" />
          <div className="building building-back" />
          <div className="building building-front"><div className="building-windows" /></div>
          <div className="art-ground" />
          <span className="art-spark spark-one">✦</span>
          <span className="art-spark spark-two">✧</span>
        </div>
      </section>
      <section className="section-heading">
        <div>
          <h2>Project Overview</h2>
          <p>Your construction intelligence tools in one place.</p>
        </div>
        <span className="live-label"><span className="live-dot" /> Workspace ready</span>
      </section>
      <section className="feature-grid">
        {features.map((feature) => (
          <article className="feature-card" key={feature.number}>
            <div className={`feature-icon ${feature.color}`}>{feature.icon}</div>
            <span className="feature-number">{feature.number}</span>
            <h3>{feature.title}</h3>
            <p>{feature.description}</p>
            <button className="text-button" onClick={() => setActiveTab(feature.tab)}>
              Open module <span>→</span>
            </button>
          </article>
        ))}
      </section>
    </>
  );
}

function App() {
  const [activeTab, setActiveTab] = useState("Overview");
  const [apiStatus, setApiStatus] = useState("Not checked");
  const [chatHistory, setChatHistory] = useState([]);

  async function checkBackend() {
    setApiStatus("Checking...");
    try {
      const response = await fetch(`${API_BASE_URL}/health`);
      if (!response.ok) throw new Error("API request failed");
      const data = await response.json();
      setApiStatus(data.status === "healthy" ? "Connected" : "Unavailable");
    } catch {
      setApiStatus("Connection failed");
    }
  }

  function renderActiveModule() {
    switch (activeTab) {
      case "Site Analysis":
        return <ImageAnalysisPanel kind="safety" />;
      case "Crack Detection":
        return <ImageAnalysisPanel kind="crack" />;
      case "Project Planning":
        return <ProjectPlanPanel />;
      case "Property Valuation":
        return <PropertyValuationPanel />;
      case "AI Assistant":
        return <ChatPanel history={chatHistory} setHistory={setChatHistory} />;
      case "Daily Site Assistant":
        return <DailyAssistantPanel />;
      case "Weather Advisory":
        return <WeatherPanel />;
      default:
        return <Overview setActiveTab={setActiveTab} />;
    }
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">C</div>
          <div>
            <h2>ConstructAI</h2>
            <span>Intelligence Platform</span>
          </div>
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav aria-label="Main navigation">
          {navigation.map(([item, icon]) => (
            <button
              key={item}
              className={`nav-item ${activeTab === item ? "active" : ""}`}
              aria-current={activeTab === item ? "page" : undefined}
              onClick={() => setActiveTab(item)}
            >
              <span className="nav-icon" aria-hidden="true">{icon}</span>
              {item}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="status-dot" />
          <span>Construction Intelligence</span>
          <small>v1.0</small>
        </div>
      </aside>

      <main className="main-content" id="main-content">
        <header className="topbar">
          <div>
            <p className="breadcrumb">Workspace / {activeTab}</p>
            <h1>{activeTab}</h1>
          </div>
          <div className="profile">
            <div className="profile-avatar">P</div>
            <div>
              <strong>Project Workspace</strong>
              <span>Construction Intelligence</span>
            </div>
          </div>
        </header>

        {renderActiveModule()}

        <section className="connection-panel">
          <div>
            <span className="connection-icon">⌘</span>
            <div>
              <h3>Backend API Connection</h3>
              <p>Check whether your FastAPI server is responding.</p>
            </div>
          </div>
          <div className="connection-actions">
            <span className={`api-status ${apiStatus === "Connected" ? "connected" : ""}`}>
              <span className="live-dot" /> {apiStatus}
            </span>
            <button className="secondary-button" onClick={checkBackend}>
              Test connection
            </button>
          </div>
        </section>
        <footer>
          <span>ConstructAI · Multimodal Construction Intelligence Platform</span>
          <span>AI outputs are decision support, not certified assessments</span>
        </footer>
      </main>
    </div>
  );
}

export default App;
