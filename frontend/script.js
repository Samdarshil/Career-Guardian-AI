/**
 * Career Guardian AI v2 — Frontend Logic
 * Uses Server-Sent Events (SSE) to stream live agent progress,
 * then renders the 9-section dashboard when the pipeline completes.
 */

'use strict';

// ── DOM References ────────────────────────────────────────────────────────────
const uploadSection  = document.getElementById('upload-section');
const loadingSection = document.getElementById('loading-section');
const resultsSection = document.getElementById('results-section');
const dropZone       = document.getElementById('drop-zone');
const fileInput      = document.getElementById('file-input');
const filePreview    = document.getElementById('file-preview');
const fileNameEl     = document.getElementById('file-name-display');
const fileSizeEl     = document.getElementById('file-size-display');
const removeFileBtn  = document.getElementById('remove-file');
const analyseBtn     = document.getElementById('analyse-btn');
const errorBanner    = document.getElementById('error-banner');
const errorMessage   = document.getElementById('error-message');
const reanalyseBtn   = document.getElementById('reanalyse-btn');
const loadingTimer   = document.getElementById('loading-timer');

let selectedFile = null;
let pipelineStart = 0;

// ── Utilities ─────────────────────────────────────────────────────────────────
const formatBytes = (b) =>
  b < 1024 ? `${b} B` : b < 1048576 ? `${(b/1024).toFixed(1)} KB` : `${(b/1048576).toFixed(2)} MB`;

const showError = (msg) => { errorMessage.textContent = msg; errorBanner.classList.remove('hidden'); };
const hideError = ()      => errorBanner.classList.add('hidden');

const scoreColor = (s) => s >= 70 ? 'score-color-high' : s >= 45 ? 'score-color-mid' : 'score-color-low';
const dialColor  = (s) => s >= 70 ? 'dial-high'        : s >= 45 ? 'dial-mid'        : 'dial-low';

function animateBar(el, pct) {
  requestAnimationFrame(() => { el.style.width = `${Math.min(100, Math.max(0, pct))}%`; });
}

function dialOffset(score) {
  return 502 - (score / 100) * 502;
}

function esc(str) {
  const d = document.createElement('div');
  d.textContent = String(str ?? '');
  return d.innerHTML;
}

function show(section) {
  [uploadSection, loadingSection, resultsSection].forEach(s => s.classList.add('hidden'));
  section.classList.remove('hidden');
}

// ── File Handling ─────────────────────────────────────────────────────────────
function setFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
    showError('Only PDF files are accepted.'); return;
  }
  if (file.size > 10 * 1024 * 1024) {
    showError('File exceeds 10 MB. Please compress your PDF.'); return;
  }
  hideError();
  selectedFile = file;
  fileNameEl.textContent = file.name;
  fileSizeEl.textContent = formatBytes(file.size);
  filePreview.classList.remove('hidden');
  analyseBtn.disabled = false;
}

function clearFile() {
  selectedFile = null;
  fileInput.value = '';
  filePreview.classList.add('hidden');
  analyseBtn.disabled = true;
  hideError();
}

fileInput.addEventListener('change', (e) => { if (e.target.files[0]) setFile(e.target.files[0]); });
removeFileBtn.addEventListener('click', clearFile);

dropZone.addEventListener('dragover',  (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', ()  => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault(); dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
});
dropZone.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });

// ── Agent Feed UI ─────────────────────────────────────────────────────────────
const AGENT_LABELS = {
  resume_agent:    'Resume Agent',
  career_agent:    'Career Agent',
  skill_gap_agent: 'Skill Gap Agent',
  roadmap_agent:   'Roadmap Agent',
  resource_agent:  'Resource Agent',
};

function resetFeed() {
  Object.keys(AGENT_LABELS).forEach(id => {
    const statusEl = document.getElementById(`status-${id}`);
    const labelEl  = document.getElementById(`label-${id}`);
    const timeEl   = document.getElementById(`time-${id}`);
    const rowEl    = document.getElementById(`feed-${id}`);
    if (statusEl) { statusEl.className = 'feed-status idle'; }
    if (labelEl)  { labelEl.textContent = 'Waiting…'; }
    if (timeEl)   { timeEl.textContent = ''; }
    if (rowEl)    { rowEl.className = 'agent-feed-row'; }
  });
  if (loadingTimer) loadingTimer.textContent = 'Connecting to agent pipeline…';
}

function onAgentStart(data) {
  const { agent, label } = data;
  const statusEl = document.getElementById(`status-${agent}`);
  const labelEl  = document.getElementById(`label-${agent}`);
  const rowEl    = document.getElementById(`feed-${agent}`);
  if (statusEl) statusEl.className = 'feed-status running';
  if (labelEl)  labelEl.textContent = label || 'Running…';
  if (rowEl)    rowEl.className = 'agent-feed-row running';
}

function onAgentDone(data) {
  const { agent, success, duration } = data;
  const statusEl = document.getElementById(`status-${agent}`);
  const labelEl  = document.getElementById(`label-${agent}`);
  const timeEl   = document.getElementById(`time-${agent}`);
  const rowEl    = document.getElementById(`feed-${agent}`);
  if (statusEl) statusEl.className = `feed-status ${success ? 'done' : 'error'}`;
  if (labelEl)  labelEl.textContent = success ? 'Complete' : 'Failed (fallback used)';
  if (timeEl)   timeEl.textContent  = duration ? `${duration}s` : '';
  if (rowEl)    rowEl.className = `agent-feed-row ${success ? 'done' : 'error'}`;

  // Update elapsed timer
  const elapsed = ((Date.now() - pipelineStart) / 1000).toFixed(1);
  if (loadingTimer) loadingTimer.textContent = `${elapsed}s elapsed…`;
}

// ── Main analysis via SSE stream ─────────────────────────────────────────────
analyseBtn.addEventListener('click', async () => {
  if (!selectedFile) return;
  hideError();
  resetFeed();
  show(loadingSection);
  pipelineStart = Date.now();

  const formData = new FormData();
  formData.append('resume', selectedFile);

  try {
    const response = await fetch('http://localhost:8000/api/stream', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      show(uploadSection);
      showError(err?.detail?.message || err?.message || 'Analysis failed. Please try again.');
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Process all complete SSE messages in buffer
      const messages = buffer.split('\n\n');
      buffer = messages.pop(); // keep incomplete last chunk

      for (const message of messages) {
        if (!message.trim()) continue;

        let eventType = 'message';
        let eventData = '';

        for (const line of message.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            eventData = line.slice(6).trim();
          }
        }

        if (!eventData) continue;

        try {
          const data = JSON.parse(eventData);

          if (eventType === 'agent_start') {
            onAgentStart(data);
          } else if (eventType === 'agent_done') {
            onAgentDone(data);
          } else if (eventType === 'complete') {
            // Final event — render dashboard
            const elapsed = ((Date.now() - pipelineStart) / 1000).toFixed(1);
            if (loadingTimer) loadingTimer.textContent = `Complete in ${elapsed}s`;
            await new Promise(r => setTimeout(r, 400)); // brief pause to show final state
            renderDashboard(data);
            show(resultsSection);
            window.scrollTo({ top: 0, behavior: 'smooth' });
          } else if (eventType === 'error') {
            show(uploadSection);
            showError(data?.message || 'Analysis failed. Please try again.');
          }
        } catch (parseErr) {
          console.warn('SSE parse error:', parseErr, 'raw:', eventData);
        }
      }
    }

  } catch (err) {
    show(uploadSection);
    if (err.name === 'AbortError') {
      showError('Request timed out. Please try again.');
    } else {
      showError('Network error. Please check your connection and try again.');
    }
  }
});

reanalyseBtn.addEventListener('click', () => {
  clearFile();
  show(uploadSection);
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

// ── Dashboard Renderer ────────────────────────────────────────────────────────
function renderDashboard(data) {
  renderHeader(data);
  renderFocusScore(data.focus_score);
  renderCareerDirection(data.career_direction);
  renderResumeRating(data.resume_rating);
  renderSkillGap(data.skill_gap);
  renderResumeIntelligence(data.resume_intelligence);
  renderRoadmap(data.growth_roadmap);
  renderCertifications(data.certifications || []);
  renderProjects(data.projects || []);
  renderOpportunities(data.opportunities || []);
  renderTimings(data.agent_timings || {});
}

function renderHeader(data) {
  const ri = data.resume_intelligence || {};
  const name = ri.name && ri.name !== 'Not detected' ? ri.name : 'Your Resume';
  const role = data.career_direction?.primary || '';
  document.getElementById('dash-candidate-name').textContent =
    role ? `${name} — ${role}` : name;
}

function renderTimings(timings) {
  const container = document.getElementById('agent-timing-pills');
  if (!container || !Object.keys(timings).length) return;
  Object.entries(timings).forEach(([agent, secs]) => {
    const short = agent.replace('_agent', '').replace('_', ' ');
    const pill = document.createElement('div');
    pill.className = 'timing-pill';
    pill.title = agent;
    pill.innerHTML = `${short} <span>${secs}s</span>`;
    container.appendChild(pill);
  });
}

// ── Focus Score ───────────────────────────────────────────────────────────────
function renderFocusScore(fs) {
  if (!fs) return;
  const score = fs.score ?? 0;

  const dialCircle = document.getElementById('focus-dial-circle');
  const scoreText  = document.getElementById('dial-score-text');
  const catText    = document.getElementById('dial-category-text');

  scoreText.textContent = score;
  catText.textContent   = fs.category || '';
  dialCircle.classList.add(dialColor(score));
  setTimeout(() => { dialCircle.style.strokeDashoffset = dialOffset(score); }, 200);

  document.getElementById('focus-reasoning').textContent = fs.reasoning || '';

  const bars = [
    ['bar-skill-align',   'val-skill-align',   fs.skill_alignment],
    ['bar-project-align', 'val-project-align', fs.project_alignment],
    ['bar-cert-align',    'val-cert-align',    fs.certification_alignment],
    ['bar-exp-align',     'val-exp-align',     fs.experience_alignment],
    ['bar-consistency',   'val-consistency',   fs.resume_consistency],
  ];
  bars.forEach(([barId, valId, value]) => {
    const barEl = document.getElementById(barId);
    const valEl = document.getElementById(valId);
    if (!barEl || !valEl) return;
    const pct = value ?? 0;
    barEl.classList.add(scoreColor(pct));
    valEl.textContent = pct;
    setTimeout(() => animateBar(barEl, pct), 300);
  });

  const strengthsEl = document.getElementById('focus-strengths');
  (fs.strengths || []).slice(0, 4).forEach(s => {
    strengthsEl.insertAdjacentHTML('beforeend', `<li>${esc(s)}</li>`);
  });

  const weaknessesEl = document.getElementById('focus-weaknesses');
  (fs.weaknesses || []).slice(0, 4).forEach(w => {
    weaknessesEl.insertAdjacentHTML('beforeend', `<li>${esc(w)}</li>`);
  });

  const recsEl = document.getElementById('focus-recs');
  (fs.recommendations || []).slice(0, 4).forEach(r => {
    recsEl.insertAdjacentHTML('beforeend', `<li>${esc(r)}</li>`);
  });
}

// ── Career Direction ──────────────────────────────────────────────────────────
function renderCareerDirection(cd) {
  if (!cd) return;
  document.getElementById('career-primary').textContent   = cd.primary || '—';
  document.getElementById('career-secondary').textContent = cd.secondary || '—';
  document.getElementById('career-reasoning').textContent = cd.reasoning || '';
  const conf = cd.confidence ?? 0;
  document.getElementById('confidence-pct').textContent = `${conf}%`;
  const bar = document.getElementById('confidence-bar');
  setTimeout(() => animateBar(bar, conf), 300);
}

// ── Resume Rating ─────────────────────────────────────────────────────────────
function renderResumeRating(rr) {
  if (!rr) return;
  const overall = rr.overall ?? 0;
  const overallEl = document.getElementById('overall-score');
  overallEl.textContent = overall;
  overallEl.style.color = overall >= 70 ? 'var(--green)' : overall >= 50 ? 'var(--amber)' : 'var(--red)';

  const ss = rr.subscores || {};
  const explanations = rr.explanations || {};
  const grid = document.getElementById('subscores-grid');
  const keys = ['skills', 'projects', 'certifications', 'experience', 'presentation', 'focus'];

  keys.forEach((key, idx) => {
    const val = ss[key] ?? 0;
    const row = document.createElement('div');
    row.className = 'subscore-row';
    row.title = explanations[key] || '';
    row.innerHTML = `
      <span class="subscore-label">${esc(key.charAt(0).toUpperCase() + key.slice(1))}</span>
      <div class="subscore-bar-outer">
        <div class="subscore-bar-inner ${scoreColor(val)}" id="ssbar-${key}" style="width:0%"></div>
      </div>
      <span class="subscore-val">${val}</span>`;
    grid.appendChild(row);
    setTimeout(() => animateBar(document.getElementById(`ssbar-${key}`), val), 300 + idx * 80);
  });
}

// ── Skill Gap ─────────────────────────────────────────────────────────────────
function renderSkillGap(sg) {
  if (!sg) return;
  document.getElementById('skill-gap-role').textContent =
    sg.role ? `— ${sg.role}` : '';

  const assessEl = document.getElementById('skill-assessment');
  if (sg.current_skill_assessment && assessEl) {
    assessEl.textContent = sg.current_skill_assessment;
  }

  const grid = document.getElementById('skill-gap-grid');
  (sg.missing_skills || []).forEach(skill => {
    const pClass = `priority-${(skill.priority || 'Medium').toLowerCase()}`;
    const item = document.createElement('div');
    item.className = 'skill-gap-item';
    item.innerHTML = `
      <div class="skill-priority-badge ${pClass}">${esc(skill.priority || 'Medium')}</div>
      <div class="skill-name">${esc(skill.skill || '')}</div>
      <div class="skill-why">${esc(skill.why_it_matters || '')}</div>
      ${skill.learning_resource
        ? `<div class="skill-resource">${esc(skill.learning_resource)}</div>`
        : ''}`;
    grid.appendChild(item);
  });

  // Partial skills section
  const partials = sg.partially_present_skills || [];
  if (partials.length) {
    const section = document.getElementById('partial-skills-section');
    const partGrid = document.getElementById('partial-skills-grid');
    if (section) section.style.display = '';
    partials.forEach(p => {
      const item = document.createElement('div');
      item.className = 'partial-skill-item';
      item.innerHTML = `
        <div class="partial-skill-name">${esc(p.skill)}</div>
        <div class="partial-skill-row">Now: ${esc(p.current_level)}</div>
        <div class="partial-skill-row">Need: <strong>${esc(p.needed_level)}</strong></div>`;
      if (partGrid) partGrid.appendChild(item);
    });
  }
}

// ── Resume Intelligence ───────────────────────────────────────────────────────
function renderResumeIntelligence(ri) {
  if (!ri) return;
  const grid = document.getElementById('intel-grid');

  if (ri.summary) {
    grid.insertAdjacentHTML('beforeend', `
      <div class="intel-summary">
        <div class="intel-section-title">Professional Summary</div>
        <p>${esc(ri.summary)}</p>
      </div>`);
  }

  const tagSections = [
    { label: 'Skills',          items: ri.skills },
    { label: 'Projects',        items: ri.projects },
    { label: 'Experience',      items: ri.experience },
    { label: 'Education',       items: ri.education },
    { label: 'Certifications',  items: ri.certifications },
    { label: 'Achievements',    items: ri.achievements },
  ];

  tagSections.forEach(({ label, items }) => {
    if (!items || !items.length) return;
    const section = document.createElement('div');
    section.innerHTML = `<div class="intel-section-title">${esc(label)}</div>`;
    const tagsWrap = document.createElement('div');
    tagsWrap.className = 'intel-tags';
    items.forEach(item => {
      tagsWrap.insertAdjacentHTML('beforeend', `<span class="intel-tag">${esc(item)}</span>`);
    });
    section.appendChild(tagsWrap);
    grid.appendChild(section);
  });
}

// ── Roadmap ───────────────────────────────────────────────────────────────────
function renderRoadmap(roadmap) {
  if (!roadmap) return;

  const summaryEl = document.getElementById('milestone-summary');
  if (roadmap.milestone_summary && summaryEl) {
    summaryEl.textContent = roadmap.milestone_summary;
  }

  const phases = [
    { id: 'roadmap-30', steps: roadmap.day_30 },
    { id: 'roadmap-60', steps: roadmap.day_60 },
    { id: 'roadmap-90', steps: roadmap.day_90 },
  ];

  phases.forEach(({ id, steps }) => {
    const el = document.getElementById(id);
    if (!el || !steps) return;
    steps.forEach(step => {
      const li = document.createElement('li');
      li.className = 'phase-step';
      li.innerHTML = `
        <div class="phase-step-action">${esc(step.action || '')}</div>
        <div class="phase-step-details">${esc(step.details || '')}</div>
        <div class="phase-step-outcome">${esc(step.outcome || '')}</div>
        ${step.time_commitment
          ? `<div class="phase-step-time">${esc(step.time_commitment)}</div>`
          : ''}`;
      el.appendChild(li);
    });
  });
}

// ── Certifications ────────────────────────────────────────────────────────────
function renderCertifications(certs) {
  const list = document.getElementById('cert-list');
  if (!certs.length) {
    list.innerHTML = '<p style="color:var(--text-dim);font-size:14px">No certifications recommended.</p>';
    return;
  }
  certs.forEach(cert => {
    const levelClass = `level-${(cert.level || 'Beginner').toLowerCase()}`;
    const item = document.createElement('div');
    item.className = 'cert-item';
    item.innerHTML = `
      <div class="cert-top">
        <div class="cert-name">${esc(cert.name || '')}</div>
        <div class="cert-level-badge ${levelClass}">${esc(cert.level || 'Beginner')}</div>
      </div>
      <div class="cert-provider">${esc(cert.provider || '')}</div>
      <div class="cert-reason">${esc(cert.why_recommended || '')}
        <span style="color:var(--green)"> → ${esc(cert.expected_benefit || '')}</span>
      </div>
      ${cert.approximate_cost ? `<div class="cert-cost">${esc(cert.approximate_cost)}</div>` : ''}
      ${cert.url ? `<a class="cert-link" href="${esc(cert.url)}" target="_blank" rel="noopener noreferrer">View certification</a>` : ''}`;
    list.appendChild(item);
  });
}

// ── Projects ──────────────────────────────────────────────────────────────────
function renderProjects(projects) {
  const list = document.getElementById('project-list');
  if (!projects.length) {
    list.innerHTML = '<p style="color:var(--text-dim);font-size:14px">No projects recommended.</p>';
    return;
  }
  projects.forEach(proj => {
    const diffClass = `diff-${(proj.difficulty || 'Intermediate').toLowerCase()}`;
    const techStack = (proj.tech_stack || []).map(s =>
      `<span class="project-skill-tag">${esc(s)}</span>`).join('');
    const skills = (proj.skills_learned || []).map(s =>
      `<span class="project-skill-tag" style="background:var(--green-dim);color:var(--green);border-color:rgba(63,185,80,0.2)">${esc(s)}</span>`).join('');
    const item = document.createElement('div');
    item.className = 'project-item';
    item.innerHTML = `
      <div class="project-top">
        <div class="project-name">${esc(proj.name || '')}</div>
        <div class="project-diff-badge ${diffClass}">${esc(proj.difficulty || 'Intermediate')}</div>
      </div>
      <div class="project-desc">${esc(proj.description || '')}</div>
      ${techStack ? `<div class="project-tech-label">Tech stack</div><div class="project-skills">${techStack}</div>` : ''}
      ${skills    ? `<div class="project-tech-label">Skills learned</div><div class="project-skills">${skills}</div>` : ''}
      <div class="project-why">${esc(proj.why_it_helps || '')}</div>
      ${proj.github_starter ? `<div class="skill-resource">Suggested repo: ${esc(proj.github_starter)}</div>` : ''}`;
    list.appendChild(item);
  });
}

// ── Opportunities ─────────────────────────────────────────────────────────────
function renderOpportunities(opportunities) {
  const grid = document.getElementById('opportunity-grid');
  if (!opportunities.length) {
    grid.innerHTML = '<p style="color:var(--text-dim);font-size:14px">No opportunities found.</p>';
    return;
  }
  opportunities.forEach(opp => {
    const item = document.createElement('div');
    item.className = 'opportunity-item';
    item.innerHTML = `
      ${opp.type ? `<div class="opportunity-type">${esc(opp.type)}</div>` : ''}
      <div class="opportunity-name">${esc(opp.platform || '')}</div>
      <div class="opportunity-audience">${esc(opp.target_audience || '')}</div>
      <div class="opportunity-why">${esc(opp.why_useful || '')}</div>
      ${opp.url
        ? `<a class="opportunity-link" href="${esc(opp.url)}" target="_blank" rel="noopener noreferrer">
             ${esc(opp.url.replace(/^https?:\/\//, ''))}
           </a>`
        : ''}`;
    grid.appendChild(item);
  });
}
