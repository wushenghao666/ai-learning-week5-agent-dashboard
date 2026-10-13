const $ = (s) => document.querySelector(s);
const API_BASE = window.AGENT_API_BASE || '';
const state = { session: null, busy: false };
let token = localStorage.getItem('week5-session-token');
if (!token) { token = crypto.randomUUID(); localStorage.setItem('week5-session-token', token); }
const statusText = { pending: '待执行', running: '执行中', done: '已完成', failed: '失败' };
const modeText = {rules:'规则规划',simulation:'模拟模型',openai:'真实模型'};
function escapeHtml(value) { return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char])); }
function format(value) { return typeof value === 'string' ? value : JSON.stringify(value, null, 2); }
function code(value) { return `<pre class="trace-code">${escapeHtml(format(value))}</pre>`; }
async function request(path, options = {}) {
  if (!API_BASE && location.hostname.endsWith('github.io')) return window.demoRequest(path, options);
  const response = await fetch(`${API_BASE}${path}`, {headers:{'Content-Type':'application/json','X-Session-Token':token},...options});
  const data = await response.json();
  if (!response.ok) { const error = new Error(data.error || '请求失败'); error.planningTrace = data.planning_trace; throw error; }
  return data;
}
function showNotice(text, error = false) { $('#notice').textContent = text; $('#notice').style.color = error ? '#dc2626' : '#64748b'; }
function buttons() {
  const exists = Array.isArray(state.session?.tasks);
  $('#createBtn').disabled = state.busy;
  $('#resetBtn').disabled = state.busy;
  $('#runBtn').disabled = state.busy || !exists || !state.session.ready_tasks?.length;
  $('#llmMode').disabled = state.busy;
}
function busy(text) {
  state.busy = !!text; buttons();
  $('#requestProgress').textContent = text || '';
  $('#requestProgress').classList.toggle('hidden', !text);
  if (text) $('#operation').textContent = text;
}
function planning(trace) {
  $('#planningTrace').innerHTML = trace?.length ? trace.map(entry => `<details class="trace-entry ${entry.stage === 'error' ? 'trace-error' : ''}" ${entry.stage === 'output' ? 'open' : ''}><summary>${escapeHtml(entry.title)} ${entry.mode ? `<span class="badge">${escapeHtml(modeText[entry.mode])}</span>` : ''}</summary><div class="trace-meta">${escapeHtml(entry.timestamp)}${entry.model ? ` · ${escapeHtml(entry.model)}` : ''}${entry.duration_ms !== undefined ? ` · ${entry.duration_ms} ms` : ''}${entry.task_count !== undefined ? ` · ${entry.task_count} 个任务` : ''}</div>${entry.input !== undefined ? `<h4>输入目标</h4>${code(entry.input)}` : ''}${entry.instructions ? `<details><summary>规划指令</summary>${code(entry.instructions)}</details>` : ''}${entry.output !== undefined ? `<h4>${entry.stage === 'output' ? '输出内容' : '处理结果'}</h4>${code(entry.output)}` : ''}${entry.error ? code(entry.error) : ''}${entry.note ? `<p>${escapeHtml(entry.note)}</p>` : ''}${entry.usage && Object.keys(entry.usage).length ? `<details><summary>Token 用量</summary>${code(entry.usage)}</details>` : ''}</details>`).join('') : '<p class="trace-note">这份旧会话没有规划记录，创建新计划即可查看。</p>';
}
function graph(session) {
  const tasks = session.tasks;
  const width = Math.max(360, tasks.length * 185 + 20);
  const top = 55 + tasks.length * 8;
  const ready = new Set(session.ready_tasks);
  const palette = {done:'#16a34a',failed:'#dc2626',pending:'#94a3b8',running:'#d97706'};
  const edges = tasks.flatMap((task,i) => task.depends_on.map(dep => {
    const j = tasks.findIndex(t => t.id === dep); if (j < 0) return '';
    const a = j*185+95, b = i*185+95, y = 20+(i-j)*8;
    return `<path d="M ${a} ${top} C ${a} ${y}, ${b} ${y}, ${b} ${top-5}" fill="none" stroke="#94a3b8" stroke-width="2" marker-end="url(#arrow)"/><text x="${(a+b)/2}" y="${y}" font-size="10" text-anchor="middle" fill="#64748b">${escapeHtml(dep)} → ${escapeHtml(task.id)}</text>`;
  })).join('');
  const nodes = tasks.map((task,i) => {
    const color = ready.has(task.id) ? '#536dfe' : palette[task.status] || '#94a3b8';
    return `<g><rect x="${i*185+20}" y="${top}" width="150" height="80" rx="12" fill="white" stroke="${color}" stroke-width="2"/><text x="${i*185+95}" y="${top+23}" text-anchor="middle" font-size="13" fill="#1d2939">${escapeHtml(task.id)} · ${escapeHtml(task.title.slice(0,9))}</text><text x="${i*185+95}" y="${top+47}" text-anchor="middle" font-size="11" fill="${color}">${ready.has(task.id) ? '可以执行' : statusText[task.status]}</text><text x="${i*185+95}" y="${top+66}" text-anchor="middle" font-size="10" fill="#64748b">${escapeHtml(task.tool)}</text></g>`;
  }).join('');
  $('#dependencyGraph').innerHTML = `<svg viewBox="0 0 ${width} ${top+100}" width="${width}" height="${top+100}" role="img" aria-label="任务依赖图"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="#94a3b8"/></marker></defs>${edges}${nodes}</svg>`;
}
function render(session) {
  state.session = session;
  const exists = Array.isArray(session?.tasks);
  $('#modelNotice').textContent = session?.model_notice || '';
  $('#modelNotice').classList.toggle('hidden', !session?.model_notice);
  $('#empty').classList.toggle('hidden', exists); $('#dashboard').classList.toggle('hidden', !exists);
  buttons(); if (!exists) return;
  const report = session.review || {};
  $('#completion').textContent = `${Math.round((report.completion_rate || 0)*100)}%`;
  $('#success').textContent = `${Math.round((report.tool_success_rate || 0)*100)}%`;
  $('#ready').textContent = session.ready_tasks.length; $('#events').textContent = session.events.length;
  $('#goalText').textContent = session.goal; $('#modeLabel').textContent = modeText[session.model_mode] || '旧会话';
  const complete = session.tasks.every(t => t.status === 'done');
  const validated = session.planning_trace?.some(e => e.stage === 'validated');
  const stages = [['接收目标',true],['生成计划',true],['校验计划',validated],['执行工具',complete],['完成复盘',complete]];
  $('#pipeline').innerHTML = stages.map(([title,done],i) => `<div class="stage ${done?'complete':''}"><span>${done?'✓':i+1}</span>${title}</div>`).join('');
  $('#operation').textContent = complete ? '所有工具已执行，复盘指标已更新' : session.ready_tasks.length ? `下一批可执行：${session.ready_tasks.join('、')}；每次只执行当前依赖已满足的任务` : '没有可执行任务，请检查失败记录';
  planning(session.planning_trace); graph(session);
  $('#tasks').innerHTML = session.tasks.map(task => `<article class="task ${escapeHtml(task.status)}"><div class="task-head"><span class="task-title">${escapeHtml(task.id)} · ${escapeHtml(task.title)}</span><span class="badge">${statusText[task.status] || '未知'}</span></div><div class="task-meta">${escapeHtml(task.action)} · 工具：${escapeHtml(task.tool)} · 前置：${escapeHtml(task.depends_on.join('、') || '无')} · 尝试 ${task.attempts}</div><details><summary>执行参数与结果</summary><h4>输入</h4>${code(task.argument)}${task.result !== null ? `<h4>输出</h4>${code(task.result)}`:''}${task.error ? `<h4>错误</h4>${code(task.error)}`:''}</details></article>`).join('');
  $('#timeline').innerHTML = session.events.length ? [...session.events].reverse().map(event => `<details class="event ${event.status === 'error' ? 'trace-error':''}" open><summary>${escapeHtml(event.task_id)} · ${escapeHtml(event.tool)} · ${event.status === 'ok' ? '成功':'失败'}</summary><small>${escapeHtml(event.timestamp)}${event.attempt ? ` · 第 ${event.attempt} 次尝试`:''}${event.duration_ms !== null && event.duration_ms !== undefined ? ` · ${event.duration_ms} ms`:''}</small><h4>工具输入</h4>${code(event.input)}<h4>${event.status === 'ok'?'工具输出':'错误'}</h4>${code(event.output ?? event.error ?? '')}</details>`).join('') : '<p class="trace-note">等待工具调用。点击执行下一步后，这里将记录参数、返回值和耗时。</p>';
  $('#suggestions').innerHTML = (report.suggestions || []).map(item=>`<li>${escapeHtml(item)}</li>`).join('');
}
async function operation(text, action) {
  if (state.busy) return;
  busy(text); showNotice(text);
  try { await action(); }
  catch(error) { const message = error.message === 'Failed to fetch' ? '无法连接后端，操作结果尚未确认；请刷新会话后再继续' : error.message; showNotice(message,true); $('#operation').textContent = `操作失败：${message}`; if (error.planningTrace?.length) { $('#empty').classList.add('hidden'); $('#dashboard').classList.remove('hidden'); planning(error.planningTrace); $('#operation').textContent = '本次规划失败，详情见规划记录；原有会话未被替换'; } }
  finally { busy(''); }
}
$('#createBtn').onclick = () => { const goal=$('#goal').value.trim(); if (!goal) return showNotice('请先输入任务目标',true); return operation('接收目标 → 请求规划 → 等待输出与校验…',async()=>{render(await request('/api/init',{method:'POST',body:JSON.stringify({goal,use_llm:$('#llmMode').checked})})); showNotice(state.session.model_mode==='simulation'?'模拟计划已创建，请查看警告':state.session.model_mode==='openai'?'真实模型计划已创建':'规则计划已创建');}); };
$('#runBtn').onclick = () => operation(`检查依赖 → 调用 ${state.session?.ready_tasks?.join('、') || ''} 的工具 → 保存结果…`,async()=>{const result=await request('/api/run',{method:'POST',body:'{}'});render(result);showNotice(result.outputs.length?`完成 ${result.outputs.length} 个任务`:'当前没有可执行任务');});
$('#resetBtn').onclick = () => operation('清空当前会话…',async()=>{render(await request('/api/reset',{method:'POST',body:'{}'}));showNotice('会话已清空');});
request('/api/session').then(render).catch(error=>showNotice(error.message,true));
for(const button of document.querySelectorAll('.example')) button.onclick=()=>{if(state.busy)return;$('#goal').value=button.dataset.goal;$('#goal').focus();showNotice('已填入示例目标');};
