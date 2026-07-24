// ============================================================
// 本地档案模板 + 字段映射引擎
// 参考 CampusApply 的 fieldMappingRules（50+规则）+ matchingEngine（3级匹配）
// ============================================================

// 用户完整档案（存储于 chrome.storage.local / IndexedDB）
export const EMPTY_PROFILE = {
  name: '', nameEn: '', gender: '', birthDate: '', phone: '', email: '',
  idNumber: '', ethnicity: '', politicalStatus: '', nativePlace: '', currentCity: '',
  wechat: '', linkedin: '', github: '', portfolio: '',
  targetCities: [], targetPositions: [], expectedSalary: '', availableDate: '',
  educations: [],
  experiences: [],
  skills: [],
  selfEvaluation: '', awards: '', publications: '', competitions: '',
};

// ============================================================
// 字段映射规则（融合 CampusApply 50+ 规则 + ResuMatch Skill Graph）
// ============================================================
export const FIELD_RULES = [
  // ===== 基础信息 =====
  { keywords: ['姓名','真实姓名','名字','中文名','全名','考生姓名','申请人姓名','您的姓名','name','full name','your name'], path: 'name', priority: 100 },
  { keywords: ['英文名','英文姓名','拼音','姓名拼音','english name'], path: 'nameEn', priority: 90 },
  { keywords: ['姓氏','姓','last name','family name','surname'], path: 'name', priority: 80, transform: 'surname' },
  { keywords: ['名','first name','given name'], path: 'name', priority: 80, transform: 'givenName' },
  { keywords: ['性别','男/女','男女','gender','sex'], path: 'gender', priority: 100 },
  { keywords: ['出生日期','出生年月','生日','出生年月日','出生时间','birth date','date of birth','birthday','dob'], path: 'birthDate', priority: 100 },
  { keywords: ['手机','手机号','手机号码','联系电话','电话号码','移动电话','联系方式','联系手机','phone','mobile','tel','telephone','cell phone'], path: 'phone', priority: 100 },
  { keywords: ['邮箱','电子邮箱','邮件','电子邮件','email','e-mail','email address'], path: 'email', priority: 100 },
  { keywords: ['身份证','身份证号','身份证号码','证件号','证件号码','id number','id card'], path: 'idNumber', priority: 95 },
  { keywords: ['民族','族别','ethnicity','ethnic group'], path: 'ethnicity', priority: 90 },
  { keywords: ['政治面貌','政治身份','党派','political status'], path: 'politicalStatus', priority: 90 },
  { keywords: ['籍贯','户籍','户籍所在地','户口所在地','原籍','native place','hometown'], path: 'nativePlace', priority: 85 },
  { keywords: ['现居城市','居住城市','现居住地','当前所在地','目前所在城市','所在城市','所在地区','常住地','current city','location','city'], path: 'currentCity', priority: 80 },
  { keywords: ['微信','微信号','微信账号','wechat','weixin'], path: 'wechat', priority: 85 },
  { keywords: ['linkedin','领英','linkedin链接'], path: 'linkedin', priority: 80 },
  { keywords: ['github','github链接','代码仓库'], path: 'github', priority: 80 },
  { keywords: ['作品集','个人作品','作品链接','个人网站','个人主页','博客','portfolio','personal website','blog'], path: 'portfolio', priority: 75 },

  // ===== 教育经历 =====
  { keywords: ['学校','毕业院校','院校','所学学校','就读学校','本科学校','硕士学校','毕业学校','大学','所在学校','school','university','college','institution'], path: 'educations.0.school', priority: 100 },
  { keywords: ['学院','院系','所在学院','所属学院','faculty','department'], path: 'educations.0.college', priority: 90 },
  { keywords: ['专业','所学专业','主修专业','就读专业','专业名称','专业方向','major','field of study'], path: 'educations.0.major', priority: 100 },
  { keywords: ['学历','最高学历','学历层次','学位','学历学位','学位类别','degree','education level','qualification'], path: 'educations.0.type', priority: 95 },
  { keywords: ['入学时间','入学日期','开始时间','就读开始','start date','enrollment date','from'], path: 'educations.0.startDate', priority: 85 },
  { keywords: ['毕业时间','毕业日期','预计毕业','结束时间','毕业年月','graduation date','end date','expected graduation','to'], path: 'educations.0.endDate', priority: 85 },
  { keywords: ['gpa','绩点','平均绩点','平均成绩','学分绩','学业成绩','成绩绩点'], path: 'educations.0.gpa', priority: 95 },
  { keywords: ['排名','专业排名','年级排名','全班排名','成绩排名','名次','ranking','rank'], path: 'educations.0.ranking', priority: 90 },
  { keywords: ['培养方式','学习形式','全日制','非全日制','training mode'], path: 'educations.0.trainingMode', priority: 70 },
  { keywords: ['四级','cet4','cet-4','英语四级','大学英语四级','四级成绩'], path: 'educations.0.cet4', priority: 90 },
  { keywords: ['六级','cet6','cet-6','英语六级','大学英语六级','六级成绩'], path: 'educations.0.cet6', priority: 90 },
  { keywords: ['雅思','ielts','雅思成绩'], path: 'educations.0.ielts', priority: 85 },
  { keywords: ['托福','toefl','托福成绩'], path: 'educations.0.toefl', priority: 85 },
  { keywords: ['主修课程','所学课程','主要课程','专业课程','核心课程','courses'], path: 'educations.0.mainCourses', priority: 70, transform: 'join' },
  { keywords: ['获奖','获奖情况','所获奖项','荣誉奖项','奖学金','校内获奖','awards','honors'], path: 'educations.0.awards', priority: 70, transform: 'join' },

  // ===== 实习/工作经历 =====
  { keywords: ['实习公司','实习单位','公司名称','公司','企业名称','organization','company'], path: 'experiences.0.organization', priority: 90 },
  { keywords: ['实习岗位','实习职位','岗位名称','职位','职务','role','position','title'], path: 'experiences.0.role', priority: 90 },
  { keywords: ['实习开始','实习起始','入职时间','entry date'], path: 'experiences.0.startDate', priority: 75 },
  { keywords: ['实习结束','实习截止','离职时间','leave date'], path: 'experiences.0.endDate', priority: 75 },
  { keywords: ['实习内容','工作内容','实习描述','工作描述','主要职责','responsibilities','description'], path: 'experiences.0.description', priority: 80 },
  { keywords: ['工作成果','实习成果','主要业绩','工作亮点','achievements','accomplishments'], path: 'experiences.0.achievements', priority: 75, transform: 'join' },

  // ===== 项目经历 =====
  { keywords: ['项目名称','项目标题','课题名称','project name','project title'], path: 'experiences.1.organization', priority: 85 },
  { keywords: ['项目角色','担任角色','你的职责','负责内容','project role','your role'], path: 'experiences.1.role', priority: 80 },
  { keywords: ['项目描述','项目简介','项目介绍','project description'], path: 'experiences.1.description', priority: 80 },
  { keywords: ['项目成果','主要成果','取得成果','项目亮点','关键产出','project outcome','key results'], path: 'experiences.1.achievements', priority: 80, transform: 'join' },
  { keywords: ['技术栈','使用技术','技术工具','技术关键词','关键技能','tech stack','technologies','skills used'], path: 'experiences.1.techStack', priority: 85, transform: 'join' },

  // ===== 技能 =====
  { keywords: ['专业技能','个人技能','技能特长','核心技能','专业能力','skills','skill'], path: 'skills', priority: 80, transform: 'join' },

  // ===== 求职意向 =====
  { keywords: ['意向城市','期望城市','期望工作城市','工作城市','工作地点','期望工作地','意向工作地','preferred city','work location'], path: 'targetCities', priority: 85, transform: 'join' },
  { keywords: ['意向岗位','期望岗位','应聘岗位','申请岗位','意向职位','期望职位','目标岗位','preferred position','desired position','target position'], path: 'targetPositions', priority: 85, transform: 'join' },
  { keywords: ['期望薪资','期望薪酬','薪资期望','薪资要求','期望月薪','薪资范围','expected salary','salary expectation'], path: 'expectedSalary', priority: 80 },
  { keywords: ['到岗时间','最早到岗','可到岗','入职时间','可入职时间','到岗日期','available date','start date','availability'], path: 'availableDate', priority: 80 },

  // ===== 其他 =====
  { keywords: ['自我评价','个人评价','自我介绍','个人介绍','self evaluation','self introduction','about me'], path: 'selfEvaluation', priority: 75 },
  { keywords: ['兴趣爱好','爱好','个人爱好','特长','兴趣特长','hobbies','interests','hobby'], path: 'hobbies', priority: 60 },
  { keywords: ['职业规划','职业发展','个人规划','发展计划','未来规划','career plan','career goal'], path: 'careerPlan', priority: 60 },
  { keywords: ['竞赛经历','比赛经历','竞赛获奖','比赛获奖','competition'], path: 'competitions', priority: 70 },
  { keywords: ['论文发表','学术论文','科研成果','专利','发表论文','学术成果','publication','paper','patent'], path: 'publications', priority: 70 },
];

// ============================================================
// 3级匹配引擎（规则 → 模糊 → 兜底）
// ============================================================
export function matchField(fieldLabel, profile) {
  const clean = fieldLabel.replace(/[*：:\s（）()【】\[\]]/g, '').replace(/请输入|请选择|请填写|可选|选填|必填/g, '').toLowerCase().trim();

  // Level 1: 规则精确匹配
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
    { test: /教育|学校|院校|学历|专业|gpa|成绩|学位|毕业|四级|六级|雅思|托福/, cat: 'education' },
    { test: /实习|工作|公司|岗位|入职|离职|职责/, cat: 'internship' },
    { test: /项目|课题|技术栈|开发|实现|成果/, cat: 'project' },
    { test: /技能|技术|语言|框架|工具|数据库|证书/, cat: 'skill' },
    { test: /意向|期望|求职|目标|薪资|到岗/, cat: 'intention' },
  ];

  for (const cr of contextRules) {
    if (cr.test.test(clean)) {
      const catRules = FIELD_RULES.filter(r => {
        if (cr.cat === 'education') return r.path.includes('educations');
        if (cr.cat === 'internship') return r.path.includes('experiences.0');
        if (cr.cat === 'project') return r.path.includes('experiences.1');
        if (cr.cat === 'skill') return r.path.includes('skills');
        if (cr.cat === 'intention') return r.path.includes('target') || r.path.includes('expected') || r.path.includes('available');
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

  // Level 3: 无匹配
  if (best) return best;
  return { value: '', matchedBy: 'none', confidence: 0 };
}

// ============================================================
// 数据路径解析
// ============================================================
function resolvePath(obj, path, transform) {
  let val = path.split('.').reduce((o, k) => (o && o[k] !== undefined) ? o[k] : '', obj);
  if (!val || val === '') return '';

  // 数组处理
  if (Array.isArray(val)) {
    if (transform === 'join') return val.filter(Boolean).join('、');
    return val[0] || '';
  }

  val = String(val);

  // 值转换
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
  if (transform === 'join') return val;

  return val;
}

// ============================================================
// 后端响应 → Profile 转换
// ============================================================
export function backendToProfile(uploadResult) {
  const p = uploadResult.profile || {};
  const profile = { ...EMPTY_PROFILE };

  // 基本信息
  profile.name = p.name || '';
  profile.email = p.email || '';
  profile.phone = p.phone || '';

  // 教育 — 从 profile.education
  if (p.education && p.education.length > 0) {
    const edu = p.education[0];
    profile.educations = [{
      type: (edu.degree || '').includes('硕士') ? '硕士' : (edu.degree || '').includes('博士') ? '博士' : '本科',
      school: edu.school || '',
      major: edu.major || '',
      startDate: (edu.time || '').split(/[-–—]/)[0]?.trim() || '',
      endDate: (edu.time || '').split(/[-–—]/)[1]?.trim() || '',
      college: '', gpa: '', ranking: '', cet4: '', cet6: '', mainCourses: [], awards: [],
    }];
  }

  // 项目经历 → experiences
  const exps = [];
  if (p.projects) {
    p.projects.forEach((proj, i) => {
      exps.push({
        type: '项目', organization: proj.name || '', role: proj.role || '',
        startDate: (proj.duration || '').split(/[-–—]/)[0]?.trim() || '',
        endDate: (proj.duration || '').split(/[-–—]/)[1]?.trim() || '',
        description: proj.description || '',
        bullets: proj.key_result ? [proj.key_result] : [],
        techStack: proj.tech_stack || [],
        achievements: proj.key_result ? [proj.key_result] : [],
        versions: [], abilityTags: [], industryTags: [], order: i,
      });
    });
  }
  if (p.work_experience) {
    p.work_experience.forEach((w, i) => {
      exps.push({
        type: '实习', organization: w.company || '', role: w.position || '',
        startDate: (w.duration || '').split(/[-–—]/)[0]?.trim() || '',
        endDate: (w.duration || '').split(/[-–—]/)[1]?.trim() || '',
        description: w.description || '', bullets: [],
        techStack: [], achievements: [],
        versions: [], abilityTags: [], industryTags: [], order: exps.length + i,
      });
    });
  }
  profile.experiences = exps;

  // 技能
  if (p.skills) {
    const byCat = {};
    p.skills.forEach(s => {
      const cat = s.category || 'other';
      if (!byCat[cat]) byCat[cat] = [];
      byCat[cat].push(s.name);
    });
    profile.skills = Object.entries(byCat).map(([cat, items]) => ({ id: cat, category: cat, items }));
  }

  // 成果 → awards
  if (p.achievements) {
    profile.awards = p.achievements.map(a => a.description || '').filter(Boolean).join('；');
  }

  return profile;
}

// ============================================================
// 存储
// ============================================================
export async function saveProfile(profile) {
  await chrome.storage.local.set({ profile, profileTime: Date.now() });
}

export async function loadProfile() {
  const data = await chrome.storage.local.get(['profile']);
  return data.profile || null;
}
