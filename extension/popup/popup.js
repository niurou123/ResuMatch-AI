// ResuMatch Popup v3 — 完整修复版
(function(){
const API='http://localhost:8000/api/v1';
let fields=[],profile=null;

// 后端检测
fetch(API+'/health').then(r=>r.json()).then(d=>{
  if(d.status==='ok')document.getElementById('status').className='info ok',document.getElementById('status').textContent='🟢 后端已连接';
}).catch(()=>{});
chrome.storage.local.get(['profile'],d=>{profile=d.profile;});

// ========== 扫描 ==========
document.getElementById('scan').onclick=()=>{
  const btn=document.getElementById('scan');btn.textContent='⏳ 扫描中...';
  chrome.tabs.query({active:true,currentWindow:true},tabs=>{
    chrome.scripting.executeScript({target:{tabId:tabs[0].id},func:scanPage}).then(([r])=>{
      btn.textContent='🔍 重新扫描';fields=r.result.fields||[];
      // 去重
      const seen=new Set();fields=fields.filter(f=>{const k=f.label+f.tag+f.type;if(seen.has(k))return false;seen.add(k);return true;});
      document.getElementById('result').innerHTML='<div class="info ok">✅ '+fields.length+' 个字段（已去重）</div>'+fields.map(f=>{
        let m='';if(profile){const v=matchF(f);if(v)m=' → <span style="color:#6ee7b7">'+v.substring(0,15)+'</span>';}
        const t=f.tag+(f.options?.length?' ['+f.options.join('/')+']':'');
        return '<div class="row"><span>'+f.label+'</span><span style="font-size:10px;color:#94a3b8">'+t+m+'</span></div>';
      }).join('');
      if(profile)document.getElementById('fill').style.display='block';
    }).catch(e=>{btn.textContent='🔍 扫描当前页面';document.getElementById('result').innerHTML='<div class="info err">'+e.message+'</div>';});
  });
};

// ========== 填充 ==========
document.getElementById('fill').onclick=()=>{
  document.getElementById('fill').textContent='⏳ 填充中...';
  chrome.storage.local.get(['profile'],d=>{profile=d.profile;});
  const data=fields.map(f=>({id:f.id,value:matchF(f)||'',tag:f.tag,type:f.type,options:f.options||[]}));
  chrome.tabs.query({active:true,currentWindow:true},tabs=>{
    chrome.scripting.executeScript({target:{tabId:tabs[0].id},func:fillPage,args:[data]}).then(([r])=>{
      document.getElementById('fill').textContent='✨ 一键填充';
      const ok=(r.result||[]).filter(x=>x.status==='success').length;
      const details=(r.result||[]).map(x=>'<div class="row"><span>'+x.label+'</span><span style="color:'+(x.status==='success'?'#6ee7b7':'#fca5a5')+'">'+(x.status==='success'?'✓ '+x.value:'✗ '+((x.error||'').substring(0,20)))+'</span></div>').join('');
      document.getElementById('result').innerHTML='<div class="info ok">✅ '+ok+'/'+(r.result||[]).length+' 成功</div>'+details;
    }).catch(e=>{document.getElementById('fill').textContent='✨ 一键填充';alert(e.message);});
  });
};

document.getElementById('upload').onclick=()=>{
  chrome.windows.create({url:chrome.runtime.getURL('sidebar/sidebar.html'),type:'popup',width:420,height:620});
  window.close();
};

// ========== 匹配（智能默认值版） ==========
function matchF(f){
  const label=(f.label||'').replace(/[*：:\s（）()【】\[\]]/g,'').replace(/请输入|请选择|请填写|必填|选填|（必填）|（选填）/g,'');
  const edu=(profile?.educations||[])[0]||{};
  const intern=(profile?.experiences||[]).find(x=>x.type==='实习')||{};
  const proj=(profile?.experiences||[]).find(x=>x.type==='项目')||{};

  // 智能默认值
  const DEFAULTS={
    '民族':'汉族','政治面貌':'共青团员','籍贯':'','现家庭住址':'',
    '证件类型':'身份证','奖学金':'无','语言能力':'否','掌握母语':'否',
    '培养方式':'全日制','学习形式':'全日制',
    '性别':profile?.gender||'', // 有则有
  };
  function v(key){return profile?.[key]||DEFAULTS[key]||'';}
  function ev(key){return edu?.[key]||'';}
  function iv(key){return intern?.[key]||'';}
  function pv(key){return proj?.[key]||'';}

  const m={
    '姓名':v('name'),'名字':v('name'),'中文名':v('name'),'全名':v('name'),
    '性别':()=>f.options?.length?matchOpt(f.options,v('gender')):v('gender'),
    '出生年月':()=>(v('birthDate')).replace(/-/g,''),'出生日期':()=>v('birthDate'),'生日':()=>v('birthDate'),
    '手机':v('phone'),'电话':v('phone'),'手机号码':v('phone'),'mobile':v('phone'),
    '邮箱':v('email'),'email':v('email'),'电子邮箱':v('email'),
    '证件号码':v('idNumber'),'身份证':v('idNumber'),'证件类型':()=>f.options?.length?matchOpt(f.options,'身份证'):'身份证',
    '毕业学校':ev('school'),'学校':ev('school'),'院校':ev('school'),'大学':ev('school'),
    '专业':ev('major'),'毕业学校专业':ev('major'),'毕业专业':ev('major'),
    '最高学历':()=>f.options?.length?matchOpt(f.options,ev('type')||'本科'):(ev('type')||'本科'),'学历':()=>f.options?.length?matchOpt(f.options,ev('type')||'本科'):(ev('type')||'本科'),'学位':()=>f.options?.length?matchOpt(f.options,ev('type')||'本科'):(ev('type')||'本科'),
    '民族':()=>f.options?.length?matchOpt(f.options,'汉族'):'汉族',
    '政治面貌':'共青团员','政治身份':'共青团员',
    '籍贯':v('nativePlace'),'现家庭住址':v('nativePlace'),
    '微信':v('wechat'),'微信号':v('wechat'),'wechat':v('wechat'),
    'GPA':ev('gpa'),'绩点':ev('gpa'),'平均成绩':ev('gpa'),
    '排名':ev('ranking'),'名次':ev('ranking'),
    '四级':ev('cet4'),'CET4':ev('cet4'),'英语四级':ev('cet4'),
    '六级':ev('cet6'),'CET6':ev('cet6'),'英语六级':ev('cet6'),
    '实习公司':iv('organization'),'实习单位':iv('organization'),
    '实习岗位':iv('role'),'实习职位':iv('role'),
    '项目名称':pv('organization'),'项目名':pv('organization'),
    '项目角色':pv('role'),'项目技术栈':(pv('techStack')||[]).join('、'),
    '项目成果':(pv('achievements')||[])[0]||'',
    '发表论文':v('publications'),'论文':v('publications'),
    '竞赛':v('competitions'),'获奖':v('awards'),
    '意向城市':(v('targetCities')||''),'意向岗位':(v('targetPositions')||''),
    '期望薪资':v('expectedSalary'),'到岗时间':v('availableDate'),
    '自我评价':v('selfEvaluation'),'自我介绍':v('selfEvaluation'),
    '语言能力':'否','掌握母语':'否',
    '奖学金':'无','培养方式':'全日制','学习形式':'全日制',
  };

  // 精确查找
  for(const [k,v] of Object.entries(m)){
    if(label===k||(label.length>=4&&k.length>=4&&(label.startsWith(k)||label.endsWith(k)))){
      const val=typeof v==='function'?v():v;
      if(val)return val;
    }
    if(k.length>=4&&label.includes(k)){
      const val=typeof v==='function'?v():v;
      if(val)return val;
    }
  }
  // 模糊查找
  for(const [k,v] of Object.entries(m)){
    if(k.length<3)continue;
    const ol=[...k].filter(c=>label.includes(c)).length/k.length;
    if(ol>=0.7){const val=typeof v==='function'?v():v;if(val)return val;}
  }
  return'';
}

function matchOpt(opts,val){
  if(!val||!opts.length)return null;
  const f=opts.find(o=>o===val||o.includes(val)||(val&&val.includes(o)));
  if(f)return f;
  const b=opts.reduce((b,o)=>{if(!o)return b;const s=[...val].filter(c=>o.includes(c)).length/val.length;return s>b.s?{o,s}:b;},{o:null,s:0});
  return b.s>=0.4?b.o:null;
}

// ==================== 页面注入 ====================
function scanPage(){
  function clean(t){return(t||'').replace(/[*：:]/g,'').replace(/\s+/g,' ').replace(/请输入|请选择|请填写|必填|选填|（必填）|（选填）/g,'').trim();}
  function findLabel(el){
    if(el.id){const lb=document.querySelector('label[for="'+CSS.escape(el.id)+'"]');if(lb?.textContent?.trim())return clean(lb.textContent);}
    for(const s of['.ant-form-item','.el-form-item','.form-item','.form-group','tr','td']){
      const c=el.closest(s);if(c){const lb=c.querySelector('.ant-form-item-label label,.el-form-item__label,label,.label');if(lb&&lb!==el&&lb.textContent?.trim()?.length<60)return clean(lb.textContent);}
    }
    const pl=el.closest('label');if(pl?.textContent)return clean(pl.textContent.replace(el.value||'','').trim())||clean(pl.textContent);
    const ph=el.getAttribute('placeholder')||'';if(ph&&ph.length<40&&!ph.includes('请输入')&&!ph.includes('请选择'))return clean(ph);
    return(el.getAttribute('name')||'').replace(/[_-]/g,'')||'';
  }
  function radioContainer(el){let p=el.parentElement;for(let i=0;i<6&&p;i++){if(p.querySelectorAll('input[type="radio"]').length>=2)return p;p=p.parentElement;}return el.parentElement;}

  const fields=[],seen=new Set();
  // Radio
  document.querySelectorAll('input[type="radio"]').forEach(el=>{
    if(seen.has(el))return;
    const c=radioContainer(el),g=c.querySelectorAll('input[type="radio"]');
    const opts=Array.from(g).map(r=>{
      if(r.labels?.length)return r.labels[0].textContent.trim();
      const pp=r.closest('label');if(pp)return clean(pp.textContent.replace(r.value,'',''))||r.value;
      return r.value;
    });
    let label='';const fi=c.closest('.ant-form-item,.el-form-item,.form-item,[class*=form-item]');
    if(fi){const lb=fi.querySelector('.ant-form-item-label label,.el-form-item__label,label,.label');if(lb)label=clean(lb.textContent);}
    if(!label)label=findLabel(g[0]);
    if(!label){const prev=c.previousElementSibling;if(prev?.textContent?.trim().length<30)label=clean(prev.textContent);}
    const id='rg_'+Math.random().toString(36).slice(2,8);
    g.forEach(r=>{r.setAttribute('data-rm-id',id);seen.add(r);});
    fields.push({id,label:label||'单选项',tag:'radio',type:'radio',options:opts});
  });
  // 其余
  document.querySelectorAll('input:not([type="hidden"]):not([type="radio"]):not([type="submit"]):not([type="button"]):not([type="reset"]), select, textarea, [contenteditable="true"]').forEach((el,i)=>{
    if(seen.has(el))return;
    const s=getComputedStyle(el);if(s.display==='none'||s.visibility==='hidden')return;
    const t=(el.type||'').toLowerCase();
    if(['hidden','submit','button','reset','image','file'].includes(t))return;
    if((el.getAttribute('name')||'').toLowerCase().includes('captcha'))return;
    if(el.disabled){seen.add(el);return;} // 跳过 disabled
    const id='f'+i;el.setAttribute('data-rm-id',id);seen.add(el);
    const label=findLabel(el)||'';
    const f={id,label:label||('字段_'+i),tag:el.tagName.toLowerCase(),type:t,value:el.value||''};
    // Select 选项
    if(el.tagName==='SELECT')f.options=Array.from(el.options).map(o=>o.textContent.trim()).filter(x=>x&&x!=='请选择');
    fields.push(f);
  });
  return {fields};
}

function fillPage(data){
  const R=[];
  // CSS
  if(!document.getElementById('rm-css')){const s=document.createElement('style');s.id='rm-css';s.textContent='[data-rm-status="success"]{outline:2px solid #22c55e!important}[data-rm-status="error"]{outline:2px solid #ef4444!important}';document.head.appendChild(s);}
  // Native setter
  const inputSetter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')?.set;
  const textareaSetter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value')?.set;

  data.forEach(({id,value,tag,type,options})=>{
    if(!value)return;
    const els=document.querySelectorAll('[data-rm-id="'+id+'"]');
    if(!els.length){R.push({label:id,status:'failed',error:'未找到元素'});return;}
    try{
      // Radio
      if(tag==='radio'||type==='radio'){
        let matched=false;
        for(const el of els){
          const v=el.value||'';let lb='';if(el.labels?.length)lb=el.labels[0].textContent.trim();
          if(!lb){const pp=el.closest('label');if(pp)lb=pp.textContent.replace(v,'').trim();}
          if(v===value||lb===value||lb.includes(value)||(value&&value.includes(lb))){
            el.click();el.checked=true;el.dispatchEvent(new Event('change',{bubbles:true}));matched=true;break;
          }
        }
        if(!matched){for(const el of els){if(value.includes(el.value[0])||el.value.includes(value[0])){el.click();el.checked=true;el.dispatchEvent(new Event('change',{bubbles:true}));matched=true;break;}}}
        const el0=els[0];el0.setAttribute('data-rm-status',matched?'success':'error');
        R.push({label:el0.getAttribute('data-rm-id'),status:matched?'success':'failed',value});
        return;
      }
      // Select
      if(tag==='select'){
        const el=els[0];const opts=Array.from(el.options);
        let found=opts.find(o=>o.value===value||o.textContent.trim()===value);
        if(!found)found=opts.find(o=>o.textContent.includes(value)||(value&&value.includes(o.textContent.trim())));
        if(!found){let b=null,bs=0;opts.forEach(o=>{if(!o.value||o.value==='-1')return;const sc=[...value].filter(c=>o.textContent.includes(c)).length/value.length;if(sc>bs&&sc>=0.4){bs=sc;b=o;}});found=b;}
        if(found){el.value=found.value;el.dispatchEvent(new Event('change',{bubbles:true}));el.setAttribute('data-rm-status','success');R.push({label:id,status:'success',value:found.textContent.trim()});}
        else{el.setAttribute('data-rm-status','error');R.push({label:id,status:'failed',value,error:'选项未匹配'});}
        return;
      }
      // Text/textarea（使用 native setter 绕过 readonly）
      const el=els[0];
      if(el.getAttribute('contenteditable')==='true'){el.innerHTML=value;el.dispatchEvent(new Event('input',{bubbles:true}));}
      else{
        const setter=el.tagName==='TEXTAREA'?textareaSetter:inputSetter;
        el.focus();el.dispatchEvent(new Event('focus',{bubbles:true}));
        if(setter)setter.call(el,value);else el.value=value;
        el.dispatchEvent(new Event('input',{bubbles:true}));
        el.dispatchEvent(new Event('change',{bubbles:true}));
        el.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText'}));
        el.dispatchEvent(new Event('blur',{bubbles:true}));
      }
      el.setAttribute('data-rm-status','success');
      R.push({label:id,status:'success',value});
    }catch(e){R.push({label:id,status:'failed',error:e.message});}
  });
  return R;
}
})();
