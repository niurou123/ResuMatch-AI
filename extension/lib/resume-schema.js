// 简历结构化Schema v3 — 全面适配网申全场景
// 参考：AI-Resume-Form-Filling-Assistant + 北森/Moka/智联/51job/牛客
(function(){'use strict';
if(window.ResumeSchema)return;

// ===== 下拉选项别名组 =====
const SELECT_ALIASES=[
  // 性别
  {v:['男','male','man','m','先生']},{v:['女','female','woman','f','女士']},
  // 学历（各 ATS 表述差异大：大学本科/普通本科/本科毕业都是本科）
  {v:['高中','highschool']},{v:['大专','专科','associate','高职']},
  {v:['本科','大学本科','普通本科','本科毕业','本科及以上','bachelor','undergraduate','学士','学士学位','大学']},
  {v:['硕士','研究生','硕士研究生','文学硕士','理学硕士','工学硕士','研究生及以上','master','masters','硕士学位']},
  {v:['MBA','mba','工商管理硕士']},{v:['博士','doctorate','phd','博士研究生','博士学位']},
  {v:['其他','other','其它']},
  // 学历层次（招聘网站常见"学历要求"三档）
  {v:['大专及以上','专科及以上']},{v:['本科及以上','本科以上']},{v:['硕士及以上','研究生及以上']},{v:['博士及以上']},
  // 用工类型
  {v:['全职','全职工作','fulltime','full-time']},{v:['兼职','parttime','part-time']},
  {v:['实习','实习生','internship','intern']},{v:['合同','contract','合同工']},{v:['自由职业','freelance']},{v:['劳务派遣','派遣']},
  // 布尔
  {v:['是','yes','true','1','有']},{v:['否','no','false','0','无','没有']},
  // 证件
  {v:['身份证','identitycard','idcard','居民身份证']},{v:['护照','passport']},{v:['居留许可','residencepermit']},{v:['港澳通行证','台胞证']},
  // 婚姻
  {v:['未婚','single','未婚未育']},{v:['已婚','married','已婚已育']},{v:['离异','divorced']},{v:['保密','不愿透露']},
  // 政治面貌
  {v:['中共党员','党员','中国共产党党员','正式党员']},{v:['共青团员','团员','中国共青团员','共青团']},
  {v:['群众','普通群众','无党派人士']},{v:['中共预备党员','预备党员']},{v:['民主党派','民主党派成员','民主']},
  // 学历类型
  {v:['全日制','统招','统招全日制','全国统招','fulltimedegree']},{v:['非全日制','非统招','在职','parttimedegree']},
  {v:['海外留学','overseasstudy','studyabroad','海外学历']},{v:['联合培养','jointprogram']},
  // 毕业状态
  {v:['已毕业','毕业','graduated','应届毕业生','应届']},{v:['预计毕业','expected','2026届毕业','2027届毕业']},{v:['在读','在读学生','enrolled','current','在校生']},{v:['肄业','dropped']},
  // 语言水平
  {v:['母语','native','精通']},{v:['流利','熟练','fluent']},
  {v:['工作熟练','professional','business','工作用语']},
  {v:['中等','intermediate','日常会话']},{v:['基础','basic','入门']},
  // 办公方式
  {v:['现场办公','坐班','onsite','on-site','办公室办公']},{v:['混合办公','hybrid','混合']},{v:['远程办公','远程','remote','居家办公']},
  // 英语考试
  {v:['CET-4','CET4','四级','英语四级','cet4','大学英语四级']},{v:['CET-6','CET6','六级','英语六级','cet6','大学英语六级']},
  {v:['雅思','IELTS','ielts']},{v:['托福','TOEFL','toefl']},
  // 校园经历类型
  {v:['学生组织','学生会','studentorganization']},{v:['社团','社团活动','club','association']},
  {v:['志愿服务','志愿者','volunteer','公益']},{v:['科研','科研项目','research','科研经历']},{v:['竞赛','比赛','competition','contest','学科竞赛']},
  // 到岗时间
  {v:['随时','随时到岗','立即','立即到岗']},{v:['一周内','3天内','三天内']},{v:['一个月内','30天内']},{v:['三个月内','面议','协商']},
  // 意向工作性质
  {v:['互联网','IT','软件','计算机']},{v:['金融','银行','证券']},{v:['教育','培训']},{v:['医疗','医药','健康']},{v:['制造业','硬件']},
  // 民族（常见）
  {v:['汉族']},{v:['蒙古族']},{v:['回族']},{v:['藏族']},{v:['维吾尔族']},
  {v:['苗族']},{v:['彝族']},{v:['壮族']},{v:['满族']},{v:['土家族']},
  // 工作经验年限（常见档位）
  {v:['应届','无经验','0年','在校生']},{v:['1年以下','1年以内','不到1年']},{v:['1-3年','1-3年经验']},{v:['3-5年','3-5年经验']},{v:['5-10年','5-10年经验']},{v:['10年以上','10年+']},
];

// ===== 完整分区定义（14个分区）=====
const SECTIONS=[
  // 1. 基本信息
  {key:'personal',label:'基本信息',type:'group',fields:[
    {key:'fullName',label:'姓名',input:'text',placeholder:'张三'},
    {key:'englishName',label:'英文名',input:'text',placeholder:'Sam Zhang'},
    {key:'gender',label:'性别',input:'select',options:['','男','女']},
    {key:'birthDate',label:'出生日期',input:'date'},
    {key:'age',label:'年龄',input:'text',placeholder:'22'},
    {key:'email',label:'邮箱',input:'email',placeholder:'name@example.com'},
    {key:'alternateEmail',label:'备用邮箱',input:'email',placeholder:'备选'},
    {key:'phone',label:'手机号码',input:'tel',placeholder:'13800138000'},
    {key:'alternatePhone',label:'备用电话',input:'tel',placeholder:'备选'},
    {key:'wechat',label:'微信号',input:'text'},
    {key:'nationality',label:'民族',input:'text',placeholder:'汉族'},
    {key:'politicalStatus',label:'政治面貌',input:'text',placeholder:'共青团员'},
    {key:'maritalStatus',label:'婚姻状况',input:'select',options:['','未婚','已婚']},
    {key:'currentCity',label:'现居城市',input:'text',placeholder:'上海'},
    {key:'currentProvince',label:'现居省份',input:'text',placeholder:'上海'},
    {key:'hometownCity',label:'籍贯城市',input:'text',placeholder:'南京'},
    {key:'hukouLocation',label:'户口所在地',input:'text'},
    {key:'idType',label:'证件类型',input:'select',options:['','身份证','护照','居留许可']},
    {key:'idNumber',label:'证件号码',input:'text'},
    {key:'currentCompany',label:'当前公司',input:'text'},
    {key:'currentTitle',label:'当前职位',input:'text'},
    {key:'yearsOfExperience',label:'工作年限',input:'text',placeholder:'3'},
    {key:'highestEducationLevel',label:'最高学历',input:'select',options:['','高中','大专','本科','硕士','MBA','博士']},
    {key:'summary',label:'个人简介',input:'textarea',placeholder:'简短自我介绍，适合复制到招聘表单'},
  ]},

  // 2. 联系方式与地址
  {key:'contact',label:'联系方式与地址',type:'group',fields:[
    {key:'addressLine1',label:'现居地址',input:'text',placeholder:'详细地址'},
    {key:'postalCode',label:'邮政编码',input:'text',placeholder:'200120'},
    {key:'emergencyContactName',label:'紧急联系人',input:'text',placeholder:'李四'},
    {key:'emergencyContactPhone',label:'紧急联系人电话',input:'tel',placeholder:'13700137000'},
  ]},

  // 3. 在线资料
  {key:'onlinePresence',label:'在线资料',type:'group',fields:[
    {key:'linkedinUrl',label:'LinkedIn',input:'url',placeholder:'https://linkedin.com/in/...'},
    {key:'githubUrl',label:'GitHub',input:'url',placeholder:'https://github.com/...'},
    {key:'portfolioUrl',label:'作品集',input:'url',placeholder:'https://...'},
    {key:'websiteUrl',label:'个人网站',input:'url',placeholder:'https://...'},
    {key:'blogUrl',label:'博客',input:'url',placeholder:'https://...'},
    {key:'leetcodeUrl',label:'LeetCode',input:'url',placeholder:'https://leetcode.com/...'},
    {key:'otherProfiles',label:'其他主页',input:'textarea',placeholder:'知乎/X/哔哩哔哩/Kaggle...'},
  ]},

  // 4. 求职偏好
  {key:'jobPreferences',label:'求职偏好',type:'group',fields:[
    {key:'targetRole',label:'目标岗位',input:'text',placeholder:'后端开发工程师'},
    {key:'targetLevel',label:'目标职级',input:'text',placeholder:'高级/专家'},
    {key:'targetDepartment',label:'目标部门',input:'text',placeholder:'技术部'},
    {key:'targetIndustry',label:'目标行业',input:'text',placeholder:'AI/SaaS/电商'},
    {key:'expectedCity',label:'期望城市',input:'text',placeholder:'上海'},
    {key:'preferredLocations',label:'可接受工作地点',input:'textarea',placeholder:'上海、北京、杭州、远程'},
    {key:'expectedSalary',label:'期望薪资',input:'text',placeholder:'25k-35k/月'},
    {key:'noticePeriod',label:'到岗周期',input:'text',placeholder:'随时/30天'},
    {key:'availableDate',label:'可入职日期',input:'date'},
    {key:'employmentType',label:'期望用工类型',input:'select',options:['','全职','兼职','实习','合同','自由职业']},
    {key:'willingToRelocate',label:'是否接受异地',input:'select',options:['','是','否']},
    {key:'willingToTravel',label:'是否接受出差',input:'select',options:['','是','否']},
    {key:'remotePreference',label:'办公方式偏好',input:'select',options:['','现场办公','混合办公','远程办公']},
  ]},

  // 5. 技能
  {key:'skills',label:'技能与亮点',type:'group',fields:[
    {key:'primarySkills',label:'核心技能',input:'textarea',placeholder:'分布式系统、系统设计、工程架构...'},
    {key:'programmingLanguages',label:'编程语言',input:'textarea',placeholder:'Python、Go、TypeScript...'},
    {key:'frameworks',label:'框架',input:'textarea',placeholder:'FastAPI、React、LangGraph...'},
    {key:'databases',label:'数据库',input:'textarea',placeholder:'PostgreSQL、Redis、ChromaDB...'},
    {key:'aiTools',label:'AI/大模型工具',input:'textarea',placeholder:'LangChain、RAG、Agent...'},
    {key:'cloudPlatforms',label:'云平台',input:'textarea',placeholder:'AWS、阿里云、腾讯云...'},
    {key:'tooling',label:'工程工具',input:'textarea',placeholder:'Docker、K8s、GitHub Actions...'},
    {key:'domainKnowledge',label:'行业经验',input:'textarea',placeholder:'金融、电商、教育、AI...'},
    {key:'softSkills',label:'软技能',input:'textarea',placeholder:'沟通、推动、协作、领导力...'},
    {key:'notableAchievements',label:'代表性成绩',input:'textarea',placeholder:'最能体现能力的数据化成绩'},
  ]},

  // 6. 教育经历
  {key:'educations',label:'教育经历',type:'list',slots:3,itemLabel:'教育',fields:[
    {key:'school',label:'学校',input:'text',placeholder:'清华大学'},
    {key:'educationType',label:'学历类型',input:'select',options:['','全日制','非全日制','海外留学','其他']},
    {key:'degree',label:'学历层次',input:'select',options:['','高中','大专','本科','硕士','MBA','博士']},
    {key:'major',label:'专业',input:'text',placeholder:'计算机科学与技术'},
    {key:'minor',label:'辅修专业',input:'text',placeholder:'数学'},
    {key:'college',label:'院系',input:'text',placeholder:'计算机学院'},
    {key:'lab',label:'实验室',input:'text',placeholder:'CAD&CG国家重点实验室'},
    {key:'researchDirection',label:'研究方向',input:'text',placeholder:'AIGC/多模态/推荐系统'},
    {key:'advisor',label:'导师',input:'text',placeholder:'王老师'},
    {key:'city',label:'所在城市',input:'text',placeholder:'北京'},
    {key:'startDate',label:'入学时间',input:'date'},
    {key:'endDate',label:'毕业时间',input:'date'},
    {key:'graduationStatus',label:'毕业状态',input:'select',options:['','已毕业','预计毕业','在读','肄业']},
    {key:'gpa',label:'GPA',input:'text',placeholder:'3.8/4.0'},
    {key:'ranking',label:'排名/荣誉',input:'text',placeholder:'前10%'},
    {key:'cet4',label:'英语四级',input:'text',placeholder:'580'},
    {key:'cet6',label:'英语六级',input:'text',placeholder:'530'},
    {key:'courses',label:'核心课程',input:'textarea',placeholder:'算法、操作系统、机器学习...'},
    {key:'description',label:'补充说明',input:'textarea',placeholder:'交换经历、荣誉、研究方向等'},
  ]},

  // 7. 实习经历
  {key:'internships',label:'实习经历',type:'list',slots:3,itemLabel:'实习',fields:[
    {key:'company',label:'公司',input:'text',placeholder:'字节跳动'},
    {key:'title',label:'职位',input:'text',placeholder:'后端开发实习生'},
    {key:'department',label:'部门',input:'text',placeholder:'推荐架构部'},
    {key:'city',label:'城市',input:'text',placeholder:'北京'},
    {key:'startDate',label:'开始时间',input:'date'},
    {key:'endDate',label:'结束时间',input:'date'},
    {key:'isCurrent',label:'是否仍在实习',input:'select',options:['','是','否']},
    {key:'description',label:'工作内容',input:'textarea',placeholder:'岗位职责、项目内容、负责模块'},
    {key:'achievements',label:'成果',input:'textarea',placeholder:'量化结果、业务影响、关键交付'},
    {key:'technologies',label:'使用技术',input:'textarea',placeholder:'Java、Go、Redis、Kafka'},
  ]},

  // 8. 工作经历
  {key:'workExperiences',label:'工作经历',type:'list',slots:3,itemLabel:'工作',fields:[
    {key:'company',label:'公司',input:'text',placeholder:'某科技公司'},
    {key:'title',label:'职位',input:'text',placeholder:'软件工程师'},
    {key:'department',label:'部门',input:'text',placeholder:'平台研发部'},
    {key:'industry',label:'行业',input:'text',placeholder:'AI/SaaS/电商'},
    {key:'city',label:'城市',input:'text',placeholder:'上海'},
    {key:'startDate',label:'开始时间',input:'date'},
    {key:'endDate',label:'结束时间',input:'date'},
    {key:'isCurrent',label:'是否为当前工作',input:'select',options:['','是','否']},
    {key:'teamSize',label:'团队规模',input:'text',placeholder:'8'},
    {key:'description',label:'工作职责',input:'textarea',placeholder:'主要负责的业务和职责范围'},
    {key:'achievements',label:'工作成绩',input:'textarea',placeholder:'量化结果、关键产出'},
    {key:'technologies',label:'使用技术',input:'textarea',placeholder:'TypeScript、React、PostgreSQL'},
  ]},

  // 9. 项目经历
  {key:'projects',label:'项目经历',type:'list',slots:4,itemLabel:'项目',fields:[
    {key:'name',label:'项目名称',input:'text',placeholder:'AI简历填表助手'},
    {key:'role',label:'项目角色',input:'text',placeholder:'负责人/核心开发'},
    {key:'organization',label:'所属组织',input:'text',placeholder:'个人项目/公司项目'},
    {key:'url',label:'项目链接',input:'url',placeholder:'https://...'},
    {key:'repoUrl',label:'代码仓库',input:'url',placeholder:'https://github.com/...'},
    {key:'startDate',label:'开始时间',input:'date'},
    {key:'endDate',label:'结束时间',input:'date'},
    {key:'description',label:'项目描述',input:'textarea',placeholder:'项目做什么，负责哪些部分'},
    {key:'highlights',label:'项目亮点',input:'textarea',placeholder:'效果、指标、架构亮点、难点突破'},
    {key:'technologies',label:'技术栈',input:'textarea',placeholder:'Chrome Extension、LLM、JavaScript'},
  ]},

  // 10. 校园经历
  {key:'campusExperiences',label:'校园经历',type:'list',slots:3,itemLabel:'校园',fields:[
    {key:'category',label:'经历类型',input:'select',options:['','学生组织','社团','志愿服务','科研','竞赛']},
    {key:'organization',label:'组织名称',input:'text',placeholder:'ACM协会'},
    {key:'role',label:'担任角色',input:'text',placeholder:'技术负责人'},
    {key:'startDate',label:'开始时间',input:'date'},
    {key:'endDate',label:'结束时间',input:'date'},
    {key:'description',label:'描述',input:'textarea',placeholder:'职责、活动内容'},
    {key:'achievements',label:'成果',input:'textarea',placeholder:'获奖、影响力、覆盖人数'},
  ]},

  // 11. 证书与认证
  {key:'certificates',label:'证书与认证',type:'list',slots:3,itemLabel:'证书',fields:[
    {key:'name',label:'证书名称',input:'text',placeholder:'AWS认证解决方案架构师'},
    {key:'issuer',label:'颁发机构',input:'text',placeholder:'亚马逊云科技'},
    {key:'issueDate',label:'发证日期',input:'date'},
    {key:'expiryDate',label:'到期日期',input:'date'},
    {key:'score',label:'成绩/等级',input:'text',placeholder:'选填'},
    {key:'credentialId',label:'证书编号',input:'text',placeholder:'ABC-123'},
  ]},

  // 12. 语言能力
  {key:'languages',label:'语言能力',type:'list',slots:3,itemLabel:'语言',fields:[
    {key:'name',label:'语言',input:'text',placeholder:'英语'},
    {key:'proficiency',label:'熟练程度',input:'select',options:['','母语','流利','工作熟练','中等','基础']},
    {key:'testScore',label:'语言成绩',input:'text',placeholder:'雅思7.5/托福105/CET-6 530'},
  ]},

  // 13. 补充信息
  {key:'additional',label:'补充信息',type:'group',fields:[
    {key:'awards',label:'奖项荣誉',input:'textarea',placeholder:'奖学金、竞赛获奖、优秀员工等'},
    {key:'publications',label:'论文发表',input:'textarea',placeholder:'论文标题、会议/期刊、年份'},
    {key:'patents',label:'专利',input:'textarea',placeholder:'专利名称、编号、状态'},
    {key:'competitions',label:'竞赛经历',input:'textarea',placeholder:'黑客松、ACM、Kaggle、数学建模等'},
    {key:'openSourceContributions',label:'开源贡献',input:'textarea',placeholder:'仓库、PR、维护经历'},
    {key:'volunteerExperience',label:'志愿者经历',input:'textarea',placeholder:'组织、职责、时长'},
    {key:'coverLetterHighlights',label:'求职信要点',input:'textarea',placeholder:'可复用的自我介绍、求职动机'},
    {key:'customNotes',label:'其他备注',input:'textarea',placeholder:'表单里经常会问到的其它信息'},
  ]},
];

// ===== 工具函数 =====
function buildEmptyObjectFromFields(fields){
  const out={};
  fields.forEach(f=>{out[f.key]='';});
  return out;
}

function getSectionDefinition(key){
  return SECTIONS.find(s=>s.key===key)||null;
}

function createEmptyListItem(sectionKey){
  const s=getSectionDefinition(sectionKey);
  if(!s||s.type!=='list')return{};
  return buildEmptyObjectFromFields(s.fields);
}

function createEmptyProfile(){
  const p={};
  SECTIONS.forEach(s=>{
    if(s.type==='group'){p[s.key]=buildEmptyObjectFromFields(s.fields);}
    else{p[s.key]=[];for(let i=0;i<(s.slots||1);i++){p[s.key].push(createEmptyListItem(s.key));}}
  });
  return p;
}

function getValueByPath(obj,path){
  return path.split('.').reduce((o,k)=>(o&&o[k]!==undefined)?o[k]:'',obj);
}

function matchSelectOption(options,value){
  if(!value||!options||!options.length)return'';
  const clean=s=>String(s||'').toLowerCase().replace(/\s+/g,'').replace(/['"`\'""]/g,'').replace(/[()（）[\]【】{}<>]/g,'').replace(/[.,，/\\\-_:：;+]/g,'');
  const v=clean(value);if(!v)return'';
  // 精确匹配
  const exact=options.find(o=>clean(o)===v);if(exact)return exact;
  // 别名展开匹配
  for(const group of SELECT_ALIASES){
    if(group.v.some(a=>clean(a)===v)){
      for(const alias of group.v){const m=options.find(o=>clean(o)===clean(alias));if(m)return m;}
    }
  }
  // 包含匹配
  const contain=options.find(o=>clean(o).includes(v)||v.includes(clean(o)));if(contain)return contain;
  // 模糊匹配（字符重叠率>=40%）
  let best='',bs=0;options.forEach(o=>{if(!o)return;const s=[...v].filter(c=>clean(o).includes(c)).length/v.length;if(s>bs&&s>=0.4){bs=s;best=o;}});
  return best;
}

window.ResumeSchema={
  SECTIONS,SELECT_ALIASES,
  createEmptyProfile,createEmptyListItem,getSectionDefinition,
  getValueByPath,matchSelectOption,
  version:3,
};
})();
