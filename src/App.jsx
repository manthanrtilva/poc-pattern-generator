import { useState, useRef, useEffect, useCallback } from "react";

export default function App() {
  const [masters, setMasters] = useState([]);
  const [slaves, setSlaves] = useState([]);
  const [connections, setConnections] = useState([]); // { fromType, fromIndex, toType, toIndex }
  const [selected, setSelected] = useState(null); // { type: "master"|"slave", index }
  const [contextMenu, setContextMenu] = useState(null); // { x, y, type, index }
  const [rows, setRows] = useState([]); // each row: { items: [{ label, type, color }] }
  const [selectedBoxes, setSelectedBoxes] = useState(new Set()); // Set of "ri-i-ci" keys
  const mastersRef = useRef(masters);
  const slavesRef = useRef(slaves);
  const selectedRef = useRef(selected);
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const [canvasWidth, setCanvasWidth] = useState(800);
  const dragRef = useRef(null);
  const didDragRef = useRef(false);

  useEffect(() => { mastersRef.current = masters; }, [masters]);
  useEffect(() => { slavesRef.current = slaves; }, [slaves]);
  useEffect(() => { selectedRef.current = selected; }, [selected]);

  useEffect(() => {
    function updateWidth() {
      if (containerRef.current) {
        setCanvasWidth(containerRef.current.clientWidth);
      }
    }
    updateWidth();
    window.addEventListener("resize", updateWidth);
    return () => window.removeEventListener("resize", updateWidth);
  }, []);

  function clearAll() {
    setMasters([]);
    setSlaves([]);
    setConnections([]);
    setSelected(null);
    setContextMenu(null);
    setRows([]);
  }

  // Layout constants for groups (1 master + 5 slaves)
  const NODE_W = 60;
  const NODE_H = 30;
  const NODE_GAP = 5;
  const GROUP_WIDTH = NODE_W + NODE_GAP + 5 * (NODE_W + NODE_GAP); // master + 5 slaves
  const GROUP_GAP = 20;
  const GROUP_STRIDE = GROUP_WIDTH + GROUP_GAP;
  const LEFT_MARGIN = 10;

  function getGroupsPerRow() {
    return Math.max(1, Math.floor((canvasWidth - LEFT_MARGIN + GROUP_GAP) / GROUP_STRIDE));
  }

  function addMaster() {
    const masterCount = masters.length;
    const groupsPerRow = getGroupsPerRow();
    const col = masterCount % groupsPerRow;
    const row = Math.floor(masterCount / groupsPerRow);
    setMasters((prev) => [
      ...prev,
      {
        x: LEFT_MARGIN + col * GROUP_STRIDE,
        y: 20 + row * 50,
        w: NODE_W,
        h: NODE_H,
        label: `M${masterCount + 1}`,
      },
    ]);
  }

  function addSlave() {
    const slaveCount = slaves.length;
    let x, y;
    if (slaveCount > 0) {
      const last = slaves[slaveCount - 1];
      x = last.x + NODE_W + NODE_GAP;
      y = last.y;
    } else {
      const groupIndex = 0;
      const groupsPerRow = getGroupsPerRow();
      const col = groupIndex % groupsPerRow;
      const row = Math.floor(groupIndex / groupsPerRow);
      x = LEFT_MARGIN + col * GROUP_STRIDE + NODE_W + NODE_GAP;
      y = 20 + row * 50;
    }
    setSlaves((prev) => [
      ...prev,
      {
        x,
        y,
        w: NODE_W,
        h: NODE_H,
        label: `S${slaveCount + 1}`,
      },
    ]);
  }

  function buildBinary() {
    const leds = rows.length > 0 ? rows[0].items.length * 8 : 0;
    const payload = {
      leds,
      rows: rows.map((row) => ({
        colors: row.items.flatMap((item) =>
          item.colors.map((hex) => {
            const r = parseInt(hex.slice(1, 3), 16);
            const g = parseInt(hex.slice(3, 5), 16);
            const b = parseInt(hex.slice(5, 7), 16);
            return (r << 16) | (g << 8) | b;
          })
        ),
        delay: row.value,
      })),
    };
    fetch("/api/pattern-generator", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then((res) => res.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "pattern.bin";
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch((err) => console.error("BuildBinary error:", err));
  }
function addRow() {
    // Build ordered items by following connections
    const items = [];
    const visited = { master: new Set(), slave: new Set() };

    function addItem(type, index) {
      if (visited[type].has(index)) return;
      visited[type].add(index);
      const node = type === "master" ? masters[index] : slaves[index];
      if (!node) return;
      const defaultColor = type === "master" ? "#ff0000" : "#0000ff";
      items.push({
        label: node.label,
        type,
        colors: Array(8).fill(defaultColor),
      });
      // Follow outgoing connections in order
      for (const c of connections) {
        if (c.fromType === type && c.fromIndex === index) {
          addItem(c.toType, c.toIndex);
        }
      }
    }

    // Start from nodes that are connection sources (roots first)
    const hasIncoming = { master: new Set(), slave: new Set() };
    for (const c of connections) {
      hasIncoming[c.toType].add(c.toIndex);
    }

    // Add connected roots (no incoming) first
    for (const c of connections) {
      if (!hasIncoming[c.fromType].has(c.fromIndex)) {
        addItem(c.fromType, c.fromIndex);
      }
    }
    // Then any remaining connected nodes
    for (const c of connections) {
      addItem(c.fromType, c.fromIndex);
      addItem(c.toType, c.toIndex);
    }
    // Finally add any unconnected nodes
    masters.forEach((_, i) => { if (!visited.master.has(i)) items.push({ label: masters[i].label, type: "master", colors: Array(8).fill("#ff0000") }); });
    slaves.forEach((_, i) => { if (!visited.slave.has(i)) items.push({ label: slaves[i].label, type: "slave", colors: Array(8).fill("#0000ff") }); });

    setRows((prev) => [...prev, { items, value: 1000 }]);
  }

  function deleteNode(type, index) {
    const setter = type === "master" ? setMasters : setSlaves;
    setter((prev) => prev.filter((_, i) => i !== index));
    setConnections((prev) =>
      prev
        .filter((c) => !(c.fromType === type && c.fromIndex === index) && !(c.toType === type && c.toIndex === index))
        .map((c) => ({
          ...c,
          fromIndex: c.fromType === type && c.fromIndex > index ? c.fromIndex - 1 : c.fromIndex,
          toIndex: c.toType === type && c.toIndex > index ? c.toIndex - 1 : c.toIndex,
        }))
    );
    setSelected(null);
    setContextMenu(null);
  }

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw connections
    for (const c of connections) {
      const fromItems = c.fromType === "master" ? masters : slaves;
      const toItems = c.toType === "master" ? masters : slaves;
      const from = fromItems[c.fromIndex];
      const to = toItems[c.toIndex];
      if (!from || !to) continue;
      ctx.strokeStyle = "#333";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(from.x + from.w / 2, from.y + from.h);
      ctx.lineTo(to.x + to.w / 2, to.y);
      ctx.stroke();
    }

    // Draw masters
    for (let i = 0; i < masters.length; i++) {
      const m = masters[i];
      const isSelected = selected?.type === "master" && selected?.index === i;
      ctx.fillStyle = isSelected ? "#cc0000" : "red";
      ctx.fillRect(m.x, m.y, m.w, m.h);
      if (isSelected) {
        ctx.strokeStyle = "yellow";
        ctx.lineWidth = 3;
        ctx.strokeRect(m.x, m.y, m.w, m.h);
      }
      ctx.fillStyle = "white";
      ctx.font = "bold 11px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(m.label, m.x + m.w / 2, m.y + m.h / 2);
    }

    // Draw slaves
    for (let i = 0; i < slaves.length; i++) {
      const s = slaves[i];
      const isSelected = selected?.type === "slave" && selected?.index === i;
      ctx.fillStyle = isSelected ? "#0000aa" : "blue";
      ctx.fillRect(s.x, s.y, s.w, s.h);
      if (isSelected) {
        ctx.strokeStyle = "yellow";
        ctx.lineWidth = 3;
        ctx.strokeRect(s.x, s.y, s.w, s.h);
      }
      ctx.fillStyle = "white";
      ctx.font = "bold 11px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(s.label, s.x + s.w / 2, s.y + s.h / 2);
    }
  }, [masters, slaves, connections, selected]);

  useEffect(() => {
    draw();
  }, [draw]);

  function getMousePos(e) {
    const rect = canvasRef.current.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  function hitTest(x, y, items) {
    for (let i = items.length - 1; i >= 0; i--) {
      const r = items[i];
      if (x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h) return i;
    }
    return -1;
  }

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    function onMouseDown(e) {
      didDragRef.current = false;
      const { x, y } = getMousePos(e);

      const si = hitTest(x, y, slavesRef.current);
      if (si >= 0) {
        dragRef.current = { type: "slave", index: si, offsetX: x - slavesRef.current[si].x, offsetY: y - slavesRef.current[si].y };
        canvas.style.cursor = "grabbing";
        return;
      }
      const mi = hitTest(x, y, mastersRef.current);
      if (mi >= 0) {
        dragRef.current = { type: "master", index: mi, offsetX: x - mastersRef.current[mi].x, offsetY: y - mastersRef.current[mi].y };
        canvas.style.cursor = "grabbing";
        return;
      }
    }

    function onMouseMove(e) {
      if (!dragRef.current) return;
      didDragRef.current = true;
      const { x, y } = getMousePos(e);
      const { type, index, offsetX, offsetY } = dragRef.current;
      const setter = type === "master" ? setMasters : setSlaves;
      setter((prev) =>
        prev.map((m, i) =>
          i === index ? { ...m, x: x - offsetX, y: y - offsetY } : m
        )
      );
    }

    function onMouseUp(e) {
      const wasDrag = didDragRef.current;
      const drag = dragRef.current;
      dragRef.current = null;
      canvas.style.cursor = "default";

      if (wasDrag) return;

      // Click (no drag) — handle selection/connection
      const { x, y } = getMousePos(e);
      const mi = hitTest(x, y, mastersRef.current);
      const si = hitTest(x, y, slavesRef.current);
      const sel = selectedRef.current;

      if (mi >= 0) {
        if (sel && !(sel.type === "master" && sel.index === mi)) {
          // Connect selected → this master
          setConnections((prev) => [
            ...prev,
            { fromType: sel.type, fromIndex: sel.index, toType: "master", toIndex: mi },
          ]);
          setSelected(null);
        } else {
          setSelected({ type: "master", index: mi });
        }
        return;
      }

      if (si >= 0) {
        if (sel && !(sel.type === "slave" && sel.index === si)) {
          // Connect selected → this slave
          setConnections((prev) => [
            ...prev,
            { fromType: sel.type, fromIndex: sel.index, toType: "slave", toIndex: si },
          ]);
          setSelected(null);
        } else {
          setSelected({ type: "slave", index: si });
        }
        return;
      }

      // Clicked empty space — deselect
      setSelected(null);
    }

    function onContextMenu(e) {
      e.preventDefault();
      const { x, y } = getMousePos(e);

      const si = hitTest(x, y, slavesRef.current);
      if (si >= 0) {
        setContextMenu({ x: e.clientX, y: e.clientY, type: "slave", index: si });
        return;
      }

      const mi = hitTest(x, y, mastersRef.current);
      if (mi >= 0) {
        setContextMenu({ x: e.clientX, y: e.clientY, type: "master", index: mi });
        return;
      }

      setContextMenu(null);
    }

    canvas.addEventListener("mousedown", onMouseDown);
    canvas.addEventListener("mousemove", onMouseMove);
    canvas.addEventListener("mouseup", onMouseUp);
    canvas.addEventListener("contextmenu", onContextMenu);
    canvas.addEventListener("mouseleave", () => {
      dragRef.current = null;
      canvas.style.cursor = "default";
    });

    return () => {
      canvas.removeEventListener("mousedown", onMouseDown);
      canvas.removeEventListener("mousemove", onMouseMove);
      canvas.removeEventListener("mouseup", onMouseUp);
      canvas.removeEventListener("contextmenu", onContextMenu);
    };
  }, []);

  return (
    <div ref={containerRef} style={{ fontFamily: "sans-serif", padding: "2rem" }} onClick={() => setContextMenu(null)}>
      <h1>Pattern Generator</h1>
      <button onClick={clearAll}>Clear</button>
      <button onClick={addMaster}>AddMaster</button>
      <button onClick={addSlave}>AddSlave</button>
      <button onClick={addRow}>AddRow</button>
      <button onClick={buildBinary}>BuildBinary</button>
      {selected !== null && (
        <span style={{ marginLeft: "1rem", color: "#cc0000" }}>
          Click another node to connect with {
            selected.type === "master"
              ? masters[selected.index]?.label
              : slaves[selected.index]?.label
          }
        </span>
      )}
      <canvas
        ref={canvasRef}
        width={canvasWidth}
        height={300}
        style={{ border: "1px solid #ccc", display: "block", marginTop: "1rem", cursor: "default", width: "100%" }}
      />
      {contextMenu && (
        <div
          style={{
            position: "fixed",
            top: contextMenu.y,
            left: contextMenu.x,
            background: "#fff",
            border: "1px solid #ccc",
            borderRadius: 4,
            boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
            zIndex: 1000,
          }}
        >
          <div
            style={{ padding: "8px 16px", cursor: "pointer" }}
            onMouseEnter={(e) => (e.target.style.background = "#eee")}
            onMouseLeave={(e) => (e.target.style.background = "#fff")}
            onClick={(e) => {
              e.stopPropagation();
              deleteNode(contextMenu.type, contextMenu.index);
            }}
          >
            Delete {contextMenu.type === "master"
              ? masters[contextMenu.index]?.label
              : slaves[contextMenu.index]?.label}
          </div>
        </div>
      )}
      {rows.map((row, ri) => (
        <div key={ri} onClick={() => setSelectedBoxes(new Set())} style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: "0.5rem", padding: "6px", border: "1px solid #ddd", borderRadius: 4, alignItems: "center" }}>
          {row.items.map((item, i) => (
            <span key={i} style={{ display: "inline-flex", gap: 1, marginRight: 4 }}>
              {item.colors.map((color, ci) => {
                const boxKey = `${ri}-${i}-${ci}`;
                const isBoxSelected = selectedBoxes.has(boxKey);
                return (
                  <label
                    key={ci}
                    style={{ display: "inline-block", outline: isBoxSelected ? "2px solid yellow" : "none", outlineOffset: 1, borderRadius: 3, cursor: "pointer", position: "relative" }}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (e.shiftKey) {
                        e.preventDefault();
                        setSelectedBoxes((prev) => {
                          const next = new Set(prev);
                          if (next.has(boxKey)) next.delete(boxKey); else next.add(boxKey);
                          return next;
                        });
                      }
                    }}
                  >
                    <span style={{ background: color, color: color === "#ffffff" ? "black" : "white", padding: "4px 6px", borderRadius: 3, fontSize: 11, fontWeight: "bold", display: "inline-block" }}>{item.label}.{ci + 1}</span>
                    <input
                      type="color"
                      value={color}
                      onClick={(e) => { if (e.shiftKey) e.preventDefault(); }}
                      onInput={(e) => {
                        const newColor = e.target.value;
                        if (selectedBoxes.size > 0) {
                          setRows((prev) => prev.map((r, rIdx) => ({
                            ...r,
                            items: r.items.map((it, iIdx) => ({
                              ...it,
                              colors: it.colors.map((c, cIdx) => selectedBoxes.has(`${rIdx}-${iIdx}-${cIdx}`) ? newColor : c),
                            })),
                          })));
                        } else {
                          setRows((prev) => prev.map((r, rIdx) =>
                            rIdx === ri ? { ...r, items: r.items.map((it, iIdx) => iIdx === i ? { ...it, colors: it.colors.map((c, cIdx) => cIdx === ci ? newColor : c) } : it) } : r
                          ));
                        }
                      }}
                      onChange={() => setSelectedBoxes(new Set())}
                      style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", opacity: 0, cursor: "pointer" }}
                    />
                  </label>
                );
              })}
            </span>
          ))}
          <select
            value={row.value}
            onChange={(e) => {
              const newVal = Number(e.target.value);
              setRows((prev) => prev.map((r, rIdx) => rIdx === ri ? { ...r, value: newVal } : r));
            }}
            style={{ marginLeft: "auto", fontSize: 12, padding: "2px 4px" }}
          >
            {Array.from({ length: 2001 }, (_, v) => (
              <option key={v} value={v}>{v}</option>
            ))}
          </select>
        </div>
      ))}
    </div>
  );
}
