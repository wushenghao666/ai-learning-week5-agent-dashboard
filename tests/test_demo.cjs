const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const cache = new Map();
const context = {window:{}, localStorage:{getItem:k=>cache.get(k)||null,setItem:(k,v)=>cache.set(k,v),removeItem:k=>cache.delete(k)}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('web/demo.js','utf8'),context);
const call=context.window.demoRequest;
(async()=>{
  for (const [goal,time] of [['本周学习 RAG，安排 6 小时','3 天'],['设计作品集网站，安排 8 小时','4 天'],['准备机器学习面试，安排 4 小时','2 天'],['整理读书笔记','每天 1 小时']]) {
    let session=await call('/api/init',{body:JSON.stringify({goal,use_llm:true})});
    assert.equal(session.model_mode,'simulation'); assert.equal(session.planning_trace[1].stage,'output'); assert.equal(JSON.parse(session.planning_trace[1].output).tasks.length,4); assert.match(session.model_notice,/未调用真实大模型/);
    for (const rate of [.25,.5,.75,1]) { session=await call('/api/run'); assert.equal(session.review.completion_rate,rate); }
    assert.equal(session.events.length,4); assert.equal(session.events[0].attempt,1); assert.equal(typeof session.events[0].duration_ms,'number'); assert.equal(session.review.tool_success_rate,1); assert.ok(session.tasks[2].result.includes(time));
    const restored=await call('/api/session'); assert.equal(restored.review.completion_rate,1);
    await call('/api/reset'); assert.equal((await call('/api/session')).session,null);
  }
  await call('/api/init',{body:JSON.stringify({goal:'学习 0 小时'})});
  for(let i=0;i<3;i++) await call('/api/run');
  const failure=await call('/api/session'); assert.equal(failure.tasks[2].status,'failed'); assert.equal(failure.tasks[3].status,'pending');
  console.log('Four scenarios, refresh/reset and failed dependencies passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
