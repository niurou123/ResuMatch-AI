// ResuMatch Sidebar — 纯 JS 无模块依赖
(function() {
'use strict';
const API = 'http://localhost:8000/api/v1';
const $ = s => document.querySelector(s);

// ==================== 字段匹配规则 ====================
const FIELD_RULES = [
  { keys: ['姓名','名字','中文名','全名','name','full name'], path: 'name', pri: 100 },
  { keys: ['性别','男/女','gender','sex'], path: 'gender', pri: 100 },
  { keys: ['出生日期','出生年月','生日','birthday','dob'], path: 'birthDate', pri: 100 },
  { keys: ['手机','手机号','手机号码','电话','mobile','phone','tel'], path: 'phone', pri: 100 },
  { keys: ['邮箱','电子邮箱','email','e-mail'], path: 'email', pri: 100 },
  { keys: ['身份证','证件号','id number','id card'], path: 'idNumber', pri: 95 },
  { keys: ['民族','ethnicity'], path: 'ethnicity', pri: 90 },
  { keys: ['政治面貌','政治身份'], path: 'politicalStatus', pri: 90 },
  { keys: ['籍贯','户籍','户口','hometown'], path: 'nativePlace', pri: 85 },
  { keys: ['现居','所在城市','city','location'], path: 'currentCity', pri: 80 },
  { keys: ['学校','毕业院校','院校','大学','school','university'], path: 'school', pri: 100 },
  { keys: ['学院','院系','college','department'], path: 'college', pri: 90 },
  { keys: ['专业','所学专业','major'], path: 'major', pri: 100 },
  { keys: ['学历','最高学历','学位','degree'], path: 'degree', pri: 95 },
  { keys: ['入学','开始时间','from'], path: 'startDate', pri: 85 },
  { keys: ['毕业','结束时间','预计毕业','to'], path: 'endDate', pri: 85 },
  { keys: ['GPA','gpa','绩点','平均成绩'], path: 'gpa', pri: 95 },
  { keys: ['排名','名次','ranking','rank'], path: 'ranking', pri: 90 },
  { keys: ['四级','CET4','cet-4'], path: 'cet4', pri: 90 },
  { keys: ['六级','CET6','cet-6'], path: 'cet6', pri: 90 },
  { keys: ['公司','实习单位','company','organization'], path: 'internCompany', pri: 90 },
  { keys: ['岗位','职位','position','role','title'], path: 'internRole', pri: 90 },
  { keys: ['项目名称','project name'], path: 'projName', pri: 85 },
  { keys: ['技术栈','使用技术','tech stack'], path: 'projTech', pri: 85 },
  { keys: ['编程语言','开发语言'], path: 'skills', pri: 80 },
  { keys: ['意向城市','期望城市','工作城市'], path: 'targetCities', pri: 85 },
  { keys: ['意向岗位','期望岗位','应聘岗位'], path: 'targetPositions', pri: 85 },
  { keys: ['自我评价','自我介绍','about me'], path: 'selfEvaluation', pri: 75 },
  { keys: ['获奖','所获奖项','awards'], path: 'awards', pri: 70 },
];

function matchField(label, profile) {
  const clean = label.replace(/[*：:\s（）()【】\[\]]/g,'').replace(/请输入|请选择|请填写|必填|选填|（必填）|（选填）/g,'');
  for (const rule of FIELD_RULES) {
    for (const kw of rule.keys) {
      if (clean.includes(kw) || kw.includes(clean)) {
        const val = dp(profile, rule.path);
        if (val) return { value: val, matchedBy: 'rule' };
      }
    }
  }
  // 模糊匹配
  for (const rule of FIELD_RULES) {
    for (const kw of rule.keys) {
      const overlap = [...kw].filter(c => clean.includes(c)).length / kw.length;
      if (overlap >= 0.5) { const val = dp(profile, rule.path); if (val) return { value: val, matchedBy: 'fuzzy' }; }
    }
  }
  return { value: '', matchedBy: 'none' };
}

function dp(obj, path) {
  const edu = (obj.educations||[])[0]||{};
  const intern = (obj.experiences||[]).find(e=>e.type==='实习')||{};
  const proj = (obj.experiences||[]).find(e=>e.type==='项目')||{};
  const map = {
    name:obj.name, gender:obj.gender, birthDate:obj.birthDate, phone:obj.phone, email:obj.email,
    idNumber:obj.idNumber, ethnicity:obj.ethnicity, politicalStatus:obj.politicalStatus,
    nativePlace:obj.nativePlace, currentCity:obj.currentCity,
    school:edu.school, college:edu.college, major:edu.major, degree:edu.type,
    startDate:edu.startDate, endDate:edu.endDate, gpa:edu.gpa, ranking:edu.ranking,
    cet4:edu.cet4, cet6:edu.cet6,
    internCompany:intern.organization, internRole:intern.role,
    projName:proj.organization, projTech:(proj.techStack||[]).join('、'),
    skills:(obj.skills||[]).map(s=>s.items?.join('、')).join('；'),
    targetCities:(obj.targetCities||[]).join('、'), targetPositions:(obj.targetPositions||[]).join('、'),
    selfEvaluation:obj.selfEvaluation, awards:obj.awards,
  };
  return map[path] || '';
}

// ==================== Tab 切换 ====================
document.querySelectorAll('.tab').forEach(t => {
  t.onclick = () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
    $('#panel-'+t.dataset.tab).classList.add('active');
    if (t.dataset.tab === 'template') renderProfile();
  };
});

// ==================== 后端检测 ====================
function checkHealth() {
  fetch(API+'/health').then(r=>r.json()).then(d=>{
    const bar = $('#statusBar');
    if(d.status==='ok'){bar.className='status-bar online';bar.innerHTML='🟢 后端已连接 — '+d.app;}
  }).catch(()=>{});
}
checkHealth(); setInterval(checkHealth,15000);

// ==================== 简历上传 ====================
$('#btnUpload').onclick = async () => {
  const file = $('#fileInput').files[0];
  if(!file) return alert('请先选择简历文件');
  const btn = $('#btnUpload'); btn.textContent='⏳ AI解析中...'; btn.disabled=true;
  const fd = new FormData(); fd.append('file', file);
  try {
    const r = await fetch(API+'/resume/upload', {method:'POST',body:fd});
    const d = await r.json();
    if(d.success) {
      // 转 profile
      const pp = d.profile||{};
      const profile = {
        name:pp.name||'', email:pp.email||'', phone:pp.phone||'', gender:'', birthDate:'', idNumber:'', ethnicity:'', politicalStatus:'', nativePlace:'', currentCity:'',
        educations:[], experiences:[], skills:[], targetCities:[], targetPositions:[], selfEvaluation:'', awards:'',
      };
      if(pp.education&&pp.education.length>0){
        profile.educations=[{type:((pp.education[0].degree||'').includes('硕士')?'硕士':'本科'),school:pp.education[0].school||'',major:pp.education[0].major||'',startDate:'',endDate:'',college:'',gpa:'',ranking:'',cet4:'',cet6:''}];
      }
      if(pp.projects) pp.projects.forEach((p,i)=>{
        profile.experiences.push({type:'项目',organization:p.name||'',role:p.role||'',description:p.description||'',techStack:p.tech_stack||[],achievements:p.key_result?[p.key_result]:[],startDate:'',endDate:'',bullets:[]});
      });
      if(pp.skills){
        const by={}; pp.skills.forEach(s=>{ const c=s.category||'other'; if(!by[c])by[c]=[]; by[c].push(s.name); });
        profile.skills=Object.entries(by).map(([c,items])=>({category:c,items}));
      }
      await chrome.storage.local.set({profile});
      $('#parseStatus').classList.remove('hidden');
      $('#parseStatus').innerHTML=`<div class="card"><h4>✅ 解析成功</h4><p style="font-size:12px;color:#94a3b8;">${Object.values(profile).filter(v=>Array.isArray(v)?v.length>0:v).length} 个字段已提取，切换到📋档案查看</p></div>`;
    } else {
      $('#parseStatus').classList.remove('hidden');
      $('#parseStatus').innerHTML=`<span class="tag red">❌ ${d.message||'失败'}</span>`;
    }
  } catch(e) {
    $('#parseStatus').classList.remove('hidden');
    $('#parseStatus').innerHTML='<span class="tag red">❌ 连接后端失败</span>';
  }
  btn.textContent='📤 上传并解析'; btn.disabled=false;
};

// ==================== 档案编辑 ====================
async function renderProfile() {
  const {profile} = await chrome.storage.local.get(['profile']);
  if(!profile){$('#templateView').innerHTML='<p style="color:#94a3b8">请先在📄简历中上传</p>';return;}
  const edu=profile.educations?.[0]||{};
  const intern=(profile.experiences||[]).find(e=>e.type==='实习')||{};
  const proj=(profile.experiences||[]).find(e=>e.type==='项目')||{};
  const vals={name:profile.name,gender:profile.gender,birthDate:profile.birthDate,phone:profile.phone,email:profile.email,idNumber:profile.idNumber,ethnicity:profile.ethnicity,politicalStatus:profile.politicalStatus,nativePlace:profile.nativePlace,currentCity:profile.currentCity,edu_type:edu.type,edu_school:edu.school,edu_major:edu.major,edu_start:edu.startDate,edu_end:edu.endDate,edu_gpa:edu.gpa,edu_ranking:edu.ranking,edu_cet4:edu.cet4,edu_cet6:edu.cet6,intern_company:intern.organization,intern_role:intern.role,intern_start:intern.startDate,intern_end:intern.endDate,proj_name:proj.organization,proj_role:proj.role,proj_tech:(proj.techStack||[]).join('、'),proj_result:(proj.achievements||proj.bullets||[])[0]||'',target_cities:(profile.targetCities||[]).join('、'),target_positions:(profile.targetPositions||[]).join('、'),self_eval:profile.selfEvaluation,awards:profile.awards};
  const sections=[
    {t:'📌 基本情况',f:[['name','姓名'],['gender','性别'],['birthDate','出生日期'],['phone','手机'],['email','邮箱'],['idNumber','身份证'],['ethnicity','民族'],['politicalStatus','政治面貌'],['nativePlace','籍贯'],['currentCity','现居']]},
    {t:'🎓 教育',f:[['edu_type','学历'],['edu_school','学校'],['edu_major','专业'],['edu_start','入学'],['edu_end','毕业'],['edu_gpa','GPA'],['edu_ranking','排名'],['edu_cet4','四级'],['edu_cet6','六级']]},
    {t:'💼 实习',f:[['intern_company','公司'],['intern_role','岗位'],['intern_start','开始'],['intern_end','结束']]},
    {t:'🚀 项目',f:[['proj_name','项目名'],['proj_role','角色'],['proj_tech','技术栈'],['proj_result','成果']]},
    {t:'🎯 其他',f:[['target_cities','意向城市'],['target_positions','意向岗位'],['self_eval','自我评价'],['awards','获奖']]},
  ];
  let h='';
  sections.forEach(sec=>{
    h+=`<div class="section"><div class="section-title">${sec.t}</div>`;
    sec.f.forEach(([k,lb])=>{ h+=`<div class="row"><span class="label">${lb}</span><input data-f="${k}" value="${esc(vals[k]||'')}" style="flex:1;padding:4px 6px;border:1px solid #334155;border-radius:4px;background:#0f172a;color:#e2e8f0;font-size:12px;margin-left:8px;"></div>`; });
    h+='</div>';
  });
  h+=`<div class="section"><div class="section-title">📝 详细描述</div><div style="margin-bottom:6px"><span style="font-size:12px;color:#94a3b8">实习内容</span><textarea data-f="intern_desc" style="min-height:50px">${esc(intern.description||'')}</textarea></div><div style="margin-bottom:6px"><span style="font-size:12px;color:#94a3b8">项目描述</span><textarea data-f="proj_desc" style="min-height:50px">${esc(proj.description||'')}</textarea></div></div>`;
  $('#templateView').innerHTML=h;
  $('#btnSaveTemplate').classList.remove('hidden');
}
function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

$('#btnSaveTemplate').onclick = async () => {
  const {profile} = await chrome.storage.local.get(['profile']);
  if(!profile) return;
  const g=k=>{const el=document.querySelector(`[data-f="${k}"]`);return el?el.value||'':'';};
  profile.name=g('name');profile.gender=g('gender');profile.birthDate=g('birthDate');profile.phone=g('phone');profile.email=g('email');profile.idNumber=g('idNumber');profile.ethnicity=g('ethnicity');profile.politicalStatus=g('politicalStatus');profile.nativePlace=g('nativePlace');profile.currentCity=g('currentCity');profile.selfEvaluation=g('self_eval');profile.awards=g('awards');
  profile.targetCities=g('target_cities').split(/[,，、]/).map(s=>s.trim()).filter(Boolean);
  profile.targetPositions=g('target_positions').split(/[,，、]/).map(s=>s.trim()).filter(Boolean);
  if(!profile.educations?.[0])profile.educations=[{}];
  const e=profile.educations[0]; e.type=g('edu_type')||'本科'; e.school=g('edu_school'); e.major=g('edu_major'); e.startDate=g('edu_start'); e.endDate=g('edu_end'); e.gpa=g('edu_gpa'); e.ranking=g('edu_ranking'); e.cet4=g('edu_cet4'); e.cet6=g('edu_cet6');
  let intern=profile.experiences?.find(x=>x.type==='实习');
  if(!intern){intern={type:'实习',organization:'',role:'',startDate:'',endDate:'',description:'',bullets:[],techStack:[],achievements:[]};profile.experiences.unshift(intern);}
  intern.organization=g('intern_company');intern.role=g('intern_role');intern.startDate=g('intern_start');intern.endDate=g('intern_end');intern.description=g('intern_desc');
  let proj=profile.experiences?.find(x=>x.type==='项目');
  if(!proj){proj={type:'项目',organization:'',role:'',startDate:'',endDate:'',description:'',bullets:[],techStack:[],achievements:[]};profile.experiences.push(proj);}
  proj.organization=g('proj_name');proj.role=g('proj_role');proj.techStack=g('proj_tech').split(/[,，、]/).map(s=>s.trim()).filter(Boolean);proj.description=g('proj_desc');proj.achievements=g('proj_result')?[g('proj_result')]:[];
  await chrome.storage.local.set({profile});
  alert('✅ 已保存');
};

// ==================== 网申扫描填充 ====================
let scannedFields = [];

$('#btnScan').onclick = async () => {
  $('#btnScan').textContent='⏳ 扫描中...'; $('#btnScan').disabled=true;

  // 通过 background.js 中转消息到目标页面
  chrome.runtime.sendMessage({type:'SCAN_PAGE'}, async res => {
    $('#btnScan').textContent='🔍 扫描当前页面表单'; $('#btnScan').disabled=false;
    if (!res?.ok) {
      $('#scanPreview').innerHTML=`<span class="tag red">❌ 扫描失败</span><p style="font-size:11px;color:#94a3b8;">${res?.error||'未知错误'}${res?.tabUrl?' — 页面: '+res.tabUrl:''}</p><p style="font-size:11px;color:#fbbf24;">👉 请<b>刷新网申页面</b>后重试</p>`;
      return;
    }
    scannedFields=res.fields||[];
    const {profile}=await chrome.storage.local.get(['profile']);
    let matched=0;
    const preview=scannedFields.slice(0,20).map(f=>{const m=profile?matchField(f.label,profile):{value:''};if(m.value)matched++;return`<div class="row"><span>${f.label}</span><span class="tag ${m.value?'green':'red'}">${m.value?'✓':'✗'} ${(m.value||f.value||'').substring(0,15)}</span></div>`;}).join('');
    $('#scanPreview').innerHTML=`<div class="card"><h4>🔍 ${res.atsName||'当前页面'} — ${scannedFields.length}字段，匹配${matched}个</h4>${preview}${scannedFields.length>20?`<p style="font-size:11px;color:#94a3b8;">...${scannedFields.length-20} 个更多</p>`:''}</div>`;
    $('#btnFill').classList.remove('hidden'); $('#btnClear').classList.remove('hidden');
  });
};

$('#btnFill').onclick = async () => {
  const {profile}=await chrome.storage.local.get(['profile']);
  const fillData=scannedFields.map(f=>{const m=profile?matchField(f.label,profile):{value:''};return{id:f.id,value:m.value||f.value||''};});
  chrome.runtime.sendMessage({type:'FILL_PAGE',data:fillData},res=>{
    if(!res?.ok) return;
    const ok=res.results.filter(r=>r.status==='success').length;
    const fail=res.results.filter(r=>r.status==='failed').length;
    $('#fillResult').innerHTML=`<div class="card" style="margin-top:8px"><h4>填充结果</h4><span class="tag green">✅${ok}成功</span>${fail?` <span class="tag red">❌${fail}失败</span>`:''} <span class="tag blue">📋${scannedFields.length}总计</span></div>`;
  });
};

$('#btnClear').onclick = async () => {
  chrome.runtime.sendMessage({type:'CLEAR_PAGE'});
  scannedFields=[];$('#scanPreview').innerHTML='';$('#fillResult').innerHTML='';
  $('#btnFill').classList.add('hidden');$('#btnClear').classList.add('hidden');
};

})();
