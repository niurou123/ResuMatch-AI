#!/usr/bin/env node
/**
 * 表单字段映射覆盖率评测（静态，无需浏览器 / 无需 LLM）
 *
 * 直接加载扩展真实的映射引擎（extension/lib/template.js 的 matchField 与
 * resume-schema.js 的 matchSelectOption），对 ATS 字段夹具逐字段求值，
 * 因此评测结果与线上填充走的是同一套代码，不存在"另写一份规则"的漂移。
 *
 * 指标：
 *   1. 字段覆盖率   filled / total            —— 真正能填进去的比例
 *   2. 规则命中率   (filled + ruleEmpty)/total —— 引擎能否识别出这是哪个字段
 *   3. 空值不编造   expect_empty 中返回空的比例 —— 档案无数据时必须留空
 *   4. 下拉别名准确率 下拉值能否映射到选项中的对应项
 *
 * 用法：
 *   node scripts/eval_form_fill.js                  # 默认用 B01 画像
 *   node scripts/eval_form_fill.js --resume B03
 *   node scripts/eval_form_fill.js --json data/eval/form_fill_report.json
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');

// ---- 扩展库依赖的浏览器全局：打桩后即可在 Node 中复用真实引擎 ----
global.window = {};
global.chrome = {
  storage: { local: { get: async () => ({}), set: async () => {} } },
};

require(path.join(ROOT, 'extension', 'lib', 'resume-schema.js'));
require(path.join(ROOT, 'extension', 'lib', 'template.js'));

const T = global.window.ResuMatchTemplate;
const S = global.window.ResumeSchema;
if (!T || !S) {
  console.error('无法加载扩展映射引擎（window.ResuMatchTemplate / ResumeSchema 缺失）');
  process.exit(1);
}

// ---- 参数 ----
function arg(name, def) {
  const i = process.argv.indexOf('--' + name);
  return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : def;
}
const resumeId = arg('resume', '');
const profileFile = arg('profile', path.join(ROOT, 'data', 'eval', 'form_profile.json'));
const outJson = arg('json', path.join(ROOT, 'data', 'eval', 'form_fill_report.json'));

// ---- 载入评测档案 ----
// 默认用完整合成档案（data/eval/form_profile.json），字段覆盖 14 分区 schema；
// 传 --resume Bxx 时改用评测简历经 backendToProfile() 转换的稀疏档案
let profile;
let profileLabel;
if (resumeId) {
  const seeds = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'eval', 'profile_seed.json'), 'utf8'));
  if (!seeds[resumeId]) {
    console.error(`未知简历 ID: ${resumeId}`);
    process.exit(1);
  }
  profile = T.backendToProfile({ profile: seeds[resumeId] });
  profileLabel = `评测简历 ${resumeId}（backendToProfile 转换）`;
} else {
  profile = Object.assign(JSON.parse(JSON.stringify(T.EMPTY_PROFILE)),
    JSON.parse(fs.readFileSync(profileFile, 'utf8')));
  profileLabel = `完整档案 ${path.basename(profileFile)}`;
}
const fixtures = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'eval', 'form_fixtures.json'), 'utf8'));

// ---- 1) 字段覆盖率 ----
const vendorRows = [];
const unrecognized = [];
let totalAll = 0, filledAll = 0, ruleHitAll = 0;

for (const [vendor, labels] of Object.entries(fixtures.vendors)) {
  let filled = 0, ruleHit = 0;
  for (const label of labels) {
    const r = T.matchField(label, profile);
    const hasValue = !!(r.value && String(r.value).trim());
    const matched = r.matchedBy && r.matchedBy !== 'none';
    if (hasValue) filled++;
    if (matched) ruleHit++;
    if (!matched) unrecognized.push(`${vendor}: ${label}`);
  }
  totalAll += labels.length;
  filledAll += filled;
  ruleHitAll += ruleHit;
  vendorRows.push({ vendor, total: labels.length, filled, ruleHit, rate: filled / labels.length });
}

// ---- 2) 下拉别名匹配 ----
const dropdownRows = [];
for (const c of fixtures.dropdowns) {
  const got = S.matchSelectOption(c.options, c.value);
  dropdownRows.push({ field: c.field, value: c.value, expect: c.expect, got, ok: got === c.expect });
}
const dropOk = dropdownRows.filter(r => r.ok).length;

// ---- 3) 空值不编造 ----
const emptyRows = [];
for (const c of fixtures.expect_empty) {
  const r = T.matchField(c.field, profile);
  const got = (r.value || '').trim();
  emptyRows.push({ field: c.field, got, ok: got === '', why: c.why });
}
const emptyOk = emptyRows.filter(r => r.ok).length;

// ---- 输出 ----
const pct = v => (v * 100).toFixed(1) + '%';

console.log('='.repeat(78));
console.log(`表单字段映射评测  |  档案: ${profileLabel}  |  引擎: template v${T.version} / schema v${S.version}`);
console.log('='.repeat(78));
console.log('\n【1】各站点字段覆盖率');
console.log('站点'.padEnd(16) + '总字段'.padStart(8) + '已填'.padStart(8) + '覆盖率'.padStart(10) + '规则命中'.padStart(10));
for (const r of vendorRows) {
  console.log(r.vendor.padEnd(16) +
    String(r.total).padStart(8) +
    String(r.filled).padStart(8) +
    pct(r.rate).padStart(10) +
    pct(r.ruleHit / r.total).padStart(10));
}
console.log('-'.repeat(78));
console.log('合计'.padEnd(16) + String(totalAll).padStart(8) + String(filledAll).padStart(8) +
  pct(filledAll / totalAll).padStart(10) + pct(ruleHitAll / totalAll).padStart(10));

console.log('\n【2】下拉选项别名匹配');
for (const r of dropdownRows) {
  console.log(`  ${r.ok ? '✓' : '✗'} ${r.field}: ${r.value} → ${r.got || '(空)'}` +
    (r.ok ? '' : `  [期望 ${r.expect}]`));
}
console.log(`  准确率: ${dropOk}/${dropdownRows.length}`);

console.log('\n【3】空值不编造（档案无数据时必须留空）');
for (const r of emptyRows) {
  console.log(`  ${r.ok ? '✓' : '✗'} ${r.field} → ${r.got === '' ? '(空)' : r.got}`);
}
console.log(`  通过率: ${emptyOk}/${emptyRows.length}`);

if (unrecognized.length) {
  console.log(`\n【4】未被任何规则识别的字段（共 ${unrecognized.length} 个，建议补规则）`);
  unrecognized.forEach(u => console.log('  - ' + u));
}

const report = {
  generated_at: new Date().toISOString().slice(0, 19).replace('T', ' '),
  resume_id: resumeId,
  engine: { template: T.version, schema: S.version, rules: T.FIELD_RULES.length },
  field_coverage: {
    total: totalAll, filled: filledAll,
    rate: +(filledAll / totalAll).toFixed(4),
    rule_hit_rate: +(ruleHitAll / totalAll).toFixed(4),
    by_vendor: vendorRows,
  },
  dropdown_alias: { total: dropdownRows.length, ok: dropOk, rate: +(dropOk / dropdownRows.length).toFixed(4), detail: dropdownRows },
  no_fabrication: { total: emptyRows.length, ok: emptyOk, rate: +(emptyOk / emptyRows.length).toFixed(4), detail: emptyRows },
  unrecognized_fields: unrecognized,
};

fs.mkdirSync(path.dirname(outJson), { recursive: true });
fs.writeFileSync(outJson, JSON.stringify(report, null, 1), 'utf8');
console.log(`\n报告已写入 ${outJson}`);
