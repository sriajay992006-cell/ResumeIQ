'use strict';

// ── STATE ────────────────────────────────────────────────
let experiences = [], educations = [], certs = [], projects = [];
let expCounter = 0, eduCounter = 0, certCounter = 0, projCounter = 0;
let activeAIChip = 'summary';
let lastAIContent = '', lastAIType = '';
let uploadedFile = null;
let currentResumeId = null;
let currentATSResult = null;
let currentJobFilter = 'all';
let allJobs = [];

// ── UTILS ─────────────────────────────────────────────────
function showToast(msg, type = '') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show' + (type ? ' ' + type : '');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove('show'), 3500);
}
function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function scoreColor(s) {
  return s >= 75 ? 'var(--green)' : s >= 50 ? 'var(--amber)' : 'var(--red)';
}
function statusMeta(status) {
  const map = {
    saved:     { label: '📌 Saved',     cls: 'status-saved' },
    applied:   { label: '📤 Applied',   cls: 'status-applied' },
    interview: { label: '💬 Interview', cls: 'status-interview' },
    offer:     { label: '🎉 Offer',     cls: 'status-offer' },
    rejected:  { label: '❌ Rejected',  cls: 'status-rejected' },
  };
  return map[status] || map.saved;
}

// ── TABS ──────────────────────────────────────────────────
function switchTab(name) {
  const names = ['builder','ats','ai','jobs'];
  document.querySelectorAll('.tab').forEach((t,i) => t.classList.toggle('active', names[i] === name));
  names.forEach(t => {
    const el = document.getElementById('tab-' + t);
    if (el) el.classList.toggle('active', t === name);
  });
  const isJobs = name === 'jobs';
  document.getElementById('resume-preview-wrapper').style.display = isJobs ? 'none' : 'block';
  document.getElementById('ats-result-card').style.display = isJobs ? 'none' : 'block';
  const aiCard = document.getElementById('ai-helper-card');
  if (isJobs) aiCard.style.display = 'none';
  document.getElementById('jobs-panel').style.display = isJobs ? 'block' : 'none';
  if (isJobs) loadJobsPanel();
}

// ── FILE UPLOAD ───────────────────────────────────────────
const uploadZone = document.getElementById('uploadZone');
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('dragover'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', e => { e.preventDefault(); uploadZone.classList.remove('dragover'); if (e.dataTransfer.files[0]) applyFile(e.dataTransfer.files[0]); });

function handleFileSelect(input) { if (input.files[0]) applyFile(input.files[0]); }
function applyFile(f) {
  uploadedFile = f;
  uploadZone.classList.add('has-file');
  uploadZone.innerHTML = `<div class="upload-icon-sm">✅</div><span>${esc(f.name)}</span><span style="font-size:0.72rem;color:var(--green);">File ready — click Analyze below</span>`;
  showToast('✅ ' + f.name + ' ready', 'success');
}

// ── EXPERIENCE ────────────────────────────────────────────
function addExperience(data={}) {
  const id = expCounter++;
  experiences.push({ id, title:'', company:'', start:'', end:'', bullets:'', ...data });
  renderExperiences();
}
function renderExperiences() {
  const list = document.getElementById('exp-list');
  list.innerHTML = '';
  experiences.forEach(exp => {
    const div = document.createElement('div');
    div.className = 'entry-card';
    div.innerHTML = `
      <button class="remove-btn" onclick="removeExp(${exp.id})">✕</button>
      <div class="field-row">
        <div class="field-group"><label>Job Title</label><input type="text" value="${esc(exp.title)}" placeholder="Software Engineer" oninput="updateExp(${exp.id},'title',this.value)"></div>
        <div class="field-group"><label>Company</label><input type="text" value="${esc(exp.company)}" placeholder="Acme Corp" oninput="updateExp(${exp.id},'company',this.value)"></div>
      </div>
      <div class="field-row">
        <div class="field-group"><label>Start Date</label><input type="text" value="${esc(exp.start)}" placeholder="Jan 2021" oninput="updateExp(${exp.id},'start',this.value)"></div>
        <div class="field-group"><label>End Date</label><input type="text" value="${esc(exp.end)}" placeholder="Present" oninput="updateExp(${exp.id},'end',this.value)"></div>
      </div>
      <div class="field-group"><label>Responsibilities / Achievements</label>
        <textarea placeholder="• Led migration to microservices, reducing latency by 40%&#10;• Managed team of 4 engineers..." oninput="updateExp(${exp.id},'bullets',this.value)">${esc(exp.bullets)}</textarea>
      </div>`;
    list.appendChild(div);
  });
  updatePreview();
}
function updateExp(id,field,val) { const e=experiences.find(x=>x.id===id); if(e){e[field]=val;updatePreview();} }
function removeExp(id) { experiences=experiences.filter(e=>e.id!==id); renderExperiences(); }

// ── EDUCATION ─────────────────────────────────────────────
function addEducation(data={}) {
  const id = eduCounter++;
  educations.push({ id, degree:'', school:'', year:'', ...data });
  renderEducations();
}
function renderEducations() {
  const list = document.getElementById('edu-list');
  list.innerHTML = '';
  educations.forEach(edu => {
    const div = document.createElement('div');
    div.className = 'entry-card';
    div.innerHTML = `
      <button class="remove-btn" onclick="removeEdu(${edu.id})">✕</button>
      <div class="field-group"><label>Degree</label><input type="text" value="${esc(edu.degree)}" placeholder="B.S. Computer Science" oninput="updateEdu(${edu.id},'degree',this.value)"></div>
      <div class="field-row">
        <div class="field-group"><label>Institution</label><input type="text" value="${esc(edu.school)}" placeholder="MIT" oninput="updateEdu(${edu.id},'school',this.value)"></div>
        <div class="field-group"><label>Year</label><input type="text" value="${esc(edu.year)}" placeholder="2019" oninput="updateEdu(${edu.id},'year',this.value)"></div>
      </div>`;
    list.appendChild(div);
  });
  updatePreview();
}
function updateEdu(id,field,val) { const e=educations.find(x=>x.id===id); if(e){e[field]=val;updatePreview();} }
function removeEdu(id) { educations=educations.filter(e=>e.id!==id); renderEducations(); }

// ── CERTIFICATIONS ────────────────────────────────────────
function addCert(data={}) {
  const id = certCounter++;
  certs.push({ id, name:'', issuer:'', date:'', ...data });
  renderCerts();
}
function renderCerts() {
  const list = document.getElementById('cert-list');
  list.innerHTML = '';
  certs.forEach(c => {
    const div = document.createElement('div');
    div.className = 'entry-card';
    div.innerHTML = `
      <button class="remove-btn" onclick="removeCert(${c.id})">✕</button>
      <div class="field-group"><label>Certification Name</label><input type="text" value="${esc(c.name)}" placeholder="AWS Certified Developer" oninput="updateCert(${c.id},'name',this.value)"></div>
      <div class="field-row">
        <div class="field-group"><label>Issuer</label><input type="text" value="${esc(c.issuer)}" placeholder="Amazon Web Services" oninput="updateCert(${c.id},'issuer',this.value)"></div>
        <div class="field-group"><label>Date</label><input type="text" value="${esc(c.date)}" placeholder="Mar 2024" oninput="updateCert(${c.id},'date',this.value)"></div>
      </div>`;
    list.appendChild(div);
  });
  updatePreview();
}
function updateCert(id,field,val) { const c=certs.find(x=>x.id===id); if(c){c[field]=val;updatePreview();} }
function removeCert(id) { certs=certs.filter(c=>c.id!==id); renderCerts(); }

// ── PROJECTS ──────────────────────────────────────────────
function addProject(data={}) {
  const id = projCounter++;
  projects.push({ id, name:'', technologies:'', description:'', ...data });
  renderProjects();
}
function renderProjects() {
  const list = document.getElementById('proj-list');
  list.innerHTML = '';
  projects.forEach(p => {
    const div = document.createElement('div');
    div.className = 'entry-card';
    div.innerHTML = `
      <button class="remove-btn" onclick="removeProject(${p.id})">✕</button>
      <div class="field-row">
        <div class="field-group"><label>Project Name</label><input type="text" value="${esc(p.name)}" placeholder="E-commerce Platform" oninput="updateProject(${p.id},'name',this.value)"></div>
        <div class="field-group"><label>Technologies</label><input type="text" value="${esc(p.technologies)}" placeholder="React, Node.js" oninput="updateProject(${p.id},'technologies',this.value)"></div>
      </div>
      <div class="field-group"><label>Description</label><textarea rows="2" oninput="updateProject(${p.id},'description',this.value)">${esc(p.description)}</textarea></div>`;
    list.appendChild(div);
  });
  updatePreview();
}
function updateProject(id,field,val) { const p=projects.find(x=>x.id===id); if(p){p[field]=val;updatePreview();} }
function removeProject(id) { projects=projects.filter(p=>p.id!==id); renderProjects(); }

// ── LIVE PREVIEW ──────────────────────────────────────────
function updatePreview() {
  const fname=document.getElementById('fname').value.trim();
  const lname=document.getElementById('lname').value.trim();
  const fullName=(fname+' '+lname).trim();
  const jobtitle=document.getElementById('jobtitle').value.trim();
  const email=document.getElementById('email').value.trim();
  const phone=document.getElementById('phone').value.trim();
  const location=document.getElementById('location').value.trim();
  const website=document.getElementById('website').value.trim();
  const summary=document.getElementById('summary').value.trim();
  const skills=document.getElementById('skills').value.trim();

  if (!fullName&&!jobtitle&&!summary&&!experiences.length&&!educations.length&&!skills) {
    document.getElementById('resume-preview').innerHTML=`<div class="preview-placeholder"><svg width="48" height="48" fill="none" viewBox="0 0 48 48"><rect x="8" y="6" width="32" height="36" rx="3" stroke="#94A3B8" stroke-width="2"/><line x1="14" y1="16" x2="34" y2="16" stroke="#94A3B8" stroke-width="2" stroke-linecap="round"/><line x1="14" y1="22" x2="34" y2="22" stroke="#94A3B8" stroke-width="2" stroke-linecap="round"/><line x1="14" y1="28" x2="26" y2="28" stroke="#94A3B8" stroke-width="2" stroke-linecap="round"/></svg><p>Start filling in your details and your resume will appear here in real time.</p></div>`;
    return;
  }

  let html='';
  if(fullName) html+=`<div class="preview-name">${esc(fullName)}</div>`;
  if(jobtitle) html+=`<div class="preview-title">${esc(jobtitle)}</div>`;
  const contacts=[email,phone,location,website].filter(Boolean);
  if(contacts.length) html+=`<div class="preview-contact">${contacts.map(c=>`<span>• ${esc(c)}</span>`).join('')}</div>`;
  if(summary) html+=`<div class="preview-section-title">Professional Summary</div><p class="preview-summary">${esc(summary)}</p>`;
  if(experiences.length) {
    html+=`<div class="preview-section-title">Experience</div>`;
    experiences.forEach(exp=>{
      html+=`<div style="margin-bottom:1rem;">`;
      if(exp.title) html+=`<div class="preview-exp-title">${esc(exp.title)}</div>`;
      html+=`<div class="preview-exp-meta">`;
      if(exp.company) html+=`<span style="font-weight:600;">${esc(exp.company)}</span>`;
      const dates=[exp.start,exp.end].filter(Boolean).join(' – ');
      if(dates) html+=`<span>${esc(dates)}</span>`;
      html+=`</div>`;
      if(exp.bullets){const lines=exp.bullets.split('\n').map(l=>l.replace(/^[•\-\*]\s*/,'').trim()).filter(Boolean);if(lines.length)html+=`<ul class="preview-exp-bullets">${lines.map(l=>`<li>${esc(l)}</li>`).join('')}</ul>`;}
      html+=`</div>`;
    });
  }
  if(educations.length) {
    html+=`<div class="preview-section-title">Education</div>`;
    educations.forEach(edu=>{
      html+=`<div style="margin-bottom:0.75rem;">`;
      if(edu.degree) html+=`<div class="preview-edu-name">${esc(edu.degree)}</div>`;
      const meta=[edu.school,edu.year].filter(Boolean).join(' · ');
      if(meta) html+=`<div class="preview-edu-meta">${esc(meta)}</div>`;
      html+=`</div>`;
    });
  }
  if(skills){const sl=skills.split(',').map(s=>s.trim()).filter(Boolean);html+=`<div class="preview-section-title">Skills</div><div class="preview-skills-wrap">${sl.map(s=>`<span class="preview-skill-tag">${esc(s)}</span>`).join('')}</div>`;}
  if(certs.length){
    html+=`<div class="preview-section-title">Certifications</div>`;
    certs.forEach(c=>{if(c.name){const m=[c.issuer,c.date].filter(Boolean).join(' · ');html+=`<div class="preview-cert"><strong>${esc(c.name)}</strong>${m?' — '+esc(m):''}</div>`;}});
  }
  if(projects.length){
    html+=`<div class="preview-section-title">Projects</div>`;
    projects.forEach(p=>{if(p.name){html+=`<div style="margin-bottom:0.75rem;"><div class="preview-edu-name">${esc(p.name)}</div>`;if(p.technologies)html+=`<div class="preview-edu-meta">Tech: ${esc(p.technologies)}</div>`;if(p.description)html+=`<p class="preview-summary" style="margin-top:0.2rem;">${esc(p.description)}</p>`;html+=`</div>`;}});
  }
  document.getElementById('resume-preview').innerHTML=html;
}

// ── RESUME PAYLOAD ────────────────────────────────────────
function getResumeText() {
  const fname=document.getElementById('fname').value.trim();
  const lname=document.getElementById('lname').value.trim();
  const jobtitle=document.getElementById('jobtitle').value.trim();
  const summary=document.getElementById('summary').value.trim();
  const skills=document.getElementById('skills').value.trim();
  const expText=experiences.map(e=>`${e.title} at ${e.company} (${e.start}–${e.end}): ${e.bullets}`).join('\n');
  const eduText=educations.map(e=>`${e.degree} from ${e.school} (${e.year})`).join('\n');
  const certText=certs.map(c=>`${c.name} by ${c.issuer}`).join('\n');
  return `Name: ${fname} ${lname}\nTitle: ${jobtitle}\nSummary: ${summary}\nExperience:\n${expText}\nEducation:\n${eduText}\nSkills: ${skills}\nCertifications: ${certText}`;
}

function getResumePayload() {
  const fname=document.getElementById('fname').value.trim();
  const lname=document.getElementById('lname').value.trim();
  return {
    id: currentResumeId,
    name: (fname+' '+lname).trim()||'My Resume',
    personalInfo: { fullName:(fname+' '+lname).trim(), jobTitle:document.getElementById('jobtitle').value.trim(), email:document.getElementById('email').value.trim(), phone:document.getElementById('phone').value.trim(), location:document.getElementById('location').value.trim(), linkedin:document.getElementById('website').value.trim() },
    summary: document.getElementById('summary').value.trim(),
    experience: experiences.map(e=>({position:e.title,company:e.company,startDate:e.start,endDate:e.end,description:e.bullets})),
    education: educations.map(e=>({degree:e.degree,institution:e.school,graduationYear:e.year})),
    skills: document.getElementById('skills').value.split(',').map(s=>s.trim()).filter(Boolean).map(n=>({name:n,level:'Intermediate'})),
    certifications: certs.map(c=>({name:c.name,issuer:c.issuer,date:c.date})),
    projects: projects.map(p=>({name:p.name,technologies:p.technologies,description:p.description}))
  };
}

// ── SAVE RESUME ───────────────────────────────────────────
document.getElementById('saveBtn').addEventListener('click', async () => {
  const payload = getResumePayload();
  try {
    const res = await fetch('/api/resumes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data = await res.json();
    if(data.success){currentResumeId=data.id;showToast('✅ Resume saved!','success');}
    else showToast('Save failed: '+(data.error||'Unknown'),'error');
  } catch(e){ showToast('Network error','error'); }
});

// ── LOAD MODAL ────────────────────────────────────────────
document.getElementById('loadBtn').addEventListener('click', async () => {
  const list = document.getElementById('saved-list');
  list.innerHTML = '<div style="text-align:center;padding:1rem;color:var(--slate)">Loading…</div>';
  document.getElementById('loadModal').style.display = 'flex';
  try {
    const resumes = await fetch('/api/resumes').then(r=>r.json());
    if(!resumes.length){list.innerHTML='<div style="text-align:center;padding:2rem;color:var(--slate-light)">No saved resumes yet.</div>';return;}
    list.innerHTML = resumes.map(r=>`
      <div class="saved-resume-row" onclick="loadResume(${r.id})">
        <div><div class="saved-resume-name">${esc(r.name)}</div><div class="saved-resume-date">${new Date(r.updated_at).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})}</div></div>
        <div class="saved-resume-actions" onclick="event.stopPropagation()">
          <button class="btn btn-primary" style="font-size:0.72rem;padding:0.3rem 0.65rem;" onclick="loadResume(${r.id})">Load</button>
          <button class="btn" style="background:#FEE2E2;color:var(--red);font-size:0.72rem;padding:0.3rem 0.65rem;border:none;" onclick="deleteResume(${r.id},this)">Delete</button>
        </div>
      </div>`).join('');
  } catch(e){ list.innerHTML='<div style="text-align:center;color:var(--red)">Failed to load</div>'; }
});

function closeLoadModal() { document.getElementById('loadModal').style.display='none'; }

async function loadResume(id) {
  try {
    const data = await fetch(`/api/resumes/${id}`).then(r=>r.json());
    if(data.error){showToast(data.error,'error');return;}
    currentResumeId = data.id;
    const pi = data.personalInfo||{};
    const parts = (pi.fullName||'').split(' ');
    document.getElementById('fname').value = parts[0]||'';
    document.getElementById('lname').value = parts.slice(1).join(' ')||'';
    document.getElementById('jobtitle').value = pi.jobTitle||'';
    document.getElementById('email').value = pi.email||'';
    document.getElementById('phone').value = pi.phone||'';
    document.getElementById('location').value = pi.location||'';
    document.getElementById('website').value = pi.linkedin||'';
    document.getElementById('summary').value = data.summary||'';
    document.getElementById('skills').value = (data.skills||[]).map(s=>s.name).join(', ');
    experiences=(data.experience||[]).map(e=>({id:expCounter++,title:e.position||'',company:e.company||'',start:e.startDate||'',end:e.endDate||'',bullets:e.description||''}));
    educations=(data.education||[]).map(e=>({id:eduCounter++,degree:e.degree||'',school:e.institution||'',year:e.graduationYear||''}));
    certs=(data.certifications||[]).map(c=>({id:certCounter++,name:c.name||'',issuer:c.issuer||'',date:c.date||''}));
    projects=(data.projects||[]).map(p=>({id:projCounter++,name:p.name||'',technologies:p.technologies||'',description:p.description||''}));
    renderExperiences(); renderEducations(); renderCerts(); renderProjects(); updatePreview();
    closeLoadModal(); switchTab('builder');
    showToast('✅ Resume loaded!','success');
  } catch(e){ showToast('Load error','error'); }
}

async function deleteResume(id, btn) {
  if(!confirm('Delete this resume permanently?'))return;
  await fetch(`/api/resumes/${id}`,{method:'DELETE'});
  if(currentResumeId===id) currentResumeId=null;
  btn.closest('.saved-resume-row').remove();
  showToast('Deleted','success');
}

// ── EXPORT RESUME PDF ─────────────────────────────────────
async function exportPDF() {
  const btn = document.getElementById('exportPdfBtn');
  const prev = document.getElementById('previewExportBtn');
  [btn,prev].forEach(b=>{ if(b){b.disabled=true;} });
  btn && (btn.textContent='⏳ Generating…');
  try {
    const res = await fetch('/api/export-pdf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(getResumePayload())});
    if(!res.ok){showToast('PDF export failed','error');return;}
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const name = (document.getElementById('fname').value+'_'+document.getElementById('lname').value+'_Resume.pdf').replace(/\s+/g,'_')||'Resume.pdf';
    a.href=url; a.download=name; a.click();
    URL.revokeObjectURL(url);
    showToast('✅ PDF downloaded!','success');
  } catch(e){ showToast('Export error: '+e.message,'error'); }
  finally { [btn,prev].forEach(b=>{if(b)b.disabled=false;}); if(btn) btn.textContent='⬇ Export PDF'; }
}
document.getElementById('exportPdfBtn').addEventListener('click', exportPDF);
document.getElementById('previewExportBtn').addEventListener('click', exportPDF);

// ── ATS ANALYSIS ──────────────────────────────────────────
// ── ATS MODE TOGGLE ───────────────────────────────────────
let currentAtsMode = 'review';   // 'review' | 'match'

function setAtsMode(mode) {
  currentAtsMode = mode;
  const isMatch = mode === 'match';

  document.getElementById('mode-btn-review').classList.toggle('active', !isMatch);
  document.getElementById('mode-btn-match').classList.toggle('active', isMatch);
  document.getElementById('jd-section').style.display = isMatch ? 'block' : 'none';
  document.getElementById('analyze-btn-text').textContent = isMatch
    ? '✦ Check Job Match'
    : '✦ Analyze My Resume';
  document.getElementById('mode-desc').textContent = isMatch
    ? 'Paste a job description to see how well your resume matches the role and which keywords are missing.'
    : 'Upload your resume to get an instant ATS health score — no job description needed.';
  document.getElementById('result-card-title').textContent = isMatch
    ? 'Job Match Score'
    : 'Resume Health Score';

  // Reset results panel when switching modes
  document.getElementById('ats-empty-state').style.display='flex';
  document.getElementById('health-results').style.display='none';
  document.getElementById('ats-results').style.display='none';
  document.getElementById('ats-loading').style.display='none';
  document.getElementById('ats-score-label').textContent='—';
  document.getElementById('save-report-btn').style.display='none';
  document.getElementById('export-report-btn').style.display='none';
}

// ── ATS ANALYZE ───────────────────────────────────────────
async function analyzeATS() {
  const isMatch = currentAtsMode === 'match';
  const jd = document.getElementById('job-description').value.trim();

  if(isMatch && !jd){
    showToast('⚠ Please paste a job description first','error');
    return;
  }

  const hasResume = uploadedFile || getResumeText().trim().length > 50;
  if(!hasResume){
    showToast('⚠ Upload a resume file or fill in the Resume Builder first','error');
    return;
  }

  const btn=document.getElementById('analyze-btn');
  const btnText=document.getElementById('analyze-btn-text');
  btn.disabled=true;
  btnText.textContent='Analyzing…';
  document.getElementById('ats-loading-text').textContent = isMatch
    ? 'Analyzing resume against the job description…'
    : 'Analyzing resume health and ATS readability…';

  document.getElementById('ats-empty-state').style.display='none';
  document.getElementById('ats-loading').style.display='flex';
  document.getElementById('health-results').style.display='none';
  document.getElementById('ats-results').style.display='none';
  document.getElementById('ats-score-label').textContent='Analyzing…';
  document.getElementById('save-report-btn').style.display='none';
  document.getElementById('export-report-btn').style.display='none';
  currentATSResult = null;

  try {
    let data;

    if(isMatch) {
      // ── Job Match mode ──
      if(uploadedFile) {
        const fd=new FormData();
        fd.append('resume',uploadedFile);
        fd.append('job_description',jd);
        data = await fetch('/api/ats-check',{method:'POST',body:fd}).then(r=>r.json());
      } else {
        const resumeText = getResumeText();
        data = await fetch('/api/ats-check-text',{method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({resume_text:resumeText,job_description:jd})
        }).then(r=>r.json());
      }
    } else {
      // ── Resume Review / Health Check mode ──
      if(uploadedFile) {
        const fd=new FormData();
        fd.append('resume',uploadedFile);
        data = await fetch('/api/ats-health-check',{method:'POST',body:fd}).then(r=>r.json());
      } else {
        const resumeText = getResumeText();
        data = await fetch('/api/ats-health-check',{method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({resume_text:resumeText})
        }).then(r=>r.json());
      }
    }

    if(data.error){
      showToast('⚠ '+data.error,'error');
      document.getElementById('ats-loading').style.display='none';
      document.getElementById('ats-empty-state').style.display='flex';
      return;
    }

    currentATSResult = data;

    if(data.mode === 'health') {
      renderHealthResults(data);
    } else {
      renderATSResults(data);
      document.getElementById('save-report-btn').style.display='';
      document.getElementById('export-report-btn').style.display='';
    }

  } catch(e){
    showToast('⚠ Analysis failed. Try again.','error');
    document.getElementById('ats-loading').style.display='none';
    document.getElementById('ats-empty-state').style.display='flex';
  } finally {
    btn.disabled=false;
    btnText.textContent = isMatch ? '✦ Check Job Match' : '✦ Analyze My Resume';
  }
}

// ── RENDER HEALTH RESULTS (Resume Review mode) ────────────
function renderHealthResults(r) {
  document.getElementById('ats-loading').style.display='none';
  document.getElementById('health-results').style.display='block';

  const score = r.overall || 0;
  const col = scoreColor(score);
  document.getElementById('ats-score-label').textContent = r.verdict || 'Analyzed';

  // Animate score ring
  const ring = document.getElementById('health-score-ring');
  ring.style.stroke = col;
  setTimeout(() => { ring.style.strokeDashoffset = 283 - (score / 100) * 283; }, 80);
  let cur = 0;
  const step = () => {
    cur = Math.min(cur + 2, score);
    const el = document.getElementById('health-score-number');
    el.textContent = cur; el.style.color = col;
    if(cur < score) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);

  // Health breakdown bars (6 dimensions with max values)
  const breakdown = r.breakdown || {};
  const bdEl = document.getElementById('health-breakdown');
  const colorForPct = (s, max) => scoreColor(Math.round(s / max * 100));
  bdEl.innerHTML = Object.values(breakdown).map(dim => {
    const pct = dim.max > 0 ? Math.round(dim.score / dim.max * 100) : 0;
    const bc = colorForPct(dim.score, dim.max);
    return `<div class="ats-band">
      <span class="ats-band-label">${esc(dim.label)}</span>
      <div class="ats-band-bar-wrap">
        <div class="ats-band-bar health-bar" style="width:0%;background:${bc};" data-pct="${pct}"></div>
      </div>
      <span class="ats-band-val" style="color:${bc}">${dim.score}/${dim.max}</span>
    </div>`;
  }).join('');

  // Animate bars after paint
  setTimeout(() => {
    bdEl.querySelectorAll('.health-bar').forEach(b => {
      b.style.width = b.dataset.pct + '%';
    });
  }, 120);

  // Feedback sections
  let html = '';
  if(r.critical?.length)
    html += feedSection('✗ Critical Issues', 'var(--red)', r.critical, 'bad');
  if(r.strengths?.length)
    html += feedSection('✓ Strengths', 'var(--green)', r.strengths, 'good');
  if(r.warnings?.length)
    html += feedSection('⚠ Suggestions', 'var(--amber)', r.warnings, 'warn');
  if(r.quick_fixes?.length)
    html += feedSection('⚡ Quick Fixes', 'var(--blue)', r.quick_fixes, 'warn');

  // Word count badge
  if(r.word_count)
    html += `<div style="margin-top:0.6rem;font-size:0.72rem;color:var(--slate-light);">Word count: ${r.word_count} words</div>`;

  document.getElementById('health-feedback').innerHTML = html;
  switchTab('builder');
}

function feedSection(title, color, items, cls) {
  return `<div class="feedback-section">
    <div class="feedback-title" style="color:${color};">${title}</div>
    <div class="feedback-items">
      ${items.map(s=>`<div class="feedback-item ${cls}">${esc(s)}</div>`).join('')}
    </div>
  </div>`;
}

// ── RENDER JOB MATCH RESULTS ──────────────────────────────
function renderATSResults(r) {
  document.getElementById('ats-loading').style.display='none';
  document.getElementById('ats-results').style.display='block';

  const score=r.overall||r.score||0;
  const col=scoreColor(score);
  document.getElementById('ats-score-label').textContent=r.verdict||(score>=75?'Excellent':score>=50?'Good':'Needs Work');

  const ring=document.getElementById('score-ring');
  ring.style.stroke=col;
  setTimeout(()=>{ring.style.strokeDashoffset=283-(score/100)*283;},80);
  let cur=0;
  const step=()=>{cur=Math.min(cur+2,score);const el=document.getElementById('score-number');el.textContent=cur;el.style.color=col;if(cur<score)requestAnimationFrame(step);};
  requestAnimationFrame(step);

  const bands=[{key:'keywords',bar:'bar-keywords',val:'val-keywords'},{key:'skills',bar:'bar-skills',val:'val-skills'},{key:'experience',bar:'bar-exp',val:'val-exp'},{key:'format',bar:'bar-format',val:'val-format'}];
  bands.forEach(b=>{
    const v=r[b.key]||0;const bc=scoreColor(v);
    setTimeout(()=>{document.getElementById(b.bar).style.width=v+'%';document.getElementById(b.bar).style.background=bc;},200);
    const ve=document.getElementById(b.val);ve.textContent=v+'%';ve.style.color=bc;
  });

  const kwSection=document.getElementById('keywords-section');
  const matching=r.matching_keywords||[];const missing=r.missing_keywords||[];
  if(matching.length||missing.length){
    kwSection.style.display='block';
    document.getElementById('matching-tags').innerHTML=matching.map(k=>`<span class="kw-tag kw-match">${esc(k)}</span>`).join('');
    document.getElementById('missing-tags').innerHTML=missing.map(k=>`<span class="kw-tag kw-miss">${esc(k)}</span>`).join('');
  }

  let feedHtml='';
  if(r.critical?.length)  feedHtml+=feedSection('✗ Critical Issues','var(--red)',r.critical,'bad');
  if(r.strengths?.length) feedHtml+=feedSection('✓ Strengths','var(--green)',r.strengths,'good');
  if(r.warnings?.length)  feedHtml+=feedSection('⚠ Suggestions','var(--amber)',r.warnings,'warn');
  document.getElementById('ats-feedback').innerHTML=feedHtml;

  switchTab('builder');
}

// ── SAVE ATS REPORT ───────────────────────────────────────
async function saveATSReport() {
  if(!currentATSResult){showToast('No analysis to save','error');return;}
  const jobTitle=document.getElementById('ats-job-title').value.trim()||'Untitled Role';
  const company=document.getElementById('ats-company').value.trim();
  const fname=document.getElementById('fname').value.trim();
  const lname=document.getElementById('lname').value.trim();
  const resumeName=(fname+' '+lname).trim()||'Unknown';
  const jd=document.getElementById('job-description').value.trim();

  try {
    const res=await fetch('/api/ats-reports',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_title:jobTitle,company,resume_name:resumeName,score_data:currentATSResult,job_description:jd})});
    const data=await res.json();
    if(data.success){showToast('✅ ATS report saved!','success');}
    else showToast('Save failed','error');
  } catch(e){ showToast('Network error','error'); }
}

// ── EXPORT ATS REPORT PDF ─────────────────────────────────
async function exportATSReportPDF() {
  if(!currentATSResult){showToast('No analysis to export','error');return;}
  const jobTitle=document.getElementById('ats-job-title').value.trim()||'ATS_Report';
  const company=document.getElementById('ats-company').value.trim();
  const btn=document.getElementById('export-report-btn');
  btn.disabled=true; btn.textContent='⏳…';
  try {
    const res=await fetch('/api/ats-reports/export-pdf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_title:jobTitle,company,resume_name:(document.getElementById('fname').value+' '+document.getElementById('lname').value).trim(),score_data:currentATSResult})});
    if(!res.ok){showToast('Export failed','error');return;}
    const blob=await res.blob();
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a'); a.href=url; a.download=`ATS_Report_${jobTitle.replace(/\s+/g,'_')}.pdf`; a.click();
    URL.revokeObjectURL(url);
    showToast('✅ ATS Report PDF downloaded!','success');
  } catch(e){ showToast('Export error','error'); }
  finally { btn.disabled=false; btn.textContent='⬇ Export PDF'; }
}

// ── AI WRITING HELP ───────────────────────────────────────
function selectChip(el, type) {
  document.querySelectorAll('.ai-chip').forEach(c=>c.classList.remove('active'));
  el.classList.add('active');
  activeAIChip=type;
  document.getElementById('cover-extra').style.display=type==='cover'?'block':'none';
  document.getElementById('improve-extra').style.display=type==='improve'?'block':'none';
}
function aiWriteSummary() {
  switchTab('ai');
  document.querySelectorAll('.ai-chip').forEach((c,i)=>c.classList.toggle('active',i===0));
  activeAIChip='summary';
  const ctx=`${document.getElementById('jobtitle').value} with experience in ${document.getElementById('skills').value}`;
  if(ctx.trim().length>3) document.getElementById('ai-context').value=ctx;
}
function aiSuggestSkills() {
  switchTab('ai');
  document.querySelectorAll('.ai-chip').forEach((c,i)=>c.classList.toggle('active',c.textContent.includes('Skills')));
  activeAIChip='skills';
  const jt=document.getElementById('jobtitle').value;
  if(jt) document.getElementById('ai-context').value=jt+' professional';
}

async function runAIHelp() {
  const context=document.getElementById('ai-context').value.trim();
  const type=activeAIChip;
  if(!context&&type!=='improve'){showToast('Please provide some context first','error');return;}

  const btn=document.getElementById('ai-generate-btn');
  const btnText=document.getElementById('ai-btn-text');
  btn.disabled=true; btnText.textContent='Generating…';
  document.getElementById('ai-helper-card').style.display='block';
  document.getElementById('ai-output-box').textContent='✦ Writing with Gemini AI…';

  let endpoint='', payload={};
  const resume=getResumePayload();

  if(type==='summary'){
    endpoint='/api/ai/summary';
    payload={resume,context};
  } else if(type==='bullets'){
    endpoint='/api/ai/improve-bullet';
    payload={bullet:context,role:document.getElementById('jobtitle').value||'Professional'};
  } else if(type==='skills'){
    endpoint='/api/ai/suggest-skills';
    payload={resume,jobTitle:context};
  } else if(type==='cover'){
    endpoint='/api/ai/cover-letter';
    payload={resume,jobTitle:document.getElementById('jobtitle').value,company:document.getElementById('ai-company')?.value||'',jobDescription:context};
  } else if(type==='improve'){
    endpoint='/api/ai/improve-resume';
    payload={resume_text:getResumeText(),job_description:document.getElementById('ai-jd').value||context,job_title:document.getElementById('jobtitle').value||context};
  }

  try {
    const res=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=await res.json();
    if(data.error){document.getElementById('ai-output-box').textContent='⚠ '+data.error;return;}

    let content='';
    if(type==='summary') content=data.summary||'';
    else if(type==='bullets') content=data.improved||'';
    else if(type==='skills') {
      const sk=data.skills||[];
      content=Array.isArray(sk)?sk.map(s=>`• ${s.name} (${s.level||'Intermediate'})`).join('\n'):(data.raw||'');
    }
    else if(type==='cover') content=data.cover_letter||'';
    else if(type==='improve') {
      const suggestions=data.suggestions||[];
      content=Array.isArray(suggestions)?suggestions.map((s,i)=>`${i+1}. ${s}`).join('\n\n'):(data.raw||'No suggestions generated');
    }

    lastAIContent=content; lastAIType=type;
    document.getElementById('ai-output-box').textContent=content;
  } catch(e){
    document.getElementById('ai-output-box').textContent='⚠ Failed to generate. Check your GEMINI_API_KEY.';
  } finally {
    btn.disabled=false; btnText.textContent='✦ Generate with AI';
  }
}

function applyAIContent() {
  if(!lastAIContent)return;
  if(lastAIType==='summary'){
    document.getElementById('summary').value=lastAIContent; updatePreview(); switchTab('builder');
    showToast('✓ Summary applied to your resume','success');
  } else if(lastAIType==='skills'){
    const existing=document.getElementById('skills').value;
    const newSkills=lastAIContent.split('\n').map(s=>s.replace(/^[•\d\.\s]+/,'').split('(')[0].trim()).filter(Boolean);
    const combined=[...new Set([...existing.split(',').map(s=>s.trim()),...newSkills])].filter(Boolean).join(', ');
    document.getElementById('skills').value=combined; updatePreview(); switchTab('builder');
    showToast('✓ Skills applied to your resume','success');
  } else {
    navigator.clipboard.writeText(lastAIContent).catch(()=>{});
    showToast('✓ Content copied — paste it into the relevant field','success');
  }
}
function copyAIOutput() {
  navigator.clipboard.writeText(lastAIContent||document.getElementById('ai-output-box').textContent||'').then(()=>showToast('Copied!','success'));
}

// ── BULLET IMPROVER MODAL ─────────────────────────────────
function openBulletImprover() {
  document.getElementById('bullet-input').value='';
  document.getElementById('bullet-role').value=document.getElementById('jobtitle').value;
  document.getElementById('bullet-result').style.display='none';
  document.getElementById('bullet-actions').style.display='none';
  document.getElementById('bulletModal').style.display='flex';
}
function closeBulletModal() { document.getElementById('bulletModal').style.display='none'; }

async function improveBullet() {
  const bullet=document.getElementById('bullet-input').value.trim();
  const role=document.getElementById('bullet-role').value.trim();
  if(!bullet){showToast('Please enter a bullet point','error');return;}
  const btn=document.getElementById('improveBulletBtn');
  const btnText=document.getElementById('improve-btn-text');
  btn.disabled=true; btnText.textContent='Improving…';
  try {
    const data=await fetch('/api/ai/improve-bullet',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bullet,role})}).then(r=>r.json());
    if(data.error){showToast(data.error,'error');return;}
    const el=document.getElementById('bullet-result');
    el.textContent=data.improved||''; el.style.display='block';
    document.getElementById('bullet-actions').style.display='flex';
  } catch(e){ showToast('AI error: '+e.message,'error'); }
  finally { btn.disabled=false; btnText.textContent='✦ Improve with AI'; }
}
function copyBulletResult() {
  navigator.clipboard.writeText(document.getElementById('bullet-result').textContent).then(()=>showToast('Copied!','success'));
}

// ── JOB TRACKER ───────────────────────────────────────────
async function loadJobsPanel() {
  try {
    allJobs = await fetch('/api/jobs').then(r=>r.json());
    renderJobStats();
    renderJobCards();
    loadATSReportsList();
  } catch(e){ showToast('Failed to load jobs','error'); }
}

function renderJobStats() {
  const total=allJobs.length;
  const interviews=allJobs.filter(j=>j.status==='interview').length;
  const offers=allJobs.filter(j=>j.status==='offer').length;
  const withScore=allJobs.filter(j=>j.ats_score!=null&&j.ats_score>0);
  const avgScore=withScore.length?Math.round(withScore.reduce((a,j)=>a+j.ats_score,0)/withScore.length):0;
  document.getElementById('jobs-stats').innerHTML=`
    <div class="stat-card"><div class="stat-num">${total}</div><div class="stat-label">Applications</div></div>
    <div class="stat-card"><div class="stat-num" style="color:var(--amber)">${interviews}</div><div class="stat-label">Interviews</div></div>
    <div class="stat-card"><div class="stat-num" style="color:var(--green)">${offers}</div><div class="stat-label">Offers</div></div>
    <div class="stat-card"><div class="stat-num" style="color:${avgScore>=70?'var(--green)':avgScore>=50?'var(--amber)':'var(--red)'}">${withScore.length?avgScore+'%':'—'}</div><div class="stat-label">Avg ATS Score</div></div>`;
}

function filterJobs(status, btn) {
  currentJobFilter=status;
  document.querySelectorAll('.filter-chip').forEach(c=>c.classList.remove('active'));
  btn.classList.add('active');
  renderJobCards();
}

function renderJobCards() {
  const filtered=currentJobFilter==='all'?allJobs:allJobs.filter(j=>j.status===currentJobFilter);
  const grid=document.getElementById('jobs-grid');
  if(!filtered.length){
    grid.innerHTML=`<div class="preview-placeholder" style="min-height:200px;">
      <svg width="40" height="40" fill="none" viewBox="0 0 40 40"><rect x="4" y="8" width="32" height="26" rx="3" stroke="#94A3B8" stroke-width="2"/><path d="M14 6v4M26 6v4" stroke="#94A3B8" stroke-width="2" stroke-linecap="round"/></svg>
      <p>${currentJobFilter==='all'?'No applications yet. Add your first job on the left.':'No applications with this status.'}</p>
    </div>`;
    return;
  }
  grid.innerHTML=filtered.map(j=>{
    const sm=statusMeta(j.status);
    const scoreHtml=j.ats_score?`<span class="ats-score-mini" style="color:${scoreColor(j.ats_score)};background:${j.ats_score>=75?'#F0FDF4':j.ats_score>=50?'#FFFBEB':'#FEF2F2'}">${j.ats_score}%</span>`:'';
    const notesHtml=j.notes?`<div class="job-notes">${esc(j.notes)}</div>`:'';
    const urlHtml=j.job_url?`<a href="${esc(j.job_url)}" target="_blank" class="btn" style="font-size:0.72rem;padding:0.3rem 0.7rem;background:var(--bg);border:1px solid var(--border);color:var(--blue);">🔗 View Job</a>`:'';
    return `<div class="job-card">
      <div class="job-card-header" style="background:${j.status==='offer'?'linear-gradient(135deg,#052E16,#14532D)':j.status==='interview'?'linear-gradient(135deg,#1C1C07,#451A03)':j.status==='rejected'?'linear-gradient(135deg,#1C0707,#450A0A)':'var(--navy)'};">
        <span class="status-badge ${sm.cls}">${sm.label}</span>
        ${scoreHtml}
      </div>
      <div class="job-card-body">
        <div class="job-title">${esc(j.job_title)}</div>
        <div class="job-company">${esc(j.company)}</div>
        ${j.applied_date?`<div class="job-meta">📅 ${esc(j.applied_date)}</div>`:''}
        ${notesHtml}
        <div class="job-actions">
          <button class="btn btn-primary" style="font-size:0.72rem;padding:0.3rem 0.7rem;" onclick="openEditJob(${j.id})">✏ Edit</button>
          ${urlHtml}
          <button class="btn" style="background:#FEE2E2;color:var(--red);font-size:0.72rem;padding:0.3rem 0.7rem;border:none;" onclick="deleteJobCard(${j.id})">Delete</button>
        </div>
      </div>
    </div>`;
  }).join('');
}

async function addJob() {
  const title=document.getElementById('new-job-title').value.trim();
  const company=document.getElementById('new-job-company').value.trim();
  if(!title||!company){showToast('Job title and company are required','error');return;}
  const payload={
    job_title:title,company,
    job_url:document.getElementById('new-job-url').value.trim(),
    status:document.getElementById('new-job-status').value,
    applied_date:document.getElementById('new-job-date').value.trim(),
    notes:document.getElementById('new-job-notes').value.trim()
  };
  try {
    const data=await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).then(r=>r.json());
    if(data.success){
      showToast('✅ Application added!','success');
      ['new-job-title','new-job-url','new-job-date','new-job-notes'].forEach(id=>document.getElementById(id).value='');
      document.getElementById('new-job-company').value='';
      document.getElementById('new-job-status').value='saved';
      loadJobsPanel();
    } else showToast(data.error||'Failed','error');
  } catch(e){ showToast('Network error','error'); }
}

function openEditJob(id) {
  const j=allJobs.find(x=>x.id===id); if(!j)return;
  document.getElementById('edit-job-id').value=j.id;
  document.getElementById('edit-job-title').value=j.job_title||'';
  document.getElementById('edit-job-company').value=j.company||'';
  document.getElementById('edit-job-url').value=j.job_url||'';
  document.getElementById('edit-job-status').value=j.status||'saved';
  document.getElementById('edit-job-date').value=j.applied_date||'';
  document.getElementById('edit-job-ats').value=j.ats_score||'';
  document.getElementById('edit-job-notes').value=j.notes||'';
  document.getElementById('editJobModal').style.display='flex';
}
function closeEditJobModal() { document.getElementById('editJobModal').style.display='none'; }

async function saveEditJob() {
  const id=parseInt(document.getElementById('edit-job-id').value);
  const atsVal=document.getElementById('edit-job-ats').value;
  const payload={
    job_title:document.getElementById('edit-job-title').value.trim(),
    company:document.getElementById('edit-job-company').value.trim(),
    job_url:document.getElementById('edit-job-url').value.trim(),
    status:document.getElementById('edit-job-status').value,
    applied_date:document.getElementById('edit-job-date').value.trim(),
    ats_score:atsVal?parseInt(atsVal):null,
    notes:document.getElementById('edit-job-notes').value.trim()
  };
  try {
    const data=await fetch(`/api/jobs/${id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).then(r=>r.json());
    if(data.success){closeEditJobModal();showToast('✅ Updated!','success');loadJobsPanel();}
    else showToast(data.error||'Failed','error');
  } catch(e){ showToast('Network error','error'); }
}

async function deleteJobCard(id) {
  if(!confirm('Delete this application?'))return;
  await fetch(`/api/jobs/${id}`,{method:'DELETE'});
  showToast('Deleted','success');
  loadJobsPanel();
}

// ── ATS REPORTS LIST ──────────────────────────────────────
async function loadATSReportsList() {
  try {
    const reports=await fetch('/api/ats-reports').then(r=>r.json());
    const card=document.getElementById('reports-card');
    if(!reports.length){card.style.display='none';return;}
    card.style.display='block';
    document.getElementById('reports-list').innerHTML=reports.map(r=>{
      const score=r.score_data?(JSON.parse(r.score_data||'{}')):null;
      const s=score&&score.overall!=null?score.overall:null;
      const scoreHtml=s!=null?`<span class="report-score-badge" style="color:${scoreColor(s)};background:${s>=75?'#F0FDF4':s>=50?'#FFFBEB':'#FEF2F2'}">${s}%</span>`:'';
      return `<div class="report-row" onclick="openReportDetail(${r.id})">
        <div>
          <div style="font-weight:600;font-size:0.85rem;">${esc(r.job_title)}${r.company?' — '+esc(r.company):''}</div>
          <div style="font-size:0.72rem;color:var(--slate-light);">${r.created_at?r.created_at.slice(0,10):''} · ${esc(r.resume_name||'')}</div>
        </div>
        <div style="display:flex;align-items:center;gap:0.5rem;">
          ${scoreHtml}
          <button class="btn" style="font-size:0.7rem;padding:0.25rem 0.55rem;background:#FEE2E2;color:var(--red);border:none;" onclick="event.stopPropagation();deleteReport(${r.id},this)">✕</button>
        </div>
      </div>`;
    }).join('');
  } catch(e){}
}

function toggleReportsPanel() {
  const panel=document.getElementById('reports-list-panel');
  const icon=document.getElementById('reports-toggle-icon');
  const hidden=panel.style.display==='none';
  panel.style.display=hidden?'block':'none';
  icon.textContent=hidden?'▲ Hide':'▼ Show';
}

async function openReportDetail(id) {
  const data=await fetch(`/api/ats-reports/${id}`).then(r=>r.json());
  if(data.error){showToast(data.error,'error');return;}
  const sd=data.score_data||{};
  const score=sd.overall||0;
  const col=scoreColor(score);
  document.getElementById('report-modal-title').textContent=`ATS Report — ${data.job_title}${data.company?' @ '+data.company:''}`;
  document.getElementById('report-modal-body').innerHTML=`
    <div style="display:flex;align-items:center;gap:1.5rem;margin-bottom:1rem;">
      <div style="text-align:center;">
        <div style="font-family:'DM Serif Display',serif;font-size:2.5rem;color:${col};">${score}</div>
        <div style="font-size:0.72rem;font-weight:700;color:var(--slate);text-transform:uppercase;">${sd.verdict||''}</div>
      </div>
      <div style="flex:1;">
        ${[['Keywords',sd.keywords],['Skills',sd.skills],['Experience',sd.experience],['Format',sd.format]].map(([l,v])=>`
          <div class="ats-band"><span class="ats-band-label">${l}</span>
          <div class="ats-band-bar-wrap"><div class="ats-band-bar" style="width:${v||0}%;background:${scoreColor(v||0)};"></div></div>
          <span class="ats-band-val" style="color:${scoreColor(v||0)}">${v||0}%</span></div>`).join('')}
      </div>
    </div>
    ${sd.strengths?.length?`<div class="feedback-section"><div class="feedback-title" style="color:var(--green);">✓ Strengths</div><div class="feedback-items">${sd.strengths.map(s=>`<div class="feedback-item good">${esc(s)}</div>`).join('')}</div></div>`:''}
    ${sd.warnings?.length?`<div class="feedback-section"><div class="feedback-title" style="color:var(--amber);">⚠ Suggestions</div><div class="feedback-items">${sd.warnings.map(s=>`<div class="feedback-item warn">${esc(s)}</div>`).join('')}</div></div>`:''}
    ${sd.critical?.length?`<div class="feedback-section"><div class="feedback-title" style="color:var(--red);">✗ Critical</div><div class="feedback-items">${sd.critical.map(s=>`<div class="feedback-item bad">${esc(s)}</div>`).join('')}</div></div>`:''}
    <div style="margin-top:0.75rem;font-size:0.75rem;color:var(--slate);">Created: ${data.created_at?data.created_at.slice(0,16):''}</div>`;
  document.getElementById('report-modal-export-btn').onclick=()=>downloadReportPDF(id);
  document.getElementById('reportDetailModal').style.display='flex';
}

async function downloadReportPDF(id) {
  const btn=document.getElementById('report-modal-export-btn');
  btn.disabled=true; btn.textContent='⏳…';
  try {
    const res=await fetch(`/api/ats-reports/${id}/export-pdf`);
    if(!res.ok){showToast('Export failed','error');return;}
    const blob=await res.blob();
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a'); a.href=url; a.download='ATS_Report.pdf'; a.click();
    URL.revokeObjectURL(url);
    showToast('✅ Report PDF downloaded!','success');
  } catch(e){ showToast('Export error','error'); }
  finally { btn.disabled=false; btn.textContent='⬇ Export PDF'; }
}

async function deleteReport(id, btn) {
  event.stopPropagation();
  if(!confirm('Delete this ATS report?'))return;
  await fetch(`/api/ats-reports/${id}`,{method:'DELETE'});
  btn.closest('.report-row').remove();
  showToast('Deleted','success');
}

// ── INIT ──────────────────────────────────────────────────
addExperience();
addEducation();
updatePreview();
