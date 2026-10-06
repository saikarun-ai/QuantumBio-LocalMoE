import asyncio
import json
import os
import random
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from ..config import settings
from ..engine import LocalMoEEngine
from ..reporting import Report, curate, export
from ..schemas import GenerationParams

router = APIRouter()

MODEL_ID = settings.API_NAME


ROOT_HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QuantumBio-LocalMoE</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
  .wrap { max-width: 860px; margin: 0 auto; padding: 32px 20px 64px; }
  h1 { font-size: 24px; margin: 0; color: #fff; }
  .sub { color: #94a3b8; margin: 6px 0 24px; font-size: 14px; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 18px; margin-bottom: 16px; }
  .card h2 { margin: 0 0 12px; font-size: 16px; color: #7dd3fc; }
  label { font-size: 13px; color: #cbd5e1; }
  input[type=text], textarea { width: 100%; box-sizing: border-box; padding: 10px 12px; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: #e2e8f0; font: inherit; margin: 6px 0 10px; }
  button { padding: 9px 16px; border: 0; border-radius: 8px; background: #0891b2; color: #fff; font: inherit; cursor: pointer; }
  button:hover { background: #06b6d4; }
  pre { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 12px; overflow: auto; font-size: 13px; white-space: pre-wrap; word-break: break-word; }
  .ok { color: #4ade80; } .bad { color: #f87171; } .dim { color: #94a3b8; }
  .pill { display: inline-block; background: #334155; border-radius: 999px; padding: 2px 10px; margin: 2px; font-size: 12px; }
  details.settings { border: 1px solid #334155; border-radius: 8px; padding: 8px 12px; margin: 8px 0 12px; }
  details.settings summary { cursor: pointer; font-size: 13px; color: #7dd3fc; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; margin-top: 8px; }
  .grid label { display: flex; flex-direction: column; font-size: 12px; color: #cbd5e1; }
  .grid input { margin: 4px 0 0; padding: 6px 8px; border-radius: 6px; border: 1px solid #475569; background: #0f172a; color: #e2e8f0; font: inherit; }
  canvas#molCanvas { width: 100%; border: 1px solid #334155; border-radius: 8px; background: #0b1220; cursor: crosshair; }
  .toolbar { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; align-items: center; }
  .toolbar button { padding: 6px 11px; font-size: 13px; }
  .toolbar select { padding: 6px 8px; border-radius: 6px; border: 1px solid #475569; background: #0f172a; color: #e2e8f0; font: inherit; }
  .hint { font-size: 12px; color: #94a3b8; margin: 4px 0 8px; }
  .row { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
  #pdfPreview { border: 1px solid #334155; border-radius: 8px; margin-top: 8px; max-width: 100%; }
</style>
</head>
<body>
<div class="wrap">
  <h1>&#x1F331; QuantumBio-LocalMoE</h1>
  <p class="sub">Air-gapped local Mixture-of-Experts reasoning engine</p>

  <div class="card">
    <h2>Status</h2>
    <div id="health">Checking...</div>
  </div>

  <div class="card">
    <h2>LLM Model</h2>
    <label for="llmSelect">Active text model (select to avoid copying weights)</label>
    <select id="llmSelect"></select>
    <button onclick="selectLlm()">Load selected</button>
    <div id="llmStatus" class="dim">Fetching catalog...</div>
    <label for="llmDir">Or scan an extra GGUF/AWQ directory (no copy needed)</label>
    <input type="text" id="llmDir" placeholder="D:/Gen AI Applications/LLMS">
    <button onclick="scanDir()">Scan &amp; reload</button>
  </div>

  <div class="card">
    <h2>Model Catalog</h2>
    <div id="models" class="dim">Loading...</div>
  </div>

  <div class="card">
    <h2>Expert Routing</h2>
    <label for="routePrompt">Prompt</label>
    <input type="text" id="routePrompt" placeholder="e.g. Synthesize an OpenQASM 3.0 circuit ...">
    <button onclick="runRoute()">Route</button>
    <pre id="routeOut" class="dim">Routing decision appears here.</pre>
  </div>

  <div class="card">
    <h2>Chat Completion</h2>
    <label for="chatPrompt">Prompt</label>
    <textarea id="chatPrompt" rows="3" placeholder="Ask the local MoE..."></textarea>
    <details class="settings" id="paramPanel" open>
      <summary>Response settings &#8212; tune clarity &amp; efficiency</summary>
      <p class="dim" style="font-size:12px;margin:6px 0 0;">
        Lower temperature + repeat penalty &#8594; focused output; max_tokens &#8594; length cap for efficiency.
      </p>
      <div class="grid">
        <label>Temperature <input type="number" id="pTemperature" min="0" max="2" step="0.05" value="0.2"></label>
        <label>Top-P <input type="number" id="pTopP" min="0" max="1" step="0.05" value="0.9"></label>
        <label>Top-K <input type="number" id="pTopK" min="1" max="1000" step="1" value="40"></label>
        <label>Repeat penalty <input type="number" id="pRepeat" min="1" max="2" step="0.05" value="1.1"></label>
        <label>Max tokens <input type="number" id="pMaxTokens" min="16" max="8192" step="16" value="256"></label>
      </div>
      <button onclick="resetParams()" style="margin-top:8px">Reset defaults</button>
    </details>
    <button onclick="runChat()">Generate</button>
    <pre id="chatOut" class="dim">LLM response appears here.</pre>
  </div>

  <div class="card">
    <h2>System Prompts</h2>
    <label for="promptExpert">Customize the LLM's system prompt per expert</label>
    <select id="promptExpert" onchange="loadActivePrompt()"></select>
    <textarea id="promptText" rows="6" placeholder="System prompt plays a crucial role - customize it here to steer output clarity and style..."></textarea>
    <p class="hint">Saved overrides are persisted to <code>data/system_prompts.json</code> and win over the built-in per-expert defaults.</p>
    <button onclick="saveSystemPrompt()">Save prompt</button>
    <button onclick="clearSystemPrompt()">Reset to default</button>
    <div id="promptStatus" class="dim">Fetching prompt profile...</div>
  </div>

  <div class="card">
    <h2>Molecule Builder</h2>
    <p class="hint">For genetic &amp; bio-engineering workflows. Click an atom to select (A), then another (B); press <strong>Connect</strong> to bond them. Drag a selected atom to move it, double-click a bond side to cycle bond order.</p>
    <div class="toolbar">
      <button onclick="molAdd('C')">C</button>
      <button onclick="molAdd('H')">H</button>
      <button onclick="molAdd('N')">N</button>
      <button onclick="molAdd('O')">O</button>
      <button onclick="molAdd('P')">P</button>
      <button onclick="molAdd('S')">S</button>
      <select id="molOrder">
        <option value="1">single bond</option>
        <option value="2">double bond</option>
        <option value="3">triple bond</option>
      </select>
      <button onclick="molConnect()">Connect</button>
      <button onclick="molDelete()">Delete selected</button>
      <button onclick="molClear()">Clear</button>
      <button onclick="molAnalyze()">Analyze with LLM</button>
    </div>
    <canvas id="molCanvas" width="820" height="340"></canvas>
    <pre id="molSummary" class="dim">Add atoms and bonds to build a molecule.</pre>
    <pre id="molOut" class="dim">Molecule analysis appears here.</pre>
  </div>

  <div class="card">
    <h2>Report &amp; Export</h2>
    <label for="reportSource">Source content (the LLM curates this into a report draft)</label>
    <textarea id="reportSource" rows="5" placeholder="Paste engine output to curate, or generate a chat first - it auto-fills here."></textarea>
    <label for="reportTopic">Report topic (optional)</label>
    <input type="text" id="reportTopic" placeholder="e.g. CRISPR off-target analysis">
    <div class="row">
      <button onclick="curateReport()">Curate with LLM</button>
      <button onclick="downloadMd()">&#8595; .md</button>
      <button onclick="downloadTxt()">&#8595; .txt</button>
      <button onclick="downloadPdf()">&#8595; .pdf</button>
      <button onclick="downloadPptx()">&#8595; .pptx</button>
      <button onclick="exportAll()">Export all (server)</button>
      <button onclick="sendToChat()">Send source to chat</button>
    </div>
    <pre id="reportDraft" class="dim">Curated report draft appears here.</pre>
    <div id="reportLinks" class="dim"></div>
    <canvas id="pdfPreview" width="0" height="0" style="display:none"></canvas>
    <p class="hint" style="margin-top:8px">Formats: Markdown, plain text, PDF (server-side, reportlab) and PowerPoint (pptxgenjs in-browser + python-pptx server-side). PDF.js renders a first-page preview after a PDF export.</p>
  </div>

  <p class="dim">REST API docs: <a href="/docs" style="color:#7dd3fc">/docs</a></p>
</div>

<script src="/static/pptxgen.bundle.js"></script>
<script src="/static/pdf.min.js"></script>
<script src="/static/molecules.js"></script>
<script>
async function getJson(url, opts) {
  const r = await fetch(url, opts);
  return r.json();
}

async function showHealth() {
  try {
    const h = await getJson('/health');
    document.getElementById('health').innerHTML =
      '<span class="ok">&#10003; OK</span> &middot; <span class="pill">' + h.model + '</span>';
  } catch (e) {
    document.getElementById('health').innerHTML = '<span class="bad">API not reachable</span>';
  }
}

async function showModels() {
  try {
    const m = await getJson('/v1/models');
    const ids = m.data.map(x => '<span class="pill">' + x.id + '</span>').join('');
    document.getElementById('models').innerHTML = ids || '<span class="dim">none</span>';
  } catch (e) {
    document.getElementById('models').innerHTML = '<span class="bad">unavailable</span>';
  }
}

async function runRoute() {
  const prompt = document.getElementById('routePrompt').value;
  if (!prompt) return;
  document.getElementById('routeOut').textContent = 'Routing...';
  try {
    const r = await getJson('/v1/route?prompt=' + encodeURIComponent(prompt));
    document.getElementById('routeOut').textContent = JSON.stringify(r, null, 2);
  } catch (e) { document.getElementById('routeOut').textContent = 'Error: ' + e; }
}

async function runChat() {
  const prompt = document.getElementById('chatPrompt').value;
  if (!prompt) return;
  const params = collectParams();
  persistParams(params);
  const body = {
    model: 'quantumbio-moe-local',
    messages: [{ role: 'user', content: prompt }],
    max_tokens: params.max_tokens,
    temperature: params.temperature,
    top_p: params.top_p,
    top_k: params.top_k,
    repeat_penalty: params.repeat_penalty
  };
  document.getElementById('chatOut').textContent = 'Generating...';
  try {
    const r = await getJson('/v1/chat/completions', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    document.getElementById('chatOut').textContent = r.choices[0].message.content;
    const src = document.getElementById('reportSource');
    if (src && !src.value) src.value = r.choices[0].message.content;
  } catch (e) { document.getElementById('chatOut').textContent = 'Error: ' + e; }
}

const PARAM_FIELDS = {
  temperature: 'pTemperature',
  top_p: 'pTopP',
  top_k: 'pTopK',
  repeat_penalty: 'pRepeat',
  max_tokens: 'pMaxTokens'
};
const PARAM_DEFAULTS = { temperature: 0.2, top_p: 0.9, top_k: 40, repeat_penalty: 1.1, max_tokens: 256 };

function collectParams() {
  return {
    temperature: parseFloat(document.getElementById(PARAM_FIELDS.temperature).value),
    top_p: parseFloat(document.getElementById(PARAM_FIELDS.top_p).value),
    top_k: parseInt(document.getElementById(PARAM_FIELDS.top_k).value, 10),
    repeat_penalty: parseFloat(document.getElementById(PARAM_FIELDS.repeat_penalty).value),
    max_tokens: parseInt(document.getElementById(PARAM_FIELDS.max_tokens).value, 10)
  };
}

function persistParams(params) {
  try { localStorage.setItem('qbio_gen_params', JSON.stringify(params)); } catch (e) {}
}

function loadParams() {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem('qbio_gen_params') || '{}'); } catch (e) {}
  Object.assign(PARAM_DEFAULTS, saved);
  Object.keys(PARAM_FIELDS).forEach(k => {
    const el = document.getElementById(PARAM_FIELDS[k]);
    if (el && PARAM_DEFAULTS[k] !== undefined) el.value = PARAM_DEFAULTS[k];
  });
}

function resetParams() {
  PARAM_DEFAULTS.temperature = 0.2;
  PARAM_DEFAULTS.top_p = 0.9;
  PARAM_DEFAULTS.top_k = 40;
  PARAM_DEFAULTS.repeat_penalty = 1.1;
  PARAM_DEFAULTS.max_tokens = 256;
  Object.keys(PARAM_FIELDS).forEach(k => {
    document.getElementById(PARAM_FIELDS[k]).value = PARAM_DEFAULTS[k];
  });
  persistParams(PARAM_DEFAULTS);
}

function mb(bytes) { return (bytes / 1048576).toFixed(0) + ' MB'; }

async function loadLlmCatalog() {
  try {
    const r = await getJson('/v1/engine/models');
    const sel = document.getElementById('llmSelect');
    sel.innerHTML = '';
    r.models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.path;
      opt.textContent = m.name + '  [' + m.kind + ', ' + mb(m.size_bytes) + ']';
      sel.appendChild(opt);
    });
    document.getElementById('llmStatus').textContent = 'Active: ' + (r.active || 'none');
  } catch (e) { document.getElementById('llmStatus').textContent = 'Error: ' + e; }
}

async function selectLlm() {
  const path = document.getElementById('llmSelect').value;
  if (!path) return;
  document.getElementById('llmStatus').textContent = 'Loading ' + path + ' ...';
  try {
    const r = await getJson('/v1/engine/models/select', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path })
    });
    document.getElementById('llmStatus').textContent =
      'Active: ' + r.active + '  [backend: ' + r.backend + (r.fallback ? ', offline fallback]' : ', running]');
  } catch (e) { document.getElementById('llmStatus').textContent = 'Error: ' + e; }
}

async function scanDir() {
  const directory = document.getElementById('llmDir').value;
  if (!directory) return;
  document.getElementById('llmStatus').textContent = 'Scanning ' + directory + ' ...';
  try {
    const r = await getJson('/v1/engine/models/scan', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ directory })
    });
    await loadLlmCatalog();
    document.getElementById('llmStatus').textContent = 'Scan complete - ' + r.models.length + ' models indexed.';
  } catch (e) { document.getElementById('llmStatus').textContent = 'Error: ' + e; }
}

/* ---- System Prompts ---- */
let promptProfile = { experts: {}, overrides: {} };

async function loadPromptProfile() {
  try {
    promptProfile = await getJson('/v1/prompts');
    const sel = document.getElementById('promptExpert');
    sel.innerHTML = '';
    const names = { default: 'all experts (global default)', quantum: 'Quantum Circuit', genomic: 'Genomic Sequence', biosecurity: 'Biosecurity Audit', general: 'General Reasoning', image: 'Creative Imaging' };
    ['default'].concat(Object.keys(promptProfile.experts || {})).forEach(k => {
      const opt = document.createElement('option');
      opt.value = k;
      opt.textContent = names[k] || k;
      sel.appendChild(opt);
    });
    document.getElementById('promptStatus').textContent = '';
    loadActivePrompt();
  } catch (e) {
    document.getElementById('promptStatus').textContent = 'Error: ' + e;
  }
}

function loadActivePrompt() {
  const k = document.getElementById('promptExpert').value;
  const expert = (promptProfile.experts || {})[k];
  const text = k === 'default'
    ? (promptProfile.default_override || (expert && expert.default) || '')
    : ((promptProfile.experts[k] || {}).active || '');
  document.getElementById('promptText').value = text;
  document.getElementById('promptStatus').textContent =
    k === 'default' ? 'Global default prompt.' : ('Active prompt for "' + k + '" (default differs if customized).');
}

async function saveSystemPrompt() {
  const k = document.getElementById('promptExpert').value;
  const text = document.getElementById('promptText').value;
  try {
    promptProfile = await getJson('/v1/prompts', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expert: k, system_prompt: text })
    });
    document.getElementById('promptStatus').textContent = 'Saved. Applied to all new generations.';
  } catch (e) { document.getElementById('promptStatus').textContent = 'Error: ' + e; }
}

async function clearSystemPrompt() {
  const k = document.getElementById('promptExpert').value;
  try {
    promptProfile = await getJson('/v1/prompts', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expert: k, clear: true })
    });
    loadActivePrompt();
  } catch (e) { document.getElementById('promptStatus').textContent = 'Error: ' + e; }
}

/* ---- Molecule Builder ---- */
function molAdd(symbol) {
  if (window.moleculeBuilder) window.moleculeBuilder.addAtom(symbol);
}
function molConnect() {
  if (!window.moleculeBuilder) return;
  const order = parseInt(document.getElementById('molOrder').value, 10) || 1;
  window.moleculeBuilder.connect(order);
}
function molDelete() { if (window.moleculeBuilder) window.moleculeBuilder.removeSelected(); }
function molClear() { if (window.moleculeBuilder) window.moleculeBuilder.clear(); }

async function molAnalyze() {
  const b = window.moleculeBuilder;
  if (!b || b.nodes.length === 0) return;
  const prompt = b.analysisPrompt();
  const el = document.getElementById('molOut');
  el.textContent = 'Analyzing molecule with local LLM...';
  try {
    const r = await getJson('/v1/chat/completions', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: 'quantumbio-moe-local', messages: [{ role: 'user', content: prompt }], max_tokens: 320, temperature: 0.2 })
    });
    const answer = r.choices[0].message.content;
    el.textContent = answer;
    const data = b.serialize();
    const src = document.getElementById('reportSource');
    if (src) {
      src.value = 'MOLECULE REPORT\nFormula: ' + data.formula +
        '\nMolar mass: ' + data.molar_mass_g_mol + ' g/mol' +
        '\nAtoms: ' + JSON.stringify(data.atoms) +
        '\nBonds: ' + JSON.stringify(data.bonds) +
        '\n\nLLM ANALYSIS\n\n' + answer;
    }
  } catch (e) { el.textContent = 'Error: ' + e; }
}

function sendToChat() {
  const src = document.getElementById('reportSource');
  if (!src || !src.value) return;
  document.getElementById('chatPrompt').value = src.value;
  document.getElementById('chatOut').textContent = 'Source copied to chat prompt.';
}

/* ---- Report & Export ---- */
let lastDraft = '';
let lastTitle = 'Report';

function buildClientMarkdown(draft, title) {
  const now = new Date().toISOString().slice(0, 19).replace('T', ' ');
  let body = (draft || '').replace(/^\s*#\s+.+\n?/, '').trim();
  return '# ' + (title || 'Report') + '\n\n> **Generated by** QuantumBio-LocalMoE  ·  ' + now + '\n\n---\n\n' + body + '\n';
}

function downloadBlob(name, content, type) {
  const blob = new Blob([content], { type: type || 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 800);
}

function reportSourceText() {
  return document.getElementById('reportSource').value.trim();
}

function requireSource() {
  const src = reportSourceText();
  if (!src) {
    document.getElementById('reportDraft').textContent = 'Add source content first (generate a chat or paste text).';
    return null;
  }
  return src;
}

async function curateReport() {
  const src = requireSource();
  if (!src) return;
  const topic = document.getElementById('reportTopic').value;
  document.getElementById('reportDraft').textContent = 'Curating with the local LLM...';
  try {
    const r = await getJson('/v1/report/draft', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: src, topic: topic || null })
    });
    lastDraft = r.draft;
    lastTitle = r.title;
    document.getElementById('reportDraft').textContent = r.draft;
  } catch (e) { document.getElementById('reportDraft').textContent = 'Error: ' + e; }
}

function downloadMd() {
  const src = requireSource();
  if (!src) return;
  const title = lastTitle || document.getElementById('reportTopic').value || 'Report';
  downloadBlob(title.replace(/[^a-z0-9_-]+/gi, '_') + '.md', buildClientMarkdown(lastDraft || src, title), 'text/markdown;charset=utf-8');
}

function downloadTxt() {
  const src = requireSource();
  if (!src) return;
  const title = lastTitle || document.getElementById('reportTopic').value || 'Report';
  const body = (lastDraft || src).replace(/^#\s+.+\n?/m, '').replace(/`/g, '').replace(/\*\*/g, '').replace(/\B#\s?/g, '');
  downloadBlob(title.replace(/[^a-z0-9_-]+/gi, '_') + '.txt', title.toUpperCase() + '\n' + '='.repeat(title.length) + '\n\n' + body + '\n', 'text/plain;charset=utf-8');
}

async function serverExport(fmt, type) {
  const src = requireSource();
  if (!src) return null;
  const title = lastTitle || document.getElementById('reportTopic').value || 'Report';
  try {
    const r = await fetch('/v1/export', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: lastDraft || src, title: title, format: fmt })
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const body = await r.json();
    const blob = await (await fetch(body.url)).blob();
    downloadBlob(body.filename, blob, type || blob.type);
    return body.url;
  } catch (e) {
    document.getElementById('reportLinks').textContent = 'Export .' + fmt + ' failed: ' + e;
    return null;
  }
}

async function downloadPdf() {
  const url = await serverExport('pdf', 'application/pdf');
  if (url) previewPdf(url);
}

async function downloadPptx() {
  const src = requireSource();
  if (!src) return;
  const title = lastTitle || document.getElementById('reportTopic').value || 'Report';
  const body = (lastDraft || src).replace(/^#\s+.+\n?/m, '');
  try {
    if (window.PptxGenJS) {
      const pptx = new PptxGenJS();
      pptx.defineLayout({ name: 'WIDE', width: 13.33, height: 7.5 });
      pptx.layout = 'LAYOUT_WIDE';
      pptx.title = title;
      const slide = pptx.addSlide();
      slide.addText(title, { x: 0.4, y: 0.5, w: 12.5, h: 1, fontSize: 30, bold: true, color: '0F172A' });
      slide.addText('QuantumBio-LocalMoE · ' + new Date().toISOString().slice(0, 10), { x: 0.4, y: 1.6, w: 12.5, fontSize: 14, color: '64748B' });
      body.split('\n').forEach(function (line) {
        const s = line.trim();
        if (!s) return;
        const titleMatch = s.match(/^#{1,3}\s+(.*)$/);
        const bullet = s.match(/^[-*]\s+(.*)$/);
        const slide2 = pptx.addSlide();
        if (titleMatch) {
          slide2.addText(titleMatch[1], { x: 0.4, y: 0.5, w: 12.5, fontSize: 24, bold: true, color: '0891B2' });
        } else if (bullet) {
          slide2.addText('• ' + bullet[1].replace(/\*\*/g, ''), { x: 0.4, y: 0.5, w: 12.5, fontSize: 16 });
        } else {
          slide2.addText(s.replace(/\*\*/g, ''), { x: 0.4, y: 0.5, w: 12.5, fontSize: 14 });
        }
      });
      pptx.writeFile({ fileName: title.replace(/[^a-z0-9_-]+/gi, '_') + '.pptx' });
    } else {
      serverExport('pptx', 'application/vnd.openxmlformats-officedocument.presentationml.presentation');
    }
  } catch (e) {
    document.getElementById('reportLinks').textContent = 'PPTX error: ' + e;
  }
}

async function exportAll() {
  const src = requireSource();
  if (!src) return;
  const topic = document.getElementById('reportTopic').value;
  document.getElementById('reportLinks').textContent = 'Generating md, txt, pdf and pptx via the server...';
  try {
    const r = await getJson('/v1/report/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: src, topic: topic || null, formats: ['md', 'txt', 'pdf', 'pptx'] })
    });
    lastTitle = r.title;
    const links = r.files.map(function (f) { return '<a href="' + f.url + '" style="color:#7dd3fc">' + f.filename + '</a>'; });
    document.getElementById('reportLinks').innerHTML = 'Exported "' + r.title + '": ' + links.join(' · ');
    const pdf = r.files.find(function (f) { return f.format === 'pdf'; });
    if (pdf) previewPdf(pdf.url);
  } catch (e) { document.getElementById('reportLinks').textContent = 'Error: ' + e; }
}

async function previewPdf(url) {
  const canvas = document.getElementById('pdfPreview');
  if (!canvas || !window.pdfjsLib) return;
  try {
    pdfjsLib.GlobalWorkerOptions.workerSrc = '/static/pdf.worker.min.js';
    const pdf = await pdfjsLib.getDocument(url).promise;
    const page = await pdf.getPage(1);
    const viewport = page.getViewport({ scale: 1.4 });
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.display = 'block';
    await page.render({ canvasContext: canvas.getContext('2d'), viewport: viewport }).promise;
  } catch (e) { /* preview is optional */ }
}

showHealth();
showModels();
loadLlmCatalog();
loadParams();
loadPromptProfile();
initMoleculeBuilder('molCanvas', 'molSummary');
</script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    return HTMLResponse(content=ROOT_HTML)


def get_engine(request: Request) -> LocalMoEEngine:
    engine: LocalMoEEngine = request.app.state.engine
    if engine is None:
        raise HTTPException(status_code=503, detail="Engine is still starting")
    return engine


class ChatMessage(BaseModel):
    role: str = "user"
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = MODEL_ID
    messages: list[ChatMessage]
    max_tokens: int = Field(default=256, ge=1, le=32768)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int = Field(default=40, ge=1, le=1000)
    repeat_penalty: float = Field(default=1.1, ge=0.0, le=2.0)
    min_p: float = Field(default=0.05, ge=0.0, le=1.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    stream: bool = False
    stop: list[str] | None = None
    user: str | None = None


class ImageGenerationRequest(BaseModel):
    model: str = "quantumbio-image-local"
    prompt: str
    negative_prompt: str = ""
    n: int = Field(default=1, ge=1, le=4)
    size: str = "512x512"
    steps: int = Field(default=20, ge=1, le=150)


class TranscriptionRequest(BaseModel):
    model: str = "quantumbio-whisper-local"
    file: str
    language: str | None = None


class ModelSelectRequest(BaseModel):
    path: str


class DirectoryScanRequest(BaseModel):
    directory: str


class PromptUpdateRequest(BaseModel):
    expert: str = Field(default="default", min_length=1)
    system_prompt: str = ""
    clear: bool = False


class ReportDraftRequest(BaseModel):
    source: str = Field(min_length=1)
    topic: str | None = None


class ReportExportRequest(BaseModel):
    content: str = Field(min_length=1)
    title: str | None = None
    format: str = "md"


class ReportGenerateRequest(BaseModel):
    source: str = Field(min_length=1)
    topic: str | None = None
    formats: list[str] = Field(default_factory=lambda: ["md", "txt", "pdf", "pptx"])


def _now() -> int:
    return int(time.time())


def _chat_id() -> str:
    return f"chatcmpl-local-{random.randint(10000, 99999)}"


def _build_usage(prompt_tokens: int, completion_tokens: int) -> dict:
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "model": MODEL_ID, "engine": settings.API_NAME}


@router.get("/v1/models")
async def list_models(request: Request) -> dict:
    engine = get_engine(request)
    experts = [expert["key"] for expert in engine.expert_catalog()]
    data = []
    for suffix in ("quantumbio-moe-local", "quantumbio-image-local", "quantumbio-whisper-local"):
        data.append({"id": suffix, "object": "model", "created": _now(),
                     "owned_by": "quantumbio"})
    data.append({"id": f"{MODEL_ID}:experts", "object": "model", "created": _now(),
                 "owned_by": "quantumbio", "experts": experts})
    return {"object": "list", "data": data}


def _model_payload(model) -> dict:
    return {
        "name": model.name,
        "path": model.path,
        "kind": model.kind,
        "size_bytes": model.size_bytes,
    }


@router.get("/v1/engine/models")
async def engine_models(request: Request) -> dict:
    engine = get_engine(request)
    return {
        "active": engine.current_model,
        "directories": engine.registry.directories,
        "models": [_model_payload(model) for model in engine.registry.models],
    }


@router.post("/v1/engine/models/select")
async def engine_select_model(request: Request, payload: ModelSelectRequest) -> dict:
    engine = get_engine(request)
    try:
        return await engine.select_model(payload.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/v1/engine/models/scan")
async def engine_scan_directory(request: Request, payload: DirectoryScanRequest) -> dict:
    engine = get_engine(request)
    try:
        models = engine.add_model_directory(payload.directory)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "directories": engine.registry.directories,
        "models": models,
    }


REPORT_FORMATS = {"md", "txt", "pdf", "pptx"}


def _validate_format(fmt: str) -> str:
    fmt = fmt.lower()
    if fmt not in REPORT_FORMATS:
        raise HTTPException(status_code=422, detail=f"format must be one of {sorted(REPORT_FORMATS)}")
    return fmt


def _report_file(path: str) -> dict:
    return {
        "format": os.path.splitext(path)[1].lstrip("."),
        "filename": os.path.basename(path),
        "path": path,
        "url": f"/reports/{os.path.basename(path)}",
    }


@router.get("/v1/reports")
async def list_reports() -> dict:
    directory = os.path.abspath("reports")
    files = []
    if os.path.isdir(directory):
        for name in sorted(os.listdir(directory)):
            full = os.path.join(directory, name)
            if os.path.isfile(full):
                files.append({"filename": name, "url": f"/reports/{name}", "size": os.path.getsize(full)})
    return {"directory": directory, "reports": files}


@router.get("/v1/prompts")
async def get_prompts(request: Request) -> dict:
    engine = get_engine(request)
    return engine.prompt_profile_view()


@router.post("/v1/prompts")
async def update_prompts(request: Request, payload: PromptUpdateRequest) -> dict:
    engine = get_engine(request)
    if payload.expert != "default" and engine.router is not None and payload.expert not in engine.router.experts:
        raise HTTPException(status_code=422, detail=f"unknown expert key: {payload.expert}")
    engine.update_system_prompt(payload.expert, None if payload.clear else payload.system_prompt)
    return engine.prompt_profile_view()


@router.post("/v1/report/draft")
async def report_draft(request: Request, payload: ReportDraftRequest) -> dict:
    engine = get_engine(request)
    return await curate(engine, payload.source, topic=payload.topic)


@router.post("/v1/export")
async def export_report(payload: ReportExportRequest) -> dict:
    fmt = _validate_format(payload.format)
    report = Report(title=(payload.title or "Report").strip() or "Report",
                    source=payload.content, draft=payload.content)
    path = export(report, fmt=fmt, out_dir="reports")
    return {"ok": True, **_report_file(path)}


@router.post("/v1/report/generate")
async def report_generate(request: Request, payload: ReportGenerateRequest) -> dict:
    engine = get_engine(request)
    curated = await curate(engine, payload.source, topic=payload.topic)
    files = []
    for fmt in payload.formats:
        fmt = _validate_format(fmt)
        report = Report(title=curated["title"], source=payload.source, draft=curated["draft"],
                        expert=curated["expert"], model=curated["model"],
                        prompt_tokens=curated["prompt_tokens"],
                        completion_tokens=curated["completion_tokens"])
        path = export(report, fmt=fmt, out_dir="reports")
        files.append(_report_file(path))
    return {
        "title": curated["title"],
        "expert": curated["expert"],
        "model": curated["model"],
        "tokens": curated["prompt_tokens"] + curated["completion_tokens"],
        "files": files,
    }


@router.get("/v1/route")
async def evaluate_route(request: Request, prompt: str) -> dict:
    engine = get_engine(request)
    return engine.router.evaluate(prompt)


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(request: Request, payload: ChatCompletionRequest) -> dict | StreamingResponse:
    engine = get_engine(request)
    if not payload.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")
    prompt = "\n".join(message.content for message in payload.messages if message.role != "system")
    system_text = "\n".join(message.content for message in payload.messages if message.role == "system")

    params = GenerationParams(
        max_tokens=payload.max_tokens,
        temperature=payload.temperature,
        top_p=payload.top_p,
        top_k=payload.top_k,
        repeat_penalty=payload.repeat_penalty,
        min_p=payload.min_p,
        presence_penalty=payload.presence_penalty,
        frequency_penalty=payload.frequency_penalty,
    )
    response = await engine.generate(prompt, params=params, system_prompt=system_text or None)

    if payload.stream:
        async def event_stream():
            prefix = {
                "id": _chat_id(),
                "object": "chat.completion.chunk",
                "created": _now(),
                "model": payload.model,
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(prefix)}\n\n"
            words = response.text.split(" ")
            for index in range(0, len(words), 8):
                chunk = " ".join(words[index:index + 8])
                if not chunk:
                    continue
                body = {
                    "id": _chat_id(),
                    "object": "chat.completion.chunk",
                    "created": _now(),
                    "model": payload.model,
                    "choices": [{"index": 0, "delta": {"content": chunk + " "}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(body)}\n\n"
                await asyncio.sleep(0.02)
            done = {
                "id": _chat_id(),
                "object": "chat.completion.chunk",
                "created": _now(),
                "model": payload.model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(done)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return {
        "id": _chat_id(),
        "object": "chat.completion",
        "created": _now(),
        "model": payload.model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": response.text},
            "finish_reason": response.finish_reason,
        }],
        "usage": _build_usage(response.prompt_tokens, response.completion_tokens),
    }


@router.post("/v1/images/generations")
async def images_generations(request: Request, payload: ImageGenerationRequest) -> dict:
    engine = get_engine(request)
    try:
        width, height = (int(part) for part in payload.size.lower().split("x"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid size: {exc}")
    urls = []
    for _ in range(payload.n):
        try:
            path = await engine.generate_image(payload.prompt, negative_prompt=payload.negative_prompt,
                                               width=width, height=height, steps=payload.steps)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        urls.append({"url": f"/outputs/{os.path.basename(path)}", "path": path})
    return {"created": _now(), "data": urls}


@router.post("/v1/audio/transcriptions")
async def audio_transcriptions(request: Request, payload: TranscriptionRequest) -> dict:
    engine = get_engine(request)
    try:
        text = await engine.transcribe(payload.file)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"text": text}