/**
 * Career Guardian AI — Frontend Logic
 * Handles: file upload, drag-drop, API call, dashboard rendering
 */
'use strict';

// ── DOM References ────────────────────────────────────────────
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
const loadingSteps   = document.querySelectorAll('.loading-step');

let selectedFile = null;

// ── Utility ───────────────────────────────────────────────────
function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function showError(msg) {
  errorMessage.textContent = msg;
  errorBanner.classList.remove('hidden');
}

function hideError() {
  errorBanner.classList.add('hidden');
}

function scoreColor(score) {
  if (score >= 70) return 'score-color-high';
  if (score >= 45) return 'score-color-mid';
  return 'score-color-low';
}

function dialColor(score) {
  if (score >= 70) return 'dial-high';
  if (score >= 45) return 'dial-mid';
  return 'dial-low';
}

function animateBar(el, pct) {
  // Defer to next frame so CSS transition fires
  requestAnimationFrame(() => {
    el.style.width = `${Math.min(100, Math.max(0, pct))}%`;
  });
}

function dialOffset(score) {
  // Full circle circumference = 2 * π * 80 ≈ 502
  const circumference = 502;
  return circumference - (score / 100) * circumference;
}

function esc(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

// ── File Handling ────────────────────────────────────────────
function setFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
    showError('Only PDF files are accepted.');
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    showError('File exceeds 10 MB. Please compress your PDF.');
    return;
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

fileInput.addEventListener('change', (e) => {
  if (e.target.files[0]) setFile(e.target.files[0]);
});

removeFileBtn.addEventListener('click', clearFile);

// Drag and drop
dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
});
dropZone.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') fileInput.click();
});

// ── Loading Step Animator ─────────────────────────────────────
let stepInterval = null;
let currentStep = 0;

function startLoadingAnimation() {
  currentStep = 0;
  loadingSteps.forEach((s, i) => {
    s.classList.remove('active', 'done');
    if (i === 0) s.classList.add('active');
  });
  stepInterval = setInterval(() => {
    if (currentStep < loadingSteps.length - 1) {
      loadingSteps[currentStep].classList.remove('active');
      loadingSteps[currentStep].classList.add('done');
      currentStep++;
      loadingSteps[currentStep].classList.add('active');
    }
  }, 3500);
}

function stopLoadingAnimation() {
  clearInterval(stepInterval);
  loadingSteps.forEach(s => s.classList.remove('active', 'done'));
}

// ── Section Switcher ──────────────────────────────────────────
function show(section) {
  uploadSection.classList.add('hidden');
  loadingSection.classList.add('hidden');
  resultsSection.classList.add('hidden');
  section.classList.remove('hidden');
}

// ── API Call ─────────────────────────────────────────────────
analyseBtn.addEventListener('click', async () => {
  if (!selectedFile) return;
  hideError();
  show(loadingSection);
  startLoadingAnimation();

  const formData = new FormData();
  formData.append('resume', selectedFile);

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 90000);

    const response = await fetch('http://127.0.0.1:8000/api/analyze', {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    clearTimeout(timeout);

    const data = await response.json();

    if (!response.ok) {
      const msg = data?.detail?.message || data?.message || 'Analysis failed. Please try again.';
      stopLoadingAnimation();
      show(uploadSection);
      showError(msg);
      return;
    }

    stopLoadingAnimation();
    renderDashboard(data);
    show(resultsSection);
    window.scrollTo({ top: 0, behavior: 'smooth' });

  } catch (err) {
    stopLoadingAnimation();
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

// ── Dashboard Renderer ────────────────────────────────────────
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
}

function renderHeader(data) {
  const ri = data.resume_intelligence || {};
  const name = ri.name || 'Your Resume';
  document.getElementById('dash-candidate-name').textContent =
    `${name} — ${data.career_direction?.primary || 'Career Analysis'}`;
}

// ── Focus Score ───────────────────────────────────────────────
function renderFocusScore(fs) {
  if (!fs) return;
  const score = fs.score ?? 0;

  // Dial
  const dialCircle = document.getElementById('focus-dial-circle');
  const scoreText  = document.getElementById('dial-score-text');
  const catText    = document.getElementById('dial-category-text');

  scoreText.textContent = score;
  catText.textContent   = fs.category || '';
  dialCircle.classList.add(dialColor(score));

  setTimeout(() => {
    dialCircle.style.strokeDashoffset = dialOffset(score);
  }, 200);

  // Reasoning
  document.getElementById('focus-reasoning').textContent = fs.reasoning || '';

  // Breakdown bars
  const bars = [
    ['bar-skill-align',    'val-skill-align',    fs.skill_alignment],
    ['bar-project-align',  'val-project-align',  fs.project_alignment],
    ['bar-cert-align',     'val-cert-align',      fs.certification_alignment],
    ['bar-exp-align',      'val-exp-align',       fs.experience_alignment],
    ['bar-consistency',    'val-consistency',     fs.resume_consistency],
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

  // Strengths
  const strengthsEl = document.getElementById('focus-strengths');
  (fs.strengths || []).slice(0, 4).forEach(s => {
    strengthsEl.insertAdjacentHTML('beforeend', `<li>${esc(s)}</li>`);
  });

  // Weaknesses
  const weaknessesEl = document.getElementById('focus-weaknesses');
  (fs.weaknesses || []).slice(0, 4).forEach(w => {
    weaknessesEl.insertAdjacentHTML('beforeend', `<li>${esc(w)}</li>`);
  });

  // Recommendations
  const recsEl = document.getElementById('focus-recs');
  (fs.recommendations || []).slice(0, 4).forEach(r => {
    recsEl.insertAdjacentHTML('beforeend', `<li>${esc(r)}</li>`);
  });
}

// ── Career Direction ──────────────────────────────────────────
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

// ── Resume Rating ─────────────────────────────────────────────
function renderResumeRating(rr) {
  if (!rr) return;

  const overall = rr.overall ?? 0;
  const overallEl = document.getElementById('overall-score');
  overallEl.textContent = overall;

  // Colour overall score
  if (overall >= 70) overallEl.style.color = 'var(--green)';
  else if (overall >= 50) overallEl.style.color = 'var(--amber)';
  else overallEl.style.color = 'var(--red)';

  const ss = rr.subscores || {};
  const explanations = rr.explanations || {};
  const grid = document.getElementById('subscores-grid');
  const keys = ['skills', 'projects', 'certifications', 'experience', 'presentation', 'focus'];

  keys.forEach((key, idx) => {
    const val = ss[key] ?? 0;
    const colorClass = scoreColor(val);
    const row = document.createElement('div');
    row.className = 'subscore-row';
    row.title = explanations[key] || '';
    row.innerHTML = `
      <span class="subscore-label">${esc(key.charAt(0).toUpperCase() + key.slice(1))}</span>
      <div class="subscore-bar-outer">
        <div class="subscore-bar-inner ${colorClass}" id="ssbar-${key}" style="width:0%"></div>
      </div>
      <span class="subscore-val">${val}</span>
    `;
    grid.appendChild(row);
    setTimeout(() => animateBar(document.getElementById(`ssbar-${key}`), val), 300 + idx * 80);
  });
}

// ── Skill Gap ─────────────────────────────────────────────────
function renderSkillGap(sg) {
  if (!sg) return;
  document.getElementById('skill-gap-role').textContent = sg.role ? `— ${sg.role}` : '';

  const grid = document.getElementById('skill-gap-grid');
  const skills = sg.missing_skills || [];

  // Sort: High → Medium → Low
  const order = { High: 0, Medium: 1, Low: 2 };
  const sorted = [...skills].sort((a, b) => (order[a.priority] ?? 1) - (order[b.priority] ?? 1));

  sorted.forEach(skill => {
    const pClass = `priority-${(skill.priority || 'Medium').toLowerCase()}`;
    const item = document.createElement('div');
    item.className = 'skill-gap-item';
    item.innerHTML = `
      <div class="skill-priority-badge ${pClass}">${esc(skill.priority || 'Medium')}</div>
      <div class="skill-name">${esc(skill.skill || '')}</div>
      <div class="skill-why">${esc(skill.why_it_matters || '')}</div>
    `;
    grid.appendChild(item);
  });
}

// ── Resume Intelligence ───────────────────────────────────────
function renderResumeIntelligence(ri) {
  if (!ri) return;
  const grid = document.getElementById('intel-grid');

  // Summary (full width)
  if (ri.summary) {
    grid.insertAdjacentHTML('beforeend', `
      <div class="intel-summary">
        <div class="intel-section-title">Professional Summary</div>
        <p>${esc(ri.summary)}</p>
      </div>
    `);
  }

  // Tag sections
  const tagSections = [
    { label: 'Skills',          items: ri.skills          },
    { label: 'Projects',        items: ri.projects        },
    { label: 'Experience',      items: ri.experience      },
    { label: 'Education',       items: ri.education       },
    { label: 'Certifications',  items: ri.certifications  },
    { label: 'Achievements',    items: ri.achievements    },
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

// ── Roadmap ───────────────────────────────────────────────────
function renderRoadmap(roadmap) {
  if (!roadmap) return;
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
      `;
      el.appendChild(li);
    });
  });
}

// ── Certifications ────────────────────────────────────────────
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
      <div class="cert-reason">${esc(cert.why_recommended || '')} <span style="color:var(--green)">→ ${esc(cert.expected_benefit || '')}</span></div>
    `;
    list.appendChild(item);
  });
}

// ── Projects ──────────────────────────────────────────────────
function renderProjects(projects) {
  const list = document.getElementById('project-list');
  if (!projects.length) {
    list.innerHTML = '<p style="color:var(--text-dim);font-size:14px">No projects recommended.</p>';
    return;
  }
  projects.forEach(proj => {
    const diffClass = `diff-${(proj.difficulty || 'Intermediate').toLowerCase()}`;
    const skills = (proj.skills_learned || []).map(s => `<span class="project-skill-tag">${esc(s)}</span>`).join('');
    const item = document.createElement('div');
    item.className = 'project-item';
    item.innerHTML = `
      <div class="project-top">
        <div class="project-name">${esc(proj.name || '')}</div>
        <div class="project-diff-badge ${diffClass}">${esc(proj.difficulty || 'Intermediate')}</div>
      </div>
      <div class="project-desc">${esc(proj.description || '')}</div>
      <div class="project-skills">${skills}</div>
      <div class="project-why">${esc(proj.why_it_helps || '')}</div>
    `;
    list.appendChild(item);
  });
}

// ── Opportunities ─────────────────────────────────────────────
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
      <div class="opportunity-name">${esc(opp.platform || '')}</div>
      <div class="opportunity-audience">${esc(opp.target_audience || '')}</div>
      <div class="opportunity-why">${esc(opp.why_useful || '')}</div>
      ${opp.url ? `<a class="opportunity-link" href="${esc(opp.url)}" target="_blank" rel="noopener noreferrer">${esc(opp.url.replace(/^https?:\/\//, ''))}</a>` : ''}
    `;
    grid.appendChild(item);
  });
}
