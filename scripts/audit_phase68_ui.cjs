/* Real UI event reducer/restore contracts, executed without a browser. */
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const root = path.resolve(__dirname, '..');
const sandbox = {window: {}, localStorage: {getItem: () => null, setItem: () => {}}, Date, Math};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(root, 'web/app/events.jsx'), 'utf8'), sandbox);
const api = sandbox.window;
const rows = [];
for (const type of ['grounding', 'saydo']) {
  let messages = [];
  const turn = new api.TurnBuilder(update => {messages = update(messages);});
  api.handleEvent({type, ok:false, unverified:['73'], action:'corrected_claim', turn_seq:1}, turn, {});
  rows.push({case:`${type}_event_visible`, passed:messages.length>0, actual:messages, expected:'visible verification feedback'});
}
const history = [{role:'assistant', content:'Waiting.', turn_seq:1, metadata:{
  tool_calls:[{name:'create_widget',arguments:{type:'note'},result:'{"blocked":true}',failed:false,blocked:true}],
  saydo:{action:'proposed_unconfirmed',false_exec_claim:true}
}}];
const restored = api.historyToMessages(history, 'synthetic-session');
const status = restored.find(x => x.kind==='toolgroup').entries[0].status;
rows.push({case:'blocked_history_stays_blocked',passed:status==='blocked',actual:status,expected:'blocked'});
rows.push({case:'saydo_report_survives_history',passed:restored.some(x => x.kind==='saydo'),actual:restored.map(x=>x.kind),expected:'saydo report visible'});
const out = {scope:'real events.jsx reducers; not a visual browser QA', results:rows};
fs.mkdirSync(path.join(root,'outputs'), {recursive:true});
fs.writeFileSync(path.join(root,'outputs/phase68_ui_contracts.json'),JSON.stringify(out,null,2));
process.stdout.write(JSON.stringify(out,null,2));
