/* QuantumBio-LocalMoE molecule builder.
 * Lightweight, self-contained 2-D molecule sketchpad for bioengineering:
 * CHNOPS atoms, single/double/triple bonds, Hill-notation formula,
 * approximate molar mass, and LLM analysis that feeds the report exporter.
 */
(function () {
  "use strict";

  var ATOMS = {
    C: { m: 12.011, color: "#94a3b8", text: "#0f172a" },
    H: { m: 1.008, color: "#e2e8f0", text: "#0f172a" },
    N: { m: 14.007, color: "#3b82f6", text: "#fff" },
    O: { m: 15.999, color: "#ef4444", text: "#fff" },
    P: { m: 30.974, color: "#f59e0b", text: "#0f172a" },
    S: { m: 32.06, color: "#eab308", text: "#0f172a" }
  };
  var RADIUS = 17;

  function MoleculeBuilder(canvas, summaryEl) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.summaryEl = summaryEl;
    this.nodes = [];
    this.edges = [];
    this.nextId = 1;
    this.selA = null;
    this.selB = null;
    this.dragId = null;
    this.bondOrder = 1;
    this.dirty = true;
    this._attach();
    this.redraw();
  }

  MoleculeBuilder.prototype._attach = function () {
    var self = this;
    this.canvas.addEventListener("mousedown", function (e) { self.onMouseDown(e); });
    this.canvas.addEventListener("mousemove", function (e) { self.onMouseMove(e); });
    this.canvas.addEventListener("mouseup", function () { self.onMouseUp(); });
    this.canvas.addEventListener("mouseleave", function () { self.dragging = false; });
    this.canvas.addEventListener("dblclick", function (e) {
      var hit = self._hit(e);
      if (hit != null) self._cycleBondOrderOn(hit);
    });
  };

  MoleculeBuilder.prototype._pos = function (e) {
    var rect = this.canvas.getBoundingClientRect();
    var scaleX = this.canvas.width / Math.max(rect.width, 1);
    var scaleY = this.canvas.height / Math.max(rect.height, 1);
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY };
  };

  MoleculeBuilder.prototype._hit = function (e) {
    var p = this._pos(e);
    for (var i = 0; i < this.nodes.length; i++) {
      var n = this.nodes[i];
      if (Math.hypot(n.x - p.x, n.y - p.y) <= RADIUS + 4) return n.id;
    }
    return null;
  };

  MoleculeBuilder.prototype.onMouseDown = function (e) {
    var id = this._hit(e);
    if (id == null) {
      this.selA = null; this.selB = null;
    } else if (this.selA == null) {
      this.selA = id; this.selB = null;
    } else if (this.selA !== id) {
      this.selB = id;
    } else {
      this.dragId = id;
    }
    this.redraw();
  };

  MoleculeBuilder.prototype.onMouseMove = function (e) {
    if (this.dragId == null) return;
    var p = this._pos(e);
    var n = this._node(this.dragId);
    if (n) { n.x = p.x; n.y = p.y; }
    this.redraw();
  };

  MoleculeBuilder.prototype.onMouseUp = function () { this.dragId = null; };

  MoleculeBuilder.prototype._node = function (id) {
    for (var i = 0; i < this.nodes.length; i++) if (this.nodes[i].id === id) return this.nodes[i];
    return null;
  };

  MoleculeBuilder.prototype.addAtom = function (symbol) {
    if (!ATOMS[symbol]) return;
    var w = this.canvas.width, h = this.canvas.height;
    var x = 60 + (this.nodes.length % 8) * 35 + Math.random() * 14;
    var y = 70 + (this.nodes.length % 6) * 30 + Math.random() * 14;
    this.nodes.push({ id: this.nextId++, x: Math.min(x, w - 50), y: Math.min(y, h - 50), symbol: symbol });
    this.dirty = true; this.redraw(); this.updateSummary();
  };

  MoleculeBuilder.prototype.connect = function (order) {
    if (this.selA == null || this.selB == null || this.selA === this.selB) return;
    var existing = this._edge(this.selA, this.selB);
    if (existing) {
      existing.order = order;
    } else {
      this.edges.push({ a: this.selA, b: this.selB, order: order });
    }
    this.dirty = true; this.redraw(); this.updateSummary();
  };

  MoleculeBuilder.prototype._edge = function (a, b) {
    for (var i = 0; i < this.edges.length; i++) {
      var e = this.edges[i];
      if ((e.a === a && e.b === b) || (e.a === b && e.b === a)) return e;
    }
    return null;
  };

  MoleculeBuilder.prototype._cycleBondOrderOn = function (nodeId) {
    var candidates = this.edges.filter(function (e) { return e.a === nodeId || e.b === nodeId; });
    for (var i = 0; i < candidates.length; i++) {
      candidates[i].order = (candidates[i].order % 3) + 1;
    }
    this.redraw(); this.updateSummary();
  };

  MoleculeBuilder.prototype.removeSelected = function () {
    var doomed = [this.selA, this.selB].filter(function (x) { return x != null; });
    var self = this;
    doomed.forEach(function (id) {
      self.nodes = self.nodes.filter(function (n) { return n.id !== id; });
      self.edges = self.edges.filter(function (e) { return e.a !== id && e.b !== id; });
    });
    this.selA = null; this.selB = null;
    this.redraw(); this.updateSummary();
  };

  MoleculeBuilder.prototype.clear = function () {
    this.nodes = []; this.edges = []; this.nextId = 1; this.selA = null; this.selB = null;
    this.redraw(); this.updateSummary();
  };

  MoleculeBuilder.prototype.redraw = function () {
    var ctx = this.ctx;
    var w = this.canvas.width, h = this.canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0b1220";
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = "rgba(148,163,184,0.08)";
    ctx.lineWidth = 1;
    for (var gx = 20; gx < w; gx += 20) { ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, h); ctx.stroke(); }
    for (var gy = 20; gy < h; gy += 20) { ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(w, gy); ctx.stroke(); }

    if (this.selA != null && this.selB != null && this.selA !== this.selB && this._edge(this.selA, this.selB) == null) {
      var na = this._node(this.selA), nb = this._node(this.selB);
      ctx.strokeStyle = "rgba(34,211,238,0.55)";
      ctx.setLineDash([4, 4]);
      ctx.beginPath(); ctx.moveTo(na.x, na.y); ctx.lineTo(nb.x, nb.y); ctx.stroke();
      ctx.setLineDash([]);
    }

    var self = this;
    this.edges.forEach(function (e) {
      var a = self._node(e.a), b = self._node(e.b);
      if (!a || !b) return;
      var dx = b.x - a.x, dy = b.y - a.y;
      var len = Math.hypot(dx, dy) || 1;
      var ux = dx / len, uy = dy / len;
      var nx = -uy, ny = ux;
      var x1 = a.x + ux * RADIUS, y1 = a.y + uy * RADIUS;
      var x2 = b.x - ux * RADIUS, y2 = b.y - uy * RADIUS;
      ctx.strokeStyle = "#cbd5e1";
      ctx.lineWidth = 2.2;
      var off = e.order >= 2 ? 3.2 : 0;
      for (var k = 0; k < e.order; k++) {
        var shift = (k - (e.order - 1) / 2) * 2 * off;
        ctx.beginPath();
        ctx.moveTo(x1 + nx * shift, y1 + ny * shift);
        ctx.lineTo(x2 + nx * shift, y2 + ny * shift);
        ctx.stroke();
      }
    });

    this.nodes.forEach(function (n) {
      var a = ATOMS[n.symbol] || ATOMS.C;
      ctx.beginPath();
      ctx.arc(n.x, n.y, RADIUS, 0, Math.PI * 2);
      ctx.fillStyle = a.color;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = n.id === self.selA || n.id === self.selB ? "#22d3ee" : "#475569";
      ctx.stroke();
      ctx.fillStyle = a.text;
      ctx.font = "bold 13px ui-monospace, monospace";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(n.symbol, n.x, n.y + 0.5);
    });
    this.dirty = false;
  };

  MoleculeBuilder.prototype.compute = function () {
    var counts = {};
    this.nodes.forEach(function (n) { counts[n.symbol] = (counts[n.symbol] || 0) + 1; });
    var formula = "";
    ["C", "H"].forEach(function (sym) {
      if (counts[sym]) formula += sym + (counts[sym] > 1 ? counts[sym] : "");
    });
    Object.keys(counts).sort().forEach(function (sym) {
      if (sym === "C" || sym === "H") return;
      formula += sym + (counts[sym] > 1 ? counts[sym] : "");
    });
    var mw = 0;
    Object.keys(counts).forEach(function (sym) { mw += counts[sym] * (ATOMS[sym] ? ATOMS[sym].m : 0); });
    var bondSummary = {};
    this.edges.forEach(function (e) { bondSummary[e.order] = (bondSummary[e.order] || 0) + 1; });
    return {
      atoms: counts,
      formula: formula || "—",
      molar_mass_g_mol: Math.round(mw * 100) / 100,
      bonds: bondSummary,
      n_atoms: this.nodes.length,
      n_bonds: this.edges.length
    };
  };

  MoleculeBuilder.prototype.updateSummary = function () {
    if (!this.summaryEl) return;
    var c = this.compute();
    var bonds = Object.keys(c.bonds).map(function (k) { return k + "-bond x" + c.bonds[k]; }).join(", ") || "none";
    this.summaryEl.textContent =
      "Formula: " + c.formula + "\n" +
      "Molar mass: " + c.molar_mass_g_mol + " g/mol\n" +
      "Atoms: " + c.n_atoms + "   Bonds: " + c.bonds + "\n\n" +
      "Serialized (JSON):\n" + JSON.stringify(c, null, 2);
  };

  MoleculeBuilder.prototype.serialize = function () {
    var c = this.compute();
    return {
      formula: c.formula,
      molar_mass_g_mol: c.molar_mass_g_mol,
      atoms: this.nodes.map(function (n) { return { symbol: n.symbol, x: Math.round(n.x), y: Math.round(n.y) }; }),
      bonds: this.edges.map(function (e) { return { a: e.a, b: e.b, order: e.order }; })
    };
  };

  MoleculeBuilder.prototype.analysisPrompt = function () {
    var c = this.compute();
    var lines = [
      "Perform a biosafety and dual-use risk review of this molecule for a bioengineering context. " +
        "Summarize composition, plausible functional class, stability notes and any containment concerns.",
      "",
      "Molecule data:",
      "- Molecular formula: " + c.formula,
      "- Approximate molar mass: " + c.molar_mass_g_mol + " g/mol",
      "- Atom counts: " + JSON.stringify(c.atoms)
    ];
    return lines.join("\n");
  };

  window.MoleculeBuilder = MoleculeBuilder;
  window.initMoleculeBuilder = function (canvasId, summaryId) {
    var canvas = document.getElementById(canvasId);
    if (!canvas) return null;
    canvas.width = 820;
    canvas.height = 340;
    var builder = new MoleculeBuilder(canvas, document.getElementById(summaryId));
    window.moleculeBuilder = builder;
    return builder;
  };
})();