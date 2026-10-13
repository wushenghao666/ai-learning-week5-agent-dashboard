const $ = (s) => document.querySelector(s);
const API_BASE = window.AGENT_API_BASE || '';
const state = { session: null };
let token = localStorage.getItem('week5-session-token');
if (!token) { token = crypto.randomUUID(); localStorage.setItem('week5-session-token', token); }
const statusText = { pending: '待执行', running: '执行中', done: '已完成', failed: '失败' };
async function request(path, options = {}) {
  if (!API_BASE && location.hostname.endsWith('github.io')) return window.demoRequest(path, options);
  const response = await fetch(`${API_BASE}${path}`, { headers: {'Content-Type':'application/json', 'X-Session-Token': token}, ...options });
  const data = await response.json(); if (!response.ok) throw new Error(data.error || '请求失败'); return data;
}
function showNotice(text, error = false) { const node = $('#notice'); node.textContent = text; node.style.color = error ? '#dc2626' : '#64748b'; }
function render(session) { state.session = session; const notice = $('#modelNotice'); if (notice) { notice.textContent = session?.model_notice || ''; notice.classList.toggle('hidden', !session?.model_notice); }  const exists = Array.isArray(session?.tasks); $('#empty').classList.toggle('hidden', exists); $('#dashboard').classList.toggle('hidden', !exists); if (!exists) return; const report = session.review || {}; $('#completion').textContent = `${Math.round((report.completion_rate || 0) * 100)}%`; $('#success').textContent = `${Math.round((report.tool_success_rate || 0) * 100)}%`; $('#ready').textContent = session.ready_tasks.length; $('#events').textContent = session.events.length; $('#goalText').textContent = session.goal; $('#tasks').innerHTML = session.tasks.map((task) => `<article class="task ${task.status}"><div class="task-head"><span class="task-title">${escapeHtml(task.id)} · ${escapeHtml(task.title)}</span><span class="badge">${statusText[task.status] || task.status}</span></div><div class="task-meta">${escapeHtml(task.action)} · 工具：${escapeHtml(task.tool)} · 前置：${task.depends_on.length ? escapeHtml(task.depends_on.join('、')) : '无'} · 尝试 ${task.attempts}</div>${task.result ? `<div class="task-meta">结果：${escapeHtml(task.result)}</div>` : ''}${task.error ? `<div class="task-meta">错误：${escapeHtml(task.error)}</div>` : ''}</article>`).join(''); $('#timeline').innerHTML = session.events.length ? [...session.events].reverse().map((event) => `<div class="event"><strong>${escapeHtml(event.task_id)} · ${escapeHtml(event.tool)} · ${event.status === 'ok' ? '成功' : '失败'}</strong><small>${escapeHtml(event.timestamp)}</small><p>${escapeHtml(event.output || event.error || '')}</p></div>`).join('') : '<p class="section-title">还没有工具调用，点击执行下一步。</p>'; $('#suggestions').innerHTML = (report.suggestions || []).map((item) => `<li>${escapeHtml(item)}</li>`).join(''); }
function escapeHtml(value) { return String(value).replace(/[&<>]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[char])); }
$('#createBtn').onclick = async () => { const goal = $('#goal').value.trim(); if (!goal) return showNotice('请先输入学习目标', true); try { showNotice('正在生成计划…'); render(await request('/api/init', {method:'POST', body: JSON.stringify({goal, use_llm: $('#llmMode').checked})})); showNotice(state.session.model_mode === 'simulation' ? '模拟计划已创建，请查看警告' : state.session.model_mode === 'openai' ? '真实模型计划已创建' : '规则计划已创建'); } catch (error) { showNotice(error.message, true); } };
$('#runBtn').onclick = async () => { try { showNotice('正在执行可运行任务…'); const result = await request('/api/run', {method:'POST', body:'{}'}); render(result); showNotice(result.outputs.length ? `完成 ${result.outputs.length} 个任务` : '当前没有可执行任务'); } catch (error) { showNotice(error.message, true); } };
$('#resetBtn').onclick = async () => { render(await request('/api/reset', {method:'POST', body:'{}'})); showNotice('会话已清空'); };
request('/api/session').then(render).catch((error) => showNotice(error.message, true));

for (const button of document.querySelectorAll('.example')) button.onclick = () => { $('#goal').value = button.dataset.goal; $('#goal').focus(); showNotice('已填入示例目标'); };


