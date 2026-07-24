// ResuMatch Popup v4 — LLM智能匹配版（学习自RESUME_SKILL）
(function(){
const API='http://localhost:8000/api/v1';
let fields=[];

fetch(API+'/health').then(r=>r.json()).then(d=>{
  if(d.status==='ok')document.getElementById('status').className='info ok',document.getElementById('status').textContent='🟢 '+d.app;
}).catch(()=>{});

// ========== 扫描 ==========
document.getElementById('scan').onclick=()=>{
  const btn=document.getElementById('scan');btn.textContent='⏳ 扫描中...';
  chrome.tabs.query({active:true,currentWindow:true},tabs=>{
    chrome.scripting.executeScript({target:{tabId:tabs[0].id},func:scanPage}).then(async([r])=>{
      btn.textContent='🔍 重新扫描';fields=r.result.fields||[];
      // 去重
      const seen=new Set();fields=fields.filter(f=>{const k=f.label+f.tag+f.type;if(seen.has(k))return false;seen.add(k);return true;});

      // 调用后端LLM智能匹配
      document.getElementById('result').innerHTML='<div class="info ok">✅ '+fields.length+' 字段，AI匹配中...</div>';
      try{
        const fr=await fetch(API+'/form/fill',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fields,url:tabs[0].url})});
        const plan=await fr.json();
        const fillPlan=plan.fill_plan||[];

        // 合并到 fields
        fillPlan.forEach(p=>{if(fields[p.index]){fields[p.index].ai_value=p.value;fields[p.index].ai_strategy=p.fill_strategy;fields[p.index].ai_action=p.action;fields[p.index].ai_confidence=p.confidence;fields[p.index].ai_reason=p.reason;}});

        // 显示预览
        const auto=fields.filter(f=>f.ai_action==='auto_fill').length;
        const review=fields.filter(f=>f.ai_action==='review').length;
        document.getElementById('result').innerHTML=
          '<div class="info ok">✅ '+fields.length+' 字段 | 🤖 自动填充'+auto+' | 👀 需确认'+review+' | ⏭️ 跳过'+(fields.length-auto-review)+'</div>'+
          fields.map(f=>{
            const v=f.ai_value||'';const act=f.ai_action||'skip';
            const color=act==='auto_fill'?'#6ee7b7':act==='review'?'#fbbf24':'#64748b';
            return '<div class="row"><span>'+f.label+'</span><span style="color:'+color+';font-size:10px">'+(v?act==='auto_fill'?'🤖 '+v.substring(0,15):'👀 '+v.substring(0,15):'⏭️ 跳过')+'</span></div>';
          }).join('');
        document.getElementById('fill').style.display='block';
        document.getElementById('fill').textContent='✨ 一键填充 ('+auto+'个自动)';
      }catch(e){
        document.getElementById('result').innerHTML='<div class="info err">❌ LLM匹配失败: '+e.message+'<br><small>后端是否启动？</small></div>';
      }
    }).catch(e=>{btn.textContent='🔍 扫描当前页面';document.getElementById('result').innerHTML='<div class="info err">'+e.message+'</div>';});
  });
};

// ========== 填充 ==========
document.getElementById('fill').onclick=()=>{
  document.getElementById('fill').textContent='⏳ 填充中...';
  const data=fields.filter(f=>f.ai_value).map(f=>({id:f.id,value:f.ai_value,strategy:f.ai_strategy||'text',tag:f.tag,type:f.type,options:f.options||[]}));
  chrome.tabs.query({active:true,currentWindow:true},tabs=>{
    chrome.scripting.executeScript({target:{tabId:tabs[0].id},func:fillPage,args:[data]}).then(([r])=>{
      document.getElementById('fill').textContent='✨ 一键填充';
      const ok=(r.result||[]).filter(x=>x.status==='success').length;
      document.getElementById('result').innerHTML='<div class="info ok">✅ '+ok+'/'+(r.result||[]).length+' 成功</div>'+(r.result||[]).map(x=>'<div class="row"><span>'+x.label+'</span><span style="color:'+(x.status==='success'?'#6ee7b7':'#fca5a5')+'">'+(x.status==='success'?'✓ '+x.value:'✗')+'</span></div>').join('');
    }).catch(e=>{document.getElementById('fill').textContent='✨ 一键填充';alert(e.message);});
  });
};

document.getElementById('upload').onclick=()=>{
  chrome.windows.create({url:chrome.runtime.getURL('sidebar/sidebar.html'),type:'popup',width:420,height:620});
  window.close();
};

// ==================== 页面注入函数 ====================
function scanPage(){
  function clean(t){return(t||'').replace(/[*：:]/g,'').replace(/\s+/g,' ').replace(/请输入|请选择|请填写|必填|选填|（必填）|（选填）/g,'').trim();}
  function findLabel(el){
    if(el.id){const lb=document.querySelector('label[for="'+CSS.escape(el.id)+'"]');if(lb?.textContent?.trim())return clean(lb.textContent);}
    for(const s of['.ant-form-item','.el-form-item','.form-item','.form-group','tr','td','[class*=item]']){
      const c=el.closest(s);if(c){const lb=c.querySelector('.ant-form-item-label label,.el-form-item__label,label,.label,[class*="label"]');if(lb&&lb!==el&&lb.textContent?.trim()?.length<80)return clean(lb.textContent);}
    }
    const pl=el.closest('label');if(pl?.textContent)return clean(pl.textContent.replace(el.value||'','').trim())||clean(pl.textContent);
    const ph=el.getAttribute('placeholder')||'';if(ph&&ph.length<40)return clean(ph);
    const aria=el.getAttribute('aria-label')||'';if(aria)return clean(aria);
    return(el.getAttribute('name')||'').replace(/[_-]/g,'')||'';
  }
  function radioContainer(el){let p=el.parentElement;for(let i=0;i<6&&p;i++){if(p.querySelectorAll('input[type="radio"]').length>=2)return p;p=p.parentElement;}return el.parentElement;}

  const fields=[],seen=new Set();
  // Radio 分组
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
    if(!label){for(const r of g){const l=findLabel(r);if(l&&l!=='字段'){label=l;break;}}}
    const id='rg_'+Math.random().toString(36).slice(2,8);
    g.forEach(r=>{r.setAttribute('data-rm-id',id);seen.add(r);});
    fields.push({id,label:label||'单选项',tag:'radio',type:'radio',options:opts,required:false});
  });
  // 其余字段
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
      // Radio
      if(tag==='radio'||type==='radio'||strategy==='radio_click'){
        let matched=false;
        for(const el of els){
          const v=el.value||'';let lb='';if(el.labels?.length)lb=el.labels[0].textContent.trim();
          if(!lb){const pp=el.closest('label');if(pp)lb=pp.textContent.replace(v,'').trim();}
          if(v===value||lb===value||lb.includes(value)||(value&&value.includes(lb))){el.click();el.checked=true;el.dispatchEvent(new Event('change',{bubbles:true}));matched=true;break;}
        }
        if(!matched){for(const el of els){if(value[0]&&(el.value||'').includes(value[0])||value.includes(el.value||''[0])){el.click();el.checked=true;el.dispatchEvent(new Event('change',{bubbles:true}));matched=true;break;}}}
        els[0].setAttribute('data-rm-status',matched?'success':'error');
        R.push({label:els[0].getAttribute('data-rm-id'),status:matched?'success':'failed',value});
        return;
      }
      // Select / Custom Select
      if(tag==='select'||strategy==='select'||strategy==='custom_select'){
        const el=els[0];
        if(el.tagName==='SELECT'){
          const opts=Array.from(el.options);
          let found=opts.find(o=>o.value===value||o.textContent.trim()===value);
          if(!found)found=opts.find(o=>o.textContent.includes(value)||(value&&value.includes(o.textContent.trim())));
          if(!found&&value){let b=null,bs=0;opts.forEach(o=>{if(!o.value||o.value==='-1')return;const sc=[...value].filter(c=>o.textContent.includes(c)).length/value.length;if(sc>bs&&sc>=0.3){bs=sc;b=o;}});found=b;}
          if(found){el.value=found.value;el.dispatchEvent(new Event('change',{bubbles:true}));el.setAttribute('data-rm-status','success');R.push({label:id,status:'success',value:found.textContent.trim()});}
          else{el.setAttribute('data-rm-status','error');R.push({label:id,status:'failed',value,error:'选项未匹配'});}
        } else {
          // Custom select (Ant Design等): click → type → Enter
          el.click();setTimeout(()=>{},200);
          if(isv)isv.call(el,value);else el.value=value;
          el.dispatchEvent(new Event('input',{bubbles:true}));
          el.dispatchEvent(new Event('change',{bubbles:true}));
          el.setAttribute('data-rm-status','success');
          R.push({label:id,status:'success',value});
        }
        return;
      }
      // Datepicker
      if(strategy==='datepicker'||type==='date'||type==='month'){
        const el=els[0];el.focus();
        if(isv)isv.call(el,value);else el.value=value;
        el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));
        el.setAttribute('data-rm-status','success');
        R.push({label:id,status:'success',value});return;
      }
      // Text/textarea（默认）
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
      el.setAttribute('data-rm-status','success');
      R.push({label:id,status:'success',value});
    }catch(e){R.push({label:id,status:'failed',error:e.message});}
  });
  return R;
}
})();
