import { useState, useRef, useEffect, useCallback } from "react";

export default function ViewImpl() {
  const fileInputRef = useRef(null);
  const [fileName, setFileName] = useState(null);
  const [data, setData] = useState(null); // { leds, rows: [{ colors: [0xRRGGBB,...], delay }] }
  const [version, setVersion] = useState("V0");

  async function handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;
    setFileName(file.name);
    const buf = await file.arrayBuffer();

    // Try sending file to /view API first. If API returns JSON with leds/rows, use it.
    try {
      const resp = await fetch('/api/pattern-generator/view/'+version, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/octet-stream',
          'X-Pattern-Version': version,
        },
        body: buf,
      });
      if (resp.ok) {
        const text = await resp.text();
        try {
          const json = JSON.parse(text);
          if (json && typeof json.leds === 'number' && Array.isArray(json.rows)) {
            setData(json);
            return;
          }
        } catch (err) {
          // not JSON, continue to local parsing
        }
      }
    } catch (err) {
      // network error - continue to local parsing
    }
  }

  return (
    <div style={{ fontFamily: "sans-serif", padding: "2rem" }}>
      <a href="/" style={{ marginRight: "0.75rem", fontSize: 14, color: "#0366d6", textDecoration: "none" }}>Generator</a>
      <a href="/view">View</a><p/>
      <input
        ref={fileInputRef}
        type="file"
        accept=".bin"
        onChange={handleFileSelect}
        style={{ display: "none" }}
      />
      <div style={{ display: "inline-block", marginRight: "0.5rem" }}>
        <select value={version} onChange={(e) => setVersion(e.target.value)} style={{ padding: 6, fontSize: 13 }}>
          <option value="V0">V0</option>
          <option value="V1">V1</option>
          <option value="V2">V2</option>
          <option value="V3">V3</option>
          <option value="V4">V4</option>
        </select>
      </div>
      <button onClick={() => fileInputRef.current.click()}>Open File</button>
      {fileName && <span style={{ marginLeft: "0.5rem" }}>{fileName}</span>}
      {data && (
        <div style={{ marginTop: "1rem" }}>
          <div style={{ marginBottom: "0.5rem", fontSize: 13 }}>LEDs: {data.leds} | Rows: {data.rows.length}</div>
          {data.rows.map((row, ri) => (
            <div key={ri} style={{ display: "flex", gap: 2, flexWrap: "wrap", marginTop: 4, padding: 4, border: "1px solid #ddd", borderRadius: 4, alignItems: "center" }}>
              {row.colors.map((c, ci) => {
                const hex = "#" + c.toString(16).padStart(6, "0");
                return (
                  <span
                    key={ci}
                    style={{
                      background: hex,
                      color: c > 0x808080 ? "black" : "white",
                      padding: "4px 6px",
                      borderRadius: 3,
                      fontSize: 11,
                      fontWeight: "bold",
                      display: "inline-block",
                    }}
                  >
                    {ci + 1}
                  </span>
                );
              })}
              <span style={{ marginLeft: "auto", fontSize: 12 }}>delay: {row.delay}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}