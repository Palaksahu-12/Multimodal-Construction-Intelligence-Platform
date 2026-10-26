import { useEffect, useState } from "react";
import { API_BASE_URL } from "./api";

const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

function useApiRequest() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  async function send(endpoint, body, isFormData = false) {
    setIsLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: "POST",
        headers: isFormData ? undefined : { "Content-Type": "application/json" },
        body: isFormData ? body : JSON.stringify(body),
      });
      let data;
      try {
        data = await response.json();
      } catch {
        throw new Error(
          response.ok
            ? "The backend returned an unreadable response."
            : `The backend request failed (HTTP ${response.status}).`
        );
      }
      if (!data || typeof data !== "object" || Array.isArray(data)) {
        throw new Error("The backend returned an invalid response.");
      }
      if (!response.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail.map((item) => item.msg).join("; ")
          : data.detail;
        throw new Error(
          typeof detail === "string" && detail
            ? detail
            : `The backend request failed (HTTP ${response.status}).`
        );
      }
      setResult(data);
      return data;
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not connect to the backend."
      );
      return null;
    } finally {
      setIsLoading(false);
    }
  }

  return { isLoading, error, result, send, setResult, setError };
}

function Field({ label, children, className = "" }) {
  return (
    <label className={`workflow-field ${className}`}>
      <span>{label}</span>
      {children}
    </label>
  );
}

function WorkflowPanel({ title, description, children }) {
  return (
    <section className="workflow-panel">
      <div className="section-heading">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

function OutputValue({ value }) {
  if (value === null || value === undefined || value === "") {
    return <span>Not provided</span>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <span>None reported</span>;
    if (typeof value[0] === "object" && value[0] !== null) {
      return (
        <div className="result-list">
          {value.map((item, index) => (
            <article className="result-list-item" key={index}>
              {Object.entries(item).map(([key, itemValue]) => (
                <p key={key}>
                  <strong>{formatLabel(key)}:</strong>{" "}
                  <OutputValue value={itemValue} />
                </p>
              ))}
            </article>
          ))}
        </div>
      );
    }
    return (
      <ul>
        {value.map((item, index) => (
          <li key={index}>{String(item)}</li>
        ))}
      </ul>
    );
  }
  if (typeof value === "object") {
    return (
      <dl className="result-definition-list">
        {Object.entries(value).map(([key, itemValue]) => (
          <div key={key}>
            <dt>{formatLabel(key)}</dt>
            <dd><OutputValue value={itemValue} /></dd>
          </div>
        ))}
      </dl>
    );
  }
  if (typeof value === "number") {
    return <span>{new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value)}</span>;
  }
  return <span>{String(value)}</span>;
}

function formatLabel(value) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function WorkflowResult({ title, data }) {
  if (!data) return null;
  const entries = Object.entries(data).filter(([key]) => key !== "status");
  return (
    <section className="workflow-result" aria-live="polite">
      <h3>{title}</h3>
      <dl className="result-definition-list">
        {entries.map(([key, value]) => (
          <div key={key}>
            <dt>{formatLabel(key)}</dt>
            <dd><OutputValue value={value} /></dd>
          </div>
        ))}
      </dl>
      <p className="decision-support-note">
        AI-supported information only; verify important decisions with qualified professionals.
      </p>
    </section>
  );
}

function WorkflowStatus({ busy, error }) {
  if (busy) {
    return <p className="upload-status loading" role="status">Working…</p>;
  }
  if (error) {
    return <p className="upload-status error" role="alert">{error}</p>;
  }
  return null;
}

export function ImageAnalysisPanel({ kind }) {
  const isCrack = kind === "crack";
  const request = useApiRequest();
  const [image, setImage] = useState(null);
  const [context, setContext] = useState("");
  const [validationError, setValidationError] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  function selectImage(event) {
    const file = event.target.files?.[0] || null;
    setImage(null);
    request.setError("");
    request.setResult(null);
    setValidationError("");
    setPreviewUrl("");
    if (!file) return;
    if (!IMAGE_TYPES.includes(file.type)) {
      setValidationError("Please choose a JPG, PNG, or WEBP image.");
      event.target.value = "";
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setValidationError("The image must be 10 MB or smaller.");
      event.target.value = "";
      return;
    }
    setImage(file);
    setPreviewUrl(URL.createObjectURL(file));
  }

  async function submit(event) {
    event.preventDefault();
    if (!image) {
      setValidationError("Select an image before submitting.");
      return;
    }
    const formData = new FormData();
    formData.append("image", image);
    if (context.trim()) formData.append("context", context.trim());
    await request.send(
      isCrack ? "/api/crack-analysis/analyze" : "/api/site-safety/analyze",
      formData,
      true
    );
  }

  return (
    <WorkflowPanel
      title={isCrack ? "Crack Detection" : "Site Safety Analysis"}
      description={
        isCrack
          ? "Review visible crack characteristics and possible next steps. Images cannot establish structural integrity."
          : "Review visible hazards and safety concerns. An incomplete view cannot establish that a site is safe."
      }
    >
      <form className="workflow-form" onSubmit={submit}>
        <label className="upload-dropzone">
          <span className="upload-symbol" aria-hidden="true">↑</span>
          <strong>{isCrack ? "Choose a building or concrete image" : "Choose a construction-site image"}</strong>
          <span>JPG, PNG or WEBP · Maximum 10 MB</span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            aria-label={isCrack ? "Select a crack analysis image" : "Select a site safety image"}
            disabled={request.isLoading}
            onChange={selectImage}
          />
        </label>
        {!image && !validationError && (
          <p className="form-note">No image selected. Choose a supported image to begin; no analysis is generated until you submit it.</p>
        )}
        {previewUrl && (
          <div className="image-preview">
            <img src={previewUrl} alt="Selected analysis preview" />
            <p>{image?.name}</p>
          </div>
        )}
        <Field label="Optional context">
          <textarea
            value={context}
            maxLength={1000}
            onChange={(event) => setContext(event.target.value)}
            placeholder="Describe what is visible or where the image was taken."
            rows={3}
          />
        </Field>
        {(validationError || request.error) && (
          <WorkflowStatus busy={false} error={validationError || request.error} />
        )}
        {request.isLoading && <WorkflowStatus busy />}
        <button className="primary-button action-button" type="submit" disabled={request.isLoading || !image}>
          {request.isLoading ? "Analyzing…" : isCrack ? "Analyze Visible Cracks →" : "Analyze Site Safety →"}
        </button>
      </form>
      <WorkflowResult
        title={isCrack ? "Crack Analysis" : "AI Safety Analysis"}
        data={request.result?.analysis}
      />
    </WorkflowPanel>
  );
}

export function ProjectPlanPanel() {
  const request = useApiRequest();
  const [form, setForm] = useState({
    project_type: "Residential",
    built_up_area_sqm: "100",
    location: "",
    floors: "1",
    budget_inr: "",
    target_timeline_days: "",
  });
  function update(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
  }
  async function submit(event) {
    event.preventDefault();
    await request.send("/api/project-plan", {
      ...form,
      built_up_area_sqm: Number(form.built_up_area_sqm),
      floors: Number(form.floors),
      budget_inr: form.budget_inr ? Number(form.budget_inr) : null,
      target_timeline_days: form.target_timeline_days
        ? Number(form.target_timeline_days)
        : null,
    });
  }
  return (
    <WorkflowPanel title="Construction Project Planning" description="Get a conceptual phase plan, broad resource quantities, and transparent cost assumptions.">
      <form className="workflow-form workflow-grid" onSubmit={submit}>
        <Field label="Project type">
          <select name="project_type" value={form.project_type} onChange={update}>
            <option>Residential</option><option>Commercial</option><option>Renovation</option>
          </select>
        </Field>
        <Field label="Built-up area (m²)">
          <input required type="number" min="1" max="100000" step="0.1" name="built_up_area_sqm" value={form.built_up_area_sqm} onChange={update} />
        </Field>
        <Field label="Location (optional)">
          <input name="location" maxLength="120" value={form.location} onChange={update} />
        </Field>
        <Field label="Number of floors">
          <input required type="number" min="1" max="100" name="floors" value={form.floors} onChange={update} />
        </Field>
        <Field label="Total budget in INR (optional)">
          <input type="number" min="1" max="10000000000" name="budget_inr" value={form.budget_inr} onChange={update} />
        </Field>
        <Field label="Target timeline in days (optional)">
          <input type="number" min="5" max="5000" name="target_timeline_days" value={form.target_timeline_days} onChange={update} />
        </Field>
        <p className="form-note">Without a budget, the plan uses an illustrative broad-area factor, not a current local quotation. Quantities are not a bill of materials.</p>
        <WorkflowStatus busy={request.isLoading} error={request.error} />
        <button className="primary-button action-button" type="submit" disabled={request.isLoading}>{request.isLoading ? "Building plan…" : "Generate Conceptual Plan →"}</button>
      </form>
      <WorkflowResult title="Indicative Project Plan" data={request.result} />
    </WorkflowPanel>
  );
}

export function PropertyValuationPanel() {
  const request = useApiRequest();
  const [form, setForm] = useState({
    city: "",
    locality: "",
    property_type: "Apartment",
    area_sqm: "",
    building_age_years: "0",
    condition: "Average",
    amenities: "",
    reference_price_per_sqm_inr: "",
    reference_monthly_rent_inr: "",
    investment_cost_inr: "",
  });
  function update(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
  }
  async function submit(event) {
    event.preventDefault();
    await request.send("/api/property-valuation", {
      ...form,
      area_sqm: Number(form.area_sqm),
      building_age_years: Number(form.building_age_years),
      amenities: form.amenities.split(",").map((item) => item.trim()).filter(Boolean),
      reference_price_per_sqm_inr: form.reference_price_per_sqm_inr
        ? Number(form.reference_price_per_sqm_inr)
        : null,
      reference_monthly_rent_inr: form.reference_monthly_rent_inr
        ? Number(form.reference_monthly_rent_inr)
        : null,
      investment_cost_inr: form.investment_cost_inr
        ? Number(form.investment_cost_inr)
        : null,
    });
  }
  return (
    <WorkflowPanel title="Indicative Property Valuation" description="Use a local reference price supplied by you; this tool does not fetch market comparables or current listings.">
      <form className="workflow-form workflow-grid" onSubmit={submit}>
        <Field label="City"><input required minLength="2" maxLength="100" name="city" value={form.city} onChange={update} /></Field>
        <Field label="Locality (optional)"><input maxLength="120" name="locality" value={form.locality} onChange={update} /></Field>
        <Field label="Property type"><select name="property_type" value={form.property_type} onChange={update}><option>Apartment</option><option>Independent house</option><option>Plot</option><option>Commercial</option></select></Field>
        <Field label={form.property_type === "Plot" ? "Plot area (m²)" : "Built-up area (m²)"}><input required type="number" min="0.1" max="100000" step="0.1" name="area_sqm" value={form.area_sqm} onChange={update} /></Field>
        {form.property_type !== "Plot" && (
          <>
            <Field label="Building age (years)"><input required type="number" min="0" max="150" name="building_age_years" value={form.building_age_years} onChange={update} /></Field>
            <Field label="Condition"><select name="condition" value={form.condition} onChange={update}><option>Poor</option><option>Average</option><option>Good</option></select></Field>
            <Field label="Amenities (comma-separated)"><input name="amenities" value={form.amenities} onChange={update} placeholder="Lift, parking" /></Field>
          </>
        )}
        <Field label="Local reference price (INR/m²)"><input type="number" min="1" name="reference_price_per_sqm_inr" value={form.reference_price_per_sqm_inr} onChange={update} placeholder="Required for numeric estimate" /></Field>
        <Field label="Reference monthly rent in INR (optional)"><input type="number" min="1" name="reference_monthly_rent_inr" value={form.reference_monthly_rent_inr} onChange={update} /></Field>
        <Field label="Investment cost in INR (optional)"><input type="number" min="1" name="investment_cost_inr" value={form.investment_cost_inr} onChange={update} /></Field>
        <p className="form-note">Without a user-provided local rate, the API returns no fabricated property-value range.</p>
        <WorkflowStatus busy={request.isLoading} error={request.error} />
        <button className="primary-button action-button" type="submit" disabled={request.isLoading}>{request.isLoading ? "Calculating…" : "Estimate Property Range →"}</button>
      </form>
      <WorkflowResult title="Indicative Property Estimate" data={request.result} />
    </WorkflowPanel>
  );
}

export function ChatPanel({ history, setHistory }) {
  const request = useApiRequest();
  const [message, setMessage] = useState("");
  async function submit(event) {
    event.preventDefault();
    const text = message.trim();
    if (!text) return;
    const response = await request.send("/api/chat", { message: text, history });
    if (response) {
      const caveats = response.caveats?.length
        ? `\n\nCaveats: ${response.caveats.join(" ")}`
        : "";
      setHistory(
        [...history, { role: "user", content: text }, { role: "assistant", content: `${response.reply}${caveats}` }].slice(-12)
      );
      setMessage("");
    }
  }
  return (
    <WorkflowPanel title="Construction Assistant" description="Ask general construction or real-estate questions. Responses do not include live research.">
      <div className="chat-history" aria-live="polite">
        {history.length === 0 && <p className="form-note">Your conversation will appear here. Recent turns are sent to the backend for context.</p>}
        {history.map((item, index) => <p className={`chat-message ${item.role}`} key={`${item.role}-${index}`}><strong>{item.role === "user" ? "You" : "Assistant"}:</strong> {item.content}</p>)}
      </div>
      <form className="workflow-form" onSubmit={submit}>
        <Field label="Your question"><textarea required minLength="1" maxLength="4000" rows={3} value={message} onChange={(event) => setMessage(event.target.value)} /></Field>
        <WorkflowStatus busy={request.isLoading} error={request.error} />
        <button className="primary-button action-button" type="submit" disabled={request.isLoading || !message.trim()}>{request.isLoading ? "Thinking…" : "Send Question →"}</button>
      </form>
      {history.length > 0 && <p className="decision-support-note">General AI guidance; verify high-impact decisions with a qualified professional.</p>}
    </WorkflowPanel>
  );
}

export function DailyAssistantPanel() {
  const request = useApiRequest();
  const [form, setForm] = useState({
    site_update: "",
    planned_activities: "",
    workforce_available: "",
    materials_and_equipment: "",
    constraints: "",
  });
  function update(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
  }
  function splitLines(value) {
    return value.split(/\n|,/).map((item) => item.trim()).filter(Boolean);
  }
  async function submit(event) {
    event.preventDefault();
    await request.send("/api/daily-site-assistant", {
      site_update: form.site_update,
      planned_activities: splitLines(form.planned_activities),
      workforce_available: form.workforce_available ? Number(form.workforce_available) : null,
      materials_and_equipment: splitLines(form.materials_and_equipment),
      constraints: splitLines(form.constraints),
    });
  }
  return (
    <WorkflowPanel title="Daily Site Assistant" description="Turn your own site report into an organized summary and proposed next actions.">
      <form className="workflow-form workflow-grid" onSubmit={submit}>
        <Field label="Reported site update" className="field-wide"><textarea required minLength="1" maxLength="5000" rows={4} name="site_update" value={form.site_update} onChange={update} placeholder="Enter observed progress, issues, or other actual site facts." /></Field>
        <Field label="Planned activities (comma-separated)"><textarea rows={3} name="planned_activities" value={form.planned_activities} onChange={update} /></Field>
        <Field label="Materials and equipment (comma-separated)"><textarea rows={3} name="materials_and_equipment" value={form.materials_and_equipment} onChange={update} /></Field>
        <Field label="Available workforce (optional)"><input type="number" min="0" max="10000" name="workforce_available" value={form.workforce_available} onChange={update} /></Field>
        <Field label="Constraints or risks (comma-separated)"><textarea rows={3} name="constraints" value={form.constraints} onChange={update} /></Field>
        <p className="form-note">The assistant is instructed not to invent work completed or events not included in your update.</p>
        <WorkflowStatus busy={request.isLoading} error={request.error} />
        <button className="primary-button action-button" type="submit" disabled={request.isLoading}>{request.isLoading ? "Preparing summary…" : "Prepare Daily Summary →"}</button>
      </form>
      <WorkflowResult title="Daily Site Summary" data={request.result} />
    </WorkflowPanel>
  );
}

export function WeatherPanel() {
  const request = useApiRequest();
  const [form, setForm] = useState({
    activity: "",
    location: "",
    condition_description: "",
    precipitation_mm_per_hour: "",
    wind_speed_kmh: "",
    temperature_c: "",
  });
  function update(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
  }
  async function submit(event) {
    event.preventDefault();
    await request.send("/api/weather-advisory", {
      activity: form.activity,
      location: form.location || null,
      condition_description: form.condition_description || null,
      precipitation_mm_per_hour: form.precipitation_mm_per_hour === "" ? null : Number(form.precipitation_mm_per_hour),
      wind_speed_kmh: form.wind_speed_kmh === "" ? null : Number(form.wind_speed_kmh),
      temperature_c: form.temperature_c === "" ? null : Number(form.temperature_c),
    });
  }
  return (
    <WorkflowPanel title="Weather-Aware Advisory" description="No live weather provider is configured. Enter observations from a trusted source; they will be labeled unverified.">
      <form className="workflow-form workflow-grid" onSubmit={submit}>
        <Field label="Planned activity"><input required minLength="2" maxLength="200" name="activity" value={form.activity} onChange={update} placeholder="e.g. exterior concrete pour" /></Field>
        <Field label="Location (optional)"><input maxLength="120" name="location" value={form.location} onChange={update} /></Field>
        <Field label="Conditions description (optional)"><textarea maxLength="1000" rows={3} name="condition_description" value={form.condition_description} onChange={update} placeholder="Conditions observed or forecast by you." /></Field>
        <Field label="Precipitation (mm/hour)"><input type="number" min="0" max="1000" step="0.1" name="precipitation_mm_per_hour" value={form.precipitation_mm_per_hour} onChange={update} /></Field>
        <Field label="Wind speed (km/h)"><input type="number" min="0" max="500" step="0.1" name="wind_speed_kmh" value={form.wind_speed_kmh} onChange={update} /></Field>
        <Field label="Temperature (°C)"><input type="number" min="-80" max="70" step="0.1" name="temperature_c" value={form.temperature_c} onChange={update} /></Field>
        <WorkflowStatus busy={request.isLoading} error={request.error} />
        <button className="primary-button action-button" type="submit" disabled={request.isLoading}>{request.isLoading ? "Reviewing conditions…" : "Generate Weather Advisory →"}</button>
      </form>
      <WorkflowResult title="Weather Advisory" data={request.result} />
    </WorkflowPanel>
  );
}
