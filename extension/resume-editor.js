// ResuMatch Resume Editor — 14分区完整编辑器
(function(){
'use strict';
const S=window.ResumeSchema;
const $=s=>document.querySelector(s);
let profile=null;

// Migrate old flat format → new 14-section format
function migrateOldProfile(old){
  if(!old||!S)return S.createEmptyProfile();
  // Already new format
  if(old.personal)return old;

  const p=S.createEmptyProfile();
  const edu=old.educations?.[0]||{};
  const exps=old.experiences||[];

  // Basic info → personal
  p.personal.fullName=old.name||'';
  p.personal.email=old.email||'';
  p.personal.phone=old.phone||'';
  p.personal.gender=old.gender||'';
  p.personal.birthDate=old.birthDate||'';
  p.personal.idNumber=old.idNumber||'';
  p.personal.nationality=old.ethnicity||'';
  p.personal.politicalStatus=old.politicalStatus||'';
  p.personal.currentCity=old.currentCity||'';
  p.personal.hometownCity=old.nativePlace||'';
  p.personal.wechat=old.wechat||'';
  p.personal.summary=old.selfEvaluation||'';
  p.personal.highestEducationLevel=edu.type||'';
  p.additional.awards=old.awards||'';
  p.additional.publications=old.publications||'';
  p.additional.competitions=old.competitions||'';

  // Education
  if(edu.school||edu.major){
    p.educations[0]={school:'',degree:'',major:'',startDate:'',endDate:'',college:'',gpa:'',ranking:'',cet4:'',cet6:''};
    p.educations[0].school=edu.school||'';
    p.educations[0].degree=edu.type||'';
    p.educations[0].major=edu.major||'';
    p.educations[0].startDate=edu.startDate||'';
    p.educations[0].endDate=edu.endDate||'';
    p.educations[0].college=edu.college||'';
    p.educations[0].gpa=edu.gpa||'';
    p.educations[0].ranking=edu.ranking||'';
    p.educations[0].cet4=edu.cet4||'';
    p.educations[0].cet6=edu.cet6||'';
  }

  // Experiences → internships, workExperiences, projects
  let internIdx=0, workIdx=0, projIdx=0;
  exps.forEach(e=>{
    if(e.type==='实习'&&internIdx<(S.getSectionDefinition('internships')?.slots||3)){
      const t=p.internships[internIdx];
      t.company=e.organization||'';t.title=e.role||'';
      t.startDate=e.startDate||'';t.endDate=e.endDate||'';
      t.description=e.description||'';
      t.technologies=(e.techStack||[]).join('、');
      if(e.achievements?.length)t.achievements=e.achievements[0];
      internIdx++;
    }else if(e.type==='工作'&&workIdx<(S.getSectionDefinition('workExperiences')?.slots||3)){
      const t=p.workExperiences[workIdx];
      t.company=e.organization||'';t.title=e.role||'';
      t.startDate=e.startDate||'';t.endDate=e.endDate||'';
      t.description=e.description||'';
      t.technologies=(e.techStack||[]).join('、');
      if(e.achievements?.length)t.achievements=e.achievements[0];
      workIdx++;
    }else if(e.type==='项目'&&projIdx<(S.getSectionDefinition('projects')?.slots||4)){
      const t=p.projects[projIdx];
      t.name=e.organization||'';t.role=e.role||'';
      t.startDate=e.startDate||'';t.endDate=e.endDate||'';
      t.description=e.description||'';
      t.technologies=(e.techStack||[]).join('、');
      if(e.achievements?.length)t.highlights=e.achievements[0];
      projIdx++;
    }
  });

  // Skills
  const skillLines=[];
  (old.skills||[]).forEach(s=>{
    skillLines.push((s.category||'other')+': '+(s.items||[]).join('、'));
  });
  p.skills.primarySkills=skillLines.join('\n');

  // Job preferences
  p.jobPreferences.targetRole=(old.targetPositions||[]).join('、');
  p.jobPreferences.expectedCity=(old.targetCities||[]).join('、');
  p.jobPreferences.expectedSalary=old.expectedSalary||'';

  return p;
}

// Load profile
async function loadProfile(){
  const {profile:old}=await chrome.storage.local.get(['profile']);
  if(S&&S.createEmptyProfile){
    profile=migrateOldProfile(old);
  }else{
    profile=old||{};
  }
  render();
}

function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

function render(){
  if(!S||!S.SECTIONS){$('#sectionContent').innerHTML='<div class="tip">Schema 未加载</div>';return;}

  // Nav
  const sections=S.SECTIONS;
  $('#sectionNav').innerHTML=sections.map((s,i)=>
    '<button class="nav-btn'+(i===0?' active':'')+'" data-index="'+i+'">'+
      '<span class="nav-label">'+s.label+'</span>'+
      '<span class="nav-meta">'+(s.type==='group'?s.fields.length+' 字段':(s.slots||1)+' 条')+'</span>'+
    '</button>'
  ).join('');

  // Click
  document.querySelectorAll('.nav-btn').forEach(b=>{
    b.onclick=()=>{
      document.querySelectorAll('.nav-btn').forEach(x=>x.classList.remove('active'));
      b.classList.add('active');
      renderSection(parseInt(b.dataset.index));
      // Scroll to section
      const target=$('#sec-'+b.dataset.index);
      if(target)target.scrollIntoView({behavior:'smooth',block:'start'});
    };
  });

  // Render all sections
  $('#sectionContent').innerHTML=sections.map((s,i)=>
    '<div class="section" id="sec-'+i+'">'+renderSectionHTML(s,i)+'</div>'
  ).join('');
}

function renderSectionHTML(section,index){
  const data=profile?.[section.key]||(section.type==='group'?{}:[]);
  let body='';

  if(section.type==='group'){
    const fields=section.fields.map(f=>{
      const val=data[f.key]||'';
      const path=section.key+'.'+f.key;
      if(f.input==='textarea'){
        return '<div class="form-group field-full"><label>'+f.label+'</label><textarea class="textarea" data-path="'+path+'" placeholder="'+esc(f.placeholder||'')+'">'+esc(val)+'</textarea></div>';
      }else if(f.input==='select'){
        const opts=(f.options||[]).map(o=>'<option value="'+esc(o)+'"'+(val===o?' selected':'')+'>'+esc(o||'请选择')+'</option>').join('');
        return '<div class="form-group"><label>'+f.label+'</label><select class="select" data-path="'+path+'">'+opts+'</select></div>';
      }else if(f.input==='date'){
        return '<div class="form-group"><label>'+f.label+'</label><input class="input" type="date" data-path="'+path+'" value="'+esc(val)+'" placeholder="'+esc(f.placeholder||'')+'"></div>';
      }else{
        return '<div class="form-group"><label>'+f.label+'</label><input class="input" type="'+(f.input==='email'?'email':f.input==='tel'?'tel':f.input==='url'?'url':'text')+'" data-path="'+path+'" value="'+esc(val)+'" placeholder="'+esc(f.placeholder||'')+'"></div>';
      }
    });

    // Split into 2-col grid, textareas full width
    let html='';let nonFull=[];
    fields.forEach(f=>{
      if(f.includes('field-full')){if(nonFull.length){html+='<div class="fields-grid">'+nonFull.join('')+'</div>';nonFull=[];}html+=f;}
      else nonFull.push(f);
    });
    if(nonFull.length)html+='<div class="fields-grid">'+nonFull.join('')+'</div>';

    body='<div class="section-body">'+html+'</div>';
  }else{
    // List type
    const slots=section.slots||1;
    let slotsHTML='';
    for(let i=0;i<slots;i++){
      const item=Array.isArray(data)?(data[i]||{}):{};
      const itemFields=section.fields.map(f=>{
        const val=item[f.key]||'';
        const path=section.key+'.'+i+'.'+f.key;
        if(f.input==='textarea'){
          return '<div class="form-group field-full"><label>'+f.label+'</label><textarea class="textarea" data-path="'+path+'" placeholder="'+esc(f.placeholder||'')+'">'+esc(val)+'</textarea></div>';
        }else if(f.input==='select'){
          const opts=(f.options||[]).map(o=>'<option value="'+esc(o)+'"'+(val===o?' selected':'')+'>'+esc(o||'请选择')+'</option>').join('');
          return '<div class="form-group"><label>'+f.label+'</label><select class="select" data-path="'+path+'">'+opts+'</select></div>';
        }else if(f.input==='date'){
          return '<div class="form-group"><label>'+f.label+'</label><input class="input" type="date" data-path="'+path+'" value="'+esc(val)+'" placeholder="'+esc(f.placeholder||'')+'"></div>';
        }else{
          return '<div class="form-group"><label>'+f.label+'</label><input class="input" type="'+(f.input==='email'?'email':f.input==='tel'?'tel':f.input==='url'?'url':'text')+'" data-path="'+path+'" value="'+esc(val)+'" placeholder="'+esc(f.placeholder||'')+'"></div>';
        }
      });
      let itemHTML='';let nonFull=[];
      itemFields.forEach(f=>{
        if(f.includes('field-full')){if(nonFull.length){itemHTML+='<div class="fields-grid">'+nonFull.join('')+'</div>';nonFull=[];}itemHTML+=f;}
        else nonFull.push(f);
      });
      if(nonFull.length)itemHTML+='<div class="fields-grid">'+nonFull.join('')+'</div>';

      slotsHTML+='<div class="slot"><div class="slot-head"><span class="slot-title">'+section.itemLabel+' #'+(i+1)+'</span></div>'+itemHTML+'</div>';
    }
    body='<div class="section-body">'+slotsHTML+'</div>';
  }

  const note=section.note||'';
  return '<div class="section-card">'+
    '<div class="section-head" onclick="this.closest(\'.section-card\').querySelector(\'.section-body\').classList.toggle(\'is-collapsed\')">'+
      '<div><div class="section-title" style="cursor:pointer">'+section.label+'</div>'+
      (note?'<div class="section-summary">'+note+'</div>':'')+'</div>'+
      '<span class="section-toggle">▾</span>'+
    '</div>'+body+
  '</div>';
}

function renderSection(index){
  // Scroll to section — handled by nav click
}

// Save
$('#btnSave').onclick=async()=>{
  // Read all fields
  if(!S||!S.SECTIONS)return;

  // Build empty profile
  const p=S.createEmptyProfile();

  document.querySelectorAll('[data-path]').forEach(el=>{
    const path=el.dataset.path;
    const val=el.value||'';
    setByPath(p,path,val);
  });

  // Convert to our simpler format for compatibility
  const simple={
    name:p.personal?.fullName||'',email:p.personal?.email||'',
    phone:p.personal?.phone||'',gender:p.personal?.gender||'',
    birthDate:p.personal?.birthDate||'',idNumber:p.personal?.idNumber||'',
    ethnicity:p.personal?.nationality||'',politicalStatus:p.personal?.politicalStatus||'',
    nativePlace:p.personal?.hometownCity||'',currentCity:p.personal?.currentCity||'',
    wechat:p.personal?.wechat||'',
    educations:[],experiences:[],skills:[],targetCities:[],targetPositions:[],
    selfEvaluation:p.personal?.summary||'',awards:p.additional?.awards||'',
    publications:p.additional?.publications||'',competitions:p.additional?.competitions||'',
  };

  // Education
  (p.educations||[]).forEach(e=>{
    if(e.school||e.major){
      simple.educations.push({
        type:e.degree||'本科',school:e.school||'',major:e.major||'',
        startDate:e.startDate||'',endDate:e.endDate||'',
        college:e.college||'',gpa:e.gpa||'',ranking:e.ranking||'',
        cet4:e.cet4||'',cet6:e.cet6||'',
      });
    }
  });

  // Internships
  (p.internships||[]).forEach(e=>{
    if(e.company||e.title){
      simple.experiences.push({
        type:'实习',organization:e.company||'',role:e.title||'',
        startDate:e.startDate||'',endDate:e.endDate||'',
        description:e.description||'',achievements:e.achievements?[e.achievements]:[],
        techStack:(e.technologies||'').split(/[,，、]/).filter(Boolean),
        bullets:[],order:0,
      });
    }
  });

  // Work
  (p.workExperiences||[]).forEach(e=>{
    if(e.company||e.title){
      simple.experiences.push({
        type:'工作',organization:e.company||'',role:e.title||'',
        startDate:e.startDate||'',endDate:e.endDate||'',
        description:e.description||'',achievements:e.achievements?[e.achievements]:[],
        techStack:(e.technologies||'').split(/[,，、]/).filter(Boolean),
        bullets:[],order:0,
      });
    }
  });

  // Projects
  (p.projects||[]).forEach(e=>{
    if(e.name){
      simple.experiences.push({
        type:'项目',organization:e.name||'',role:e.role||'',
        startDate:e.startDate||'',endDate:e.endDate||'',
        description:e.description||'',
        techStack:(e.technologies||'').split(/[,，、]/).filter(Boolean),
        achievements:e.highlights?[e.highlights]:[],
        bullets:[],order:0,
      });
    }
  });

  // Skills — concat all skill fields
  const skillParts=[];
  const skillKeys=['primarySkills','programmingLanguages','frameworks','databases','aiTools','cloudPlatforms','tooling','domainKnowledge'];
  skillKeys.forEach(k=>{if(p.skills?.[k])skillParts.push(p.skills[k]);});
  const skillText=skillParts.join('\n');
  const skillMap={};
  skillText.split(/[,，、\n]/).forEach(s=>{s=s.trim();if(s&&s.length<40){const cat='other';if(!skillMap[cat])skillMap[cat]=[];if(!skillMap[cat].includes(s))skillMap[cat].push(s);}});
  simple.skills=Object.entries(skillMap).map(([c,items])=>({category:c,items}));

  // Job prefs
  simple.targetPositions=(p.jobPreferences?.targetRole||'').split(/[,，、]/).filter(Boolean);
  simple.targetCities=(p.jobPreferences?.expectedCity||'').split(/[,，、]/).filter(Boolean);
  simple.expectedSalary=p.jobPreferences?.expectedSalary||'';

  await chrome.storage.local.set({profile:simple});
  alert('已保存! 数据已同步到填表流程。');
};

// Reset
$('#btnReset').onclick=()=>{
  if(confirm('确定要清空所有档案数据吗？此操作不可撤销。')){
    chrome.storage.local.remove(['profile']);
    profile=null;
    render();
  }
};

function setByPath(obj,path,val){
  const segs=path.split('.');
  let cur=obj;
  for(let i=0;i<segs.length-1;i++){cur=cur[segs[i]];}
  cur[segs[segs.length-1]]=val;
}

loadProfile();
})();
