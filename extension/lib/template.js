// 本地档案模板 + 字段映射引擎
// IIFE 模式，挂载到 window.ResuMatchTemplate
(function() {
'use strict';
if (window.ResuMatchTemplate) return;

const EMPTY_PROFILE = {
  name: '', nameEn: '', gender: '', birthDate: '', phone: '', email: '',
  idNumber: '', ethnicity: '', politicalStatus: '', nativePlace: '', currentCity: '',
  wechat: '', linkedin: '', github: '', portfolio: '',
  targetCities: [], targetPositions: [], expectedSalary: '', availableDate: '',
  educations: [], experiences: [], skills: [],
  selfEvaluation: '', awards: '', publications: '', competitions: '',
};

const FIELD_RULES = [
  { keywords: ['姓名','真实姓名','名字','中文名','全名','考生姓名','申请人姓名','您的姓名','name','full name','your name'], path: 'name', priority: 100 },
  { keywords: ['性别','男/女','男女','gender','sex'], path: 'gender', priority: 100 },
  { keywords: ['出生日期','出生年月','生日','birthday','dob'], path: 'birthDate', priority: 100 },
  { keywords: ['手机','手机号','手机号码','电话','mobile','phone','tel'], path: 'phone', priority: 100 },
  { keywords: ['邮箱','电子邮箱','email','e-mail','mail'], path: 'email', priority: 100 },
  { keywords: ['身份证','身份证号','证件号','id number','id card'], path: 'idNumber', priority: 95 },
  { keywords: ['民族','ethnicity'], path: 'ethnicity', priority: 90 },
  { keywords: ['政治面貌','政治身份','political status'], path: 'politicalStatus', priority: 90 },
  { keywords: ['籍贯','户籍','户口','hometown'], path: 'nativePlace', priority: 85 },
  { keywords: ['现居','所在城市','city','location'], path: 'currentCity', priority: 80 },
  { keywords: ['学校','毕业院校','院校','大学','school','university'], path: 'educations.0.school', priority: 100 },
  { keywords: ['专业','所学专业','major'], path: 'educations.0.major', priority: 100 },
  { keywords: ['学历','最高学历','学位','degree'], path: 'educations.0.type', priority: 95 },
  { keywords: ['GPA','gpa','绩点','平均成绩'], path: 'educations.0.gpa', priority: 95 },
  { keywords: ['排名','名次','ranking'], path: 'educations.0.ranking', priority: 90 },
  { keywords: ['四级','CET4','cet-4'], path: 'educations.0.cet4', priority: 90 },
  { keywords: ['六级','CET6','cet-6'], path: 'educations.0.cet6', priority: 90 },
  { keywords: ['实习公司','公司','company','organization'], path: 'experiences.0.organization', priority: 90 },
  { keywords: ['实习岗位','岗位','职位','role','position','title'], path: 'experiences.0.role', priority: 90 },
  { keywords: ['项目名称','project name'], path: 'experiences.1.organization', priority: 85 },
  { keywords: ['项目角色','project role'], path: 'experiences.1.role', priority: 80 },
  { keywords: ['技术栈','使用技术','tech stack'], path: 'experiences.1.techStack', priority: 85 },
  { keywords: ['意向城市','期望城市','工作城市'], path: 'targetCities', priority: 85 },
  { keywords: ['意向岗位','期望岗位','应聘岗位'], path: 'targetPositions', priority: 85 },
  { keywords: ['自我评价','自我介绍','about me'], path: 'selfEvaluation', priority: 75 },
  { keywords: ['获奖','所获奖项','awards'], path: 'awards', priority: 70 },
];

function resolvePath(obj, path, transform) {
  let val = path.split('.').reduce((o, k) => (o && o[k] !== undefined) ? o[k] : '', obj);
  if (!val && val !== 0) return '';
  if (Array.isArray(val)) {
    if (transform === 'join') return val.filter(Boolean).join('、');
    return val[0] || '';
  }
  val = String(val);
  if (transform === 'surname') {
    const double = ['欧阳','司马','上官','皇甫','令狐','诸葛','司徒','公孙'];
    if (double.some(d => val.startsWith(d))) return val.substring(0, 2);
    return /[一-龥]/.test(val) ? val[0] : val.split(/\s+/).pop();
  }
  if (transform === 'givenName') {
    const double = ['欧阳','司马','上官','皇甫','令狐','诸葛','司徒','公孙'];
    if (double.some(d => val.startsWith(d))) return val.substring(2);
    return /[一-龥]/.test(val) ? val.substring(1) : val.split(/\s+/).slice(0, -1).join(' ');
  }
  return val;
}

function matchField(fieldLabel, profile) {
  if (!profile) return { value: '', matchedBy: 'none', confidence: 0 };
  const clean = (fieldLabel || '').replace(/[*：:\s（）()【】\[\]]/g, '').replace(/请输入|请选择|请填写|选填|必填/g, '').toLowerCase().trim();
  if (!clean) return { value: '', matchedBy: 'none', confidence: 0 };

  // Level 1: 精确匹配
  let best = null, bestScore = 0;
  for (const rule of FIELD_RULES) {
    for (const kw of rule.keywords) {
      const kwLower = kw.toLowerCase();
      if (clean === kwLower) {
        const val = resolvePath(profile, rule.path, rule.transform);
        if (val) return { value: val, matchedBy: 'rule', confidence: 1.0, rule };
      }
      if (clean.includes(kwLower) || kwLower.includes(clean)) {
        const score = Math.min(clean.length, kwLower.length) / Math.max(clean.length, kwLower.length);
        if (score > bestScore) {
          const val = resolvePath(profile, rule.path, rule.transform);
          if (val) { bestScore = score; best = { value: val, matchedBy: 'rule', confidence: 0.6 + score * 0.4, rule }; }
        }
      }
    }
  }
  if (best && best.confidence >= 0.8) return best;

  // Level 2: 语义模糊匹配
  const contextRules = [
    { test: /教育|学校|院校|学历|专业|gpa|成绩|学位|毕业|四级|六级/, cat: 'education' },
    { test: /实习|工作|公司|岗位|入职|离职|职责/, cat: 'internship' },
    { test: /项目|课题|技术栈|开发|实现|成果/, cat: 'project' },
    { test: /技能|技术|语言|框架|工具|数据库/, cat: 'skill' },
    { test: /意向|期望|求职|目标|薪资|到岗/, cat: 'intention' },
  ];
  for (const cr of contextRules) {
    if (cr.test.test(clean)) {
      const catRules = FIELD_RULES.filter(r => {
        if (cr.cat === 'education') return r.path.includes('educations');
        if (cr.cat === 'internship') return r.path.includes('experiences.0');
        if (cr.cat === 'project') return r.path.includes('experiences.1');
        if (cr.cat === 'skill') return r.path.includes('skills');
        if (cr.cat === 'intention') return r.path.includes('target') || r.path.includes('expected');
        return false;
      });
      for (const rule of catRules) {
        for (const kw of rule.keywords) {
          const overlap = [...kw.toLowerCase()].filter(c => clean.includes(c)).length / kw.length;
          if (overlap >= 0.5) {
            const val = resolvePath(profile, rule.path, rule.transform);
            if (val) return { value: val, matchedBy: 'semantic', confidence: overlap * 0.7, rule };
          }
        }
      }
    }
  }
  return best || { value: '', matchedBy: 'none', confidence: 0 };
}

function backendToProfile(uploadResult) {
  const p = (uploadResult && uploadResult.profile) || {};
  const profile = JSON.parse(JSON.stringify(EMPTY_PROFILE));
  profile.name = p.name || '';
  profile.email = p.email || '';
  profile.phone = p.phone || '';
  if (p.education && p.education.length > 0) {
    const edu = p.education[0];
    profile.educations = [{
      type: (edu.degree || '').includes('硕士') ? '硕士' : (edu.degree || '').includes('博士') ? '博士' : '本科',
      school: edu.school || '', major: edu.major || '',
      startDate: (edu.time || '').split(/[-–—]/)[0]?.trim() || '',
      endDate: (edu.time || '').split(/[-–—]/)[1]?.trim() || '',
      college: '', gpa: '', ranking: '', cet4: '', cet6: '', mainCourses: [], awards: [],
    }];
  }
  const exps = [];
  if (p.projects) {
    p.projects.forEach((proj, i) => {
      exps.push({
        type: '项目', organization: proj.name || '', role: proj.role || '',
        startDate: '', endDate: '', description: proj.description || '',
        bullets: proj.key_result ? [proj.key_result] : [],
        techStack: proj.tech_stack || [],
        achievements: proj.key_result ? [proj.key_result] : [],
        order: i,
      });
    });
  }
  if (p.work_experience) {
    p.work_experience.forEach((w, i) => {
      exps.push({
        type: '实习', organization: w.company || '', role: w.position || '',
        startDate: '', endDate: '', description: w.description || '',
        bullets: [], techStack: [], achievements: [], order: exps.length + i,
      });
    });
  }
  profile.experiences = exps;
  if (p.skills) {
    const byCat = {};
    p.skills.forEach(s => { const cat = s.category || 'other'; if (!byCat[cat]) byCat[cat] = []; byCat[cat].push(s.name); });
    profile.skills = Object.entries(byCat).map(([cat, items]) => ({ id: cat, category: cat, items }));
  }
  if (p.achievements) {
    profile.awards = p.achievements.map(a => a.description || '').filter(Boolean).join('；');
  }
  return profile;
}

async function saveProfile(profile) {
  await chrome.storage.local.set({ profile, profileTime: Date.now() });
}

async function loadProfile() {
  const data = await chrome.storage.local.get(['profile']);
  return data.profile || null;
}

window.ResuMatchTemplate = {
  EMPTY_PROFILE, FIELD_RULES,
  matchField, resolvePath,
  backendToProfile, saveProfile, loadProfile,
  version: 2,
};
})();
