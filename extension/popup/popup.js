// ResuMatch Popup — 学习 AI-Resume-Form-Filling-Assistant
(function(){
'use strict';
const API='http://localhost:8000/api/v1';
let fields=[],profile=null;
const $=s=>document.querySelector(s);

// Status
fetch(API+'/health').then(r=>r.json()).then(d=>{
  if(d.status==='ok'){
    const b=$('#statusBadge');b.className='status-badge on';
    b.innerHTML='<span class="status-dot"></span><span>已连接</span>';
  }
}).catch(()=>{});

chrome.storage.local.get(['profile'],d=>{profile=d.profile;});

// ===== Scan =====
$('#scan').onclick=()=>{
  const btn=$('#scan');btn.textContent='扫描中...';btn.disabled=true;
  chrome.tabs.query({active:true,currentWindow:true},tabs=>{
    chrome.scripting.executeScript({target:{tabId:tabs[0].id},func:scanPage}).then(async([r])=>{
      btn.textContent='重新扫描';btn.disabled=false;
      fields=r.result.fields||[];
      // Dedup
      const seen=new Set();fields=fields.filter(f=>{const k=f.label+f.tag+f.type;if(seen.has(k))return false;seen.add(k);return true;});
      const d=await chrome.storage.local.get(['profile']);profile=d.profile;

      // Local match
      let auto=0,review=0;
      fields.forEach(f=>{
        const v=matchFieldLocal(f,profile);
        if(v){f.ai_value=v.value;f.ai_action=v.action;f.ai_strategy=v.strategy;}
        else{f.ai_value='';f.ai_action='skip';}
        if(f.ai_action==='auto_fill')auto++;else if(f.ai_action==='review')review++;
      });

      // LLM fallback
      const unmatched=fields.filter(f=>f.ai_action==='skip');
      if(unmatched.length>0&&profile){
        try{
          const fr=await fetch(API+'/form/fill',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fields:unmatched})});
          const plan=await fr.json();
          (plan.fill_plan||[]).forEach(p=>{const idx=fields.indexOf(unmatched[p.index]);if(idx>=0){fields[idx].ai_value=p.value;fields[idx].ai_action=p.action||'auto_fill';fields[idx].ai_strategy=p.fill_strategy||'text';if(p.action==='auto_fill')auto++;}});
        }catch(e){console.log('LLM fallback:',e);}
      }

      // Stats
      $('#statsGrid').classList.remove('hidden');
      $('#statFields').textContent=fields.length;
      $('#statAuto').textContent=auto;
      $('#statManual').textContent=review;

      // Preview
      const skip=fields.length-auto-review;
      $('#result').innerHTML=
        fields.map(f=>{
          const v=f.ai_value||'';const act=f.ai_action||'skip';
          const badge=act==='auto_fill'?'<span class="badge auto">自动</span>':
                      act==='review'?'<span class="badge review">确认</span>':'<span class="badge skip">跳过</span>';
          return '<div class="row"><span>'+f.label+'</span>'+badge+'</div>';
        }).join('');

      $('#fill').classList.remove('hidden');
      $('#fill').textContent='一键填充 ('+auto+'/'+fields.length+')';
    }).catch(e=>{
      btn.textContent='扫描页面';btn.disabled=false;
      $('#result').innerHTML='<div class="row"><span style="color:var(--danger)">'+e.message+'</span></div>';
    });
  });
};

// ===== Fill =====
$('#fill').onclick=()=>{
  const btn=$('#fill');btn.textContent='填充中...';btn.disabled=true;
  const data=fields.filter(f=>f.ai_value).map(f=>({id:f.id,value:f.ai_value,strategy:f.ai_strategy||'text',tag:f.tag,type:f.type,options:f.options||[]}));
  chrome.tabs.query({active:true,currentWindow:true},tabs=>{
    chrome.scripting.executeScript({target:{tabId:tabs[0].id},func:fillPage,args:[data]}).then(([r])=>{
      btn.textContent='一键填充';btn.disabled=false;
      const ok=(r.result||[]).filter(x=>x.status==='success').length;
      const total=(r.result||[]).length;
      $('#result').innerHTML='<div class="row" style="color:var(--success)">'+ok+'/'+total+' 填充成功</div>'+
        (r.result||[]).map(x=>'<div class="row"><span>'+x.label+'</span><span style="color:'+(x.status==='success'?'var(--success)':'var(--danger)')+';font-size:10px">'+(x.status==='success'?x.value:'失败')+'</span></div>').join('');
    }).catch(e=>{btn.textContent='一键填充';btn.disabled=false;});
  });
};

// ===== Upload sidebar =====
$('#upload').onclick=()=>{
  chrome.windows.create({url:chrome.runtime.getURL('sidebar/sidebar.html'),type:'popup',width:440,height:640});
  window.close();
};

// ===== Local matching =====
function matchFieldLocal(f,profile){
  if(!profile)return null;
  const label=(f.label||'').replace(/[*：:\s（）()【】\[\]]/g,'').replace(/请输入|请选择|请填写|必填|选填|（必填）|（选填）/g,'');
  const edu=(profile.educations||[])[0]||{};
  const intern=(profile.experiences||[]).find(x=>x.type==='实习')||{};
  const proj=(profile.experiences||[]).find(x=>x.type==='项目')||{};
  const opts=f.options||[];

  function matchOpt(val){
    if(!val||!opts.length)return null;
    if(window.ResumeSchema&&window.ResumeSchema.matchSelectOption){
      return window.ResumeSchema.matchSelectOption(opts,val)||null;
    }
    const found=opts.find(o=>o===val||o.includes(val)||val.includes(o));
    if(found)return found;
    const b=opts.reduce((b,o)=>{const s=[...val].filter(c=>o.includes(c)).length/val.length;return s>b.s?{o,s}:b;},{o:null,s:0});
    return b.s>=0.4?b.o:null;
  }

  const rules={
    '姓名':profile.name,'名字':profile.name,'中文名':profile.name,
    '性别':()=>matchOpt(profile.gender)||profile.gender,
    '手机':profile.phone,'电话':profile.phone,'手机号':profile.phone,'手机号码':profile.phone,'mobile':profile.phone,'tel':profile.phone,
    '邮箱':profile.email,'电子邮箱':profile.email,'email':profile.email,'mail':profile.email,
    '出生':()=>(profile.birthDate||'').replace(/-/g,''),'生日':()=>profile.birthDate||'','出生日期':()=>profile.birthDate||'','出生年月':()=>(profile.birthDate||'').replace(/-/g,''),
    '证件号':profile.idNumber||'','身份证':profile.idNumber||'','证件类型':()=>matchOpt('身份证')||'身份证',
    '民族':()=>matchOpt(profile.ethnicity||'汉族')||'汉族',
    '政治面貌':()=>matchOpt(profile.politicalStatus||'共青团员')||'共青团员',
    '籍贯':profile.nativePlace||'','户籍':profile.nativePlace||'','户口':profile.nativePlace||'',
    '现居':profile.currentCity||'','所在城市':profile.currentCity||'','居住地':profile.currentCity||'',
    '微信':profile.wechat||'','微信号':profile.wechat||'',
    '毕业学校':edu.school||'','学校':edu.school||'','院校':edu.school||'','大学':edu.school||'','school':edu.school||'',
    '学院':edu.college||'','院系':edu.college||'',
    '专业':edu.major||'','所学专业':edu.major||'','毕业专业':edu.major||'','major':edu.major||'',
    '学历':()=>matchOpt(edu.type||'本科')||'本科','最高学历':()=>matchOpt(edu.type||'本科')||'本科','学位':()=>matchOpt(edu.type||'本科')||'本科',
    '培养方式':'全日制','学习形式':'全日制',
    '入学':(edu.startDate||'').replace(/-/g,''),'入学时间':(edu.startDate||'').replace(/-/g,''),
    '毕业时间':(edu.endDate||'').replace(/-/g,''),'预计毕业':(edu.endDate||'').replace(/-/g,''),
    'GPA':edu.gpa||'','gpa':edu.gpa||'','绩点':edu.gpa||'','平均成绩':edu.gpa||'',
    '排名':edu.ranking||'','名次':edu.ranking||'','ranking':edu.ranking||'',
    '四级':edu.cet4||'','CET4':edu.cet4||'','cet4':edu.cet4||'','英语四级':edu.cet4||'',
    '六级':edu.cet6||'','CET6':edu.cet6||'','cet6':edu.cet6||'','英语六级':edu.cet6||'',
    '实习公司':intern.organization||'','实习单位':intern.organization||'',
    '实习岗位':intern.role||'','实习职位':intern.role||'',
    '项目名称':proj.organization||'','项目名':proj.organization||'',
    '项目角色':proj.role||'','技术栈':(proj.techStack||[]).join('、'),'使用技术':(proj.techStack||[]).join('、'),
    '项目成果':(proj.achievements||proj.bullets||[])[0]||'',
    '论文':profile.publications||'','发表论文':profile.publications||'',
    '竞赛':profile.competitions||'','获奖':profile.awards||'','竞赛获奖':profile.competitions||profile.awards||'',
    '自我评价':profile.selfEvaluation||'','自我介绍':profile.selfEvaluation||'','个人评价':profile.selfEvaluation||'',
    '意向城市':(profile.targetCities||[]).join('、'),'意向岗位':(profile.targetPositions||[]).join('、'),
    '期望薪资':profile.expectedSalary||'','到岗时间':profile.availableDate||'',
    '语言':'否','掌握母语':'否','奖学金':'无',
    '现居城市':profile.currentCity||'','家庭住址':profile.nativePlace||'',
  };

  for(const [kw,fn] of Object.entries(rules)){
    if(label===kw||(kw.length>=4&&label.startsWith(kw))||(kw.length>=4&&label.endsWith(kw))){
      const v=typeof fn==='function'?fn():fn;if(v)return{value:v,action:'auto_fill',strategy:f.tag==='select'?'select':'text'};
    }
  }
  for(const [kw,fn] of Object.entries(rules)){
    if(kw.length>=4&&label.includes(kw)){
      const v=typeof fn==='function'?fn():fn;if(v)return{value:v,action:'auto_fill',strategy:f.tag==='select'?'select':'text'};
    }
  }
  for(const [kw,fn] of Object.entries(rules)){
    if(kw.length<3)continue;const ol=[...kw].filter(c=>label.includes(c)).length/kw.length;
    if(ol>=0.7){const v=typeof fn==='function'?fn():fn;if(v)return{value:v,action:'review',strategy:'text'};}
  }
  return null;
}

// ===== Page functions =====
function scanPage(){
  function clean(t){return(t||'').replace(/[*：:]/g,'').replace(/\s+/g,' ').replace(/请输入|请选择|请填写|必填|选填|（必填）|（选填）/g,'').trim();}
  function findLabel(el){
    if(el.id){const lb=document.querySelector('label[for="'+CSS.escape(el.id)+'"]');if(lb&&lb.textContent&&lb.textContent.trim())return clean(lb.textContent);}
    for(const s of['.ant-form-item','.el-form-item','.form-item','.form-group','tr','td','[class*=item]']){
      const c=el.closest(s);if(c){const lb=c.querySelector('.ant-form-item-label label,.el-form-item__label,label,.label,[class*="label"]');if(lb&&lb!==el&&lb.textContent&&lb.textContent.trim()&&lb.textContent.trim().length<80)return clean(lb.textContent);}
    }
    const pl=el.closest('label');if(pl&&pl.textContent)return clean(pl.textContent.replace(el.value||'','').trim())||clean(pl.textContent);
    const ph=el.getAttribute('placeholder')||'';if(ph&&ph.length<40)return clean(ph);
    const aria=el.getAttribute('aria-label')||'';if(aria)return clean(aria);
    return(el.getAttribute('name')||'').replace(/[_-]/g,'')||'';
  }
  function radioContainer(el){let p=el.parentElement;for(let i=0;i<6&&p;i++){if(p.querySelectorAll('input[type="radio"]').length>=2)return p;p=p.parentElement;}return el.parentElement;}

  const fields=[],seen=new Set();
  document.querySelectorAll('input[type="radio"]').forEach(el=>{
    if(seen.has(el))return;
    const c=radioContainer(el),g=c.querySelectorAll('input[type="radio"]');
    const opts=Array.from(g).map(r=>{
      if(r.labels&&r.labels.length)return r.labels[0].textContent.trim();
      const pp=r.closest('label');if(pp)return clean(pp.textContent.replace(r.value,'',''))||r.value;
      return r.value;
    });
    let label='';const fi=c.closest('.ant-form-item,.el-form-item,.form-item,[class*=form-item]');
    if(fi){const lb=fi.querySelector('.ant-form-item-label label,.el-form-item__label,label,.label');if(lb)label=clean(lb.textContent);}
    if(!label){for(const r of g){const l=findLabel(r);if(l&&l!=='字段'){label=l;break;}}}
    const id='rg_'+Math.random().toString(36).slice(2,8);
    g.forEach(r=>{r.setAttribute('data-rm-id',id);seen.add(r);});
    fields.push({id,label:label||'单选项',tag:'radio',type:'radio',options:opts,required:false});
  });
  document.querySelectorAll('input:not([type="hidden"]):not([type="radio"]):not([type="submit"]):not([type="button"]):not([type="reset"]), select, textarea, [contenteditable="true"]').forEach((el,i)=>{
    if(seen.has(el))return;
    const s=getComputedStyle(el);if(s.display==='none'||s.visibility==='hidden')return;
    if(el.disabled){seen.add(el);return;}
    const t=(el.type||'').toLowerCase();
    if(['hidden','submit','button','reset','image','file'].includes(t))return;
    if((el.getAttribute('name')||'').toLowerCase().includes('captcha'))return;
    const id='f'+i;el.setAttribute('data-rm-id',id);seen.add(el);
    const f={id,label:findLabel(el)||('字段_'+i),tag:el.tagName.toLowerCase(),type:t,placeholder:el.getAttribute('placeholder')||'',required:el.hasAttribute('required'),options:[]};
    if(el.tagName==='SELECT')f.options=Array.from(el.options).map(o=>o.textContent.trim()).filter(x=>x&&x!=='请选择'&&x!=='--请选择--');
    fields.push(f);
  });
  return {fields};
}

function fillPage(data){
  const R=[];
  if(!document.getElementById('rm-css')){const s=document.createElement('style');s.id='rm-css';s.textContent='[data-rm-status="success"]{outline:2px solid #22c55e!important}[data-rm-status="error"]{outline:2px solid #ef4444!important}';document.head.appendChild(s);}
  const isv=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')?.set;
  const tsv=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value')?.set;

  data.forEach(({id,value,strategy,tag,type,options})=>{
    if(!value)return;
    const els=document.querySelectorAll('[data-rm-id="'+id+'"]');
    if(!els.length){R.push({label:id,status:'failed',error:'未找到'});return;}
    try{
      if(tag==='radio'||type==='radio'||strategy==='radio_click'){
        let matched=false;
        for(const el of els){
          const v=el.value||'';let lb='';if(el.labels&&el.labels.length)lb=el.labels[0].textContent.trim();
          if(!lb){const pp=el.closest('label');if(pp)lb=pp.textContent.replace(v,'').trim();}
          if(v===value||lb===value||lb.includes(value)||(value&&value.includes(lb))){el.click();el.checked=true;el.dispatchEvent(new Event('change',{bubbles:true}));matched=true;break;}
        }
        if(!matched){for(const el of els){if(value[0]&&(el.value||'').includes(value[0])||value.includes(el.value||''[0])){el.click();el.checked=true;el.dispatchEvent(new Event('change',{bubbles:true}));matched=true;break;}}}
        els[0].setAttribute('data-rm-status',matched?'success':'error');
        R.push({label:els[0].getAttribute('data-rm-id'),status:matched?'success':'failed',value});return;
      }
      if(tag==='select'||strategy==='select'||strategy==='custom_select'){
        const el=els[0];
        if(el.tagName==='SELECT'){
          const opts=Array.from(el.options);
          let found=opts.find(o=>o.value===value||o.textContent.trim()===value);
          if(!found)found=opts.find(o=>o.textContent.includes(value)||(value&&value.includes(o.textContent.trim())));
          if(!found&&value){let b=null,bs=0;opts.forEach(o=>{if(!o.value||o.value==='-1')return;const sc=[...value].filter(c=>o.textContent.includes(c)).length/value.length;if(sc>bs&&sc>=0.3){bs=sc;b=o;}});found=b;}
          if(found){el.value=found.value;el.dispatchEvent(new Event('change',{bubbles:true}));el.setAttribute('data-rm-status','success');R.push({label:id,status:'success',value:found.textContent.trim()});}
          else{el.setAttribute('data-rm-status','error');R.push({label:id,status:'failed',value,error:'无匹配'});}
        }else{
          el.click();setTimeout(()=>{},200);
          if(isv)isv.call(el,value);else el.value=value;
          el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));
          el.setAttribute('data-rm-status','success');R.push({label:id,status:'success',value});
        }
        return;
      }
      if(strategy==='datepicker'||type==='date'||type==='month'){
        const el=els[0];el.focus();
        if(isv)isv.call(el,value);else el.value=value;
        el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));
        el.setAttribute('data-rm-status','success');R.push({label:id,status:'success',value});return;
      }
      const el=els[0];
      if(el.getAttribute('contenteditable')==='true'){el.innerHTML=value;el.dispatchEvent(new Event('input',{bubbles:true}));}
      else{
        const setter=el.tagName==='TEXTAREA'?tsv:isv;
        el.focus();el.dispatchEvent(new Event('focus',{bubbles:true}));
        if(setter)setter.call(el,value);else el.value=value;
        el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));
        el.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText'}));
        el.dispatchEvent(new Event('blur',{bubbles:true}));
      }
      el.setAttribute('data-rm-status','success');R.push({label:id,status:'success',value});
    }catch(e){R.push({label:id,status:'failed',error:e.message});}
  });
  return R;
}
})();
