// ResuMatch Background Service Worker
console.log('[ResuMatch BG] Started');

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: 'rm-fill', title: '📋 ResuMatch — 一键填充整页', contexts: ['page'] });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (tab?.id) scanAndFill(tab.id);
});

// ==================== 消息中枢 ====================
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'SCAN_PAGE') {
    doScan(sendResponse);
    return true;
  }
  if (msg.type === 'FILL_PAGE') {
    doFill(msg.data, sendResponse);
    return true;
  }
  if (msg.type === 'CLEAR_PAGE') {
    doClear(sendResponse);
    return true;
  }
});

// ==================== 用 executeScript 直接注入执行 ====================
async function getTargetTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs.find(t => t.url && !t.url.startsWith('chrome-extension://') && !t.url.startsWith('chrome://'));
}

function doScan(sendResponse) {
  getTargetTab().then(tab => {
    if (!tab) { sendResponse({ ok: false, error: '未找到目标页面' }); return; }
    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: scanFieldsInPage,
    }).then(([result]) => {
      sendResponse({ ok: true, ...result.result });
    }).catch(err => {
      sendResponse({ ok: false, error: err.message, tabUrl: tab.url });
    });
  });
}

function doFill(data, sendResponse) {
  getTargetTab().then(tab => {
    if (!tab) { sendResponse({ ok: false, error: '未找到目标页面' }); return; }
    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: fillFieldsInPage,
      args: [data],
    }).then(([result]) => {
      sendResponse({ ok: true, results: result.result });
    }).catch(err => {
      sendResponse({ ok: false, error: err.message });
    });
  });
}

function doClear(sendResponse) {
  getTargetTab().then(tab => {
    if (!tab) { sendResponse({ ok: false }); return; }
    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: clearFieldsInPage,
    }).then(() => sendResponse({ ok: true }))
      .catch(err => sendResponse({ ok: false, error: err.message }));
  });
}

// ==================== 页面内执行的函数（序列化注入） ====================

function scanFieldsInPage() {
  function clean(t) { return (t||'').replace(/[*：:]/g,'').replace(/\s+/g,' ').replace(/请输入|请选择|请填写|必填|选填|（必填）|（选填）/g,'').trim(); }
  function findLabel(el) {
    if (el.id) { const lb = document.querySelector('label[for="'+CSS.escape(el.id)+'"]'); if (lb?.textContent) return clean(lb.textContent); }
    const containers = ['.form-item', '.form-group', '.ant-form-item', '.el-form-item', 'tr'];
    for (const sel of containers) { const c = el.closest(sel); if (c) { const lb = c.querySelector('label, .label, [class*="label"]'); if (lb && lb !== el && lb.textContent?.trim()?.length < 50) return clean(lb.textContent); } }
    const pl = el.closest('label'); if (pl?.textContent) { const t = clean(pl.textContent); const c = t.replace(el.value || '', '').trim(); if (c) return c; }
    const ph = el.getAttribute('placeholder')||''; if (ph && ph.length < 30) return clean(ph);
    return (el.getAttribute('name')||'').replace(/[_-]/g,'') || '字段';
  }
  function detectATS() {
    const u = location.href;
    if (/\.italent\.cn|\.beisen\.com/.test(u)) return '北森';
    if (/\.mokahr\.com/.test(u)) return 'Moka';
    if (/\.zhaopin\.com/.test(u)) return '智联';
    if (/\.nowcoder\.com/.test(u)) return '牛客';
    return '通用页面';
  }
  const fields = []; const seen = new Set();
  const els = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]), select, textarea, [contenteditable="true"]');
  els.forEach((el, i) => {
    if (seen.has(el)) return; seen.add(el);
    const s = getComputedStyle(el); if (s.display === 'none' || s.visibility === 'hidden') return;
    const t = (el.type||'').toLowerCase();
    if (['hidden','submit','button','reset','image','file'].includes(t)) return;
    const nm = (el.getAttribute('name')||'').toLowerCase();
    if (nm.includes('search')||nm.includes('captcha')||nm.includes('verify')) return;
    const id = 'f'+i; el.setAttribute('data-rm-id', id);
    const f = { id, label: findLabel(el), tag: el.tagName.toLowerCase(), type: t, placeholder: el.getAttribute('placeholder')||'', required: el.hasAttribute('required'), value: el.value||'', name: el.getAttribute('name')||'' };
    if (el.tagName === 'SELECT') f.options = Array.from(el.options).map(o=>o.text.trim()).filter(t=>t&&t!=='请选择');
    fields.push(f);
  });
  return { fields, atsName: detectATS() };
}

function fillFieldsInPage(fillData) {
  const results = [];
  fillData.forEach(({id, value}) => {
    const el = document.querySelector('[data-rm-id="'+id+'"]');
    if (!el) { results.push({id,status:'failed',error:'未找到'}); return; }
    try {
      if (el.tagName === 'SELECT') {
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
    } catch(e) { el.setAttribute('data-rm-status','error'); results.push({id,status:'failed',error:e.message}); }
  });
  if (!document.getElementById('rm-css')) { const s=document.createElement('style');s.id='rm-css';s.textContent='[data-rm-status="success"]{outline:2px solid #22c55e!important}[data-rm-status="error"]{outline:2px solid #ef4444!important}';document.head.appendChild(s); }
  return results;
}

function clearFieldsInPage() {
  document.querySelectorAll('[data-rm-status]').forEach(el=>{el.removeAttribute('data-rm-status');el.style.outline='';
    if(el.tagName==='INPUT'||el.tagName==='TEXTAREA'){const s=Object.getOwnPropertyDescriptor(el.tagName==='TEXTAREA'?HTMLTextAreaElement:HTMLInputElement,'value')?.set;if(s)s.call(el,'');else el.value='';el.dispatchEvent(new Event('input',{bubbles:true}));}
    else if(el.tagName==='SELECT'){el.selectedIndex=0;el.dispatchEvent(new Event('change',{bubbles:true}));}
  });
  document.querySelectorAll('[data-rm-id]').forEach(el=>el.removeAttribute('data-rm-id'));
}
