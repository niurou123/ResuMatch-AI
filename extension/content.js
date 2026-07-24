// ResuMatch Content Script
console.log('[ResuMatch] Content Script loaded on:', location.href);

// ==================== ATS 检测 ====================
function detectATS() {
  const url = location.href;
  if (/\.italent\.cn|\.beisen\.com/.test(url)) return { name: '北森', label: 'ant' };
  if (/\.mokahr\.com/.test(url)) return { name: 'Moka', label: 'moka' };
  if (/\.zhaopin\.com/.test(url)) return { name: '智联招聘', label: 'standard' };
  if (/\.nowcoder\.com/.test(url)) return { name: '牛客网', label: 'standard' };
  if (document.querySelector('.ant-form')) return { name: 'Ant Design', label: 'ant' };
  if (document.querySelector('.el-form')) return { name: 'Element UI', label: 'element' };
  return null;
}

// ==================== Label 提取 ====================
function findLabel(el, ats) {
  if (ats?.label === 'ant') {
    const fi = el.closest('.ant-form-item');
    if (fi) { const lb = fi.querySelector('.ant-form-item-label label'); if (lb?.textContent?.trim()) return clean(lb.textContent); }
  }
  if (el.id) {
    const lb = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
    if (lb?.textContent) return clean(lb.textContent);
  }
  const containers = ['.form-item', '.form-group', '.ant-form-item', '.el-form-item', 'tr'];
  for (const sel of containers) {
    const c = el.closest(sel);
    if (c) {
      const lb = c.querySelector('label, .label, [class*="label"]');
      if (lb && lb !== el && lb.textContent?.trim()?.length < 50) return clean(lb.textContent);
    }
  }
  const pl = el.closest('label');
  if (pl?.textContent) {
    const t = clean(pl.textContent); const c = t.replace(el.value || '', '').trim(); if (c) return c;
  }
  if (el.getAttribute('aria-label')) return clean(el.getAttribute('aria-label'));
  const nameMap = { name:'姓名', username:'姓名', phone:'手机号码', mobile:'手机号码', email:'邮箱', gender:'性别', sex:'性别', birthday:'出生日期', school:'学校', university:'学校', major:'专业', degree:'学历', company:'公司', position:'岗位', address:'地址', city:'城市', idcard:'身份证号' };
  const nm = (el.getAttribute('name')||'').toLowerCase().replace(/[_-]/g,'');
  if (nameMap[nm]) return nameMap[nm]; if (nm) return nm;
  const ph = el.getAttribute('placeholder')||''; if (ph && ph.length < 30) return clean(ph);
  return '字段_' + Math.random().toString(36).slice(2,6);
}

function clean(t) { return (t||'').replace(/[*：:]/g,'').replace(/\s+/g,' ').replace(/请输入|请选择|请填写|必填|选填|（必填）|（选填）/g,'').trim(); }

// ==================== 表单扫描 ====================
function scanFields() {
  const ats = detectATS(); const fields = []; const seen = new Set();
  const els = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]), select, textarea, [contenteditable="true"]');
  els.forEach((el, i) => {
    if (seen.has(el)) return; seen.add(el);
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') return;
    const t = (el.type||'').toLowerCase();
    if (['hidden','submit','button','reset','image','file'].includes(t)) return;
    const nm = (el.getAttribute('name')||'').toLowerCase();
    if (nm.includes('search')||nm.includes('captcha')||nm.includes('verify')) return;
    const id = 'f'+i; el.setAttribute('data-rm-id', id);
    const f = { id, label: findLabel(el, ats), tag: el.tagName.toLowerCase(), type: t, placeholder: el.getAttribute('placeholder')||'', required: el.hasAttribute('required'), value: el.value||'', name: el.getAttribute('name')||'' };
    if (el.tagName === 'SELECT') f.options = Array.from(el.options).map(o=>o.text.trim()).filter(t=>t&&t!=='请选择'&&t!=='-- 请选择 --');
    fields.push(f);
  });
  return { fields, atsName: ats?.name || '通用页面' };
}

// ==================== 填充 ====================
function fillFields(fillData) {
  const results = [];
  fillData.forEach(({id, value}) => {
    const el = document.querySelector(`[data-rm-id="${id}"]`);
    if (!el) { results.push({id,status:'failed',error:'元素未找到'}); return; }
    try {
      const tag = el.tagName.toLowerCase();
      if (tag === 'select') {
        const opts = Array.from(el.options);
        let m = opts.find(o => o.value===value||o.text.trim()===value);
        if (!m) m = opts.find(o => o.text.includes(value)||(value&&value.includes(o.text)));
        if (m) { el.value = m.value; el.dispatchEvent(new Event('change',{bubbles:true})); }
      } else if (el.getAttribute('contenteditable')==='true') {
        el.innerHTML = value; el.dispatchEvent(new Event('input',{bubbles:true}));
      } else {
        const proto = el.tagName==='TEXTAREA' ? HTMLTextAreaElement : HTMLInputElement;
        const setter = Object.getOwnPropertyDescriptor(proto.prototype,'value')?.set;
        el.focus();
        if (setter) setter.call(el, value); else el.value = value;
        el.dispatchEvent(new Event('input',{bubbles:true}));
        el.dispatchEvent(new Event('change',{bubbles:true}));
        el.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText'}));
        el.dispatchEvent(new Event('blur',{bubbles:true}));
      }
      el.setAttribute('data-rm-status','success');
      results.push({id,status:'success',value:value.substring(0,50)});
    } catch(e) {
      el.setAttribute('data-rm-status','error');
      results.push({id,status:'failed',error:e.message});
    }
  });
  // 注入高亮 CSS
  if (!document.getElementById('rm-css')) {
    const s = document.createElement('style'); s.id='rm-css';
    s.textContent = `[data-rm-status="success"]{outline:2px solid #22c55e!important;outline-offset:2px}[data-rm-status="error"]{outline:2px solid #ef4444!important;outline-offset:2px}`;
    document.head.appendChild(s);
  }
  return results;
}

function clearAll() {
  document.querySelectorAll('[data-rm-status]').forEach(el=>{
    el.removeAttribute('data-rm-status');el.style.outline='';
    if (el.tagName==='INPUT'||el.tagName==='TEXTAREA'){
      const setter=Object.getOwnPropertyDescriptor(el.tagName==='TEXTAREA'?HTMLTextAreaElement:HTMLInputElement,'value')?.set;
      if(setter)setter.call(el,'');else el.value='';
      el.dispatchEvent(new Event('input',{bubbles:true}));
    } else if(el.tagName==='SELECT'){el.selectedIndex=0;el.dispatchEvent(new Event('change',{bubbles:true}));}
  });
  document.querySelectorAll('[data-rm-id]').forEach(el=>el.removeAttribute('data-rm-id'));
}

// ==================== 消息监听 ====================
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  try {
    switch (msg.type) {
      case 'PING': sendResponse({ ok: true }); break;
      case 'SCAN_FORM': sendResponse({ ok: true, ...scanFields() }); break;
      case 'FILL_ALL': sendResponse({ ok: true, results: fillFields(msg.data||[]) }); break;
      case 'CLEAR_ALL': clearAll(); sendResponse({ ok: true }); break;
      default: sendResponse({ ok: false, error: 'Unknown' });
    }
  } catch(e) {
    sendResponse({ ok: false, error: e.message });
  }
});
