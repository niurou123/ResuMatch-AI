// ResuMatch Sidebar — 学习 AI-Resume-Form-Filling-Assistant
(function(){
'use strict';
const API='http://localhost:8000/api/v1';
const $=s=>document.querySelector(s);
const S=window.ResumeSchema;
let scannedFields=[], currentSection=null;

// ===== Health =====
function checkHealth(){
  fetch(API+'/health').then(r=>r.json()).then(d=>{
    if(d.status==='ok'){
      const b=$('#statusBadge');b.className='status-badge on';
      b.innerHTML='<span class="status-dot"></span><span>已连接</span>';
    }
  }).catch(()=>{});
}
checkHealth();setInterval(checkHealth,15000);

// ===== Tabs =====
document.querySelectorAll('.tab').forEach(t=>{
  t.onclick=()=>{
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
    t.classList.add('active');
    document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));
    $('#panel-'+t.dataset.tab).classList.add('active');
    if(t.dataset.tab==='profile') renderProfilePanel();
  };
});

// ===== Resume Upload =====
$('#btnUpload').onclick=async()=>{
  const file=$('#fileInput').files[0];
  if(!file)return;
  const btn=$('#btnUpload');btn.textContent='解析中...';btn.disabled=true;
  const fd=new FormData();fd.append('file',file);
  try{
    const r=await fetch(API+'/resume/upload',{method:'POST',body:fd});
    const d=await r.json();
    if(d.success){
      const pp=d.profile||{};
      const verification=d.verification||{};

      // Build profile — old flat format (compatible with popup matching + resume-editor migration)
      const profile={
        name:pp.name||'',email:pp.email||'',phone:pp.phone||'',
        gender:'',birthDate:'',idNumber:'',ethnicity:'',politicalStatus:'',
        nativePlace:'',currentCity:'',wechat:'',
        educations:[],experiences:[],skills:[],
        targetCities:[],targetPositions:[],expectedSalary:'',
        selfEvaluation:'',awards:'',publications:'',competitions:'',
      };

      // Education
      if(pp.education&&pp.education.length>0){
        const e=pp.education[0];
        profile.educations=[{
          type:(e.degree||'').includes('硕士')?'硕士':(e.degree||'').includes('博士')?'博士':'本科',
          school:e.school||'',major:e.major||'',degree:e.degree||'',
          startDate:'',endDate:'',college:'',gpa:'',ranking:'',cet4:'',cet6:'',
        }];
      }

      // Projects → experiences
      if(pp.projects)pp.projects.forEach(p=>{
        profile.experiences.push({
          type:'项目',organization:p.name||'',role:p.role||'',
          startDate:'',endDate:'',
          description:p.description||'',
          techStack:p.tech_stack||[],
          achievements:p.key_result?[p.key_result]:[],
          bullets:[],
        });
      });

      // Skills → grouped by category
      if(pp.skills){
        const by={};
        pp.skills.forEach(s=>{
          const c=s.category||'other';
          if(!by[c])by[c]=[];
          if(!by[c].includes(s.name))by[c].push(s.name);
        });
        profile.skills=Object.entries(by).map(([c,items])=>({category:c,items}));
      }

      // Achievements → awards + competitions
      if(pp.achievements&&pp.achievements.length>0){
        profile.awards=pp.achievements.map(a=>a.description||'').filter(Boolean).join('；');
      }

      await chrome.storage.local.set({profile});

      // Count meaningful fields
      const fieldCount=[
        profile.name,profile.email,profile.phone,
        ...(profile.educations[0]?[profile.educations[0].school]:[]),
        ...profile.experiences,
        ...profile.skills,
        profile.awards,
      ].filter(v=>{
        if(!v)return false;
        if(Array.isArray(v))return v.length>0;
        if(typeof v==='object')return Object.values(v).some(x=>x);
        return true;
      }).length;

      $('#parseStatus').classList.remove('hidden');
      const hi=verification.high_confidence||0;
      const lo=verification.low_confidence||0;
      $('#parseStatus').innerHTML='<div class="tip" style="border-color:rgba(34,197,94,.3);color:var(--success)">'+
        '解析成功，'+fieldCount+' 个字段已提取。'+
        (hi>0?'高置信度 '+hi+' 项，':'')+
        (lo>0?'低置信度 '+lo+' 项（建议复核）。':'')+
        '切换到"档案"查看或编辑。</div>';
    }else{
      $('#parseStatus').classList.remove('hidden');
      $('#parseStatus').innerHTML='<div class="tip" style="border-color:rgba(239,68,68,.3);color:var(--danger)">失败: '+(d.message||'未知错误')+'</div>';
    }
  }catch(e){
    $('#parseStatus').classList.remove('hidden');
    $('#parseStatus').innerHTML='<div class="tip" style="border-color:rgba(239,68,68,.3);color:var(--danger)">API 连接失败</div>';
  }
  btn.textContent='上传并解析';btn.disabled=false;
};

// ===== Profile Panel =====
async function renderProfilePanel(){
  const {profile}=await chrome.storage.local.get(['profile']);
  if(!profile){
    $('#profileStats').innerHTML='<div class="stat-card"><div class="stat-value">-</div><div class="stat-label">未上传</div></div>';
    $('#profileNav').innerHTML='<div class="tip">请先在"简历"页上传简历文件</div>';
    return;
  }

  // Stats
  const edu=profile.educations?.[0]||{};
  const exps=profile.experiences||[];
  const skillCount=(profile.skills||[]).reduce((s,c)=>(c.items||[]).length,0);
  $('#profileStats').innerHTML=
    '<div class="stat-card"><div class="stat-value">'+(exps.length||0)+'</div><div class="stat-label">经历</div></div>'+
    '<div class="stat-card"><div class="stat-value">'+skillCount+'</div><div class="stat-label">技能</div></div>'+
    '<div class="stat-card"><div class="stat-value">'+(profile.educations?.length||0)+'</div><div class="stat-label">教育</div></div>';

  // Section nav
  const sections=[
    {key:'basic',label:'基本信息',hasVal:!!(profile.name||profile.email||profile.phone)},
    {key:'edu',label:'教育经历',hasVal:!!(edu.school||edu.major)},
    {key:'intern',label:'实习经历',hasVal:!!exps.find(e=>e.type==='实习')},
    {key:'proj',label:'项目经历',hasVal:!!exps.find(e=>e.type==='项目')},
    {key:'skill',label:'技能',hasVal:skillCount>0},
    {key:'other',label:'其他',hasVal:!!(profile.selfEvaluation||profile.awards)},
  ];
  $('#profileNav').innerHTML=sections.map(s=>
    '<button class="nav-btn'+(currentSection===s.key?' active':'')+'" data-section="'+s.key+'">'+
      '<span class="nav-label">'+s.label+'</span>'+
      '<span class="nav-dot '+(s.hasVal?'filled':'empty')+'"></span>'+
    '</button>'
  ).join('');

  // Nav click
  document.querySelectorAll('.nav-btn').forEach(b=>{
    b.onclick=()=>{
      currentSection=b.dataset.section;
      renderProfileSection(currentSection,profile);
      document.querySelectorAll('.nav-btn').forEach(x=>x.classList.remove('active'));
      b.classList.add('active');
    };
  });

  // Default: basic
  if(!currentSection)currentSection='basic';
  renderProfileSection(currentSection,profile);

  $('#btnSaveProfile').classList.remove('hidden');
}

function renderProfileSection(key,profile){
  const edu=profile.educations?.[0]||{};
  const intern=profile.experiences?.find(e=>e.type==='实习')||{};
  const proj=profile.experiences?.find(e=>e.type==='项目')||{};

  let html='';
  const input=(label,val,fieldKey)=>
    '<div class="form-group"><label>'+label+'</label><input class="input" data-f="'+fieldKey+'" value="'+esc(val||'')+'"></div>';

  if(key==='basic'){
    html='<div class="section-card"><div class="section-head"><span class="title">基本信息</span></div><div class="section-body">'+
      input('姓名',profile.name,'name')+input('性别',profile.gender,'gender')+
      input('手机',profile.phone,'phone')+input('邮箱',profile.email,'email')+
      input('出生日期',profile.birthDate,'birthDate')+
      input('微信号',profile.wechat,'wechat')+
      input('现居城市',profile.currentCity,'currentCity')+
      input('籍贯',profile.nativePlace,'nativePlace')+
      input('政治面貌',profile.politicalStatus,'politicalStatus')+
      input('民族',profile.ethnicity,'ethnicity')+
      '</div></div>';
  }else if(key==='edu'){
    html='<div class="section-card"><div class="section-head"><span class="title">教育经历</span></div><div class="section-body">'+
      input('学校',edu.school,'edu_school')+input('学历',edu.type,'edu_type')+
      input('专业',edu.major,'edu_major')+input('GPA',edu.gpa,'edu_gpa')+
      input('排名',edu.ranking,'edu_ranking')+
      '</div></div>';
  }else if(key==='intern'){
    html='<div class="section-card"><div class="section-head"><span class="title">实习经历</span></div><div class="section-body">'+
      input('公司',intern.organization,'intern_company')+input('岗位',intern.role,'intern_role')+
      '<div class="form-group"><label>工作内容</label><textarea class="textarea" data-f="intern_desc">'+esc(intern.description||'')+'</textarea></div>'+
      '</div></div>';
  }else if(key==='proj'){
    html='<div class="section-card"><div class="section-head"><span class="title">项目经历</span></div><div class="section-body">'+
      input('项目名称',proj.organization,'proj_name')+input('项目角色',proj.role,'proj_role')+
      input('技术栈',(proj.techStack||[]).join('、'),'proj_tech')+
      '<div class="form-group"><label>项目描述</label><textarea class="textarea" data-f="proj_desc">'+esc(proj.description||'')+'</textarea></div>'+
      '</div></div>';
  }else if(key==='skill'){
    const skills=(profile.skills||[]).map(s=>s.category+': '+(s.items||[]).join('、')).join('\n');
    html='<div class="section-card"><div class="section-head"><span class="title">技能</span></div><div class="section-body">'+
      '<div class="form-group"><label>技能列表（类别: 技能1、技能2）</label><textarea class="textarea" data-f="skills_text" style="min-height:100px">'+esc(skills)+'</textarea></div>'+
      '</div></div>';
  }else if(key==='other'){
    html='<div class="section-card"><div class="section-head"><span class="title">其他信息</span></div><div class="section-body">'+
      input('意向岗位',(profile.targetPositions||[]).join('、'),'target_positions')+
      input('意向城市',(profile.targetCities||[]).join('、'),'target_cities')+
      '<div class="form-group"><label>自我评价</label><textarea class="textarea" data-f="self_eval">'+esc(profile.selfEvaluation||'')+'</textarea></div>'+
      '<div class="form-group"><label>获奖</label><textarea class="textarea" data-f="awards">'+esc(profile.awards||'')+'</textarea></div>'+
      '</div></div>';
  }

  $('#profileForm').innerHTML=html;
}

function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

// Save profile
$('#btnSaveProfile').onclick=async()=>{
  const {profile}=await chrome.storage.local.get(['profile']);
  if(!profile)return;
  const g=k=>{const el=document.querySelector('[data-f="'+k+'"]');return el?el.value||'':'';};

  profile.name=g('name');profile.gender=g('gender');profile.phone=g('phone');profile.email=g('email');
  profile.birthDate=g('birthDate');profile.currentCity=g('currentCity');
  profile.wechat=g('wechat');profile.nativePlace=g('nativePlace');
  profile.politicalStatus=g('politicalStatus');profile.ethnicity=g('ethnicity');
  profile.selfEvaluation=g('self_eval');profile.awards=g('awards');
  profile.targetCities=g('target_cities').split(/[,，、]/).map(s=>s.trim()).filter(Boolean);
  profile.targetPositions=g('target_positions').split(/[,，、]/).map(s=>s.trim()).filter(Boolean);

  if(!profile.educations?.[0])profile.educations=[{}];
  const e=profile.educations[0];
  e.type=g('edu_type')||'本科';e.school=g('edu_school');e.major=g('edu_major');
  e.gpa=g('edu_gpa');e.ranking=g('edu_ranking');

  let intern=profile.experiences?.find(x=>x.type==='实习');
  if(!intern){intern={type:'实习',organization:'',role:'',startDate:'',endDate:'',description:'',bullets:[],techStack:[],achievements:[]};profile.experiences.unshift(intern);}
  intern.organization=g('intern_company');intern.role=g('intern_role');intern.description=g('intern_desc');

  let proj=profile.experiences?.find(x=>x.type==='项目');
  if(!proj){proj={type:'项目',organization:'',role:'',startDate:'',endDate:'',description:'',bullets:[],techStack:[],achievements:[]};profile.experiences.push(proj);}
  proj.organization=g('proj_name');proj.role=g('proj_role');
  proj.techStack=g('proj_tech').split(/[,，、]/).map(s=>s.trim()).filter(Boolean);
  proj.description=g('proj_desc');

  await chrome.storage.local.set({profile});
  // Update nav dots
  renderProfilePanel();
};

// Open editor button
$('#btnOpenEditor').onclick=()=>{
  chrome.tabs.create({url:chrome.runtime.getURL('resume-editor.html')});
};

// ===== Apply Panel =====
$('#btnScan').onclick=async()=>{
  const btn=$('#btnScan');btn.textContent='扫描中...';btn.disabled=true;
  chrome.runtime.sendMessage({type:'SCAN_PAGE'},async res=>{
    btn.textContent='扫描当前页面表单';btn.disabled=false;
    if(!res?.ok){
      $('#scanPreview').innerHTML='<div class="tip" style="border-color:rgba(239,68,68,.3);color:var(--danger)">扫描失败: '+(res?.error||'未知')+'</div>';
      return;
    }
    scannedFields=res.fields||[];
    const {profile}=await chrome.storage.local.get(['profile']);
    let matched=0;
    scannedFields.forEach(f=>{
      if(profile&&window.ResuMatchTemplate){
        const m=window.ResuMatchTemplate.matchField(f.label,profile);
        if(m.value){f._matchValue=m.value;matched++;}
      }
    });
    const rows=scannedFields.slice(0,15).map(f=>{
      const v=f._matchValue||'';
      return '<div class="row"><span class="label">'+f.label+'</span><span class="tag '+(v?'ok':'err')+'">'+(v||'---')+'</span></div>';
    }).join('');
    $('#scanPreview').innerHTML='<div class="section-card"><div class="section-head"><span class="title">扫描结果 — '+scannedFields.length+' 字段，匹配 '+matched+' 个</span></div><div class="section-body">'+rows+(scannedFields.length>15?'<div class="text-secondary">... 还有 '+(scannedFields.length-15)+' 个字段</div>':'')+'</div></div>';
    $('#btnFill').classList.remove('hidden');$('#btnClear').classList.remove('hidden');
  });
};

$('#btnFill').onclick=async()=>{
  const {profile}=await chrome.storage.local.get(['profile']);
  const fillData=scannedFields.map(f=>({id:f.id,value:f._matchValue||''}));
  chrome.runtime.sendMessage({type:'FILL_PAGE',data:fillData},res=>{
    if(!res?.ok)return;
    const ok=res.results.filter(r=>r.status==='success').length;
    const fail=res.results.filter(r=>r.status==='failed').length;
    $('#fillResult').innerHTML='<div class="tip" style="border-color:rgba(34,197,94,.3);color:var(--success)">'+ok+' 成功，'+fail+' 失败，共 '+scannedFields.length+' 字段</div>';
  });
};

$('#btnClear').onclick=()=>{
  chrome.runtime.sendMessage({type:'CLEAR_PAGE'});
  scannedFields=[];$('#scanPreview').innerHTML='';$('#fillResult').innerHTML='';
  $('#btnFill').classList.add('hidden');$('#btnClear').classList.add('hidden');
};

})();
