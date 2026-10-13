// Explicit browser-only fallback for an unconnected GitHub Pages deployment.
(function () {
  const key = 'week5-demo-session';
  const warning = '后端尚未连接，当前使用浏览器本地模拟模型。未调用真实大模型，所有结果为规则生成的预期演示结果。';
  function load() { return JSON.parse(localStorage.getItem(key) || 'null'); }
  function save(session) { session.updated_at = new Date().toISOString(); localStorage.setItem(key, JSON.stringify(session)); }
  function payload(session) {
    if (!session) return {session: null};
    const done = new Set(session.tasks.filter(t => t.status === 'done').map(t => t.id));
    session.ready_tasks = session.tasks.filter(t => t.status === 'pending' && t.depends_on.every(id => done.has(id))).map(t => t.id);
    session.review = {completion_rate: done.size / session.tasks.length, tool_success_rate: session.events.length ? session.events.filter(e => e.status === 'ok').length / session.events.length : 0, suggestions: [done.size === session.tasks.length ? '把复盘结果写入下一次计划' : '继续执行可运行任务并检查结果']};
    return session;
  }
  function checklist(goal) {
    if (/作品集|网站/.test(goal)) return ['整理作品与个人介绍', '绘制页面原型', '检查布局和链接'];
    if (/面试/.test(goal)) return ['复习核心知识', '练习常见问题', '记录薄弱项并复盘'];
    if (/读书|笔记/.test(goal)) return ['整理摘录', '归纳主题', '写出复盘清单'];
    return ['阅读核心概念', '完成小型实现', '运行测试并记录问题'];
  }
  window.demoRequest = async (path, options = {}) => {
    let session = load();
    if (path === '/api/session') return payload(session);
    if (path === '/api/reset') { localStorage.removeItem(key); return {session: null}; }
    if (path === '/api/init') {
      const goal = JSON.parse(options.body).goal.trim();
      if (!goal || goal.length > 2000) throw new Error('目标长度需要在 1 到 2000 字之间');
      const hour = goal.match(/(\d+)\s*(小时|h|hour)/i);
      const specs = [['明确任务目标', '提取主题和产出', 'summarize', goal], ['建立执行清单', '整理可执行步骤', 'checklist', checklist(goal)], ['安排时间预算', '计算每天投入', 'time_budget', hour ? {hours: Number(hour[1])} : goal], ['生成复盘提醒', '记录有效做法和改进点', 'review_prompt', goal]];
      session = {goal, created_at: new Date().toISOString(), model_mode: 'simulation', model_notice: warning, events: [], tasks: specs.map((s,i) => ({id:`t${i+1}`,title:s[0],action:s[1],tool:s[2],argument:s[3],depends_on:i?[`t${i}`]:[],status:'pending',attempts:0,result:null,error:null}))};
      save(session); return payload(session);
    }
    if (path === '/api/run') {
      if (!session) throw new Error('请先创建任务计划');
      const ready = payload(session).ready_tasks;
      const outputs = [];
      for (const task of session.tasks.filter(t => ready.includes(t.id))) {
        const hours = task.argument?.hours;
        const failed = task.tool === 'time_budget' && hours !== undefined && (hours < 1 || hours > 168);
        let result;
        if (task.tool === 'summarize') result = task.argument.slice(0,100);
        if (task.tool === 'checklist') result = task.argument.map((item,i) => `${i+1}. ${item}`).join('\n');
        if (task.tool === 'time_budget') { const days = Math.min(7,Math.max(1,Math.floor(hours/2)||1)); result = hours === undefined ? '目标未提供小时数，建议先安排每天 1 小时' : `总计 ${hours} 小时，建议分为 ${days} 天，每天约 ${(hours/days).toFixed(1)} 小时`; }
        if (task.tool === 'review_prompt') result = `复盘问题：${session.goal}；完成后记录一个有效做法和一个待改进点。`;
        task.status = failed ? 'failed' : 'done'; task.attempts = failed ? 2 : 1; task.result = failed ? null : result; task.error = failed ? '小时数需要在 1 到 168 之间' : null;
        for (let attempt=0; attempt<task.attempts; attempt++) session.events.push({timestamp:new Date().toISOString(),kind:'tool_call',task_id:task.id,tool:task.tool,status:failed?'error':'ok',input:task.argument,output:task.result,error:task.error});
        outputs.push({task:task.id,status:task.status,result:task.result});
      }
      save(session); return {...payload(session), outputs};
    }
    throw new Error('接口不存在');
  };
})();
